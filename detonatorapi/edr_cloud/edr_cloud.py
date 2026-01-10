from abc import abstractmethod
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from sqlalchemy.orm import Session, joinedload

from detonatorapi.database import get_db_direct, Submission, SubmissionAlert, Profile
from detonatorapi.db_interface import db_submission_add_log, db_submission_change_status_quick

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 10  # polling interval in seconds
POLLING_TIME_MINUTES = 5  # post end monitoring duration in minutes


class EdrCloud:
    def __init__(self):
        self.submission_id: int = 0


    @staticmethod
    def is_relevant(profile_data: dict) -> bool:
        return False
    

    # initializes some kind of client for the cloud access
    # (HTTP client with authentication and REST access)
    @abstractmethod
    def InitializeClient(self, profile_data) -> bool:
        return False
    

    # Implement your polling (via API client above) here
    # Create a list of SubmissionAlert of your EDR
    # and store them via store_alerts()
    @abstractmethod
    def poll(self, db: Session, submission: Submission) -> bool:
        pass


    # implement this to finalize monitoring, e.g., auto-close alerts
    @abstractmethod
    def finish_monitoring(self, db: Session, submission: Submission) -> bool:
        return True
    

    # Main entry point for the thread
    # Will call poll() periodically until submission is done
    def monitor_loop(self, submission_id: int):
        db = get_db_direct()
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        if not submission:
            logger.error(f"EDR Cloud monitor: submission {submission_id} not found")
            db.close()
            return
        submission.absorber_status = "running"
        db.commit()
        
        while True:
            db.refresh(submission)
            # check if we are done
            if submission.status in ("error", "finished"):
                # check if we are > POLLING_TIME_MINUTES after completed_at
                if submission.completed_at and \
                        submission.completed_at + timedelta(minutes=POLLING_TIME_MINUTES) < datetime.utcnow():
                    break

            # poll
            self.poll(db, submission)
            db.commit()

            # sleep a bit before next poll
            time.sleep(POLL_INTERVAL_SECONDS)

        # We finished. Close alerts
        db.refresh(submission)
        submission.absorber_status = "finished"
        self.finish_monitoring(db, submission)
        db.commit()
        db.close()


    def store_alerts(self, db: Session, submission: Submission, alerts: List[SubmissionAlert]) -> bool:
        existing_ids = {alert.alert_id for alert in submission.alerts}
        
        for alert in alerts:
            if alert.alert_id in existing_ids:
                continue
            existing_ids.add(alert.alert_id)
            
            alert.submission_id = submission.id
            db.add(alert)
            #submission.alerts.append(alert)  # SQLAlchemy should handle this automatically
            logger.info(f"submission {submission.id}: New alert stored: {alert.alert_id}")

        if len(alerts) > 0:
            if submission.edr_verdict != "virus":
                submission.edr_verdict = "detected"
            db.commit()

        return True
