import logging
import threading
from typing import Dict, List, Optional
import time
from sqlalchemy.orm import Session, joinedload

from detonatorapi.database import get_db_direct, Submission
from detonatorapi.db_interface import db_submission_change_status_quick, db_submission_add_log, db_submission_change_status
from detonatorapi.agent.agent_interface import connect_to_agent, submit_file_to_agent, gather_execution_results
from detonatorapi.edr_cloud.mde_cloud_plugin import CloudMdePlugin

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

    def is_available(self, submission_id: int) -> bool:
        """Check if the VM for this submission is available (reachable and not locked).
        
        The vm_monitor will only transition a submission from 'fresh' to 'instantiate'
        when this returns True. Subclasses should override to add connector-specific checks.
        """
        return True

    def instantiate(self, submission_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")


    def connect(self, submission_id: int):
        def connect_thread(submission_id: int):
            try:
                if connect_to_agent(submission_id):
                    db_submission_change_status(submission_id, "connected")
                else:
                    db_submission_change_status(submission_id, "error", "Could not connect")
            except Exception as e:
                logger.error(f"connect_thread unhandled exception for submission {submission_id}: {e}")
                db_submission_change_status(submission_id, "error", str(e))

        threading.Thread(target=connect_thread, args=(submission_id, )).start()


    def process(self, submission_id: int, pre_wait: int = 0):
        def process_thread(submission_id: int):
            try:
                # TODO This is to handle Azure VM startup weirdness
                # Just because we could connect, doesnt mean we want to immediately process
                # Let the VM start up for a bit
                time.sleep(pre_wait)

                execution_feedback = submit_file_to_agent(submission_id)
                if execution_feedback is None:
                    db_submission_change_status(submission_id, "stop", f"Could not start trace on RedEdr")
                    return

                gather_execution_results(submission_id, execution_feedback)
                db_submission_change_status(submission_id, "processed")
            except Exception as e:
                logger.error(f"process_thread unhandled exception for submission {submission_id}: {e}")
                db_submission_change_status(submission_id, "error", str(e))

        threading.Thread(target=process_thread, args=(submission_id, )).start()


    def stop(self, submission_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")

    def remove(self, submission_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")

    def kill(self, submission_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")
