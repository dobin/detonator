import logging
import threading
import pprint
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from sqlalchemy.orm import Session, joinedload
import json

from detonatorapi.database import get_db_direct, Submission, SubmissionAlert, Profile
from detonatorapi.db_interface import db_submission_add_log, db_submission_change_status_quick
from detonatorapi.edr_cloud.mde_cloud_client import MdeCloudClient
from .edr_cloud import EdrCloud


logger = logging.getLogger(__name__)

POLLING_TIME_MINUTES = 5  # post end monitoring duration
POLL_INTERVAL_SECONDS = 30  # polling interval


class CloudMdePlugin(EdrCloud):

    def __init__(self):
        super().__init__()
        self.mdeClient: MdeCloudClient | None = None


    @staticmethod
    def is_relevant(profile_data: dict) -> bool:
        edr_info = profile_data.get("edr_mde", None)
        return edr_info is not None


    def InitializeClient(self, profile_data) -> bool:
        mydata = profile_data.get("edr_mde", {})

        required_keys = ("tenant_id", "client_id")
        for key in required_keys:
            if key not in mydata:
                raise RuntimeError(f"Profile data edr_mde missing key: {key}")
            
        self.mdeClient = MdeCloudClient(
            tenant_id=mydata.get("tenant_id", ""),
            client_id=mydata.get("client_id", ""),
        )
        return True


    def poll(self, db: Session, submission: Submission) -> bool:
        # Submission Info
        if not submission.profile:
            return False
        device_info = submission.profile.data.get("edr_mde", None)
        if not device_info:
            return False
        device_id = device_info.get("device_id", None)
        device_hostname = device_info.get("hostname", None)

        if not self.mdeClient:
            raise RuntimeError("MDE Client not initialized")

        # Determine polling window
        time_from = submission.created_at
        time_to = submission.completed_at or datetime.utcnow()
        
        try:
            poll_msg = f"MDE poll for submission {submission.id}: from {time_from.isoformat()} to {time_to.isoformat()} "
            #db_submission_add_log(db, submission, poll_msg)
            logger.info(poll_msg)

            mde_alerts = self.mdeClient.fetch_alerts(
                device_id, device_hostname, time_from, time_to
            )
            alerts: List[SubmissionAlert] = self.convert_mde_alerts(mde_alerts)
            self.store_alerts(db, submission, alerts)
        except Exception as exc:
            db_submission_add_log(db, submission, f"MDE poll: failed: {exc}")

        return True


    def convert_mde_alerts(self, alerts: List[dict]) -> List[SubmissionAlert]:
        converted_alerts: List[SubmissionAlert] = []
        for alert in alerts:
            alert_id = alert.get("AlertId", None)
            detected_at = alert.get("Timestamp")

            detected_dt = None
            if detected_at:
                try:
                    # Handle Microsoft's ISO 8601 format with up to 7 decimal places
                    # Remove 'Z' and parse, then truncate microseconds if needed
                    timestamp_str = detected_at.rstrip('Z')
                    detected_dt = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    # Fallback: try with explicit format parsing
                    try:
                        # Try parsing with strptime, handling variable fractional seconds
                        detected_dt = datetime.strptime(detected_at[:26] + 'Z', "%Y-%m-%dT%H:%M:%S.%fZ")
                    except ValueError:
                        logger.warning(f"Invalid alert detected_at format: {detected_at}")
                        # Use current time as fallback to avoid NULL constraint violation
                        detected_dt = datetime.utcnow()
            else:
                # If no timestamp provided, use current time
                detected_dt = datetime.utcnow()
                logger.warning(f"No timestamp in alert, using current time")

            submissionAlert = SubmissionAlert(
                source="MDE Cloud Plugin",
                raw=json.dumps(alert),
                
                alert_id=alert_id,
                title=alert.get("Title"),
                severity=alert.get("Severity"),
                category=",".join(alert.get("Categories", [])),  # it seems to be a list, even with one entry
                
                detection_source=alert.get("DetectionSource"),
                detected_at=detected_dt,
                additional_data={},
            )
            converted_alerts.append(submissionAlert)
        return converted_alerts


    def finish_monitoring(self, db: Session, submission: Submission) -> bool:
        # Submission Info
        if not submission.profile:
            return False
    
        logger.info("submission %s: Finalizing MDE alert monitoring", submission.id)

        try:
            self._auto_close(db, submission)
        except Exception as exc:
            logger.error(f"Failed to auto close alerts for submission {submission.id}: {exc}")
            db_submission_add_log(db, submission, f"MDE auto-close failed: {exc}")

        return True
    

    def _auto_close(self, db: Session, submission: Submission):
        comment = f"Auto-Closed by Detonator (submission {submission.id})"
        
        #closed_incidents = set()
        #for alert in submission.alerts:
        #    if not alert.auto_closed_at:
        #        try:
        #            self.mdeClient.resolve_alert(alert.alert_id, comment)
        #            alert.status = "Resolved"
        #            alert.auto_closed_at = datetime.utcnow()
        #            alert.comment = comment
        #        except Exception as exc:
        #            logger.error(f"Failed to resolve alert {alert.alert_id}: {exc}")
        #    incident_id = alert.incident_id
        #    if incident_id and incident_id not in closed_incidents:
        #        try:
        #            self.mdeClient.resolve_incident(incident_id, comment)
        #            closed_incidents.add(incident_id)
        #        except Exception as exc:
        #            logger.error(f"Failed to resolve incident {incident_id}: {exc}")
        #db_submission_add_log(db, submission, "Detection window completed. Alerts auto-closed.")
