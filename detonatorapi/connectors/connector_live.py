import logging
import threading
from typing import Dict, List, Optional

from detonatorapi.database import get_db_for_thread, Scan
from detonatorapi.db_interface import db_scan_change_status_quick, db_scan_add_log, db_scan_change_status

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


    def instantiate(self, scan_id: int):
        # nothing todo here, the VM is already running
        db_scan_change_status(scan_id, "connect")


    def connect(self, scan_id: int):
        # default agent connect
        super().connect(scan_id)


    def scan(self, scan_id: int, pre_wait: int = 0):
        # default agent scan
        super().scan(scan_id, pre_wait=pre_wait)


    def stop(self, scan_id: int):
        # nothing todo here, VM keeps running
        db_scan_change_status(scan_id, "finished")


    def remove(self, scan_id: int):
        # nothing todo here, VM keeps running
        db_scan_change_status(scan_id, "finished")


    def kill(self, scan_id: int):
        # nothing todo here, VM keeps running
        db_scan_change_status(scan_id, "finished")
