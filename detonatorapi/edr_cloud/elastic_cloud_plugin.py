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

POLLING_TIME_MINUTES = 5  # post end monitoring duration
POLL_INTERVAL_SECONDS = 10  # polling interval


class CloudElasticPlugin(EdrCloud):

    def __init__(self):
        super().__init__()
        self.elasticClient: ElasticCloudClient | None = None
        self.thread: Optional[threading.Thread] = None


    @staticmethod
    def is_relevant(profile_data: dict) -> bool:
        edr_info = profile_data.get("edr_elastic", None)
        return edr_info is not None
    

    def start_monitoring_thread(self, submission_id: int):
        self.submission_id = submission_id
        self.thread = threading.Thread(
            target=self._monitor_loop,
            name=f"elastic-monitor-{submission_id}",
            daemon=True,
        )
        self.thread.start()
        logger.info("Alert monitoring thread started")


    def _monitor_loop(self):
        while True:
            db = None
            try:
                db = get_db_direct()
                submission = db.query(Submission).filter(Submission.id == self.submission_id).first()
                if not submission:
                    break

                # Create elastic client
                if self.elasticClient is None:
                    edr_info = submission.profile.data.get("edr_elastic", None)
                    if not edr_info:
                        raise RuntimeError(f"Profile {submission.profile.id} has no edr_elastic data")
                    required_keys = ("elastic_url", "elastic_apikey", "hostname")
                    for key in required_keys:
                        if key not in edr_info:
                            raise RuntimeError(f"Profile {submission.profile.id} edr_elastic missing key: {key}")
                    self.elasticClient = ElasticCloudClient(
                        base_url=edr_info.get("elastic_url"),
                        api_key=edr_info.get("elastic_apikey"),
                    )
                
                # check if we are done
                if submission.status in ("error", "finished"):
                    # check if we are > POLLING_TIME_MINUTES after completed_at
                    if submission.completed_at and \
                          submission.completed_at + timedelta(minutes=POLLING_TIME_MINUTES) < datetime.utcnow():
                        break

                # poll
                self._poll(db, submission)
                db.commit()

                # sleep a bit before next poll
                time.sleep(POLL_INTERVAL_SECONDS)
            except Exception as exc:
                logger.error(f"Alert monitor loop error: {exc}")
            finally:
                if db:
                    db.close()


    def _poll(self, db: Session, submission: Submission) -> bool:
        # Submission Info
        if not submission.profile:
            return False
        device_info = submission.profile.data.get("edr_elastic", None)
        if not device_info:
            return False
        if not self.elasticClient:
            return False
        
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
            alerts = self.convert_elastic_alerts(elastic_alerts)
            self._store_alerts(db, submission, alerts)
        except Exception as exc:
            db_submission_add_log(db, submission, f"ELASTIC poll: failed: {exc}")

        return True
    
    def convert_elastic_alerts(self, elastic_alerts: List[dict]) -> List[dict]:
        converted_alerts = []
        for alert in elastic_alerts:
            source = alert.get("_source", {})

            converted_alert = {
                "alert_id": alert.get("_id"),
                "title": source.get("kibana.alert.rule.name"),
                "severity": source.get("kibana.alert.severity"),
                "detection_source": source.get("message"),
                "detected_at": source.get("@timestamp"),
                "category": "",  # TBD
                "raw": json.dumps(alert),

                "additional_data": {
                    "rule_id": source.get("kibana.alert.rule.rule_id"),
                }
            }
            converted_alerts.append(converted_alert)
        return converted_alerts

    def _store_alerts(self, db: Session, submission: Submission, alerts: List[dict]) -> bool:
        existing_ids = {alert.alert_id for alert in submission.alerts}
        
        for alert in alerts:
            alert_id = alert["alert_id"]
            if alert_id in existing_ids:
                continue
            existing_ids.add(alert_id)

            detected_at = alert.get("detected_at")  # "2026-01-01T09:33:44.088Z"
            detected_dt = None
            if detected_at:
                try:
                    # Handle Elastic's ISO 8601 format: remove 'Z' and parse
                    timestamp_str = detected_at.rstrip('Z')
                    detected_dt = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    logger.warning(f"submission {submission.id}: Invalid alert detected_at format: {detected_at}")
                    # Use current time as fallback to avoid NULL constraint violation
                    detected_dt = datetime.utcnow()

            submission_alert = SubmissionAlert(
                submission_id=submission.id,
                source="Elastic Plugin",
                raw=alert.get("raw", ""),
                
                alert_id=alert_id,
                title=alert.get("title"),
                severity=alert.get("severity"),
                category=alert.get("category"),
                detection_source=alert.get("detection_source"),
                detected_at=detected_dt,
                additional_data=alert.get("additional_data", {}),
            )
            db.add(submission_alert)
            submission.alerts.append(submission_alert)
            logger.info(f"submission {submission.id}: New alert stored: {alert_id}")

        return True
