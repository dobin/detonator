import time
import requests
import os
import sys
from typing import Optional


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
    

    def submit_file(self, 
                  filename, 
                  source_url, 
                  file_comment, 
                  submission_comment, 
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
            'submission_comment': submission_comment,
            'project': project,
            'profile_name': profile_name,
            'password': password,
            'runtime': runtime,
            'drop_path': drop_path,
            'exec_arguments': exec_arguments,
        }
        response = requests.post(
            f"{self.baseUrl}/api/create-submission",
            files=files,
            data=data,
        )
        
        submission_id = None
        if response.status_code != 200:
            print(f"Error: Received status code {response.status_code} from server")
            print(response.text)
            return None
        try:
            json_response = response.json()
            submission_id = json_response.get('submission_id')
            status = json_response.get('status')
            print(f"File ID: {json_response.get('file_id')}, Submission ID: {submission_id}")
        except:
            print("Response is not valid JSON")
            return None
        if status == "error":
            print(f"Error during submission: {json_response.get('message')}")
            return None

        # Wait for completion (alerts are printed during polling)
        print("Polling for alerts until submission is complete...")
        final_submission = self._wait_for_submission_completion(submission_id)
        print("") # because of the ...
        if not final_submission:
            print("Submission error")
            return None
        if final_submission.get('edr_verdict'):
            print(f"Submission Result: {final_submission['edr_verdict']}")
        else:
            print("No edr_verdict available?")

        return submission_id
                    

    def get_submission(self, submission_id):
        """Get a specific submission by ID"""
        try:
            response = requests.get(f"{self.baseUrl}/api/submissions/{submission_id}")
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error getting submission: {e}")
            return None


    def _wait_for_submission_completion(self, submission_id, timeout=3600) -> Optional[dict]:
        #print(f"Waiting for submission {submission_id} to complete...")i
        start_time = time.time()
        seen_alerts = set()  # Track alerts we've already printed
        
        while time.time() - start_time < timeout:
            submission = self.get_submission(submission_id)
            if not submission:
                print("Error: Could not get submission status")
                return None
            
            # Check for new alerts
            if submission.get('alerts'):
                for alert in submission['alerts']:
                    # Create a unique identifier for each alert
                    alert_key = (alert.get('title'), alert.get('severity'), alert.get('source'))
                    if alert_key not in seen_alerts:
                        print(f"\n[ALERT] [{alert['severity']}] {alert['title']} (Source: {alert['source']})")
                        seen_alerts.add(alert_key)
                        sys.stdout.flush()
                
            #print(f"Submission {submission_id} status: {submission['status']}")
            #sys.stdout.write(f".")
            #sys.stdout.flush()
            
            if submission['status'] in ["finished", "error"]:
                #print(f"Submission finished with status: {submission['status']}")
                return submission
            elif self.debug:
                print(f"Submission {submission_id} status: {submission['status']}")
                
            time.sleep(1)
        
        print(f"Timeout waiting for submission {submission_id} to complete")
        return None