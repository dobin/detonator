import logging
import time
import threading
from typing import Dict, List, Optional

from detonatorapi.database import get_db, Scan, Profile
from detonatorapi.utils import mylog, scanid_to_vmname
from detonatorapi.db_interface import db_scan_change_status_quick, db_scan_add_log, db_get_profile_by_id, db_scan_change_status

from .connector import ConnectorBase
from detonatorapi.settings import *
from detonatorapi.connectors.proxmox_manager import ProxmoxManager

logger = logging.getLogger(__name__)


PROXMOX_NO_RESET = False  # for debugging

INSTANCE_USED_SLEEP_TIME = 10  # seconds to wait if instance is already used
INSTANCE_USED_RETRIES = 30     # how many retries of INSTANCE_USED_SLEEP_TIME

POST_VM_START_WAIT = 20       # seconds to wait after starting VM (after revert to snapshot)


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
            thread_db = get_db()
            db_scan = thread_db.get(Scan, scan_id)
            if not db_scan:  # check mostly for syntax checker
                logger.error(f"Scan {scan_id} not found")
                return
            db_profile: Profile = db_scan.profile
            vm_id = db_profile.data['vm_id']

            # check/wait for vm availability
            for attempt in range(INSTANCE_USED_RETRIES):
                scans_using_vm = thread_db.query(Scan).filter(
                    Scan.id != scan_id,
                    Scan.status.not_in(["finished", "error"]),
                    Scan.profile_id == db_scan.profile_id
                ).all()
                if scans_using_vm:
                    db_scan_add_log(thread_db, db_scan, f"Scan {scan_id}: Proxmox instance already used by another scan. Will try again ({attempt+1}/{INSTANCE_USED_RETRIES})")
                    # print the other scans using the VM
                    for other_scan in scans_using_vm:
                        logger.info(f"Scan {scan_id}: Proxmox instance used by scan {other_scan.id} (status: {other_scan.status})")

                    time.sleep(INSTANCE_USED_SLEEP_TIME)
                else:
                    break
            else:
                # If we exhausted all retries, set error and return
                db_scan_change_status(scan_id, "error", f"Scan {scan_id}: Proxmox instance still in use after maximum retries.")
                thread_db.close()
                return

            # if vm is not running, wait for it. 
            if not self.proxmox_manager.WaitForVmStatus(vm_id, "running", timeout=10):
                db_scan_change_status(scan_id, "error", f"Scan {scan_id}: Proxmox instance not running after waiting.")
                thread_db.close()
                return

            db_scan = thread_db.get(Scan, scan_id)  # get db entry again (may have waited for it)
            if not db_scan:  # check mostly for syntax checker
                logger.error(f"Scan {scan_id} not found")
                return
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
            thread_db = get_db()
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
            thread_db = get_db()
            db_scan = thread_db.get(Scan, scan_id)
            if not db_scan:  # check mostly for syntax checker
                logger.error(f"Scan {scan_id} not found")
                return
            db_profile: Profile = db_scan.profile
            vm_id = db_profile.data['vm_id']
            vm_snapshot = db_profile.data['vm_snapshot']

            if self.proxmox_manager.RevertVm(vm_id, vm_snapshot):
                # keep it for now
                #db_scan.vm_instance_name = None
                #db_scan.vm_ip_address = None
                db_scan_add_log(thread_db, db_scan, "VM successfully reverted")
            else:
                db_scan_change_status(scan_id, "error")
                thread_db.close()
                return

            if self.proxmox_manager.StartVm(vm_id):
                db_scan_add_log(thread_db, db_scan, "VM successfully started")
            else:
                db_scan_add_log(thread_db, db_scan, "VM failed starting")

            # we give it some time to start up
            # it may be important, when the user immediately tries to start a new scan
            # with ETW/ETW-TI which needs some warmup
            time.sleep(POST_VM_START_WAIT)

            db_scan_change_status(scan_id, "removed")
            thread_db.close()

        threading.Thread(target=remove_thread, args=(scan_id, )).start()


    def kill(self, scan_id: int):
        """Attempt to kill (stop and delete) the VM"""
        def kill_thread(scan_id: int):
            thread_db = get_db()
            db_scan = thread_db.get(Scan, scan_id)
            if not db_scan:  # check mostly for syntax checker
                logger.error(f"Scan {scan_id} not found")
                return
            db_profile: Profile = db_scan.profile
            vm_id = db_profile.data['vm_id']
            vm_snapshot = db_profile.data['vm_snapshot']
            vm_name = db_scan.vm_instance_name

            logger.info(f"Proxmox: Killing VM {vm_name} scan {scan_id}")

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
            else:
                db_scan_add_log(thread_db, db_scan, "VM failed deleting")
            
            # Set it to killed. We tried.
            # (never to error and vm_exist = 1 as it will be killed again)
            db_scan_change_status(scan_id, "killed")

        threading.Thread(target=kill_thread, args=(scan_id, )).start()
