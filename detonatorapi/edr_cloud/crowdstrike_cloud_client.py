import os
import logging
from datetime import datetime
from typing import List, Optional

from falconpy import Alerts

logger = logging.getLogger(__name__)


class CrowdstrikeCloudClient:
    """Client for querying CrowdStrike Falcon alerts via FalconPy."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url or os.getenv("FALCON_URL", "https://api.eu-1.crowdstrike.com")

        if not self.client_id:
            raise ValueError("Falcon client_id not configured")
        if not self.client_secret:
            raise ValueError("Falcon client_secret not configured")

        # FalconPy automatically handles token generation and refreshing
        self._alerts = Alerts(
            client_id=self.client_id,
            client_secret=self.client_secret,
            base_url=self.base_url,
        )

    def fetch_alerts(
        self,
        hostname: Optional[str],
        start_time: datetime,
        end_time: datetime,
    ) -> List[dict]:
        """
        Fetch CrowdStrike Falcon alerts for a given hostname within a time window.

        Uses FQL (Falcon Query Language) to filter by hostname and creation time,
        then retrieves full alert details for the matching IDs.
        """
        if not hostname:
            return []

        # Build FQL filter: hostname + time range
        start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        filter_parts = [
            f"hostname:'{hostname}'",
            f"created_timestamp:>'{start_iso}'",
            f"created_timestamp:<'{end_iso}'",
        ]
        fql_filter = "+".join(filter_parts)

        logger.info(
            "CrowdStrike query: hostname=%s, from=%s, to=%s",
            hostname, start_iso, end_iso,
        )

        # Step 1: Search for alert IDs matching the filter
        search_response = self._alerts.query_alerts_v1(
            limit=100,
            sort="created_timestamp.desc",
            filter=fql_filter,
        )

        if search_response["status_code"] != 200:
            errors = search_response.get("body", {}).get("errors", [])
            error_msg = errors[0].get("message", "Unknown error") if errors else "Unknown error"
            raise RuntimeError(
                f"CrowdStrike alert query failed: {search_response['status_code']} - {error_msg}"
            )

        alert_ids = search_response["body"].get("resources", [])
        if not alert_ids:
            logger.info("CrowdStrike: no alerts found for hostname=%s", hostname)
            return []

        logger.info("CrowdStrike: found %d alert IDs, fetching details...", len(alert_ids))

        # Step 2: Fetch full alert details for those IDs
        details_response = self._alerts.get_alerts_v1(ids=alert_ids)

        if details_response["status_code"] != 200:
            errors = details_response.get("body", {}).get("errors", [])
            error_msg = errors[0].get("message", "Unknown error") if errors else "Unknown error"
            raise RuntimeError(
                f"CrowdStrike alert details failed: {details_response['status_code']} - {error_msg}"
            )

        alerts = details_response["body"].get("resources", [])
        logger.info("CrowdStrike: retrieved %d full alert details", len(alerts))
        return alerts
