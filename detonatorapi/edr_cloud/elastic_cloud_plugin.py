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
from detonatorapi.edr_cloud.elastic_cloud_client import ElasticCloudClient
from .edr_cloud import EdrCloud


logger = logging.getLogger(__name__)


class CloudElasticPlugin(EdrCloud):

    def __init__(self):
        super().__init__()
        self.elasticClient: ElasticCloudClient | None = None


    @staticmethod
    def is_relevant(profile_data: dict) -> bool:
        edr_info = profile_data.get("edr_elastic", None)
        return edr_info is not None
    

    def InitializeClient(self, profile_data: dict) -> bool:
        required_keys = ("elastic_url", "elastic_apikey", "hostname")
        for key in required_keys:
            if key not in profile_data:
                raise RuntimeError(f"Profile data edr_elastic missing key: {key}")
        
        self.elasticClient = ElasticCloudClient(
            base_url=profile_data.get("elastic_url", ""),
            api_key=profile_data.get("elastic_apikey", ""),
        )
        return True
    

    def poll(self, db: Session, submission: Submission) -> bool:
        # Submission Info
        if not submission.profile:
            return False
        device_info = submission.profile.data.get("edr_elastic", None)
        if not device_info:
            return False
        if not self.elasticClient:
            raise RuntimeError("Elastic Client not initialized")
        device_hostname = device_info.get("hostname", None)
        # Determine polling window
        time_from = submission.created_at
        time_to = submission.completed_at or datetime.utcnow()
        
        try:
            poll_msg = f"ELASTIC poll for submission {submission.id}: from {time_from.isoformat()} to {time_to.isoformat()} "
            #db_submission_add_log(db, submission, poll_msg)
            logger.info(poll_msg)

            elastic_alerts = self.elasticClient.fetch_alerts(
                device_hostname, time_from, time_to
            )
            alerts: List[SubmissionAlert] = self.convert_elastic_alerts(elastic_alerts)
            self.store_alerts(db, submission, alerts)
        except Exception as exc:
            db_submission_add_log(db, submission, f"ELASTIC poll: failed: {exc}")

        return True
    
    
    def convert_elastic_alerts(self, elastic_alerts: List[dict]) -> List[SubmissionAlert]:
        converted_alerts: List[SubmissionAlert] = []
        for alert in elastic_alerts:
            source = alert.get("_source", {})

            detected_at = source.get("@timestamp") # "2026-01-01T09:33:44.088Z"
            detected_dt = None
            if detected_at:
                try:
                    # Handle Elastic's ISO 8601 format: remove 'Z' and parse
                    timestamp_str = detected_at.rstrip('Z')
                    detected_dt = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    logger.warning(f"Invalid alert detected_at format: {detected_at}")
                    # Use current time as fallback to avoid NULL constraint violation
                    detected_dt = datetime.utcnow()

            submissionAlert = SubmissionAlert(
                source="Elastic Plugin",
                raw=json.dumps(alert),
                
                alert_id=alert.get("_id"),
                title=source.get("kibana.alert.rule.name"),
                severity=source.get("kibana.alert.severity"),
                category="",  # TBD
                detection_source=source.get("message"),
                detected_at=detected_dt,
                additional_data={
                    "rule_id": source.get("kibana.alert.rule.rule_id"),
                }
            )
            converted_alerts.append(submissionAlert)
        return converted_alerts


    def finish_monitoring(self, db: Session, submission: Submission) -> bool:
        return True