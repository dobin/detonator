import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

import requests

logger = logging.getLogger(__name__)


class MDEClient:
    def __init__(self, tenant_config: Dict[str, any]):
        self.tenant_id = tenant_config.get("tenant_id")
        if not self.tenant_id:
            raise ValueError("tenant_id missing in MDE configuration")

        self.authority = tenant_config.get("authority") or f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes = tenant_config.get("scopes") or ["https://graph.microsoft.com/.default"]
        if isinstance(self.scopes, str):
            self.scopes = [self.scopes]

        self.client_id = tenant_config.get("client_id")
        if not self.client_id:
            raise ValueError("client_id missing in MDE configuration")

        secret_env = tenant_config.get("client_secret_env")
        if not secret_env:
            raise ValueError("client_secret_env missing in MDE configuration")

        self.client_secret = os.getenv(secret_env)
        if not self.client_secret:
            raise ValueError(f"Environment variable {secret_env} is not set")

        self.base_url = tenant_config.get("base_url", "https://graph.microsoft.com")
        self._token_cache: Tuple[Optional[str], Optional[datetime]] = (None, None)

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

    def _run_hunting_query(self, query: str) -> Tuple[List[dict], Optional[str]]:
        payload = {"query": query}
        response = self._request("POST", "/beta/security/runHuntingQuery", json=payload)
        data = response.json()
        server_time = response.headers.get("Date")
        return data.get("results", []), server_time

    def fetch_alerts(
        self,
        device_id: Optional[str],
        hostname: Optional[str],
        start_time: datetime,
        end_time: datetime,
    ) -> Tuple[List[dict], Optional[str]]:
        if (not device_id and not hostname) or start_time >= end_time:
            return [], None

        start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        def _escape(value: str) -> str:
            return value.replace('"', '\\"')

        device_filters = []
        if device_id:
            device_filters.append(f'DeviceId == "{_escape(device_id)}"')
        if hostname:
            device_filters.append(f'DeviceName =~ "{_escape(hostname)}"')

        device_clause = " or ".join(device_filters)

        query = f"""
AlertEvidence
| where Timestamp between (datetime({start_iso}) .. datetime({end_iso}))
| where {device_clause}
| summarize arg_max(Timestamp, *) by AlertId
| project Timestamp, AlertId
| order by Timestamp desc
""".strip()

        return self._run_hunting_query(query)

    def fetch_alert_evidence(self, alert_ids: List[str], chunk_size: int = 20) -> List[dict]:
        deduped: List[dict] = []
        if not alert_ids:
            return deduped

        unique_ids = sorted({alert_id for alert_id in alert_ids if alert_id})
        if not unique_ids:
            return deduped

        def _escape(value: str) -> str:
            return value.replace('"', '\\"')

        seen: Set[Tuple] = set()
        for idx in range(0, len(unique_ids), chunk_size):
            chunk = unique_ids[idx : idx + chunk_size]
            alert_list = ", ".join(f'"{_escape(alert_id)}"' for alert_id in chunk)
            query = f"""
AlertEvidence
| where AlertId has_any ({alert_list})
| order by Timestamp desc
""".strip()
            results, _ = self._run_hunting_query(query)
            for row in results:
                key = (
                    row.get("AlertId"),
                    row.get("EvidenceId"),
                    row.get("EntityType"),
                    row.get("EvidenceRole"),
                    row.get("DeviceId"),
                    row.get("FileName"),
                    row.get("ProcessCommandLine"),
                    row.get("RemoteUrl") or row.get("RemoteIP"),
                    row.get("RegistryKey"),
                )
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(row)
        return deduped

    def resolve_alert(self, alert_id: str, comment: str):
        body = {
            "status": "resolved",
            "classification": "informationalExpectedActivity",
            "determination": "securityTesting",
            "comments": [comment],
            "customDetails": {},
        }
        self._request("PATCH", f"/v1.0/security/alerts/{alert_id}", json=body)

    def resolve_incident(self, incident_id: str, comment: str):
        body = {
            "status": "resolved",
            "classification": "truePositive",
            "determination": "securityTesting",
            "comments": [comment],
        }
        self._request("PATCH", f"/v1.0/security/incidents/{incident_id}", json=body)
