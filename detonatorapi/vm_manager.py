from datetime import datetime
import logging

from .database import get_background_db, Scan
from .utils import mylog
from .db_interface import db_change_status
from .azure_manager import initialize_azure_manager, get_azure_manager


logger = logging.getLogger(__name__)


class VmManager:
    def __init__(self):
        pass

    def instantiate(self, scan_id: int):
        pass

    def connect(self, scan_id: int):
        pass

    def scan(self, scan_id: int):
        pass

    def stop(self, scan_id: int):
        pass

    def remove(self, scan_id: int):
        pass


class VmManagerNew(VmManager):
    def __init__(self):
        super().__init__()

    def instantiate(self, scan_id: int):
        logger.info("VmManagerNew: Instantiating VM for scan %s (Thread)", scan_id)
        db_change_status(scan_id, "instantiating")
        azure_manager = get_azure_manager()
        if azure_manager.create_machine(scan_id):
            db_change_status(scan_id, "instantiated")
        else:
            db_change_status(scan_id, "error", "Could not create VM")

    def connect(self, scan_id: int):
        logger.info("VmManagerNew: Connecting to VM for scan %s", scan_id)
        db_change_status(scan_id, "connecting")
        db_change_status(scan_id, "connected")

    def scan(self, scan_id: int):
        logger.info("VmManagerNew: Starting scan for VM %s", scan_id)
        db_change_status(scan_id, "scanning")
        db_change_status(scan_id, "scanned")

    def stop(self, scan_id: int):
        logger.info("VmManagerNew: Stopping VM for scan %s", scan_id)
        db_change_status(scan_id, "stopping")
        azure_manager = get_azure_manager()
        if azure_manager.shutdown_vm(scan_id):
            db_change_status(scan_id, "stopped")
        else: 
            db_change_status(scan_id, "error")

    def remove(self, scan_id: int):
        logger.info("VmManagerNew: Removing VM for scan %s", scan_id)
        db_change_status(scan_id, "removing")
        azure_manager = get_azure_manager()
        if azure_manager.delete_vm_resources(scan_id):
            db_change_status(scan_id, "removed")
        else:
            db_change_status(scan_id, "error")


class VmManagerClone(VmManager):
    pass

class VmManagerRunning(VmManager):
    pass
