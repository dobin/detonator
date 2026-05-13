import logging
import json
from datetime import datetime
from typing import List
from sqlalchemy.orm import Session

from detonatorapi.database import Submission, SubmissionAlert
from detonatorapi.db_interface import db_submission_add_log
from detonatorapi.edr_cloud.crowdstrike_cloud_client import CrowdstrikeCloudClient
from .edr_cloud import EdrCloud


logger = logging.getLogger(__name__)


class CloudCrowdstrikePlugin(EdrCloud):

    def __init__(self):
        super().__init__()
        self.crowdstrikeClient: CrowdstrikeCloudClient | None = None

    @staticmethod
    def is_relevant(profile_data: dict) -> bool:
        edr_info = profile_data.get("edr_crowdstrike", None)
        return edr_info is not None

    def InitializeClient(self, profile_data: dict) -> bool:
        mydata = profile_data.get("edr_crowdstrike", {})
        required_keys = ("hostname",)
        for key in required_keys:
            if key not in mydata:
                raise RuntimeError(f"Profile data edr_crowdstrike missing key: {key}")

        self.crowdstrikeClient = CrowdstrikeCloudClient(
            client_id=mydata.get("client_id"),
            client_secret=mydata.get("client_secret"),
            base_url=mydata.get("base_url"),
        )
        return True

    def poll(self, db: Session, submission: Submission) -> bool:
        if not submission.profile:
            return False
        device_info = submission.profile.data.get("edr_crowdstrike", None)
        if not device_info:
            return False
        if not self.crowdstrikeClient:
            raise RuntimeError("CrowdStrike Client not initialized")
        device_hostname = device_info.get("hostname", None)

        # Determine polling window
        time_from = submission.created_at
        time_to = submission.completed_at or datetime.utcnow()

        try:
            poll_msg = (
                f"CROWDSTRIKE poll for submission {submission.id}: "
                f"from {time_from.isoformat()} to {time_to.isoformat()}"
            )
            logger.info(poll_msg)

            cs_alerts = self.crowdstrikeClient.fetch_alerts(
                device_hostname, time_from, time_to
            )
            alerts: List[SubmissionAlert] = self.convert_crowdstrike_alerts(cs_alerts)
            self.store_alerts(db, submission, alerts)
        except Exception as exc:
            db_submission_add_log(db, submission, f"CROWDSTRIKE poll: failed: {exc}")

        return True

    def convert_crowdstrike_alerts(self, cs_alerts: List[dict]) -> List[SubmissionAlert]:
        converted_alerts: List[SubmissionAlert] = []
        for alert in cs_alerts:
            detected_at = alert.get("created_timestamp")  # e.g. "2026-05-12T17:47:41.430791756Z"
            detected_dt = None
            if detected_at:
                try:
                    # Truncate fractional seconds to 6 digits (microseconds) for
                    # Python 3.10 compatibility — CrowdStrike sends 9-digit nanoseconds.
                    timestamp_str = detected_at.rstrip("Z")
                    if "." in timestamp_str:
                        base, frac = timestamp_str.split(".")
                        frac = frac[:6]  # keep only microseconds
                        timestamp_str = f"{base}.{frac}"
                    detected_dt = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    logger.warning(
                        "Invalid CrowdStrike alert created_timestamp format: %s", detected_at
                    )
                    detected_dt = datetime.utcnow()

            # Build category from MITRE tactic/technique (singular strings in Falcon alerts)
            tactic = alert.get("tactic", "")
            technique = alert.get("technique", "")
            category = ""
            if tactic or technique:
                parts = [p for p in [tactic, technique] if p]
                category = ", ".join(parts)

            # Detection source: prefer source_products, fall back to source_vendors
            source_products = alert.get("source_products", [])
            source_vendors = alert.get("source_vendors", [])
            if source_products:
                detection_source = ", ".join(source_products)
            elif source_vendors:
                detection_source = ", ".join(source_vendors)
            else:
                detection_source = "CrowdStrike Falcon"

            submissionAlert = SubmissionAlert(
                source="CrowdStrike Falcon Plugin",
                raw=json.dumps(alert),

                alert_id=alert.get("composite_id"),
                title=alert.get("name") or alert.get("description", "N/A"),
                severity=alert.get("severity_name", "N/A"),
                category=category,
                detection_source=detection_source,
                detected_at=detected_dt,
                additional_data={
                    "pattern_id": alert.get("pattern_id", "N/A"),
                    "technique_id": alert.get("technique_id", "N/A"),
                    "tactic_id": alert.get("tactic_id", "N/A"),
                    "cid": alert.get("cid", "N/A"),
                    "status": alert.get("status", "N/A"),
                    "user_name": alert.get("user_name", "N/A"),
                },
            )
            converted_alerts.append(submissionAlert)
        return converted_alerts

    def finish_monitoring(self, db: Session, submission: Submission) -> bool:
        return True
