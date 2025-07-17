import logging
import time
import threading
from typing import Dict, List, Optional

from detonatorapi.database import get_db_for_thread, Scan
from detonatorapi.utils import mylog, scanid_to_vmname
from detonatorapi.db_interface import db_change_status, db_scan_add_log
from detonatorapi.connectors.azure_manager import initialize_azure_manager

from .azure_manager import get_azure_manager
from .connector import ConnectorBase

logger = logging.getLogger(__name__)


class ConnectorNewAzure(ConnectorBase):
    def __init__(self):
        pass

    def init(self) -> bool:
        return initialize_azure_manager()

    def get_description(self) -> str:
        """Return a description of what this connector does"""
        return "Creates new Azure virtual machine"
    
    def get_comment(self) -> str:
        """Return additional comments about this connector"""
        return "Wait time: around 5 minutes. Reproducability: High"
    
    def get_sample_data(self) -> Dict[str, str]:
        """Return sample data for this connector"""
        return {
            "image_reference": "/subscriptions/<subscription>/resourceGroups/detonator-rg/providers/Microsoft.Compute/images/rededr-image",
            "admin_username": "detonator",
            "admin_password": "secret",
        }


    def instantiate(self, db, db_scan: Scan):
        def instantiate_thread(scan_id: int): 
            thread_db = get_db_for_thread()
            db_scan = thread_db.get(Scan, scan_id)
            azure_manager = get_azure_manager()
            if not azure_manager:
                db_change_status(thread_db, db_scan, "error", "Azure not configured")
                thread_db.close()
                return
            if azure_manager.create_machine(thread_db, db_scan):
                db_change_status(thread_db, db_scan, "instantiated")
            else:
                db_change_status(thread_db, db_scan, "error", "Could not create VM")
            thread_db.close()
        threading.Thread(target=instantiate_thread, args=(db_scan.id, )).start()


    def connect(self, db, db_scan: Scan):
        # default agent connect
        super().connect(db, db_scan)


    def scan(self, db, db_scan: Scan, pre_wait: int = 0):
        # default agent scan
        super().scan(db, db_scan, pre_wait=120)  # 2min


    def stop(self, db, db_scan: Scan):
        def stop_thread(scan_id: int):
            thread_db = get_db_for_thread()
            azure_manager = get_azure_manager()
            if not azure_manager:
                db_change_status(thread_db, db_scan, "error", "Azure not configured")
                thread_db.close()
                return
            vm_name = scanid_to_vmname(scan_id)
            if azure_manager.shutdown_vm(vm_name):
                db_change_status(thread_db, db_scan, "stopped")
            else: 
                db_change_status(thread_db, db_scan, "error")
            thread_db.close()

        threading.Thread(target=stop_thread, args=(db_scan.id, )).start()
            

    def remove(self, db, db_scan: Scan):
        def remove_thread(scan_id: int):
            thread_db = get_db_for_thread()
            db_scan = thread_db.get(Scan, scan_id)
            azure_manager = get_azure_manager()
            if not azure_manager:
                db_change_status(thread_db, db_scan, "error", "Azure not configured")
                thread_db.close()
                return
            vm_name = scanid_to_vmname(scan_id)
            if azure_manager.delete_vm_resources(vm_name):
                db_scan.vm_exist = 0
                # keep it for now
                #db_scan.vm_instance_name = None
                #db_scan.vm_ip_address = None
                db_scan_add_log(thread_db, db_scan, "VM successfully removed")
                db_change_status(thread_db, db_scan, "removed")
            else:
                db_change_status(thread_db, db_scan, "error")
            thread_db.close()

        threading.Thread(target=remove_thread, args=(db_scan.id, )).start()


    def kill(self, db, db_scan: Scan):
        """Attempt to kill (stop and delete) the VM"""
        def kill_thread(scan_id: int):
            azure_manager = get_azure_manager()
            thread_db = get_db_for_thread()
            db_scan = thread_db.get(Scan, scan_id)
            vm_name = db_scan.vm_instance_name

            logger.info(f"Killing VM {vm_name} scan {scan_id}")

            # Stop if running
            powerState = azure_manager.get_vm_status(db_scan.vm_instance_name)
            if powerState == "running":
                if azure_manager.shutdown_vm(vm_name):
                    db_scan_add_log(thread_db, db_scan, "VM successfully stopped")
                else:
                    db_scan_add_log(thread_db, db_scan, "VM failed stopping")

            # Always try to remove
            if azure_manager.delete_vm_resources(vm_name):
                db_scan_add_log(thread_db, db_scan, "VM successfully killed")
                db_scan.vm_exist = 0  # Set to 0 to indicate VM is removed
            else:
                db_scan_add_log(thread_db, db_scan, "VM failed deleting")
            
            # Set it to killed. We tried.
            # (never to error and vm_exist = 1 as it will be killed again)
            db_change_status(thread_db, db_scan, "killed")

        threading.Thread(target=kill_thread, args=(db_scan.id, )).start()
