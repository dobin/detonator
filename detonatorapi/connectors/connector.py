import logging
import threading
from typing import Dict, List, Optional

from detonatorapi.database import get_db_for_thread, Scan
from detonatorapi.db_interface import db_change_status, db_scan_add_log
from detonatorapi.agent.agent_interface import connect_to_agent, scan_file_with_agent

from detonatorapi.database import get_db_for_thread, Scan

logger = logging.getLogger(__name__)


class ConnectorBase:
    def __init__(self,):
        pass

    def get_description(self) -> str:
        """Return a description of what this connector does"""
        return "Base connector class"
    
    def get_comment(self) -> str:
        """Return additional comments about this connector"""
        return ""

    def instantiate(self, db, db_scan: Scan):
        raise NotImplementedError("This method should be overridden by subclasses")

    def connect(self, db, db_scan: Scan):
        def connect_thread(scan_id: int):
            thread_db = get_db_for_thread()
            db_scan = thread_db.get(Scan, scan_id)
            if connect_to_agent(thread_db, db_scan):
                db_change_status(thread_db, db_scan, "connected")
            else:
                db_change_status(thread_db, db_scan, "error", "Could not connect")
            thread_db.close()

        threading.Thread(target=connect_thread, args=(db_scan.id, )).start()

    def scan(self, db, db_scan: Scan):
        def scan_thread(scan_id: int):
            thread_db = get_db_for_thread()
            db_scan = thread_db.get(Scan, scan_id)
            if scan_file_with_agent(thread_db, db_scan):
                db_change_status(thread_db, db_scan, "finished")
            else:
                db_change_status(thread_db, db_scan, "error", f"Could not start trace on RedEdr")

        threading.Thread(target=scan_thread, args=(db_scan.id, )).start()

    def stop(self, db, db_scan: Scan):
        raise NotImplementedError("This method should be overridden by subclasses")

    def remove(self, db, db_scan: Scan):
        raise NotImplementedError("This method should be overridden by subclasses")
