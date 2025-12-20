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
        if response.status_code == 200:
            #print("Success! File uploaded and submission created.")
            try:
                json_response = response.json()
                submission_id = json_response.get('submission_id')
                print(f"File ID: {json_response.get('file_id')}, Submission ID: {submission_id}")
            except:
                print("Response is not valid JSON")
                return None
        else:
            print("Error:")
            print(response.text)
            return None

        # Wait for completion
        final_submission = self._wait_for_submission_completion(submission_id)
        print("") # because of the ...
        if not final_submission:
            print("Submission error")
            return None

        # Non finished (error mostly)
        if final_submission.get('status') != 'finished':
            print(f"Submission did not complete successfully: {final_submission.get('status')}")
            print(final_submission.get('detonator_srv_logs'))
            return None

        # check for RedEdr first (no result print)
        profile = self.get_profile(profile_name)
        if profile and profile.get('edr_collector') == 'RedEdr':
            print("RedEdr data available, but not printed.")
        else:
            if final_submission.get('result'):
                print(f"Submission Result: {final_submission['result']}")
            else:
                print("No result available?")

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
        
        while time.time() - start_time < timeout:
            submission = self.get_submission(submission_id)
            if not submission:
                print("Error: Could not get submission status")
                return None
                
            #print(f"Submission {submission_id} status: {submission['status']}")
            sys.stdout.write(f".")
            sys.stdout.flush()
            
            if submission['status'] in ["finished", "error"]:
                #print(f"Submission finished with status: {submission['status']}")
                return submission
            elif self.debug:
                print(f"Submission {submission_id} status: {submission['status']}")
                
            time.sleep(1)
        
        print(f"Timeout waiting for submission {submission_id} to complete")
        return None