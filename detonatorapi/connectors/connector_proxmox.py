import logging
import time
import threading
from typing import Dict, List, Optional

from detonatorapi.database import get_db_for_thread, Scan, Profile
from detonatorapi.utils import mylog, scanid_to_vmname
from detonatorapi.db_interface import db_scan_change_status_quick, db_scan_add_log, db_get_profile_by_id, db_scan_change_status

from .connector import ConnectorBase
from detonatorapi.settings import *
from detonatorapi.connectors.proxmox_manager import ProxmoxManager

logger = logging.getLogger(__name__)


PROXMOX_NO_RESET = False  # for debugging


class ConnectorProxmox(ConnectorBase):
    def __init__(self):
        self.proxmox_manager: ProxmoxManager = ProxmoxManager()


    def init(self) -> bool:
        return self.proxmox_manager.Init()

        #if not self.proxmox_manager.SnapshotExists():
        #    logger.error("Proxmox snapshot does not exist")
        #    return False
        #return True
        

    def get_description(self) -> str:
        """Return a description of what this connector does"""
        return "Will use Proxmox VM and revert it to snapshot after scan"
    

    def get_comment(self) -> str:
        """Return additional comments about this connector"""
        return "Wait time: Instant. Reproducability: High"
    

    def get_sample_data(self) -> Dict:
        """Return sample data for this connector"""
        return {
            "vm_snapshot": "latest",
            "vm_id": 100,
            "vm_ip": "192.168.1.1",
        }


    def instantiate(self, scan_id: int):
        def instantiate_thread(scan_id: int): 
            thread_db = get_db_for_thread()
            db_scan = thread_db.get(Scan, scan_id)
            if not db_scan:  # check mostly for syntax checker
                logger.error(f"Scan {scan_id} not found")
                return
            db_profile: Profile = db_scan.profile
            vm_id = db_profile.data['vm_id']

            status = self.proxmox_manager.StatusVm(vm_id)
            logger.info(f"Proxmox VM status: {status}")
            if status != "running":
                if not self.proxmox_manager.StartVm(vm_id):
                    db_scan_change_status_quick(thread_db, db_scan, "error", "Could not start VM")
                    thread_db.close()
                    return

            db_scan.vm_exist = 1  # Set to 1 to indicate VM is running
            db_scan.vm_ip_address = db_profile.data['vm_ip']
            db_scan_change_status_quick(thread_db, db_scan, "instantiated")
            thread_db.close()

        threading.Thread(target=instantiate_thread, args=(scan_id, )).start()


    def connect(self, scan_id: int):
        # default agent connect
        super().connect(scan_id)


    def scan(self, scan_id: int, pre_wait: int = 0):
        # default agent scan
        super().scan(scan_id, pre_wait)


    def stop(self, scan_id: int):
        if PROXMOX_NO_RESET:
            db_scan_change_status(scan_id, "finished")
            return

        def stop_thread(scan_id: int):
            thread_db = get_db_for_thread()
            db_scan: Scan = thread_db.get(Scan, scan_id)
            if not db_scan:  # check mostly for syntax checker
                logger.error(f"Scan {scan_id} not found")
                return
            db_profile: Profile = db_scan.profile
            vm_id = db_profile.data['vm_id']

            if self.proxmox_manager.StopVm(vm_id):
                db_scan_change_status(scan_id, "stopped")
            else: 
                db_scan_change_status(scan_id, "error")
            thread_db.close()

        threading.Thread(target=stop_thread, args=(scan_id, )).start()
            

    def remove(self, scan_id: int):
        if PROXMOX_NO_RESET:
            db_scan_change_status(scan_id, "finished")
            return

        def remove_thread(scan_id: int):
            thread_db = get_db_for_thread()
            db_scan = thread_db.get(Scan, scan_id)
            if not db_scan:  # check mostly for syntax checker
                logger.error(f"Scan {scan_id} not found")
                return
            db_profile: Profile = db_scan.profile
            vm_id = db_profile.data['vm_id']
            vm_snapshot = db_profile.data['vm_snapshot']

            if self.proxmox_manager.RevertVm(vm_id, vm_snapshot):
                db_scan.vm_exist = 0
                # keep it for now
                #db_scan.vm_instance_name = None
                #db_scan.vm_ip_address = None
                db_scan_add_log(thread_db, db_scan, "VM successfully reverted")
            else:
                db_scan_change_status(scan_id, "error")
                thread_db.close()
                return

            # TODO cleanup()?
            time.sleep(2) # or we get "Error: VM is locked (rollback)"
            if self.proxmox_manager.StartVm(vm_id):
                db_scan_add_log(thread_db, db_scan, "VM successfully started")
            else:
                db_scan_add_log(thread_db, db_scan, "VM failed starting")

            # we give it some time to start up
            # it may be important, when the user immediately tries to start a new scan
            # with ETW/ETW-TI which needs some warmup
            time.sleep(20)

            db_scan_change_status(scan_id, "removed")
            thread_db.close()

        threading.Thread(target=remove_thread, args=(scan_id, )).start()


    def kill(self, scan_id: int):
        """Attempt to kill (stop and delete) the VM"""
        def kill_thread(scan_id: int):
            thread_db = get_db_for_thread()
            db_scan = thread_db.get(Scan, scan_id)
            if not db_scan:  # check mostly for syntax checker
                logger.error(f"Scan {scan_id} not found")
                return
            db_profile: Profile = db_scan.profile
            vm_id = db_profile.data['vm_id']
            vm_snapshot = db_profile.data['vm_snapshot']
            vm_name = db_scan.vm_instance_name

            logger.info(f"Killing VM {vm_name} scan {scan_id}")

            # Stop if running
            powerState = self.proxmox_manager.StatusVm(vm_id)
            if powerState == "running":
                if self.proxmox_manager.StopVm(vm_id):
                    db_scan_add_log(thread_db, db_scan, "VM successfully stopped")
                else:
                    db_scan_add_log(thread_db, db_scan, "VM failed stopping")

            # Always try to revert
            if self.proxmox_manager.RevertVm(vm_id, vm_snapshot):
                db_scan_add_log(thread_db, db_scan, "VM successfully killed")
                db_scan.vm_exist = 0  # Set to 0 to indicate VM is removed
            else:
                db_scan_add_log(thread_db, db_scan, "VM failed deleting")
            
            # Set it to killed. We tried.
            # (never to error and vm_exist = 1 as it will be killed again)
            db_scan_change_status(scan_id, "killed")

        threading.Thread(target=kill_thread, args=(scan_id, )).start()

