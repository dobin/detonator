import logging
import time
import threading
from typing import Dict, List, Optional

from detonatorapi.database import get_db_for_thread, Scan
from detonatorapi.utils import mylog, scanid_to_vmname
from detonatorapi.db_interface import db_change_status, db_scan_add_log

from .azure_manager import get_azure_manager
from .connector import ConnectorBase

logger = logging.getLogger(__name__)


class ConnectorNewAzure(ConnectorBase):
    def __init__(self):
        pass

    def get_description(self) -> str:
        """Return a description of what this connector does"""
        return "Creates new Azure virtual machine"
    
    def get_comment(self) -> str:
        """Return additional comments about this connector"""
        return "Wait time: around 5 minutes. Reproducability: High"

    def instantiate(self, db, db_scan: Scan):
        def instantiate_thread(scan_id: int): 
            thread_db = get_db_for_thread()
            db_scan = thread_db.get(Scan, scan_id)
            azure_manager = get_azure_manager()
            if azure_manager.create_machine(thread_db, db_scan):
                db_change_status(thread_db, db_scan, "instantiated")
            else:
                db_change_status(thread_db, db_scan, "error", "Could not create VM")
            thread_db.close()
        threading.Thread(target=instantiate_thread, args=(db_scan.id, )).start()


    def connect(self, db, db_scan: Scan):
        # default agent connect
        super().connect(db, db_scan)


    def scan(self, db, db_scan: Scan):
        # default agent scan
        super().scan(db, db_scan)


    def stop(self, db, db_scan: Scan):
        def stop_thread(scan_id: int):
            thread_db = get_db_for_thread()
            azure_manager = get_azure_manager()
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
            vm_name = scanid_to_vmname(scan_id)
            if azure_manager.delete_vm_resources(vm_name):
                db_change_status(thread_db, db_scan, "removed")
            else:
                db_change_status(thread_db, db_scan, "error")
            thread_db.close()

        threading.Thread(target=remove_thread, args=(db_scan.id, )).start()
