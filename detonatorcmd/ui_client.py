import time
import requests
import os
import sys

from detonatorapi.utils import filename_randomizer
from .client import DetonatorClient


class DetonatorClientUi(DetonatorClient):
    def __init__(self, baseUrl, token, debug=False):
        self.baseUrl = baseUrl
        self.token = token
        self.debug = debug


    def get_profiles(self):
        try:
            response = requests.get(f"{self.baseUrl}/api/profiles", headers={"Authorization": f"Bearer {self.token}"})
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching profiles: {e}")
            return {}


    def valid_profile(self, profile_name):
        profiles = self.get_profiles()
        return profile_name in profiles
    

    def scan_file(self, filename, source_url, file_comment, scan_comment, project, profile_name, password, runtime, randomize_filename=True):
        if not os.path.exists(filename):
            print(f"Error: File {filename} does not exist")
            return None

        upload_filename = os.path.basename(filename)
        if randomize_filename:
            upload_filename = filename_randomizer(upload_filename)

        # Prepare the files dict
        with open(filename, 'rb') as f:
            files = {
                'file': (upload_filename, f, 'text/plain')
            }
            data = {
                'source_url': source_url,
                'file_comment': file_comment,
                'scan_comment': scan_comment,
                'project': project,
                'profile_name': profile_name,
                'password': password,
                'runtime': runtime,
            }
            response = requests.post(
                f"{self.baseUrl}/api/upload-and-scan",
                files=files,
                data=data,
            )
            
            scan_id = None
            if response.status_code == 200:
                #print("Success! File uploaded and scan created.")
                try:
                    json_response = response.json()
                    scan_id = json_response.get('scan_id')
                    print(f"File ID: {json_response.get('file_id')}, Scan ID: {scan_id}")
                except:
                    print("Response is not valid JSON")
                    return None
            else:
                print("Error:")
                print(response.text)
                return None

            # Wait for completion
            final_scan = self._wait_for_scan_completion(scan_id)
            if final_scan:
                if final_scan.get('result'):
                    print(f"Result: {final_scan['result']}")
            else:
                print("Scan did not complete successfully")
                    

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