import logging
import threading
from typing import Dict, List, Optional

from detonatorapi.db_interface import db_submission_change_status

from .connector import ConnectorBase

logger = logging.getLogger(__name__)


class ConnectorLive(ConnectorBase):
    def __init__(self):
        pass

    def init(self) -> bool:
        return True

    def get_description(self) -> str:
        """Return a description of what this connector does"""
        return "Connects to already running virtual machine"
    
    def get_comment(self) -> str:
        """Return additional comments about this connector"""
        return "Wait time: Instant. Reproducability: Low"
    
    def get_sample_data(self) -> Dict[str, str]:
        """Return sample data for this connector"""
        return {
            "ip": "192.168.1.1",
        }


    def instantiate(self, submission_id: int):
        # nothing todo here, the VM is already running
        db_submission_change_status(submission_id, "connect")


    def connect(self, submission_id: int):
        # default agent connect
        super().connect(submission_id)


    def submission(self, submission_id: int, pre_wait: int = 0):
        # default agent submission
        super().submission(submission_id, pre_wait=pre_wait)


    def stop(self, submission_id: int):
        # nothing todo here, VM keeps running
        db_submission_change_status(submission_id, "finished")


    def remove(self, submission_id: int):
        # nothing todo here, VM keeps running
        db_submission_change_status(submission_id, "finished")


    def kill(self, submission_id: int):
        # nothing todo here, VM keeps running
        db_submission_change_status(submission_id, "finished")
