import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
import time
import threading

from .database import get_db_direct, Scan
from .db_interface import db_scan_change_status_quick
from .utils import mylog
from .settings import *

from .connectors.connector import ConnectorBase
from .connectors.connector_newazure import ConnectorNewAzure
from .connectors.connector_live import ConnectorLive
from .connectors.connectors import connectors

logger = logging.getLogger(__name__)



class VMMonitorTask:
    """Background task to monitor Scan status and lifecycle"""
    
    def __init__(self):
        self.running = False
        self.task = None


    def start_monitoring(self):
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info("VM monitoring task started")
    

    def stop_monitoring(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                self.task
            except asyncio.CancelledError:
                pass
        logger.info("VM monitoring task stopped")
    

    async def _monitor_loop(self):
        while self.running:
            db = None
            try:
                db = get_db_direct()
                self.check_all_scans(db)
                db.commit()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in VM monitoring loop: {str(e)}")
                await asyncio.sleep(1)
            finally:
                if db:
                    db.close()
    

    def check_all_scans(self, db: Session):
        scans = db.query(Scan).all()
        for scan in scans:
            scan_id: int = scan.id
            status: str = scan.status

            # Skip finished (nothing todo)
            if status in [ 'finished', 'error' ]:
                continue

            # get responsible VM manager, based on the profile->connector
            if not scan.profile.connector:
                logger.error(f"Scan {scan_id} has no profile connector")
                db_scan_change_status_quick(db, scan, "error")
                continue
            connector: ConnectorBase|None = connectors.get(scan.profile.connector)
            if not connector:
                logger.error(f"Scan {scan_id} has no valid VM manager defined for profile connector: {scan.profile.connector}")
                logger.error(f"VM Managers: {list(connectors.get_all().keys())}")
                db_scan_change_status_quick(db, scan, "error")
                continue

            # cleanup failed
            if status == "error" and scan.vm_exist == 1:
                db_scan_change_status_quick(db, scan, "killing")

            # State Machine
            match status:
                case "fresh":
                    # Start the process with instantiating the VM
                    db_scan_change_status_quick(db, scan, "instantiate")

                case "instantiate":
                    db_scan_change_status_quick(db, scan, "instantiating")
                    connector.instantiate(scan_id)
                case "instantiated":
                    db_scan_change_status_quick(db, scan, "connect")

                case "connect":
                    db_scan_change_status_quick(db, scan, "connecting")
                    connector.connect(scan_id)
                case "connected":
                    db_scan_change_status_quick(db, scan, "scan")

                case "scan":
                    db_scan_change_status_quick(db, scan, "scanning")
                    connector.scan(scan_id)

                case "scanning": 
                    # handle logs?
                    pass

                case "scanned":
                    db_scan_change_status_quick(db, scan, "stop")

                case "stop":
                    db_scan_change_status_quick(db, scan, "stopping")
                    connector.stop(scan_id)
                case "stopped":
                    db_scan_change_status_quick(db, scan, "remove")

                case "remove":
                    db_scan_change_status_quick(db, scan, "removing")
                    connector.remove(scan_id)
                case "removed":
                    db_scan_change_status_quick(db, scan, "finished")

                case "kill":
                    db_scan_change_status_quick(db, scan, "killing")
                    connector.kill(scan_id)


# Global VM monitor instance
vm_monitor = VMMonitorTask()

def start_vm_monitoring():
    """Start the global VM monitoring task"""
    vm_monitor.start_monitoring()

def stop_vm_monitoring():
    """Stop the global VM monitoring task"""
    vm_monitor.stop_monitoring()
