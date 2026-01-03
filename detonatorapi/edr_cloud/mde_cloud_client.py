import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
import requests

logger = logging.getLogger(__name__)


class MdeCloudClient:

    def __init__(self, tenant_id: str, client_id: str):
        self.tenant_id = tenant_id
        if not self.tenant_id:
            raise ValueError("tenant_id missing in MDE configuration")

        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes = ["https://graph.microsoft.com/.default"]
        if isinstance(self.scopes, str):
            self.scopes = [self.scopes]

        self.client_id = client_id
        if not self.client_id:
            raise ValueError("client_id missing in MDE configuration")

        self.client_secret = os.getenv("MDE_AZURE_CLIENT_SECRET")
        if not self.client_secret:
            raise ValueError(f"Environment variable MDE_AZURE_CLIENT_SECRET is not set")

        self.base_url = "https://graph.microsoft.com"
        self._token_cache: Tuple[Optional[str], Optional[datetime]] = (None, None)


    def fetch_alerts(
        self,
        device_id: Optional[str],
        hostname: Optional[str],
        start_time: datetime,
        end_time: datetime,
    ) -> List[dict]:
        if not device_id and not hostname:
            return []

        start_iso = self._fmt_datetime(start_time)
        end_iso = self._fmt_datetime(end_time)

        def _escape(value: str) -> str:
            return value.replace('"', '\\"')

        device_filters = []
        if device_id:
            device_filters.append(f'DeviceId == "{_escape(device_id)}"')
        if hostname:
            device_filters.append(f'DeviceName =~ "{_escape(hostname)}"')
        device_clause = " or ".join(device_filters)

        # Fetch all alerts and their evidence
        query = self._build_alert_evidence_query(
            filters=[
                f"| where Timestamp >= datetime({start_iso}) and Timestamp <= datetime({end_iso})",
                f"| where {device_clause}",
            ],
            pipeline=[
                "| order by Timestamp desc",
            ],
        )
        results = self._run_hunting_query(query)
        return results
    

    def _run_hunting_query(self, query: str) -> List[dict]:
        payload = {"query": query}
        response = self._request("POST", "/beta/security/runHuntingQuery", json=payload)
        data = response.json()
        return data.get("results", [])
    

    def resolve_alert(self, alert_id: str, comment: str):
        body = {
            "status": "resolved",
            "classification": "informationalExpectedActivity",
            "determination": "securityTesting",
            "customDetails": {comment},
        }
        self._request("PATCH", f"/v1.0/security/alerts_v2/{alert_id}", json=body)


    def resolve_incident(self, incident_id: str, comment: str):
        body = {
            "status": "resolved",
            "classification": "truePositive",
            "determination": "securityTesting",
            "resolvingComment": comment,
        }
        self._request("PATCH", f"/v1.0/security/incidents/{incident_id}", json=body)


    def _get_access_token(self) -> str:
        token, expires_at = self._token_cache
        if token and expires_at and datetime.utcnow() < expires_at:
            return token

        token_url = f"{self.authority.rstrip('/')}/oauth2/v2.0/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": " ".join(self.scopes),
            "grant_type": "client_credentials",
        }
        response = requests.post(token_url, data=data, timeout=10)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to obtain MDE token: {response.status_code} {response.text}")
        payload = response.json()
        token = payload.get("access_token")
        expires_in = payload.get("expires_in", 3599)
        self._token_cache = (token, datetime.utcnow() + timedelta(seconds=expires_in - 30))
        return token


    def _request(self, method: str, path: str, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._get_access_token()}"
        headers["Content-Type"] = "application/json"
        url = f"{self.base_url.rstrip('/')}{path}"
        response = requests.request(method, url, headers=headers, timeout=15, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f"MDE API {method} {url} failed: {response.status_code} {response.text}")
        return response



    def _build_alert_evidence_query(self, filters: List[str], pipeline: List[str]) -> str:
        lines = ["AlertEvidence"]
        lines.extend(filters)
        lines.extend(pipeline)
        return "\n".join(lines).strip()
    

    @staticmethod
    def _fmt_datetime(value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")

