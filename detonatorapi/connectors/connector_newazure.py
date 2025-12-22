import logging
import time
import threading
from typing import Dict, List, Optional

from detonatorapi.database import get_db_direct, Submission
from detonatorapi.db_interface import db_submission_change_status_quick, db_submission_add_log, db_submission_change_status
from detonatorapi.connectors.azure_manager import initialize_azure_manager, submissionid_to_vmname

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


    def instantiate(self, submission_id: int):
        def instantiate_thread(submission_id: int): 
            azure_manager = get_azure_manager()
            if not azure_manager:
                db_submission_change_status(submission_id, "error", "Azure not configured")
                return
            if azure_manager.create_machine(submission_id):
                db_submission_change_status(submission_id, "instantiated")
            else:
                db_submission_change_status(submission_id, "error", "Could not create VM")
        threading.Thread(target=instantiate_thread, args=(submission_id, )).start()


    def connect(self, submission_id: int):
        # default agent connect
        super().connect(submission_id)


    def process(self, submission_id: int, pre_wait: int = 0):
        # default agent submission
        super().process(submission_id, pre_wait=120)  # 2min


    def stop(self, submission_id: int):
        def stop_thread(submission_id: int):
            azure_manager = get_azure_manager()
            if not azure_manager:
                db_submission_change_status(submission_id, "error", "Azure not configured")
                return
            vm_name = submissionid_to_vmname(submission_id)
            if azure_manager.shutdown_vm(vm_name):
                db_submission_change_status(submission_id, "stopped")
            else: 
                db_submission_change_status(submission_id, "error", "Failed to stop VM")
        threading.Thread(target=stop_thread, args=(submission_id, )).start()
            

    def remove(self, submission_id: int):
        def remove_thread(submission_id: int):
            thread_db = get_db_direct()
            db_submission = thread_db.get(Submission, submission_id)
            if not db_submission:  # check mostly for syntax checker
                logger.error(f"Submission {submission_id} not found")
                thread_db.close()
                return
            azure_manager = get_azure_manager()
            if not azure_manager:
                db_submission_change_status_quick(thread_db, db_submission, "error", "Azure not configured")
                thread_db.close()
                return
            vm_name = submissionid_to_vmname(submission_id)
            if azure_manager.delete_vm_resources(vm_name):
                db_submission.vm_exist = 0
                # keep it for now
                #db_submission.vm_instance_name = None
                #db_submission.vm_ip_address = None
                db_submission_add_log(thread_db, db_submission, "VM successfully removed")
                db_submission_change_status_quick(thread_db, db_submission, "removed")
            else:
                db_submission_change_status_quick(thread_db, db_submission, "error", "Failed to remove VM")
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
            vm_name = db_submission.vm_instance_name
            azure_manager = get_azure_manager()
            if not azure_manager:
                db_submission_change_status_quick(thread_db, db_submission, "error", "Azure not configured")
                thread_db.close()
                return
            logger.info(f"Killing VM {vm_name} submission {submission_id}")

            # Stop if running
            powerState = azure_manager.get_vm_status(db_submission.vm_instance_name)
            if powerState == "running":
                if azure_manager.shutdown_vm(vm_name):
                    db_submission_add_log(thread_db, db_submission, "VM successfully stopped")
                else:
                    db_submission_add_log(thread_db, db_submission, "VM failed stopping")

            # Always try to remove
            if azure_manager.delete_vm_resources(vm_name):
                db_submission_add_log(thread_db, db_submission, "VM successfully killed")
                db_submission.vm_exist = 0  # Set to 0 to indicate VM is removed
            else:
                db_submission_add_log(thread_db, db_submission, "VM failed deleting")
            
            # Set it to killed. We tried.
            # (never to error and vm_exist = 1 as it will be killed again)
            db_submission_change_status_quick(thread_db, db_submission, "killed")
            thread_db.close()

        threading.Thread(target=kill_thread, args=(submission_id, )).start()
