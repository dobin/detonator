import logging
import threading
from typing import Dict, List, Optional
import time
from sqlalchemy.orm import Session, joinedload

from detonatorapi.database import get_db, Scan
from detonatorapi.db_interface import db_scan_change_status_quick, db_scan_add_log, db_scan_change_status
from detonatorapi.agent.agent_interface import connect_to_agent, scan_file_with_agent
from detonatorapi.edr_cloud.mde_alert_monitor import AlertMonitorMde
from detonatorapi.database import get_db, Scan

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

    def instantiate(self, scan_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")

    def connect(self, scan_id: int):
        def connect_thread(scan_id: int):
            if connect_to_agent(scan_id):
                db_scan_change_status(scan_id, "connected")
            else:
                db_scan_change_status(scan_id, "error", "Could not connect")

        threading.Thread(target=connect_thread, args=(scan_id, )).start()

    def scan(self, scan_id: int, pre_wait: int = 0):
        def scan_thread(scan_id: int):
            # This is to handle Azure VM startup weirdness
            # Just because we could connect, doesnt mean we want to immediately scan
            # Let the VM start up for a bit
            time.sleep(pre_wait)

            if scan_file_with_agent(scan_id):
                db_scan_change_status(scan_id, "stop")
            else:
                db_scan_change_status(scan_id, "error", f"Could not start trace on RedEdr")

        threading.Thread(target=scan_thread, args=(scan_id, )).start()

        # Check if we have MDE configured
        db = get_db()
        try:
            scan = db.query(Scan).options(joinedload(Scan.profile)).filter(Scan.id == scan_id).first()
            if not scan:
                return
            if scan.profile and scan.profile.data.get("edr_mde"):
                alertMonitorMde = AlertMonitorMde(scan_id)
                alertMonitorMde.start_monitoring()
                logger.info(f"Started Cloud-MDE alert monitoring for scan {scan_id}")
            else:
                logger.info(f"No Cloud-MDE configured for scan {scan_id}")
        finally:
            db.close()


    def stop(self, scan_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")

    def remove(self, scan_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")

    def kill(self, scan_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")
