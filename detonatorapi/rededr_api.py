import requests
import json
import logging

logger = logging.getLogger(__name__)


# Note: Copy from https://github.com/dobin/RedEdrUi/blob/main/rededrapi.py

class RedEdrApi:
    def __init__(self, rededr_ip: str):
        self.rededr_url = "http://" + rededr_ip + ":8080"


    def StartTrace(self, target_name: str) -> bool:
        url = self.rededr_url + "/api/trace"
        headers = {"Content-Type": "application/json"}
        payload = {"trace": target_name}

        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                #print("Response:", response.json())
                return True
            else:
                logging.warning("RedEdr HTTP response error: ", response.status_code, response.json())
                return False
        except requests.exceptions.RequestException as e:
            logging.warning("RedEdr HTTP response error: ", e)
            return False
        
    
    def StopTrace(self) -> bool:
        return True


    def ExecFile(self, filename: str, file_data: bytes) -> bool:
        url = self.rededr_url + "/api/exec"
        files = {
            "file": (filename, file_data)
        }
        # multipart form-data
        try:
            response = requests.post(url, files=files)
            if response.status_code == 200:
                #print("Response:", response.json())
                return True
            else:
                logging.warning("RedEdr HTTP response error: ", response.status_code, response.text)
                return False
        except requests.exceptions.RequestException as e:
            logging.warning("RedEdr HTTP response error: ", e)
            return False
        

    def GetJsonResult(self):
        url = self.rededr_url + "/api/events"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.text
                return data
            else:
                logging.warning("RedEdr HTTP response error: ", response.status_code, response.text)
                return None
        except requests.exceptions.RequestException as e:
            logging.warning("RedEdr HTTP response error: ", e)
            return None


    def GetLog(self):
        url = self.rededr_url + "/api/log"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.text
                return data
            else:
                logging.warning("RedEdr HTTP response error: ", response.status_code, response.text)
                return None
        except requests.exceptions.RequestException as e:
            logging.warning("RedEdr HTTP response error: ", e)
            return None
        

    def GetEdrLogs(self):
        url = self.rededr_url + "/api/edr_result"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.text
                return data
            else:
                logging.warning("RedEdr HTTP response error: ", response.status_code, response.text)
                return None
        except requests.exceptions.RequestException as e:
            logging.warning("RedEdr HTTP response error: ", e)
            return None
