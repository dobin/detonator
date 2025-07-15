import logging
import threading
from typing import Dict, List, Optional

from detonatorapi.database import get_db_for_thread, Scan
from detonatorapi.db_interface import db_change_status, db_scan_add_log

from .connector import ConnectorBase

logger = logging.getLogger(__name__)


class ConnectorLive(ConnectorBase):
    def __init__(self):
        pass

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


    def instantiate(self, db, db_scan: Scan):
        # nothing todo here, the VM is already running
        db_change_status(db, db_scan, "connect")


    def connect(self, db, db_scan: Scan):
        # default agent connect
        super().connect(db, db_scan)


    def scan(self, db, db_scan: Scan, pre_wait: int = 0):
        # default agent scan
        super().scan(db, db_scan, pre_wait=pre_wait)


    def stop(self, db, db_scan: Scan):
        # nothing todo here, VM keeps running
        db_change_status(db, db_scan, "finished")


    def remove(self, db, db_scan: Scan):
        # nothing todo here, VM keeps running
        db_change_status(db, db_scan, "finished")
