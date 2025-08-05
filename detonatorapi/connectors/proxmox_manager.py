import socket
import time
import requests
import sys
import os
import yaml
import logging
from typing import Dict, Any, Optional

from proxmoxer import ProxmoxAPI, ResourceException


logger = logging.getLogger(__name__)

CONFIG_FILE = 'proxmox.yaml'


def read_yaml_config(file_path) -> Dict[str, Any]:
    """Read YAML configuration file and return as dictionary"""
    try:
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        logger.error(f"Error reading YAML config {file_path}: {str(e)}")
        return {}


class ProxmoxManager:
    def __init__(self):
        self.proxmox_ip = None
        self.proxmox_node_name = None
        self.user = None
        self.password = None
        self.prox: ProxmoxAPI = None


    def Init(self) -> bool:
        config_filepath = os.path.join(os.path.dirname(__file__), CONFIG_FILE)

        # check first if config exists - aint bad if not
        if not os.path.exists(config_filepath):
            logger.warning(f"Proxmox configuration file {CONFIG_FILE} not found. Proxmox not activated.")
            return True

        # read config
        config = read_yaml_config(config_filepath)
        required_keys = ['ip', 'name' ]
        if not all(key in config for key in required_keys):
            logger.error(f"Proxmox configuration file {CONFIG_FILE} is missing required keys: {required_keys}")
            return False
        self.proxmox_ip = config['ip']
        self.proxmox_node_name = config['name']

        if 'token_id' in config and 'token_value' in config:
            logger.info(f"Using Proxmox token authentication with token_id: {config['token_id']}")
            self.prox = ProxmoxAPI(
                self.proxmox_ip, 
                token_name=config['token_id'],
                token_value=config['token_value'],
                verify_ssl=False)            
        elif 'user' in config and 'password' in config:
            self.prox = ProxmoxAPI(
                self.proxmox_ip, 
                user=config['user'], 
                password=config['password'],
                verify_ssl=False)
        else:
            logger.error(f"Proxmox configuration file {CONFIG_FILE} must contain either 'token_id' and 'token_value' or 'user' and 'password'")
            return False
        
        return True


    def WaitForVmStatus(self, vm_id, status, timeout=10):
        n = 0
        while self.StatusVm(vm_id) != status:
            if n == timeout:
                print("Proxmox WaitForVmStatus: Wait Failed")
                return False
            
            logger.info(f"Waiting for VM {vm_id} to reach status '{status}'... (current: {self.StatusVm(vm_id)})")
            time.sleep(3)
            n += 1
        return True
    

    def StatusVm(self, vm_id) -> str:
        try:
            vmStatus = self.prox.nodes(self.proxmox_node_name).qemu(vm_id).status.current.get()
        except ResourceException as e:
            logger.error(f"Proxmox StatusVm: Error getting status for VM {vm_id}: {e}")
            return "doesnotexist"
        return vmStatus["status"]
    

    def StatusVmLock(self, vm_id) -> str:
        try:
            vmStatus = self.prox.nodes(self.proxmox_node_name).qemu(vm_id).status.current.get()
        except ResourceException as e:
            logger.error(f"Proxmox StatusVmLock: Error getting lock status for VM {vm_id}: {e}")
            return "doesnotexist"
        return vmStatus.get("lock", "unlocked")
    

    def WaitForVmUnlock(self, vm_id, timeout=10):
        n = 0
        while True:
            status = self.StatusVmLock(vm_id)
            if status == "unlocked":
                return True
            if n == timeout:
                logger.error(f"Proxmox WaitForVmUnlock: Wait Failed for VM {vm_id}")
                return False
            
            logger.info(f"Waiting for VM {vm_id} to unlock... (current: {status})")
            time.sleep(3)
            n += 1
    

    def StartVm(self, vm_id) -> bool:
        task = self.prox.nodes(self.proxmox_node_name).qemu(vm_id).status.start.post()
        if not self._waitForTask(task):
            return False
        return self.WaitForVmStatus(vm_id, "running", timeout=10)


    def StopVm(self, vm_id) -> bool:
        task = self.prox.nodes(self.proxmox_node_name).qemu(vm_id).status.stop.post()
        if not self._waitForTask(task):
            return False
        return self.WaitForVmStatus(vm_id, "stopped", timeout=10)


    def RevertVm(self, vm_id, vm_snapshot) -> bool:
        task = self.prox.nodes(self.proxmox_node_name).qemu(vm_id).snapshot(vm_snapshot).rollback.post()
        if not self._waitForTask(task):
            return False
        #return self.WaitForVmStatus(vm_id, "stopped", timeout=10)
        return self.WaitForVmUnlock(vm_id)


    def SnapshotExists(self, vm_id, snapshot_name) -> bool:
        try:
            snapshots = self.prox.nodes(self.proxmox_node_name).qemu(vm_id).snapshot.get()
            if not snapshots:
                return False
            snapshot_exists = any(snapshot['name'] == snapshot_name for snapshot in snapshots)
            return snapshot_exists
        except Exception as e:
            logger.error(f"Error checking snapshot existence: {e}")
            return False


    def PrintStatus(self, vm_id):
        print("Status: " + self.StatusVm(vm_id))


    def _waitForTask(self, rollback_task, max_tries=30):
        if not rollback_task:
            return True
        if 'taskid' not in rollback_task:
            return True
        
        task_id = rollback_task['taskid']
        tries = 0
        while True:
            if tries == max_tries:
                logger.error(f"Task {task_id} failed to complete within timeout")
                return False
            
            try:
                task_status = self.prox.nodes(self.proxmox_node_name).tasks(task_id).status.get()
                
                if task_status and task_status['status'] == 'stopped':
                    if task_status['exitstatus'] == 'OK':
                        return True
                    else:
                        logger.error(f"Task {task_id} failed with status: {task_status.get('exitstatus', 'unknown')}")
                        return False
            except Exception as e:
                logger.error(f"Error checking task status: {e}")
                return False
                
            tries += 1
            time.sleep(2)

