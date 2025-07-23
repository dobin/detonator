import requests
from typing import List, Optional, Dict
import json
import logging

logger = logging.getLogger(__name__)


# Note: Copy from https://github.com/dobin/AgentUi/blob/main/rededrapi.py

class AgentApi:
    def __init__(self, agent_ip: str, agent_port: int = 8080):
        self.agent_url = "http://" + agent_ip + ":" + str(agent_port)


    def StartTrace(self, target_name: str) -> bool:
        url = self.agent_url + "/api/lock/aquire"
        try:
            response = requests.post(url)
            if response.status_code != 200:
                logging.warning("Agent: LockAquire failed: {} {}".format(response.status_code, response.text))
                return False
        except requests.exceptions.RequestException as e:
            logging.warning("Agent: LockAquire error: ", e)
            return False

        # Reset any previous trace data
        url = self.agent_url + "/api/reset"
        try:
            response = requests.post(url)
            if response.status_code == 200:
                #print("Response:", response.json())
                pass
            else:
                logging.warning("Agent: Reset error: {} {}".format(response.status_code, response.text))
                return False
        except requests.exceptions.RequestException as e:
            logging.warning("Agent: Reset error: ", e)
            return False

        # Configure trace
        url = self.agent_url + "/api/trace"
        headers = {"Content-Type": "application/json"}
        payload = {"trace": target_name}
        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                #print("Response:", response.json())
                return True
            else:
                logging.warning("Agent: StartTrace error: {} {}".format(response.status_code, response.text))
                return False
        except requests.exceptions.RequestException as e:
            logging.warning("Agent: StartTrace error: ", e)
            return False
        
    
    def StopTrace(self) -> bool:
        # kill running process
        url = self.agent_url + "/api/kill"
        try:
            response = requests.post(url)
            if response.status_code != 200:
                logging.warning("Agent: kill error: {} {}".format(response.status_code, response.text))
                return False
        except requests.exceptions.RequestException as e:
            logging.warning("Agent: kill error: ", e)
            return False
        
        url = self.agent_url + "/api/lock/release"
        try:
            response = requests.post(url)
            if response.status_code != 200:
                # meh we dont care. and should never happen
                logging.warning("Agent: LockRelease failed: {} {}".format(response.status_code, response.text))
        except requests.exceptions.RequestException as e:
            logging.warning("Agent: LockRelease error: ", e)
            return False
        
        return True


    def ExecFile(self, filename: str, file_data: bytes) -> bool:
        url = self.agent_url + "/api/exec"
        files = {
            "file": (filename, file_data),
        }
        data = {
            "path": "C:\\Users\\Public\\Downloads\\",
        }
        # multipart form-data
        try:
            response = requests.post(url, files=files, data=data)
            if response.status_code == 200:
                #print("Response:", response.json())
                return True
            else:
                logging.warning("Agent HTTP response error: {} {}".format(response.status_code, response.text))
                return False
        except requests.exceptions.RequestException as e:
            logging.warning("Agent HTTP response error: ", e)
            return False
        

    def GetRedEdrEvents(self) -> Optional[str]:
        url = self.agent_url + "/api/logs/rededr"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.text
                return data
            else:
                logging.warning("Agent HTTP response error: {} {}".format(response.status_code, response.text))
                return None
        except requests.exceptions.RequestException as e:
            logging.warning("Agent HTTP response error: ", e)
            return None


    def GetAgentLogs(self) -> Optional[str]:
        url = self.agent_url + "/api/logs/agent"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.text
                return data
            else:
                logging.warning("Agent HTTP response error: {} {}".format(response.status_code, response.text))
                return None
        except requests.exceptions.RequestException as e:
            logging.warning("Agent HTTP response error: ", e)
            return None
        

    def GetEdrLogs(self) -> Optional[str]:
        url = self.agent_url + "/api/logs/edr"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.text
                return data
            else:
                logging.warning("Agent HTTP response error: {} {}".format(response.status_code, response.text))
                return None
        except requests.exceptions.RequestException as e:
            logging.warning("Agent HTTP response error: ", e)
            return None


    def GetExecutionLogs(self) -> Optional[str]:
        url = self.agent_url + "/api/logs/execution"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.text
                return data
            else:
                logging.warning("Agent HTTP response error: {} {}".format(response.status_code, response.text))
                return None
        except requests.exceptions.RequestException as e:
            logging.warning("Agent HTTP response error: ", e)
            return None
