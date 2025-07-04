import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
import time
import threading

from .database import get_background_db, Scan
from .db_interface import db_change_status
from .vm_manager import *
from .azure_manager import get_azure_manager, AzureManager
from .utils import mylog
from .edr_templates import get_edr_template_manager
from .settings import *

logger = logging.getLogger(__name__)


vmManagers = {
    "new": VmManagerNew(),
    "clone": VmManagerClone(),
    "running": VmManagerRunning(),
}


class VMMonitorTask:
    """Background task to monitor Scan status and lifecycle"""
    
    def __init__(self):
        self.running = False
        self.task = None
        self.db = None
        self.azure_manager: AzureManager = None


    def init(self):
        """Initialize the VM monitor task"""
        self.db = get_background_db()
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
        while self.running:
            try:
                self.check_all_scans()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in VM monitoring loop: {str(e)}")
                await asyncio.sleep(1)
    

    def check_all_scans(self):
        scans = self.db.query(Scan).all()
        for scan in scans:
            scan_id: int = scan.id
            status: str = scan.status
            edr_template_id: str = scan.edr_template

            # Skip finished (nothing todo)
            if status in ["finished"]:
                continue
            # Check for validity
            edr_template = get_edr_template_manager().get_template(edr_template_id)
            if not edr_template:
                logger.error(f"EDR template {edr_template_id} not found for scan {scan_id}")
                continue
            server_type = edr_template["type"]
            vmManager: VmManager = vmManagers[server_type]

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

            # Handle based on status
            match status:
                case "fresh":
                    # Start the process with instantiating the VM
                    db_change_status(scan_id, "instantiate")

                case "instantiate":
                    thread = threading.Thread(target=vmManager.instantiate, args=(scan_id,))
                    thread.start()
                case "instantiated":
                    db_change_status(scan_id, "connect")

                case "connect":
                    thread = threading.Thread(target=vmManager.connect, args=(scan_id,))
                    thread.start()
                case "connected":
                    db_change_status(scan_id, "scan")

                case "scan":
                    thread = threading.Thread(target=vmManager.scan, args=(scan_id,))
                    thread.start()
                case "scanned":
                    db_change_status(scan_id, "stop")

                case "stop":
                    thread = threading.Thread(target=vmManager.stop, args=(scan_id,))
                    thread.start()
                case "stopped":
                    db_change_status(scan_id, "remove")

                case "remove":
                    thread = threading.Thread(target=vmManager.remove, args=(scan_id,))
                    thread.start()
                case "removed":
                    db_change_status(scan_id, "finished")


# Global VM monitor instance
vm_monitor = VMMonitorTask()

def start_vm_monitoring():
    """Start the global VM monitoring task"""
    vm_monitor.start_monitoring()

def stop_vm_monitoring():
    """Stop the global VM monitoring task"""
    vm_monitor.stop_monitoring()
