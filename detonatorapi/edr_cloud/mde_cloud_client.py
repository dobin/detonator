import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple
import requests
from dateutil.parser import isoparse

logger = logging.getLogger(__name__)


"""
Example Alert JSON from MDE Graph API:
  {
    "id": "dac6a87bc6-c97b-42a9-b9b2-f6322f6ae12a_1",
    "providerAlertId": "c6a87bc6-c97b-42a9-b9b2-f6322f6ae12a_1",
    "incidentId": "49",
    "status": "new",
    "severity": "low",
    "classification": null,
    "determination": null,
    "serviceSource": "microsoftDefenderForEndpoint",
    "detectionSource": "antivirus",
    "productName": "Microsoft Defender for Endpoint",
    "detectorId": "ea8363c3-f787-447a-a0a6-e9120fe24fbb",
    "tenantId": "8545957c-e5e0-4cb6-9015-889779522ac6",
    "title": "An active 'Ravartar' malware was detected",
    "description": "Malware and unwanted software are undesirable applications that perform annoying, disruptive, or harmful actions on affected machines. Some of these undesirable applications can replicate and spread from one machine to another. Others are able to receive commands from remote attackers and perform activities associated with cyber attacks.\n\nA malware is considered active if it is found running on the machine or it already has persistence mechanisms in place. Active malware detections are assigned higher severity ratings.\n\nBecause this malware was active, take precautionary measures and check for residual signs of infection.",
    "recommendedActions": "A. Validate the alert and scope the suspected breach.\n1. Find related machines, network addresses, and files in the incident graph.\n2. Check for other suspicious activities in the machine timeline.\n3. Locate unfamiliar processes in the process tree. Check files for prevalence, their locations, and digital signatures.\n4. Submit relevant files for deep analysis and review file behaviors. \n5. Identify unusual system activity with system owners. \n\nB. If you have validated the alert, contain and mitigate the breach.\n1. Record relevant artifacts, including those you need in mitigation rules.\n2. Stop suspicious processes. Block prevalent malware files across the network.\n3. Isolate affected machines.\n4. Identify potentially compromised accounts. If necessary, reset passwords and decommission accounts.\n5. Block relevant emails, websites, and IP addresses. Remove attack emails from mailboxes.\n6. Update antimalware signatures and run full scans. \n7. Deploy the latest security updates for Windows, web browsers, and other applications.\n\nC. Contact your incident response team, or contact Microsoft support for investigation and remediation services.",
    "category": "Malware",
    "categories": [
      "Malware"
    ],
    "assignedTo": null,
    "alertWebUrl": "https://security.microsoft.com/alerts/dac6a87bc6-c97b-42a9-b9b2-f6322f6ae12a_1?tid=8545957c-e5e0-4cb6-9015-889779522ac6",
    "incidentWebUrl": "https://security.microsoft.com/incident2/49/overview?tid=8545957c-e5e0-4cb6-9015-889779522ac6",
    "actorDisplayName": null,
    "threatDisplayName": "Trojan:Win32/Ravartar!rfn",
    "threatFamilyName": "Ravartar",
    "mitreTechniques": [],
    "createdDateTime": "2026-05-16T13:24:37.7133333Z",
    "lastUpdateDateTime": "2026-05-16T13:25:06.9933333Z",
    "resolvedDateTime": null,
    "firstActivityDateTime": "2026-05-16T13:13:44.5510402Z",
    "lastActivityDateTime": "2026-05-16T13:13:44.5510402Z",
    "systemTags": [],
    "alertPolicyId": null,
    "investigationState": "terminatedBySystem",
    "comments": [],
    "customDetails": {},
    "evidence": [
      {
        "@odata.type": "#microsoft.graph.security.deviceEvidence",
        "createdDateTime": "2026-05-16T13:24:37.7233333Z",
        "verdict": "suspicious",
        "remediationStatus": "active",
        "remediationStatusDetails": null,
        "roles": [],
        "detailedRoles": [
          "PrimaryDevice"
        ],
        "tags": [],
        "firstSeenDateTime": "2024-07-05T05:27:11.8686113Z",
        "mdeDeviceId": "26e94d7d31835ae93feefa077b51255ddc1ec98f",
        "azureAdDeviceId": null,
        "deviceDnsName": "desktop-8v3jhhq",
        "hostName": "desktop-8v3jhhq",
        "ntDomain": null,
        "dnsDomain": null,
        "osPlatform": "Windows11",
        "osBuild": 22631,
        "version": "23H2",
        "healthStatus": "active",
        "riskScore": "high",
        "rbacGroupId": 230559,
        "rbacGroupName": "devgrp1",
        "onboardingStatus": "onboarded",
        "defenderAvStatus": "notSupported",
        "lastIpAddress": "10.10.20.100",
        "lastExternalIpAddress": "91.98.182.117",
        "ipInterfaces": [],
        "vmMetadata": null,
        "loggedOnUsers": [
          {
            "accountName": "rededr",
            "domainName": "DESKTOP-8V3JHHQ"
          }
        ],
        "resourceAccessEvents": []
      },
      {
        "@odata.type": "#microsoft.graph.security.fileEvidence",
        "createdDateTime": "2026-05-16T13:24:37.7233333Z",
        "verdict": "malicious",
        "remediationStatus": "active",
        "remediationStatusDetails": null,
        "roles": [],
        "detailedRoles": [],
        "tags": [],
        "detectionStatus": "detected",
        "mdeDeviceId": "26e94d7d31835ae93feefa077b51255ddc1ec98f",
        "fileDetails": {
          "sha1": "8816aae8e4283c6ced7556ec4e61b6ba2f4101df",
          "sha256": "64b6ae38b46a94e24b2009bd6c817dc75160a9dcf6539cea68b37db0effcfcf2",
          "md5": "600ba308684fb5c33f154f8746734778",
          "sha256Ac": null,
          "fileName": "CFW9_stage-15-c2-agent.exe",
          "filePath": "C:\\Users\\Public\\Downloads",
          "fileSize": 670176,
          "filePublisher": null,
          "signer": null,
          "issuer": null
        }
      }
    ],
    "additionalData": {}
  }
"""


"""
Example Incident JSON from MDE Graph API:
  {
    "id": "46",
    "tenantId": "8545957c-e5e0-4cb6-9015-889779522ac6",
    "status": "resolved",
    "incidentWebUrl": "https://security.microsoft.com/incident2/46/overview?tid=8545957c-e5e0-4cb6-9015-889779522ac6",
    "redirectIncidentId": null,
    "displayName": "Multiple threat families detected on one endpoint",
    "createdDateTime": "2026-04-25T08:29:00.8366667Z",
    "lastUpdateDateTime": "2026-05-17T13:59:10.4733333Z",
    "assignedTo": "DobinRutishauser@rutdeval.onmicrosoft.com",
    "classification": "informationalExpectedActivity",
    "determination": "securityTesting",
    "severity": "high",
    "customTags": [],
    "systemTags": [],
    "description": null,
    "lastModifiedBy": "User-DobinRutishauser@rutdeval.onmicrosoft.com",
    "resolvingComment": null,
    "summary": null,
    "priorityScore": 96,
    "comments": []
  }
"""


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
        if not hostname or hostname == "":
            raise ValueError("Hostname is required to fetch MDE alerts")

        # Ensure start_time and end_time are timezone-aware (assume UTC if naive)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        # All new Alerts
        # We need to filter them later based on hostname and firstActivityDateTime
        filter_clauses = [
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
        filtered_alerts = []
        hostname_lower = hostname.lower()
        for alert in all_alerts:
            if self._alert_matches_hostname(alert, hostname_lower):
                filtered_alerts.append(alert)
        all_alerts = filtered_alerts

        # Client-side filtering by firstActivityDateTime since Graph API
        # alerts_v2 doesn't support OData filters on this field (awesome)
        filtered_alerts = []
        for alert in all_alerts:
            first_activity = alert.get("firstActivityDateTime")
            if first_activity:
                try:
                    # Parse the ISO 8601 datetime (dateutil handles any precision)
                    activity_dt = isoparse(first_activity)
                    if start_time <= activity_dt <= end_time:
                    #    logger.info(f"Including alert ID {alert.get('id')} with firstActivityDateTime {first_activity}")
                        filtered_alerts.append(alert)
                    #else:
                    #    logger.info(f"Excluding alert ID {alert.get('id')} with firstActivityDateTime {first_activity} outside of range")
                except (ValueError, TypeError) as e:
                    # If we can't parse the date, include the alert anyway
                    logger.warning(f"Could not parse firstActivityDateTime '{first_activity}' for alert ID {alert.get('id')}: {type(e).__name__}: {e}")

        return filtered_alerts
    

    # Not really used by Detonator - can be used manually on cmdline
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
            ts = alert.get("firstActivityDateTime", "?")
            title = alert.get("title", "?")
            severity = alert.get("severity", "?")
            status = alert.get("status", "?")
            print(f"  {i:3d}. [{severity}] {title}")
            print(f"       ID: {alert_id}  |  Status: {status}  |  FirstTime: {ts}")
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

