import time
import requests
import os
import sys

from detonatorapi.utils import filename_randomizer
from .client import DetonatorClient


class DetonatorClientApi(DetonatorClient):
    def __init__(self, baseUrl, token, debug=False):
        self.baseUrl = baseUrl
        self.token = token
        self.debug = debug


    def get_profiles(self):
        try:
            response = requests.get(f"{self.baseUrl}/api/profiles")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching profiles: {e}")
            return {}


    def valid_profile(self, profile_name):
        profiles = self.get_profiles()
        return profile_name in profiles
    

    def scan_file(self, filename, source_url, file_comment, scan_comment, project, profile_name, password, runtime, randomize_filename=True):
        file_info = self._upload_file(
            filename, 
            source_url, 
            file_comment,
            randomize_filename
        )
        if not file_info:
            print("Failed to upload file")
            return
        file_id = file_info['id']
        print(f"File uploaded successfully with ID: {file_id}")
        
        # Create scan
        scan_info = self._create_scan(
            file_id, 
            profile_name, 
            scan_comment, 
            project,
            password,
            runtime
        )
        if not scan_info:
            print("Failed to create scan")
            return
        scan_id = scan_info['id']
        print(f"Scan created successfully with ID: {scan_id}")
        
        # Wait for completion
        final_scan = self._wait_for_scan_completion(scan_id)
        if final_scan:
            if final_scan.get('result'):
                print(f"Result: {final_scan['result']}")
        else:
            print("Scan did not complete successfully")


    def _upload_file(self, filename, source_url="", comment="", randomize_filename=True):
        try:
            if not os.path.exists(filename):
                print(f"Error: File {filename} does not exist")
                return None

            upload_filename = os.path.basename(filename)
            if randomize_filename:
                upload_filename = filename_randomizer(upload_filename)

            with open(filename, "rb") as f:
                files = {"file": (upload_filename, f, "application/octet-stream")}
                data = {
                    "source_url": source_url,
                    "comment": comment
                }
                url = f"{self.baseUrl}/api/files"
                print("Uploading file to URL:", url)
                response = requests.post(url, files=files, data=data)
                response.raise_for_status()
                return response.json()
        except requests.RequestException as e:
            print(f"Error uploading file: {e}")
            return None


    def _create_scan(self, file_id, profile_name, comment="", project="", password="", runtime=10):
        try:
            data = {
                "project": project,
                "profile_name": profile_name,
                "runtime": runtime,
                "comment": comment,
            }
            if password != "":
                data["password"] = password
            
            url = f"{self.baseUrl}/api/files/{file_id}/createscan"
            response = requests.post(url, json=data, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error creating scan: {e}")
            if response and response.text:
                print(f"Response: {response.text}")
            return None


    def _get_scan_status(self, scan_id):
        try:
            response = requests.get(f"{self.baseUrl}/api/scans/{scan_id}")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error getting scan status: {e}")
            return None


    def _wait_for_scan_completion(self, scan_id, timeout=3600):
        #print(f"Waiting for scan {scan_id} to complete...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            scan = self._get_scan_status(scan_id)
            if not scan:
                print("Error: Could not get scan status")
                return None
                
            #print(f"Scan {scan_id} status: {scan['status']}")
            sys.stdout.write(f".")
            sys.stdout.flush()
            
            if scan['status'] in ["finished", "error", "stopping", "removing" ]:
                print("")
                return scan
            elif self.debug:
                print(f"Scan {scan_id} status: {scan['status']}")
                
            time.sleep(1)
        
        print(f"Timeout waiting for scan {scan_id} to complete")
        return None


