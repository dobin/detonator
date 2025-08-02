import logging
import time
import threading
from typing import Dict, List, Optional

from detonatorapi.database import get_db_for_thread, Scan, Profile
from detonatorapi.utils import mylog, scanid_to_vmname
from detonatorapi.db_interface import db_change_status, db_scan_add_log, db_get_profile_by_id

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


    def instantiate(self, db, db_scan: Scan):
        def instantiate_thread(scan_id: int): 
            thread_db = get_db_for_thread()
            db_scan = thread_db.get(Scan, scan_id)

            db_profile: Profile = db_get_profile_by_id(thread_db, db_scan.profile_id)
            vm_id = db_profile.data['vm_id']

            status = self.proxmox_manager.StatusVm(vm_id)
            logger.info(f"Proxmox VM status: {status}")
            if status != "running":
                if not self.proxmox_manager.StartVm(vm_id):
                    db_change_status(thread_db, db_scan, "error", "Could not start VM")
                    thread_db.close()
                    return

            db_scan.vm_exist = 1  # Set to 1 to indicate VM is running
            db_scan.vm_ip_address = db_profile.data['vm_ip']
            db_change_status(thread_db, db_scan, "instantiated")

            thread_db.close()

        threading.Thread(target=instantiate_thread, args=(db_scan.id, )).start()


    def connect(self, db, db_scan: Scan):
        # default agent connect
        super().connect(db, db_scan)


    def scan(self, db, db_scan: Scan, pre_wait: int = 0):
        # default agent scan
        super().scan(db, db_scan)


    def stop(self, db, db_scan: Scan):
        if PROXMOX_NO_RESET:
            db_change_status(db, db_scan, "finished")

        def stop_thread(scan_id: int):
            thread_db = get_db_for_thread()

            db_profile: Profile = db_get_profile_by_id(thread_db, db_scan.profile_id)
            vm_id = db_profile.data['vm_id']

            if self.proxmox_manager.StopVm(vm_id):
                db_change_status(thread_db, db_scan, "stopped")
            else: 
                db_change_status(thread_db, db_scan, "error")
            thread_db.close()

        threading.Thread(target=stop_thread, args=(db_scan.id, )).start()
            

    def remove(self, db, db_scan: Scan):
        if PROXMOX_NO_RESET:
            db_change_status(db, db_scan, "finished")

        def remove_thread(scan_id: int):
            thread_db = get_db_for_thread()

            db_scan = thread_db.get(Scan, scan_id)

            db_profile: Profile = db_get_profile_by_id(thread_db, db_scan.profile_id)
            vm_id = db_profile.data['vm_id']
            vm_snapshot = db_profile.data['vm_snapshot']

            if self.proxmox_manager.RevertVm(vm_id, vm_snapshot):
                db_scan.vm_exist = 0
                # keep it for now
                #db_scan.vm_instance_name = None
                #db_scan.vm_ip_address = None
                db_scan_add_log(thread_db, db_scan, "VM successfully reverted")
            else:
                db_change_status(thread_db, db_scan, "error")
                thread_db.close()
                return

            # TODO cleanup()?
            time.sleep(2) # or we get "Error: VM is locked (rollback)". Damn Proxmox.
            if self.proxmox_manager.StartVm(vm_id):
                db_scan_add_log(thread_db, db_scan, "VM successfully started")
            else:
                db_scan_add_log(thread_db, db_scan, "VM failed starting")

            db_change_status(thread_db, db_scan, "removed")
            thread_db.close()

        threading.Thread(target=remove_thread, args=(db_scan.id, )).start()


    def kill(self, db, db_scan: Scan):
        """Attempt to kill (stop and delete) the VM"""
        def kill_thread(scan_id: int):
            thread_db = get_db_for_thread()
            db_scan = thread_db.get(Scan, scan_id)

            db_profile: Profile = db_get_profile_by_id(thread_db, db_scan.profile_id)
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
            db_change_status(thread_db, db_scan, "killed")

        threading.Thread(target=kill_thread, args=(db_scan.id, )).start()


