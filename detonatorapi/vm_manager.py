from datetime import datetime
import logging
import time

from .database import get_background_db, Scan
from .utils import mylog, scanid_to_vmname
from .db_interface import db_change_status, db_scan_add_log, db_mark_scan_error
from .azure_manager import initialize_azure_manager, get_azure_manager
from .agent_interface import connect_to_agent
from .rededr_api import RedEdrApi
from .edr_templates import get_edr_template_manager

logger = logging.getLogger(__name__)


class VmManager:
    def __init__(self):
        pass

    def instantiate(self, scan_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")

    def connect(self, scan_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")

    def scan(self, scan_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")

    def stop(self, scan_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")

    def remove(self, scan_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")


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
        vm_name = scanid_to_vmname(scan_id)
        if azure_manager.shutdown_vm(vm_name):
            db_change_status(scan_id, "stopped")
        else: 
            db_change_status(scan_id, "error")

    def remove(self, scan_id: int):
        logger.info("VmManagerNew: Removing VM for scan %s", scan_id)
        db_change_status(scan_id, "removing")
        azure_manager = get_azure_manager()
        vm_name = scanid_to_vmname(scan_id)
        if azure_manager.delete_vm_resources(vm_name):
            db_change_status(scan_id, "removed")
        else:
            db_change_status(scan_id, "error")


class VmManagerClone(VmManager):
    pass


class VmManagerRunning(VmManager):
    def instantiate(self, scan_id: int):
        db_change_status(scan_id, "connect")


    def connect(self, scan_id: int):
        logger.info("VmManagerRunning: Connecting to running VM for scan %s", scan_id)
        db_change_status(scan_id, "connecting")
        if connect_to_agent(scan_id):
            db_change_status(scan_id, "connected")
        else:
            db_change_status(scan_id, "error", "Could not connect")


    def scan(self, scan_id: int):
        db = get_background_db()

        db_scan = db.query(Scan).get(scan_id)
        if not db_scan:
            logger.error(f"Scan with ID {scan_id} not found in database")
            return
        edr_template_id = db_scan.edr_template
        if not edr_template_id:
            logger.error(f"Scan {scan_id} has no EDR template defined")
            return
        edr_template = get_edr_template_manager().get_template(edr_template_id)
        if not edr_template:
            logger.error(f"EDR template {edr_template_id} not found for scan {scan_id}")
            return
        rededr_ip = edr_template.get("ip", None)
        if not rededr_ip:
            logger.error(f"EDR template {edr_template_id} has no IP defined")
            return
        
        filename = db_scan.file.filename
        db_change_status(scan_id, "scanning")
        rededrApi = RedEdrApi(rededr_ip)

        if not rededrApi.StartTrace(filename):
            db_change_status(scan_id, "error", f"Could not start trace on RedEdr")
            return
        db_scan_add_log(scan_id, [f"Started trace for file {filename} on RedEdr at {rededr_ip}"])
        time.sleep(1.0)

        if not rededrApi.ExecFile(filename, db_scan.file.content):
           db_change_status(scan_id, "error", f"Could not exec file on RedEdr")
           return
        db_scan_add_log(scan_id, [f"Executed file {db_scan.file.filename} on RedEdr at {rededr_ip}"])
        time.sleep(10.0)

        rededr_events = rededrApi.GetJsonResult()
        agent_logs = rededrApi.GetLog()  # { 'log': [ 'logline', ],  'output': '...' }
        edr_logs = rededrApi.GetEdrLogs()

        if agent_logs is None:
            agent_logs = "No logs available"
            db_scan_add_log(scan_id, ["could not get logs from RedEdr"])
        if rededr_events is None:
            rededr_events = "No results available"
            db_scan_add_log(scan_id, ["could not get results from RedEdr"])
        if edr_logs is None:
            edr_logs = "No EDR logs available"
            db_scan_add_log(scan_id, ["could not get EDR logs from RedEdr"])

        db_scan = db.query(Scan).get(scan_id)
        if not db_scan:
            logger.error(f"Scan with ID {scan_id} not found in database")
            return
        
        db_scan.edr_logs = edr_logs
        db_scan.agent_logs = agent_logs
        db_scan.rededr_events = rededr_events
        db_scan.result = "<tbd>"
        db_scan.completed_at = datetime.utcnow()
        db.commit()
        
        # nothing more todo
        db_change_status(scan_id, "finished")


    def stop(self, scan_id: int):
        db_change_status(scan_id, "finished")


    def remove(self, scan_id: int):
        db_change_status(scan_id, "finished")
