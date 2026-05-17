import logging
import threading
import pprint
import time
from datetime import datetime, timedelta, timezone
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
        
        # Log
        poll_msg = f"MDE poll for submission {submission.id}: from {time_from.isoformat()} to {time_to.isoformat()} "
        db_submission_add_log(db, submission, poll_msg)
        logger.info(poll_msg)

        # Fetch alerts from MDE
        mde_alerts = self.mdeClient.fetch_alerts(
            device_id, device_hostname, time_from, time_to
        )
        alerts: List[SubmissionAlert] = self.convert_mde_alerts(mde_alerts)
        self.store_alerts(db, submission, alerts)

        return True


    def convert_mde_alerts(self, alerts: List[dict]) -> List[SubmissionAlert]:
        converted_alerts: List[SubmissionAlert] = []
        for alert in alerts:
            # We have: 
            #   createdDatetime
            #   lastUpdateDateTime
            #   firstActivityDateTime
            #   lastActivityDateTime
            detected_at = alert.get("firstActivityDateTime", None)

            # Category: prefer the list form, fall back to single string
            categories = alert.get("categories", [])
            if categories:
                category = ", ".join(categories) if isinstance(categories, list) else str(categories)
            else:
                category = alert.get("category", "")

            additional_data = {}  # Todo?

            submissionAlert = SubmissionAlert(
                source="MDE Cloud Plugin",
                raw=json.dumps(alert),
                
                alert_id=alert.get("id"),
                title=alert.get("title"),
                severity=alert.get("severity"),
                category=category,
                
                detection_source=alert.get("detectionSource"),
                detected_at=detected_at,
                additional_data=additional_data,
            )
            converted_alerts.append(submissionAlert)
        return converted_alerts


    def finish_monitoring(self, db: Session, submission: Submission) -> bool:
        if not submission.profile:
            return False
        if not self.mdeClient:
            raise RuntimeError("MDE Client not initialized")

        comment = f"Auto-Closed by Detonator (submission {submission.id})"
        incident_ids = set()
        for alert in submission.alerts:
            if not alert.auto_closed_at:
                self.mdeClient.resolve_alert(alert.alert_id, comment)
                db_submission_add_log(db, submission, f"Closed alert {alert.id} in MDE")

                # get incident ID from alert.raw (json of original alert)
                try:
                    alert_data = json.loads(alert.raw)
                    incident_ids.add(alert_data.get("incidentId"))
                except Exception as exc:
                    logger.error(f"Failed to parse alert raw data for alert {alert.id}: {exc}")
                    incident_id = None

        for incident_id in incident_ids:
            self.mdeClient.resolve_incident(incident_id, comment)
            db_submission_add_log(db, submission, f"Closed incident {incident_id} in MDE")
                    
        db.commit()
        return True
