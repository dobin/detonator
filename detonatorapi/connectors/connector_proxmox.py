import logging
import time
import threading
from typing import Dict, List, Optional

from detonatorapi.database import get_db_direct, Submission, Profile
from detonatorapi.db_interface import db_submission_change_status_quick, db_submission_add_log, db_get_profile_by_id, db_submission_change_status

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
        return "Will use Proxmox VM and revert it to snapshot after submission"
    

    def get_comment(self) -> str:
        """Return additional comments about this connector"""
        return "Wait time: Instant. Reproducability: High"
    

    def get_sample_data(self) -> Dict:
        """Return sample data for this connector"""
        return {
            "proxmox_snapshot": "latest",
            "proxmox_id": 100,
        }


    def instantiate(self, submission_id: int):
        def instantiate_thread(submission_id: int): 
            thread_db = get_db_direct()
            db_submission = thread_db.get(Submission, submission_id)
            if not db_submission:  # check mostly for syntax checker
                logger.error(f"Submission {submission_id} not found")
                thread_db.close()
                return
            db_profile: Profile = db_submission.profile
            proxmox_id = db_profile.data['proxmox_id']

            # check/wait for vm availability
            for attempt in range(INSTANCE_USED_RETRIES):
                submissions_using_vm = thread_db.query(Submission).filter(
                    Submission.id != submission_id,
                    Submission.status.not_in(["finished", "error"]),
                    Submission.profile_id == db_submission.profile_id
                ).all()
                if submissions_using_vm:
                    db_submission_add_log(thread_db, db_submission, f"Submission {submission_id}: Proxmox instance already used by another submission. Will try again ({attempt+1}/{INSTANCE_USED_RETRIES})")
                    # print the other submissions using the VM
                    for other_submission in submissions_using_vm:
                        logger.info(f"Submission {submission_id}: Proxmox instance used by submission {other_submission.id} (status: {other_submission.status})")

                    time.sleep(INSTANCE_USED_SLEEP_TIME)
                else:
                    break
            else:
                # If we exhausted all retries, set error and return
                db_submission_change_status(submission_id, "error", f"Submission {submission_id}: Proxmox instance still in use after maximum retries.")
                thread_db.close()
                return

            # if vm is not running, wait for it. 
            if not self.proxmox_manager.WaitForVmStatus(proxmox_id, "running", timeout=10):
                db_submission_change_status(submission_id, "error", f"Submission {submission_id}: Proxmox instance not running after waiting.")
                thread_db.close()
                return

            db_submission = thread_db.get(Submission, submission_id)  # get db entry again (may have waited for it)
            if not db_submission:  # check mostly for syntax checker
                logger.error(f"Submission {submission_id} not found")
                thread_db.close()
                return
            db_submission.vm_ip_address = db_profile.vm_ip
            db_submission_change_status_quick(thread_db, db_submission, "instantiated")
            thread_db.close()

        threading.Thread(target=instantiate_thread, args=(submission_id, )).start()


    def connect(self, submission_id: int):
        # default agent connect
        super().connect(submission_id)


    def process(self, submission_id: int, pre_wait: int = 0):
        # default agent submission
        super().process(submission_id, pre_wait)


    def stop(self, submission_id: int):
        if PROXMOX_NO_RESET:
            db_submission_change_status(submission_id, "finished")
            return

        def stop_thread(submission_id: int):
            thread_db = get_db_direct()
            db_submission: Submission = thread_db.get(Submission, submission_id)
            if not db_submission:  # check mostly for syntax checker
                logger.error(f"Submission {submission_id} not found")
                thread_db.close()
                return
            db_profile: Profile = db_submission.profile
            proxmox_id = db_profile.data['proxmox_id']

            if self.proxmox_manager.StopVm(proxmox_id):
                db_submission_change_status(submission_id, "stopped")
            else: 
                db_submission_change_status(submission_id, "error")
            thread_db.close()

        threading.Thread(target=stop_thread, args=(submission_id, )).start()
            

    def remove(self, submission_id: int):
        if PROXMOX_NO_RESET:
            db_submission_change_status(submission_id, "finished")
            return

        def remove_thread(submission_id: int):
            thread_db = get_db_direct()
            db_submission = thread_db.get(Submission, submission_id)
            if not db_submission:  # check mostly for syntax checker
                logger.error(f"Submission {submission_id} not found")
                thread_db.close()
                return
            db_profile: Profile = db_submission.profile
            proxmox_id = db_profile.data['proxmox_id']
            proxmox_snapshot = db_profile.data['proxmox_snapshot']

            if self.proxmox_manager.RevertVm(proxmox_id, proxmox_snapshot):
                # keep it for now
                #db_submission.vm_instance_name = None
                #db_submission.vm_ip_address = None
                db_submission_add_log(thread_db, db_submission, "VM successfully reverted")
            else:
                db_submission_change_status(submission_id, "error")
                thread_db.close()
                return

            if self.proxmox_manager.StartVm(proxmox_id):
                db_submission_add_log(thread_db, db_submission, "VM successfully started")
            else:
                db_submission_add_log(thread_db, db_submission, "VM failed starting")

            # we give it some time to start up
            # it may be important, when the user immediately tries to start a new submission
            # with ETW/ETW-TI which needs some warmup
            time.sleep(POST_VM_START_WAIT)

            db_submission_change_status(submission_id, "removed")
            thread_db.close()

        threading.Thread(target=remove_thread, args=(submission_id, )).start()


    def kill(self, submission_id: int):
        """Attempt to kill (stop and delete) the VM"""
        def kill_thread(submission_id: int):
            thread_db = get_db_direct()
            db_submission = thread_db.get(Submission, submission_id)
            if not db_submission:  # check mostly for syntax checker
                logger.error(f"Submission {submission_id} not found")
                thread_db.close()
                return
            db_profile: Profile = db_submission.profile
            proxmox_id = db_profile.data['proxmox_id']
            proxmox_snapshot = db_profile.data['proxmox_snapshot']
            vm_name = db_submission.vm_instance_name

            logger.info(f"Proxmox: Killing VM {vm_name} submission {submission_id}")

            # Stop if running
            powerState = self.proxmox_manager.StatusVm(proxmox_id)
            if powerState == "running":
                if self.proxmox_manager.StopVm(proxmox_id):
                    db_submission_add_log(thread_db, db_submission, "VM successfully stopped")
                else:
                    db_submission_add_log(thread_db, db_submission, "VM failed stopping")

            # Always try to revert
            if self.proxmox_manager.RevertVm(proxmox_id, proxmox_snapshot):
                db_submission_add_log(thread_db, db_submission, "VM successfully killed")
            else:
                db_submission_add_log(thread_db, db_submission, "VM failed deleting")
            
            # Set it to killed. We tried.
            # (never to error and vm_exist = 1 as it will be killed again)
            db_submission_change_status(submission_id, "killed")
            thread_db.close()

        threading.Thread(target=kill_thread, args=(submission_id, )).start()
