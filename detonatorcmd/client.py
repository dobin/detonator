import time
import requests
import os
import sys
from typing import Optional

from detonatorapi.utils import filename_randomizer


class DetonatorClient:
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
        

    def get_profile(self, profile_name):
        profiles = self.get_profiles()
        return profiles.get(profile_name)


    def valid_profile(self, profile_name):
        profiles = self.get_profiles()
        return profile_name in profiles
    

    def scan_file(self, 
                  filename, 
                  source_url, 
                  file_comment, 
                  scan_comment, 
                  project, 
                  profile_name, 
                  password, 
                  runtime, 
                  drop_path="", 
                  exec_arguments="", 
                  randomize_filename=True
    ) -> Optional[str]:
        if not os.path.exists(filename):
            print(f"Error: File {filename} does not exist")
            return None

        upload_filename = os.path.basename(filename)
        if randomize_filename:
            upload_filename = filename_randomizer(upload_filename)

        # Read the file
        with open(filename, 'rb') as f:
            file_content = f.read()

        # Prepare the files dict
        files = {
            'file': (upload_filename, file_content, 'text/plain')
        }
        data = {
            'token': self.token,
            'source_url': source_url,
            'file_comment': file_comment,
            'scan_comment': scan_comment,
            'project': project,
            'profile_name': profile_name,
            'password': password,
            'runtime': runtime,
            'drop_path': drop_path,
            'exec_arguments': exec_arguments,
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
        print("") # because of the ...
        if not final_scan:
            print("Scan error")
            return None

        # Non finished (error mostly)
        if final_scan.get('status') != 'finished':
            print(f"Scan did not complete successfully: {final_scan.get('status')}")
            print(final_scan.get('detonator_srv_logs'))
            return None

        # check for RedEdr first (no result print)
        profile = self.get_profile(profile_name)
        if profile and profile.get('edr_collector') == 'RedEdr':
            print("RedEdr data available, but not printed.")
        else:
            if final_scan.get('result'):
                print(f"Scan Result: {final_scan['result']}")
            else:
                print("No result available?")

        return scan_id
                    

    def get_scan(self, scan_id):
        """Get a specific scan by ID"""
        try:
            response = requests.get(f"{self.baseUrl}/api/scans/{scan_id}")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error getting scan: {e}")
            return None


    def _wait_for_scan_completion(self, scan_id, timeout=3600) -> Optional[dict]:
        #print(f"Waiting for scan {scan_id} to complete...")i
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            scan = self.get_scan(scan_id)
            if not scan:
                print("Error: Could not get scan status")
                return None
                
            #print(f"Scan {scan_id} status: {scan['status']}")
            sys.stdout.write(f".")
            sys.stdout.flush()
            
            if scan['status'] in ["finished", "error", "stopping", "removing" ]:
                #print(f"Scan finished with status: {scan['status']}")
                return scan
            elif self.debug:
                print(f"Scan {scan_id} status: {scan['status']}")
                
            time.sleep(1)
        
        print(f"Timeout waiting for scan {scan_id} to complete")
        return None