from flask import Blueprint,  render_template, request, jsonify, redirect, url_for, flash
from typing import Optional, Dict
import requests
import logging
from .config import API_BASE_URL
import json
import logging

get_bp = Blueprint('get', __name__)
logger = logging.getLogger(__name__)


# MAIN Pages

@get_bp.route("/")
def index():
    # Fetch EDR templates from FastAPI
    try:
        response = requests.get(f"{API_BASE_URL}/api/edr-templates")
        if response.status_code == 200:
            edr_templates = response.json()
        else:
            edr_templates = []
    except requests.RequestException:
        edr_templates = []
    
    return render_template("index.html", edr_templates=edr_templates)

@get_bp.route("/files")
def files_page():
    return render_template("files.html")

@get_bp.route("/scans")
def scans_page():
    return render_template("scans.html")

@get_bp.route("/upload")
def upload_page():
    # Fetch EDR templates from FastAPI
    try:
        response = requests.get(f"{API_BASE_URL}/api/edr-templates")
        if response.status_code == 200:
            edr_templates = response.json()
        else:
            edr_templates = []
    except requests.RequestException:
        edr_templates = []
    
    return render_template("upload.html", edr_templates=edr_templates)

@get_bp.route("/vms")
def vms_page():
    return render_template("vms.html")

@get_bp.route("/edr-templates")
def edr_templates_page():
    return render_template("edr_templates.html")


# Template endpoints for HTMX (return HTML)

@get_bp.route("/templates/files")
def files_template():
    """Template endpoint to render files list via HTMX"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/files")
        if response.status_code == 200:
            files = response.json()
            # Sort scans by ID in descending order (newest first)
            files = sorted(files, key=lambda file: file['id'], reverse=True)
        else:
            files = []
    except requests.RequestException:
        files = []
    
    return render_template("partials/files_list.html", files=files)

@get_bp.route("/templates/scans")
def scans_template():
    """Template endpoint to render scans list via HTMX"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/scans")
        if response.status_code == 200:
            scans = response.json()
            # Sort scans by ID in descending order (newest first)
            scans = sorted(scans, key=lambda scan: scan['id'], reverse=True)
            
            # Apply filter if specified
            filter_status = request.args.get('filter')
            if filter_status and filter_status != 'all':
                scans = [scan for scan in scans if scan.get('status') == filter_status]
                
        else:
            scans = []
    except requests.RequestException:
        scans = []
    
    return render_template("partials/scans_list.html", scans=scans)

@get_bp.route("/templates/scan-details/<int:scan_id>")
def scan_details_template(scan_id):
    """Template endpoint to render scan details via HTMX"""
    scan: Optional[Dict] = {}
    try:
        response = requests.get(f"{API_BASE_URL}/api/scans/{scan_id}")
        if response.status_code == 200:
            scan = response.json()
        else:
            scan = None
    except requests.RequestException:
        scan = None

    # Convert execution logs
    # {
    #    "execution_logs": {
    #        "log": ["log line 1", "log line 2"],
    #        "output": "command output here"
    #    }
    # }
    log = ""
    output = ""
    if scan:
        l = scan.get("execution_logs", "")
        execution_logs: Dict = json.loads(l) if l else {}
        log = "\n".join(execution_logs.get("log", []))
        output = execution_logs.get("output", "")

    return render_template("partials/scan_details.html", 
                           scan=scan, log=log, output=output)

@get_bp.route("/templates/vms")
def vms_template():
    """Template endpoint to render VMs list via HTMX"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/vms")
        if response.status_code == 200:
            vms = response.json()
            vms = sorted(vms, key=lambda vm: vm['name'])
        else:
            vms = []
    except requests.RequestException:
        vms = []
    
    return render_template("partials/vms_list.html", vms=vms)

@get_bp.route("/templates/edr-templates")
def edr_templates_template():
    """Template endpoint to render EDR templates list via HTMX"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/edr-templates")
        if response.status_code == 200:
            templates = response.json()
            
            # Check status for each template
            for template in templates:
                if template['type'] == 'clone':
                    template['available'] = "Not exist"

                    # Check if VM exists in Azure
                    vm_name = template.get('vm_name')
                    if vm_name:
                        try:
                            vm_check_response = requests.get(f"{API_BASE_URL}/api/vms")
                            if vm_check_response.status_code == 200:
                                vms = vm_check_response.json()
                                vm_exists = any(vm['name'] == vm_name for vm in vms)
                                if vm_exists:
                                    template['available'] = "true"
                        except:
                            template['available'] = "Error"
                    else:
                        template['available'] = 'Error'
                        
                elif template['type'] == 'running':
                    template['available'] = "Not running"

                    # Check HTTP connectivity
                    ip = template.get('ip')
                    if ip:
                        try:
                            url = f"http://{ip}:8080"
                            test_response = requests.get(url, timeout=1)
                            template['available'] = "true"
                        except:
                            template['available'] = 'Error'
                    else:
                        template['connectivity_status'] = 'Error'

                elif template['type'] == 'new':
                    template["available"] = "true"
        else:
            templates = []
    except requests.RequestException:
        templates = []
    
    return render_template("partials/edr_templates_list.html", templates=templates)

# API endpoints (return JSON)

@get_bp.route("/api/files")
def get_files():
    """Proxy endpoint to fetch files from FastAPI"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/files")
        return response.json()
    except requests.RequestException:
        return {"error": "Could not fetch files"}, 500

@get_bp.route("/api/files/<int:file_id>")
def get_file(file_id):
    """Proxy endpoint to fetch a specific file from FastAPI"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/files/{file_id}")
        return response.json()
    except requests.RequestException:
        return {"error": "Could not fetch file"}, 500

@get_bp.route("/api/scans")
def get_scans():
    """Proxy endpoint to fetch scans from FastAPI"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/scans")
        return response.json()
    except requests.RequestException:
        return {"error": "Could not fetch scans"}, 500

@get_bp.route("/api/scans/<int:scan_id>")
def get_scan(scan_id):
    """Proxy endpoint to fetch a specific scan from FastAPI"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/scans/{scan_id}")
        return response.json()
    except requests.RequestException:
        return {"error": "Could not fetch scan"}, 500

@get_bp.route("/api/scans/<int:scan_id>", methods=["PUT"])
def update_scan(scan_id):
    """Proxy endpoint to update scan via FastAPI"""
    try:
        response = requests.put(f"{API_BASE_URL}/api/scans/{scan_id}", json=request.json)
        return response.json()
    except requests.RequestException:
        return {"error": "Could not update scan"}, 500

@get_bp.route("/api/edr-templates")
def get_edr_templates():
    """Proxy endpoint to fetch EDR templates from FastAPI"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/edr-templates")
        return response.json()
    except requests.RequestException:
        return [], 500

@get_bp.route("/api/vms")
def get_vms():
    """Proxy endpoint to fetch VMs from FastAPI"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/vms")
        return response.json()
    except requests.RequestException:
        return {"error": "Could not fetch VMs"}, 500

