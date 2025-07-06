import os
import sys
import time
import requests
import argparse
from pathlib import Path

# Default API base URL
API_BASE_URL = "http://localhost:8000"

def get_edr_templates():
    """Get available EDR templates from the API"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/edr-templates")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching EDR templates: {e}")
        return []

def upload_file(filename, source_url="", comment=""):
    """Upload a file to the API"""
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

def create_scan(file_id, edr_template, comment="", project=""):
    """Create a scan for the uploaded file"""
    try:
        data = {
            "edr_template": edr_template,
            "comment": comment,
            "project": project
        }
        response = requests.post(f"{API_BASE_URL}/api/files/{file_id}/createscan", json=data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error creating scan: {e}")
        return None

def get_scan_status(scan_id):
    """Get the current status of a scan"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/scans/{scan_id}")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error getting scan status: {e}")
        return None

def wait_for_scan_completion(scan_id, timeout=3600):
    """Wait for scan to complete, polling every 5 seconds"""
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
        
        if scan['status'] in ["finished", "error", "completed"]:
            print("")
            return scan
        elif scan['status'] == "failed":
            print(f"Scan {scan_id} failed")
            return scan
            
        time.sleep(1)
    
    print(f"Timeout waiting for scan {scan_id} to complete")
    return None

def main():
    parser = argparse.ArgumentParser(description="Detonator Command Line Client")
    parser.add_argument("command", choices=["scan", "list-templates"], help="Command to execute")
    parser.add_argument("filename", nargs="?", help="File to scan")
    parser.add_argument("--edr-template", "-t", default="running_rededr", help="EDR template to use")
    parser.add_argument("--comment", "-c", default="", help="Comment for the scan")
    parser.add_argument("--project", "-p", default="", help="Project name for the scan")
    parser.add_argument("--source-url", "-s", default="", help="Source URL of the file")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--timeout", type=int, default=3600, help="Timeout in seconds for scan completion")
    
    args = parser.parse_args()
    
    global API_BASE_URL
    API_BASE_URL = args.api_url
    
    if args.command == "list-templates":
        templates = get_edr_templates()
        if templates:
            print("Available EDR templates:")
            for template in templates:
                print(f"  - {template['id']}: {template.get('description', 'No description')}")
                if template.get('category'):
                    print(f"    Category: {template['category']}")
                if template.get('ports'):
                    print(f"    Ports: {', '.join(map(str, template['ports']))}")
        else:
            print("No templates available or error fetching templates")
        return
    
    elif args.command == "scan":
        if not args.filename:
            print("Error: filename is required for scan command")
            parser.print_help()
            return
            
        filename = args.filename
        edr_template_id = args.edr_template
        
        # Check if file exists
        if not os.path.exists(filename):
            print(f"Error: File {filename} does not exist")
            return
        
        # Get available templates to validate
        templates = get_edr_templates()
        template_ids = [t['id'] for t in templates] if templates else []
        if edr_template_id not in template_ids:
            print(f"Error: EDR template '{edr_template_id}' not found")
            print("Available templates:")
            for template in templates:
                print(f"  - {template['id']}: {template.get('description', 'No description')}")
            return
        
        #print(f"> Scanning file {filename} with EDR template {edr_template_id}")
        
        # Upload file
        file_info = upload_file(filename, args.source_url, f"Uploaded via CLI: {args.comment}")
        if not file_info:
            print("Failed to upload file")
            return
        file_id = file_info['id']
        #print(f"File uploaded successfully with ID: {file_id}")
        
        # Create scan
        scan_info = create_scan(file_id, edr_template_id, args.comment, args.project)
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
