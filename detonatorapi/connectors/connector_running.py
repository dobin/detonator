import logging
import threading
from typing import Dict, List, Optional

from detonatorapi.database import get_db_for_thread, Scan
from detonatorapi.db_interface import db_change_status, db_scan_add_log

from .connector import ConnectorBase

logger = logging.getLogger(__name__)


class ConnectorRunning(ConnectorBase):
    def __init__(self, db):
        self.db = db


    def instantiate(self, db_scan: Scan):
        # nothing todo here, the VM is already running
        db_change_status(self.db, db_scan, "connect")


    def connect(self, db_scan: Scan):
        # default agent connect
        super().connect(db_scan)


    def scan(self, db_scan: Scan):
        # default agent scan
        super().scan(db_scan)


    def stop(self, db_scan: Scan):
        # nothing todo here, VM keeps running
        db_change_status(self.db, db_scan, "finished")


    def remove(self, db_scan: Scan):
        # nothing todo here, VM keeps running
        db_change_status(self.db, db_scan, "finished")
