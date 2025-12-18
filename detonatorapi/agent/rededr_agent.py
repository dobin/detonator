from enum import Enum
import requests
from typing import List, Optional, Dict
import json
import logging
import random
from .result import Result

logger = logging.getLogger(__name__)


class RedEdrAgentApi:
    def __init__(self, agent_ip: str, rededr_port: int):
        self.rededr_url = "http://" + agent_ip + ":" + str(rededr_port)


    def StartTrace(self, target_names: List[str]) -> Result[None]:
        url = self.rededr_url + "/api/trace/reset"
        try:
            response = requests.post(url)
            if response.status_code == 404:
                logger.info("Agent: /api/trace/reset not found. Assuming non-RedEdr agent.")
                return Result.ok()
            if response.status_code == 200:
                #print("Response:", response.json())
                pass
            else:
                error_msg = f"Reset error: {response.status_code} {response.text}"
                logger.warning(f"Agent: {error_msg}")
                return Result.error(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"Reset error: {e}"
            logger.warning(f"Agent: {error_msg}")
            return Result.error(error_msg)

        # Configure trace
        url = self.rededr_url + "/api/trace/start"
        headers = {"Content-Type": "application/json"}
        payload = {"trace": target_names}
        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                #print("Response:", response.json())
                return Result.ok()
            else:
                error_msg = f"StartTrace error: {response.status_code} {response.text}"
                logger.warning(f"Agent: {error_msg}")
                return Result.error(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"StartTrace error: {e}"
            logger.warning(f"Agent: {error_msg}")
            return Result.error(error_msg)


    def GetEvents(self) -> Optional[str]:
        url = self.rededr_url + "/api/logs/rededr"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.text
                return data
            else:
                logger.warning(f"Agent HTTP response error: {response.status_code} {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Agent HTTP response error: {e}")
            return None
        

    def IsReachable(self) -> bool:
        # Check if RedEdr API is reachable
        try:
            test_response = requests.get(self.rededr_url, timeout=1.0)
            # Can also be 404, just connect is enough
            #return test_response.status_code == 200
            return True
        except Exception as e:
            #logger.info(f"Agent: RedEdr API not reachable at {self.rededr_url}: {e}")
            return False


    def GetAgentLogs(self) -> Optional[str]:
        url = self.rededr_url + "/api/logs/agent"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.text
                return data
            else:
                logger.warning(f"Agent HTTP response error: {response.status_code} {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Agent HTTP response error: {e}")
            return None
