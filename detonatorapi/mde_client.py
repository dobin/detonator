import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class MDEClient:
    def __init__(self, tenant_config: Dict[str, any]):
        self.tenant_id = tenant_config.get("tenant_id")
        if not self.tenant_id:
            raise ValueError("tenant_id missing in MDE configuration")

        self.authority = tenant_config.get("authority") or f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes = tenant_config.get("scopes") or ["https://api.security.microsoft.com/.default"]
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

        self.base_url = tenant_config.get("base_url", "https://api.security.microsoft.com")
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

    def fetch_alerts(self, device_id: Optional[str], hostname: Optional[str], since: Optional[datetime]) -> List[dict]:
        filters = []
        if device_id:
            filters.append(f"deviceId eq '{device_id}'")
        elif hostname:
            filters.append(f"deviceName eq '{hostname}'")
        if since:
            filters.append(f"lastUpdateTime ge {since.strftime('%Y-%m-%dT%H:%M:%SZ')}")

        params = {}
        if filters:
            params["$filter"] = " and ".join(filters)
        params["$top"] = "200"

        alerts: List[dict] = []
        path = "/api/alerts"
        while True:
            response = self._request("GET", path, params=params)
            payload = response.json()
            alerts.extend(payload.get("value", []))
            next_link = payload.get("@odata.nextLink")
            if not next_link:
                break
            # nextLink already absolute
            path = next_link.replace(self.base_url.rstrip('/'), '')
            params = {}

        return alerts

    def resolve_alert(self, alert_id: str, comment: str):
        body = {
            "status": "Resolved",
            "classification": "TruePositive",
            "determination": "SecurityTesting",
            "comments": [comment],
        }
        self._request("PATCH", f"/api/alerts/{alert_id}", json=body)

    def resolve_incident(self, incident_id: str, comment: str):
        body = {
            "status": "Resolved",
            "classification": "TruePositive",
            "determination": "SecurityTesting",
            "comments": [comment],
        }
        self._request("PATCH", f"/api/incidents/{incident_id}", json=body)
