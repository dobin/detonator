import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import pprint

from sqlalchemy.orm import Session, joinedload

from ..database import get_db_direct, Submission, SubmissionAlert, Profile
from .mde_client import MDEClient
from ..db_interface import db_submission_add_log, db_submission_change_status_quick

logger = logging.getLogger(__name__)

POLLING_TIME_MINUTES = 2  # post end monitoring duration
POLL_INTERVAL_SECONDS = 30  # polling interval

class AlertMonitorMde:

    def __init__(self, submission_id: int):
        self.submission_id = submission_id
        self.task: Optional[asyncio.Task] = None
        self.client_cache: Dict[str, MDEClient] = {}


    def start_monitoring(self):
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info("Alert monitoring task started")


    async def _monitor_loop(self):
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
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Alert monitor loop error: {exc}")
                await asyncio.sleep(5)
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
        client = self._get_client(submission.profile)
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
        client = self._get_client(submission.profile)
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


    def _store_alerts(self, db: Session, submission: Submission, alerts_with_evidence):
        """Store alerts with their evidence already included."""
        existing_ids = {alert.alert_id for alert in submission.alerts}
        
        for alert in alerts_with_evidence:
            alert_id = alert.get("AlertId", None)
            if not alert_id:
                continue
            if alert_id in existing_ids:
                continue

            # somehow we have a lot of duplicates in the list?
            existing_ids.add(alert_id)

            # Extract metadata from first evidence row
            detected_at = alert.get("Timestamp")
            detected_dt = None
            if detected_at:
                try:
                    detected_dt = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
                except ValueError:
                    detected_dt = None
            
            submission_alert = SubmissionAlert(
                submission_id=submission.id,
                alert_id=alert_id,
                title=alert.get("Title"),
                severity=alert.get("Severity"),
                category=alert.get("Categories"),
                detection_source=alert.get("DetectionSource"),
                detected_at=detected_dt,
            )
            db.add(submission_alert)
            submission.alerts.append(submission_alert)
            logger.info(f"submission {submission.id}: New alert stored: {alert_id}")
    

    def _auto_close(self, db: Session, submission: Submission, client: MDEClient):
        comment = f"Auto-Closed by Detonator (submission {submission.id})"
        closed_incidents = set()
        for alert in submission.alerts:
            if not alert.auto_closed_at:
                try:
                    client.resolve_alert(alert.alert_id, comment)
                    alert.status = "Resolved"
                    alert.auto_closed_at = datetime.utcnow()
                    alert.comment = comment
                except Exception as exc:
                    logger.error(f"Failed to resolve alert {alert.alert_id}: {exc}")
            incident_id = alert.incident_id
            if incident_id and incident_id not in closed_incidents:
                try:
                    client.resolve_incident(incident_id, comment)
                    closed_incidents.add(incident_id)
                except Exception as exc:
                    logger.error(f"Failed to resolve incident {incident_id}: {exc}")
        db_submission_add_log(db, submission, "Detection window completed. Alerts auto-closed.")


    def _get_client(self, profile: Profile) -> Optional[MDEClient]:
        cfg = profile.data.get("edr_mde") or {}
        if not cfg:
            return None
        cache_key = f"{profile.id}:{cfg.get('client_id')}"
        client = self.client_cache.get(cache_key)
        if client:
            return client
        try:
            client = MDEClient(cfg)
            self.client_cache[cache_key] = client
            return client
        except Exception as exc:
            logger.warning(f"MDE configuration invalid for profile {profile.name}: {exc}")
            return None