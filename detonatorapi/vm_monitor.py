import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
import time
import threading

from .database import get_db_for_thread, Scan
from .db_interface import db_change_status
from .vm_manager import *
from .azure_manager import get_azure_manager, AzureManager
from .utils import mylog
from .edr_templates import edr_template_manager
from .settings import *

logger = logging.getLogger(__name__)


class VMMonitorTask:
    """Background task to monitor Scan status and lifecycle"""
    
    def __init__(self):
        self.running = False
        self.task = None
        self.db = None
        self.azure_manager: AzureManager = None


    def init(self):
        """Initialize the VM monitor task"""
        #self.db = get_background_db()
        self.azure_manager = get_azure_manager()
    

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
        # IN-thread initialization
        self.db = get_db_for_thread()

        # give it the same db
        self.vmManagers = {
            "new": VmManagerNew(self.db),
            "clone": VmManagerClone(self.db),
            "running": VmManagerRunning(self.db),
        }

        while self.running:
            try:
                self.check_all_scans()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in VM monitoring loop: {str(e)}")
                await asyncio.sleep(1)

        self.db.commit()
        self.db.close()
    

    def check_all_scans(self):
        scans = self.db.query(Scan).all()
        for scan in scans:
            scan_id: int = scan.id
            status: str = scan.status
            edr_template_id: str = scan.edr_template

            # Skip finished (nothing todo)
            if status in [ 'finished' ]:
                continue
            if status in [ 'error' ]:
                continue

            # Check for validity
            edr_template = edr_template_manager.get_template(edr_template_id)
            if not edr_template:
                logger.error(f"EDR2 template {edr_template_id} not found for scan {scan_id}")
                db_change_status(self.db, scan, "error")
                continue
            server_type = edr_template["type"]
            vmManager: VmManager = self.vmManagers[server_type]

            # Try cleanup old:
            #   error
            #   non-finished older than 5 minutes
            if status in [ "error" ] or (status not in [ "finished" ] and (datetime.utcnow() - scan.created_at) > timedelta(minutes=VM_DESTROY_AFTER)):
                vm_name = scan.vm_instance_name
                if vm_name and vm_name != "":
                    azure_vm_status = self.azure_manager.get_vm_status(vm_name)
                    if azure_vm_status in [ "running" ]:
                        logger.info(f"Scan {scan_id} is in error state but VM {vm_name} running: stopping VM")
                        thread = threading.Thread(target=vmManager.stop, args=(scan_id,))
                        thread.start()
                    elif azure_vm_status in [ "stopped" ]:
                        logger.info(f"Scan {scan_id} is in error state but VM {vm_name} exist: removing VM")
                        thread = threading.Thread(target=vmManager.remove, args=(scan_id,))
                        thread.start()

            # State Machine
            match status:
                case "fresh":
                    # Start the process with instantiating the VM
                    db_change_status(self.db, scan, "instantiate")

                case "instantiate":
                    db_change_status(self.db, scan, "instantiating")
                    vmManager.instantiate(scan)
                case "instantiated":
                    db_change_status(self.db, scan, "connect")

                case "connect":
                    db_change_status(self.db, scan, "connecting")
                    vmManager.connect(scan)
                case "connected":
                    db_change_status(self.db, scan, "scan")

                case "scan":
                    db_change_status(self.db, scan, "scanning")
                    vmManager.scan(scan)
                case "scanned":
                    db_change_status(self.db, scan, "stop")

                case "stop":
                    db_change_status(self.db, scan, "stopping")
                    vmManager.stop(scan)
                case "stopped":
                    db_change_status(self.db, scan, "remove")

                case "remove":
                    db_change_status(self.db, scan, "removing")
                    vmManager.remove(scan)
                case "removed":
                    db_change_status(self.db, scan, "finished")


# Global VM monitor instance
vm_monitor = VMMonitorTask()

def start_vm_monitoring():
    """Start the global VM monitoring task"""
    vm_monitor.start_monitoring()

def stop_vm_monitoring():
    """Stop the global VM monitoring task"""
    vm_monitor.stop_monitoring()
