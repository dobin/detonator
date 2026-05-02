import logging
import threading
from typing import Dict, List, Optional

from detonatorapi.db_interface import db_submission_change_status
from detonatorapi.database import get_db_direct, Submission
from detonatorapi.agent.agent_api import AgentApi

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
        }

    def is_available(self, submission_id: int) -> bool:
        """Check if the agent is reachable and not locked."""
        db = get_db_direct()
        try:
            submission = db.get(Submission, submission_id)
            if not submission:
                return False
            agent_ip = submission.profile.vm_ip
            agent_port = submission.profile.port
            if not agent_ip:
                return False
            agent_api = AgentApi(agent_ip, agent_port)
            if not agent_api.IsReachable():
                return False
            if agent_api.IsInUse():
                return False
            return True
        finally:
            db.close()

    def instantiate(self, submission_id: int):
        # nothing todo here, the VM is already running
        db_submission_change_status(submission_id, "connect")


    def connect(self, submission_id: int):
        # default agent connect
        super().connect(submission_id)


    def process(self, submission_id: int, pre_wait: int = 0):
        # default agent submission
        super().process(submission_id, pre_wait=pre_wait)


    def stop(self, submission_id: int):
        # nothing todo here, VM keeps running
        db_submission_change_status(submission_id, "finished")


    def remove(self, submission_id: int):
        # nothing todo here, VM keeps running
        db_submission_change_status(submission_id, "finished")


    def kill(self, submission_id: int):
        # nothing todo here, VM keeps running
        db_submission_change_status(submission_id, "finished")
