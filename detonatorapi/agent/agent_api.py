from enum import Enum
import requests
from typing import List, Optional, Dict
import json
import logging
from .result import Result

logger = logging.getLogger(__name__)


class ExecutionResult(Enum):
    OK = 0,
    ERROR = 1,
    VIRUS = 2


# Note: Copy from https://github.com/dobin/AgentUi/blob/main/rededrapi.py

class AgentApi:
    def __init__(self, agent_ip: str, agent_port: int = 8080):
        self.agent_url = "http://" + agent_ip + ":" + str(agent_port)


    def IsInUse(self) -> bool:
        # Check if Agent is locked
        url = self.agent_url + "/api/lock/status"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if "in_use" not in data:
                    logging.warning("Agent: CheckLock response missing 'in_use' key")
                    return False

                is_in_use = data["in_use"]
                return is_in_use
            else:
                logging.warning("Agent: CheckLock error: {} {}".format(response.status_code, response.text))
                return False
        except requests.exceptions.RequestException as e:
            logging.warning(f"Agent: CheckLock error: {e}")
            return False


    def IsReachable(self) -> bool:
        # Check if Agent is reachable
        try:
            test_response = requests.get(self.agent_url, timeout=0.5)
            # Can also be 404, just connect is enough
            #return test_response.status_code == 200
            return True
        except Exception as e:
            #logger.info(f"Agent: Agent not reachable at {self.agent_url}: {e}")
            return False
        

    def AcquireLock(self) -> Result[None]:
        # Acquire lock
        url = self.agent_url + "/api/lock/acquire"
        try:
            response = requests.post(url)
            if response.status_code != 200:
                error_msg = f"LockAcquire failed: {response.status_code} {response.text}"
                logging.warning(f"Agent: {error_msg}")
                return Result.error(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"LockAcquire error: {e}"
            logging.warning(f"Agent: {error_msg}")
            return Result.error(error_msg)
        return Result.ok()
    

    def ReleaseLock(self) -> Result[None]:
        # Release lock
        url = self.agent_url + "/api/lock/release"
        try:
            response = requests.post(url)
            if response.status_code != 200:
                error_msg = f"LockRelease failed: {response.status_code} {response.text}"
                logging.warning(f"Agent: {error_msg}")
                return Result.error(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"LockRelease error: {e}"
            logging.warning(f"Agent: {error_msg}")
            return Result.error(error_msg)
        return Result.ok()
    

    def RedEdrStartTrace(self, target_names: List[str]) -> Result[None]:
        # Reset any previous trace data
        url = self.agent_url + "/api/trace/reset"
        try:
            response = requests.post(url)
            if response.status_code == 404:
                logging.info("Agent: /api/trace/reset not found. Assuming non-RedEdr agent.")
                return Result.ok()
            if response.status_code == 200:
                #print("Response:", response.json())
                pass
            else:
                error_msg = f"Reset error: {response.status_code} {response.text}"
                logging.warning(f"Agent: {error_msg}")
                return Result.error(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"Reset error: {e}"
            logging.warning(f"Agent: {error_msg}")
            return Result.error(error_msg)

        # Configure trace
        url = self.agent_url + "/api/trace/start"
        headers = {"Content-Type": "application/json"}
        payload = {"trace": target_names}
        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                #print("Response:", response.json())
                return Result.ok()
            else:
                error_msg = f"StartTrace error: {response.status_code} {response.text}"
                logging.warning(f"Agent: {error_msg}")
                return Result.error(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"StartTrace error: {e}"
            logging.warning(f"Agent: {error_msg}")
            return Result.error(error_msg)
        
    
    def KillProcess(self) -> Result[None]:
        # kill running process
        url = self.agent_url + "/api/execute/kill"
        try:
            response = requests.post(url)
            if response.status_code != 200:
                error_msg = f"kill error: {response.status_code} {response.text}"
                logging.warning(f"Agent: {error_msg}")
                return Result.error(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"kill error: {e}"
            logging.warning(f"Agent: {error_msg}")
            return Result.error(error_msg)
        
        return Result.ok()


    def ExecFile(self, filename: str, file_data: bytes, drop_path: str, exec_arguments: str) -> ExecutionResult:
        url = self.agent_url + "/api/execute/exec"
        
        # Choose a random XOR key between 0 and 255
        import random
        xor_key = random.randint(0, 255)
        
        # XOR encrypt the file data
        encrypted_data = bytes([b ^ xor_key for b in file_data])
        
        files = {
            "file": (filename, encrypted_data),
        }
        # add trailing slash just to make sure
        if not drop_path.endswith("\\"):
            drop_path += "\\"
        data = {
            "drop_path": drop_path,
            "executable_args": exec_arguments,
            "use_additional_etw": "false",
            "xor_key": str(xor_key),
        }
        # multipart form-data
        try:
            response = requests.post(url, files=files, data=data)
            if response.status_code == 200:
                j = response.json()
                if j.get("status", "") == "virus" :
                    logging.info(f"Agent: File {filename} is detected as malware")
                    return ExecutionResult.VIRUS
                #print("Response:", response.json())
                return ExecutionResult.OK
            else:
                logging.warning(f"Agent HTTP response error: {response.status_code} {response.text}")
                return ExecutionResult.ERROR
        except requests.exceptions.RequestException as e:
            logging.warning(f"Agent HTTP response error: {e}")
            return ExecutionResult.ERROR
        
    
    def GetLockStatus(self) -> bool:
        url = self.agent_url + "/api/lock/status"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if data.get("in_use") == "true":
                    return True
                else:
                    return False
            else:
                logging.warning(f"Agent: CheckLock error: {response.status_code} {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logging.warning(f"Agent: CheckLock error: {e}")
            return False
        

    def RedEdrGetEvents(self) -> Optional[str]:
        url = self.agent_url + "/api/logs/rededr"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.text
                return data
            else:
                logging.warning(f"Agent HTTP response error: {response.status_code} {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logging.warning(f"Agent HTTP response error: {e}")
            return None


    def GetAgentLogs(self) -> Optional[str]:
        url = self.agent_url + "/api/logs/agent"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.text
                return data
            else:
                logging.warning(f"Agent HTTP response error: {response.status_code} {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logging.warning(f"Agent HTTP response error: {e}")
            return None
        

    def GetEdrLogs(self) -> Optional[str]:
        url = self.agent_url + "/api/logs/edr"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.text
                return data
            else:
                logging.warning(f"Agent HTTP response error: {response.status_code} {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logging.warning(f"Agent HTTP response error: {e}")
            return None


    def GetExecutionLogs(self) -> Optional[str]:
        url = self.agent_url + "/api/logs/execution"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.text
                return data
            else:
                logging.warning(f"Agent HTTP response error: {response.status_code} {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logging.warning(f"Agent HTTP response error: {e}")
            return None
