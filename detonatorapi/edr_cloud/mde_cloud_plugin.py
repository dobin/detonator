import logging
import threading
import pprint
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from sqlalchemy.orm import Session, joinedload

from detonatorapi.database import get_db_direct, Submission, SubmissionAlert, Profile
from detonatorapi.db_interface import db_submission_add_log, db_submission_change_status_quick
from detonatorapi.edr_cloud.mde_cloud_client import MdeCloudClient
from .edr_cloud import EdrCloud


logger = logging.getLogger(__name__)

POLLING_TIME_MINUTES = 2  # post end monitoring duration
POLL_INTERVAL_SECONDS = 30  # polling interval


class CloudMdePlugin(EdrCloud):

    def __init__(self):
        super().__init__()
        self.thread: Optional[threading.Thread] = None
        self.client_cache: Dict[str, MdeCloudClient] = {}


    @staticmethod
    def is_relevant(profile_data: dict) -> bool:
        edr_info = profile_data.get("edr_mde", None)

        # TODO: Add more checks?

        return edr_info is not None


    def start_monitoring_thread(self, submission_id: int):
        self.submission_id = submission_id
        self.thread = threading.Thread(
            target=self._monitor_loop,
            name=f"mde-monitor-{submission_id}",
            daemon=True,
        )
        self.thread.start()
        logger.info("Alert monitoring thread started")


    def _monitor_loop(self):
        #start_time = datetime.utcnow()
        #while start_time + timedelta(minutes=POLLING_TIME_MINUTES) > datetime.utcnow():
        while True:
            db = None
            try:
                db = get_db_direct()
                submission = db.query(Submission).filter(Submission.id == self.submission_id).first()
                if not submission:
                    break
                
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

        # We finished. Close alerts
        db = get_db_direct()
        try:
            submission = db.query(Submission).filter(Submission.id == self.submission_id).first()
            if submission:
                self._finish_monitoring(db, submission)
            db.commit()
        finally:
            db.close()


    def _finish_monitoring(self, db: Session, submission: Submission) -> bool:
        # Submission Info
        if not submission.profile:
            return False
        
        # Cloud Client
        client = self._get_mdeclient(submission.profile)
        if not client:
            return False
        
        logger.info("submission %s: Finalizing MDE alert monitoring", submission.id)

        try:
            self._auto_close(db, submission, client)
        except Exception as exc:
            logger.error(f"Failed to auto close alerts for submission {submission.id}: {exc}")
            db_submission_add_log(db, submission, f"MDE auto-close failed: {exc}")

        return True


    def _poll(self, db: Session, submission: Submission) -> bool:
        # Submission Info
        if not submission.profile:
            return False
        device_info = submission.profile.data.get("edr_mde", None)
        if not device_info:
            return False
        device_id = device_info.get("device_id", None)
        device_hostname = device_info.get("hostname", None)
        
        # Cloud Client
        client = self._get_mdeclient(submission.profile)
        if not client:
            return False

        # Determine polling window
        time_from = submission.created_at
        time_to = submission.completed_at or datetime.utcnow()
        
        try:
            poll_msg = f"MDE poll for submission {submission.id}: from {time_from.isoformat()} to {time_to.isoformat()} "
            #db_submission_add_log(db, submission, poll_msg)
            logger.info(poll_msg)

            alerts = client.fetch_alerts(
                device_id, device_hostname, time_from, time_to
            )
            #pprint.pprint(alerts)
            self._store_alerts(db, submission, alerts)
        except Exception as exc:
            db_submission_add_log(db, submission, f"MDE poll: failed: {exc}")

        return True


    def _store_alerts(self, db: Session, submission: Submission, alerts: List[dict]):
        """Store alerts with their evidence already included."""
        existing_ids = {alert.alert_id for alert in submission.alerts}
        
        for alert in alerts:
            alert_id = alert.get("AlertId", None)
            if not alert_id:
                continue
            if alert_id in existing_ids:
                continue
            existing_ids.add(alert_id)

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
                        logger.warning(f"submission {submission.id}: Invalid alert detected_at format: {detected_at}")
                        # Use current time as fallback to avoid NULL constraint violation
                        detected_dt = datetime.utcnow()
            else:
                # If no timestamp provided, use current time
                detected_dt = datetime.utcnow()
                logger.warning(f"submission {submission.id}: No timestamp in alert, using current time")

            submission_alert = SubmissionAlert(
                submission_id=submission.id,
                source="MDE Cloud Plugin",
                raw="",
                
                alert_id=alert_id,
                title=alert.get("Title"),
                severity=alert.get("Severity"),
                category=",".join(alert.get("Categories", [])),  # it seems to be a list, even with one entry
                
                detection_source=alert.get("DetectionSource"),
                detected_at=detected_dt,
                additional_data={},
            )
            db.add(submission_alert)
            submission.alerts.append(submission_alert)
            logger.info(f"submission {submission.id}: New alert stored: {alert_id}")
    

    def _auto_close(self, db: Session, submission: Submission, client: MdeCloudClient):
        comment = f"Auto-Closed by Detonator (submission {submission.id})"
        
        #closed_incidents = set()
        #for alert in submission.alerts:
        #    if not alert.auto_closed_at:
        #        try:
        #            client.resolve_alert(alert.alert_id, comment)
        #            alert.status = "Resolved"
        #            alert.auto_closed_at = datetime.utcnow()
        #            alert.comment = comment
        #        except Exception as exc:
        #            logger.error(f"Failed to resolve alert {alert.alert_id}: {exc}")
        #    incident_id = alert.incident_id
        #    if incident_id and incident_id not in closed_incidents:
        #        try:
        #            client.resolve_incident(incident_id, comment)
        #            closed_incidents.add(incident_id)
        #        except Exception as exc:
        #            logger.error(f"Failed to resolve incident {incident_id}: {exc}")
        #db_submission_add_log(db, submission, "Detection window completed. Alerts auto-closed.")


    def _get_mdeclient(self, profile: Profile) -> Optional[MdeCloudClient]:
        cfg = profile.data.get("edr_mde") or {}
        if not cfg:
            return None
        cache_key = f"{profile.id}:{cfg.get('client_id')}"
        client = self.client_cache.get(cache_key)
        if client:
            return client
        try:
            client = MdeCloudClient(cfg)
            self.client_cache[cache_key] = client
            return client
        except Exception as exc:
            logger.warning(f"MDE configuration invalid for profile {profile.name}: {exc}")
            return None