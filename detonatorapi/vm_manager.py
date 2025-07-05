from datetime import datetime
import logging
import time
import threading

from .database import get_db_for_thread, Scan
from .utils import mylog, scanid_to_vmname
from .db_interface import db_change_status, db_scan_add_log
from .azure_manager import initialize_azure_manager, get_azure_manager
from .agent_interface import connect_to_agent
from .rededr_api import RedEdrApi
from .edr_templates import get_edr_template_manager

logger = logging.getLogger(__name__)


class VmManager:
    def __init__(self, db):
        self.db = db

    def instantiate(self, db_scan: Scan):
        raise NotImplementedError("This method should be overridden by subclasses")

    def connect(self, db_scan: Scan):
        raise NotImplementedError("This method should be overridden by subclasses")

    def scan(self, db_scan: Scan):
        raise NotImplementedError("This method should be overridden by subclasses")

    def stop(self, db_scan: Scan):
        raise NotImplementedError("This method should be overridden by subclasses")

    def remove(self, db_scan: Scan):
        raise NotImplementedError("This method should be overridden by subclasses")


class VmManagerNew(VmManager):
    def __init__(self, db):
        self.db = db

    def instantiate(self, db_scan: Scan):
        def instantiate_thread(scan_id: int): 
            logger.info("VmManagerNew: Instantiating VM for scan %s (Thread)", scan_id)
            thread_db = get_db_for_thread()
            db_scan = self.db.query(Scan).get(scan_id)
            azure_manager = get_azure_manager()
            if azure_manager.create_machine(self.db, db_scan):
                db_change_status(thread_db, db_scan, "instantiated")
            else:
                db_change_status(thread_db, db_scan, "error", "Could not create VM")
            thread_db.close()
        threading.Thread(target=instantiate_thread, args=(db_scan.id, )).start()


    def connect(self, db_scan: Scan):
        logger.info("VmManagerNew: Connecting to VM for scan %s", db_scan.id)
        db_change_status(self.db, db_scan, "connected")


    def scan(self, db_scan: Scan):
        logger.info("VmManagerNew: Starting scan for VM %s", db_scan.id)
        db_change_status(self.db, db_scan, "scanned")


    def stop(self, db_scan: Scan):
        logger.info("VmManagerNew: Stopping VM for scan %s", db_scan.id)

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
            

    def remove(self, db_scan: Scan):
        def remove_thread(scan_id: int):
            thread_db = get_db_for_thread()
            db_scan = self.db.query(Scan).get(scan_id)
            logger.info("VmManagerNew: Removing VM for scan %s", scan_id)
            azure_manager = get_azure_manager()
            vm_name = scanid_to_vmname(scan_id)
            if azure_manager.delete_vm_resources(vm_name):
                db_change_status(thread_db, db_scan, "removed")
            else:
                db_change_status(thread_db, db_scan, "error")
            thread_db.close()

        threading.Thread(target=remove_thread, args=(db_scan.id, )).start()


class VmManagerClone(VmManager):
    pass


class VmManagerRunning(VmManager):
    def __init__(self, db):
        self.db = db

    def instantiate(self, db_scan: Scan):
        logger.info("VmManagerRunning: Instantiating VM for scan %s", db_scan.id)
        db_change_status(self.db, db_scan, "connect")


    def connect(self, db_scan: Scan):
        def connect_thread(scan_id: int):
            thread_db = get_db_for_thread()
            db_scan = thread_db.query(Scan).get(scan_id)
            logger.info("VmManagerRunning: Connecting to running VM for scan %s", scan_id)
            if connect_to_agent(thread_db, db_scan):
                db_change_status(thread_db, db_scan, "connected")
            else:
                db_change_status(thread_db, db_scan, "error", "Could not connect")
            thread_db.close()

        threading.Thread(target=connect_thread, args=(db_scan.id, )).start()


    def scan(self, db_scan: Scan):
        def scan_thread(scan_id: int):
            thread_db = get_db_for_thread()
            db_scan = thread_db.query(Scan).get(scan_id)
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
            file_content = db_scan.file.content
            rededrApi = RedEdrApi(rededr_ip)

            if not rededrApi.StartTrace(filename):
                db_change_status(thread_db, db_scan, "error", f"Could not start trace on RedEdr")
                return
            db_scan_add_log(thread_db, db_scan, [f"Started trace for file {filename} on RedEdr at {rededr_ip}"])
            time.sleep(1.0)

            if not rededrApi.ExecFile(filename, file_content):
                db_change_status(thread_db, db_scan, "error", f"Could not exec file on RedEdr")
                return
            db_scan_add_log(thread_db, db_scan, [f"Executed file {filename} on RedEdr at {rededr_ip}"])
            time.sleep(10.0)

            rededr_events = rededrApi.GetJsonResult()
            agent_logs = rededrApi.GetLog()  # { 'log': [ 'logline', ],  'output': '...' }
            edr_logs = rededrApi.GetEdrLogs()
            is_detected = ""

            if agent_logs is None:
                agent_logs = "No logs available"
                db_scan_add_log(thread_db, db_scan, ["could not get logs from RedEdr"])
            if rededr_events is None:
                rededr_events = "No results available"
                db_scan_add_log(thread_db, db_scan, ["could not get results from RedEdr"])
            if edr_logs is None:
                is_detected = "N/A"
                edr_logs = "No EDR logs available"
                db_scan_add_log(thread_db, db_scan, ["could not get EDR logs from RedEdr"])
            else:
                # Super Simple heuristics for now (Defender)
                if 'Suspicious' in edr_logs:
                    is_detected = "detected"
                    db_scan_add_log(thread_db, db_scan, ["EDR logs indicate suspicious activity detected"])
                else:
                    is_detected = "clean"
                    db_scan_add_log(thread_db, db_scan, ["EDR logs indicate clean"])
            
            db_scan.edr_logs = edr_logs
            db_scan.agent_logs = agent_logs
            db_scan.rededr_events = rededr_events
            db_scan.result = is_detected
            db_scan.completed_at = datetime.utcnow()
            thread_db.commit()
            
            # nothing more todo
            db_change_status(thread_db, db_scan, "finished")

        threading.Thread(target=scan_thread, args=(db_scan.id, )).start()


    def stop(self, db_scan: Scan):
        db_change_status(self.db, db_scan, "finished")


    def remove(self, db_scan: Scan):
        db_change_status(self.db, db_scan, "finished")
