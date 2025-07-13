import os
import sys
import time
import requests
import argparse


# Default API base URL
API_BASE_URL = "http://localhost:8000"
DEBUG = False

def get_profiles():
    try:
        response = requests.get(f"{API_BASE_URL}/api/profiles")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching profiles: {e}")
        return {}


def upload_file(filename, source_url="", comment=""):
    try:
        with open(filename, "rb") as f:
            files = {"file": (os.path.basename(filename), f, "application/octet-stream")}
            data = {
                "source_url": source_url,
                "comment": comment
            }
            response = requests.post(f"{API_BASE_URL}/api/files", files=files, data=data)
            response.raise_for_status()
            return response.json()
    except requests.RequestException as e:
        print(f"Error uploading file: {e}")
        return None


def create_scan(file_id, profile_name, comment="", project=""):
    try:
        data = {
            "project": project,
            "profile_name": profile_name,
            "comment": comment,
            
        }
        response = requests.post(f"{API_BASE_URL}/api/files/{file_id}/createscan", json=data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error creating scan: {e}")
        return None


def get_scan_status(scan_id):
    try:
        response = requests.get(f"{API_BASE_URL}/api/scans/{scan_id}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error getting scan status: {e}")
        return None


def wait_for_scan_completion(scan_id, timeout=3600):
    #print(f"Waiting for scan {scan_id} to complete...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        scan = get_scan_status(scan_id)
        if not scan:
            print("Error: Could not get scan status")
            return None
            
        #print(f"Scan {scan_id} status: {scan['status']}")
        sys.stdout.write(f".")
        sys.stdout.flush()
        
        if scan['status'] in ["finished", "error" ]:
            print("")
            return scan
        elif DEBUG:
            print(f"Scan {scan_id} status: {scan['status']}")
            
        time.sleep(1)
    
    print(f"Timeout waiting for scan {scan_id} to complete")
    return None


def print_profiles():
    profiles = get_profiles()
    if profiles:
        #print("Available profiles:")
        for profile_name, profile in profiles.items():
            print(f"Profile: {profile_name}")
            print(f"    Connector: {profile.get('connector', '')}")
            print(f"    EDR Collector: {profile.get('edr_collector', '')}")
            print(f"    Port: {profile.get('port', '')}")
            if profile.get('comment'):
                print(f"    Comment: {profile.get('comment', '')}")
            if profile.get('data', {}).get('image_reference'):
                image_reference_name = profile.get('data', {}).get('image_reference', '').split("/")[-1]  # Last part
                print(f"    Image Reference: {image_reference_name}")
            if profile.get('data', {}).get('ip'):
                print(f"    IP: {profile.get('data', {}).get('ip')}")
    else:
        print("No profiles available or error fetching profiles")


def main():
    parser = argparse.ArgumentParser(description="Detonator Command Line Client")
    parser.add_argument("command", choices=["scan", "list-profiles"], help="Command to execute")
    parser.add_argument("filename", nargs="?", help="File to scan")
    parser.add_argument("--profile", "-p", default="running_defender", help="Profile to use")
    parser.add_argument("--comment", "-c", default="", help="Comment for the scan")
    parser.add_argument("--project", "-j", default="", help="Project name for the scan")
    parser.add_argument("--source-url", "-s", default="", help="Source URL of the file")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--timeout", type=int, default=3600, help="Timeout in seconds for scan completion")
    
    args = parser.parse_args()
    
    global API_BASE_URL
    API_BASE_URL = args.api_url
    
    if args.command == "list-profiles":
        print_profiles()
        return
    
    elif args.command == "scan":
        if not args.filename:
            print("Error: filename is required for scan command")
            parser.print_help()
            return
            
        filename = args.filename
        profile_name = args.profile
        
        # Check if file exists
        if not os.path.exists(filename):
            print(f"Error: File {filename} does not exist")
            return
        
        # Get available profiles to validate
        profiles = get_profiles()
        profile_names = list(profiles.keys()) if profiles else []
        if profile_name not in profile_names:
            print(f"Error: Profile '{profile_name}' not found")
            print("Available profiles:")
            print_profiles()
            return
        
        #print(f"> Scanning file {filename} with profile {profile_name}")
        
        # Upload file
        file_info = upload_file(filename, args.source_url, f"CLI {args.comment}")
        if not file_info:
            print("Failed to upload file")
            return
        file_id = file_info['id']
        #print(f"File uploaded successfully with ID: {file_id}")
        
        # Create scan
        scan_info = create_scan(file_id, profile_name, args.comment, args.project)
        if not scan_info:
            print("Failed to create scan")
            return
        scan_id = scan_info['id']
        #print(f"Scan created successfully with ID: {scan_id}")
        
        # Wait for completion
        final_scan = wait_for_scan_completion(scan_id, args.timeout)
        if final_scan:
            if final_scan.get('edr_logs'):
                pass

            if final_scan.get('result'):
                print(f"Result: {final_scan['result']}")
        else:
            print("Scan did not complete successfully")

if __name__ == "__main__":
    main()
