import logging
import threading
from typing import Dict, List, Optional
import time
from sqlalchemy.orm import Session, joinedload

from detonatorapi.database import get_db_direct, Submission
from detonatorapi.db_interface import db_submission_change_status_quick, db_submission_add_log, db_submission_change_status
from detonatorapi.agent.agent_interface import connect_to_agent, submit_file_to_agent, thread_gatherer
from detonatorapi.edr_cloud.mde_alert_monitor import AlertMonitorMde

logger = logging.getLogger(__name__)


class ConnectorBase:
    def __init__(self,):
        pass

    def init(self) -> bool:
        raise NotImplementedError("This method should be overridden by subclasses")

    def get_description(self) -> str:
        """Return a description of what this connector does"""
        return "Base connector class"
    
    def get_comment(self) -> str:
        """Return additional comments about this connector"""
        return ""
    
    def get_sample_data(self) -> Dict[str, str]:
        """Return sample data for this connector"""
        return {}

    def instantiate(self, submission_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")

    def connect(self, submission_id: int):
        def connect_thread(submission_id: int):
            if connect_to_agent(submission_id):
                db_submission_change_status(submission_id, "connected")
            else:
                db_submission_change_status(submission_id, "error", "Could not connect")

        threading.Thread(target=connect_thread, args=(submission_id, )).start()

    def submission(self, submission_id: int, pre_wait: int = 0):
        def submission_thread(submission_id: int):
            # This is to handle Azure VM startup weirdness
            # Just because we could connect, doesnt mean we want to immediately submission
            # Let the VM start up for a bit
            time.sleep(pre_wait)

            if submit_file_to_agent(submission_id):
                db_submission_change_status(submission_id, "stop")
            else:
                db_submission_change_status(submission_id, "stop", f"Could not start trace on RedEdr")

        # boot the submission thread already
        threading.Thread(target=submission_thread, args=(submission_id, )).start()

        # boot the agent local EDR data gatherer thread
        threading.Thread(target=thread_gatherer, args=(submission_id, )).start()

        # Check if we have MDE configured. Create a polling thread if so. 
        db = get_db_direct()
        submission = db.query(Submission).options(joinedload(Submission.profile)).filter(Submission.id == submission_id).first()
        if not submission:
            db.close()
            return
        if submission.profile and submission.profile.data.get("edr_mde"):
            alertMonitorMde = AlertMonitorMde(submission_id)
            alertMonitorMde.start_monitoring()
            logger.info(f"Started Cloud-MDE alert monitoring for submission {submission_id}")
        db.close()


    def stop(self, submission_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")

    def remove(self, submission_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")

    def kill(self, submission_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")
