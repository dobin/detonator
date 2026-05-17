import os
import logging
from datetime import datetime, timedelta, timezone
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
        """
        Fetches MDE alerts for a specific host using Graph API alerts_v2 endpoint.
        """
        if not device_id and not hostname:
            logger.warning("Neither device_id nor hostname provided. Returning empty list.")
            return []

        # Graph API expects standard ISO 8601 strings (e.g., '2026-05-17T15:00:00Z')
        start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Build OData filter with time and hostname
        filter_clauses = [
            f"createdDateTime ge {start_iso}",
            f"createdDateTime le {end_iso}",
            f"status eq 'new'",
        ]
        odata_filter = " and ".join(filter_clauses)
        
        # Base URL for modern security alerts v2
        url = "https://graph.microsoft.com/v1.0/security/alerts_v2"
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }
        params = {
            "$filter": odata_filter,
            "$top": 50,  # Page size (max 150)
        }

        all_alerts = []

        # Handle pagination smoothly via @odata.nextLink
        while url:
            response = requests.get(url, headers=headers, params=params if url.endswith("alerts_v2") else None)
            if response.status_code >= 400:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("error", {}).get("message", error_detail)
                except:
                    pass
                raise RuntimeError(f"MDE API request failed: {response.status_code} - {error_detail}")
            
            data = response.json()
            all_alerts.extend(data.get("value", []))
            
            # If there are more alerts, Graph API returns a pagination URL
            url = data.get("@odata.nextLink")

        # Client-side filtering by hostname since Graph API doesn't support
        # filtering on nested evidence properties (awesome)
        if hostname:
            filtered_alerts = []
            hostname_lower = hostname.lower()
            for alert in all_alerts:
                if self._alert_matches_hostname(alert, hostname_lower):
                    filtered_alerts.append(alert)
            return filtered_alerts

        return all_alerts
    

    def fetch_incidents(
        self,
        device_id: Optional[str],
        hostname: Optional[str],
        start_time: datetime,
        end_time: datetime,
    ) -> List[dict]:
        """Fetch incidents via Graph API with OData filters."""
        if not device_id and not hostname:
            return []

        start_iso = self._fmt_datetime(start_time)
        end_iso = self._fmt_datetime(end_time)

        filters = []
        filters.append(f"createdDateTime ge {start_iso}")
        filters.append(f"createdDateTime le {end_iso}")
        filters.append(f"status eq 'active'")
        filter_clause = " and ".join(filters)

        params = {
            "$filter": filter_clause,
            "$top": 50,
            "$orderby": "createdDateTime desc",
        }

        response = self._request(
            "GET",
            "/v1.0/security/incidents",
            params=params,
        )
        data = response.json()
        incidents = data.get("value", [])

        return incidents


    @staticmethod
    def _alert_matches_hostname(alert: dict, hostname_lower: str) -> bool:
        """Check if an alert's evidence contains the given hostname."""
        evidence_list = alert.get("evidence", [])
        if not evidence_list:
            return False
        
        for evidence in evidence_list:
            # Check if this is device evidence
            odata_type = evidence.get("@odata.type", "")
            if "deviceEvidence" not in odata_type:
                continue
            
            # Check hostname match
            host_name = evidence.get("hostName", "")
            if host_name and host_name.lower() == hostname_lower:
                return True
            
            # Also check deviceDnsName as fallback
            device_dns_name = evidence.get("deviceDnsName", "")
            if device_dns_name and device_dns_name.lower() == hostname_lower:
                return True
        
        return False
    

    def resolve_alert(self, alert_id: str, comment: str):
        body = {
            "status": "resolved",
            "classification": "informationalExpectedActivity",
            "determination": "securityTesting",
            "comment": comment,
        }
        self._request("PATCH", f"/v1.0/security/alerts_v2/{alert_id}", json=body)


    def resolve_incident(self, incident_id: str, comment: str):
        body = {
            "status": "resolved",
            "classification": "informationalExpectedActivity",
            "determination": "securityTesting",
            "resolvingComment": comment,
        }
        self._request("PATCH", f"/v1.0/security/incidents/{incident_id}", json=body)


    def _get_access_token(self) -> str:
        token, expires_at = self._token_cache
        if token and expires_at and datetime.now(timezone.utc) < expires_at:
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
        self._token_cache = (token, datetime.now(timezone.utc) + timedelta(seconds=expires_in - 30))
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


# ---------------------------------------------------------------------------
# Standalone CLI for testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import json as _json
    import sys as _sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="List MDE alerts and incidents for a hostname.",
    )
    parser.add_argument(
        "hostname",
        help="Hostname to query alerts/incidents for.",
    )
    parser.add_argument(
        "--tenant-id",
        required=True,
        help="Azure tenant ID.",
    )
    parser.add_argument(
        "--client-id",
        required=True,
        help="Azure app registration client ID.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days back to search (default: 7).",
    )
    parser.add_argument(
        "--device-id",
        default=None,
        help="Optional device ID for alert queries.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output raw JSON instead of summary.",
    )
    parser.add_argument(
        "--resolve-alert",
        metavar="ALERT_ID",
        help="Resolve an alert by its ID.",
    )
    parser.add_argument(
        "--resolve-incident",
        metavar="INCIDENT_ID",
        help="Resolve an incident by its ID.",
    )
    parser.add_argument(
        "--comment",
        default="Security testing - resolved via CLI",
        help="Comment for alert/incident resolution (default: 'Security testing - resolved via CLI').",
    )

    args = parser.parse_args()

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=args.days)

    client = MdeCloudClient(
        tenant_id=args.tenant_id,
        client_id=args.client_id,
    )

    # --- Resolve Alert (if requested) ---
    if args.resolve_alert:
        print("\n" + "=" * 80)
        print(f"  Resolving Alert ID: {args.resolve_alert}")
        print("=" * 80)
        try:
            client.resolve_alert(args.resolve_alert, args.comment)
            print(f"✓ Successfully resolved alert {args.resolve_alert}")
            print(f"  Comment: {args.comment}")
        except Exception as exc:
            print(f"ERROR resolving alert: {exc}")
            _sys.exit(1)
        _sys.exit(0)

    # --- Resolve Incident (if requested) ---
    if args.resolve_incident:
        print("\n" + "=" * 80)
        print(f"  Resolving Incident ID: {args.resolve_incident}")
        print("=" * 80)
        try:
            client.resolve_incident(args.resolve_incident, args.comment)
            print(f"✓ Successfully resolved incident {args.resolve_incident}")
            print(f"  Comment: {args.comment}")
        except Exception as exc:
            print(f"ERROR resolving incident: {exc}")
            _sys.exit(1)
        _sys.exit(0)

    # --- Alerts ---
    print("\n" + "=" * 80)
    print(f"  MDE Alerts for hostname={args.hostname}  (last {args.days} days)")
    print("=" * 80)

    try:
        alerts = client.fetch_alerts(
            device_id=args.device_id,
            hostname=args.hostname,
            start_time=start_time,
            end_time=end_time,
        )
    except Exception as exc:
        print(f"ERROR fetching alerts: {exc}")
        _sys.exit(1)

    if args.json_output:
        print(_json.dumps(alerts, indent=2, default=str))
    else:
        print(f"Found {len(alerts)} alert(s):\n")
        for i, alert in enumerate(alerts, 1):
            alert_id = alert.get("id", "?")
            ts = alert.get("lastActivityDateTime", "?")
            title = alert.get("title", "?")
            severity = alert.get("severity", "?")
            status = alert.get("status", "?")
            print(f"  {i:3d}. [{severity}] {title}")
            print(f"       ID: {alert_id}  |  Status: {status}  |  Time: {ts}")
            print(f"       Incident ID: {alert.get('incidentId', '?')}")
            print()

    # --- Incidents ---
    print("\n" + "=" * 80)
    print(f"  MDE Incidents for hostname={args.hostname}  (last {args.days} days)")
    print("=" * 80)

    try:
        incidents = client.fetch_incidents(
            device_id=args.device_id,
            hostname=args.hostname,
            start_time=start_time,
            end_time=end_time,
        )
    except Exception as exc:
        print(f"ERROR fetching incidents: {exc}")
        _sys.exit(1)

    if args.json_output:
        print(_json.dumps(incidents, indent=2, default=str))
    else:
        print(f"Found {len(incidents)} incident(s):\n")
        for i, inc in enumerate(incidents, 1):
            inc_id = inc.get("id", "?")
            display = inc.get("displayName", "?")
            severity = inc.get("severity", "?")
            status = inc.get("status", "?")
            created = inc.get("createdDateTime", "?")
            print(f"  {i:3d}. [{severity}] {display}")
            print(f"       ID: {inc_id}  |  Status: {status}  |  Created: {created}")
            print()

    print("Done.")

