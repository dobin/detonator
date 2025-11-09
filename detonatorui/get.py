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
    return render_template("index.html")

@get_bp.route("/login")
def login_page():
    return render_template("login.html")

@get_bp.route("/logout")
def logout_page():
    # This will be handled by JavaScript to clear localStorage
    return render_template("logout.html")

@get_bp.route("/files")
def files_page():
    return render_template("files.html")

@get_bp.route("/scans")
def scans_page():
    return render_template("scans.html")

@get_bp.route("/newscan")
def scan_page():
    # Fetch profiles list
    try:
        response = requests.get(f"{API_BASE_URL}/api/profiles")
        if response.status_code == 200:
            profiles = response.json()
        else:
            profiles = []
    except requests.RequestException:
        profiles = []
    
    return render_template("newscan.html", profiles=profiles)

@get_bp.route("/upload")
def upload_page():
    return render_template("upload.html")

@get_bp.route("/vms")
def vms_page():
    return render_template("vms.html")

@get_bp.route("/profiles")
def profiles_page():
    return render_template("profiles.html")

@get_bp.route("/scans-table")
def scans_table_page():
    return render_template("scans_table.html")


@get_bp.route("/semidatasieve/<int:scan_id>")
def semidatasieve(scan_id):
    """Page to display semidatasieve results for a scan"""
    return render_template("semidatasieve.html", scan_id=scan_id)

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
        # Build query parameters from request args
        params = {}
        
        # Handle pagination
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 10, type=int)
        params['skip'] = skip
        params['limit'] = limit
        
        # Handle filters
        status = request.args.get('status')
        if status and status != 'all':
            params['status'] = status
            
        project = request.args.get('project')
        if project:
            params['project'] = project
            
        result = request.args.get('result')
        if result:
            params['result'] = result
            
        search = request.args.get('search')
        if search:
            params['search'] = search
        
        # Handle user filter
        user = request.args.get('user')
        if user:
            params['user'] = user
        
        # Legacy filter support (for backward compatibility)
        filter_status = request.args.get('filter')
        if filter_status and filter_status != 'all':
            params['status'] = filter_status
        
        response = requests.get(f"{API_BASE_URL}/api/scans", params=params)
        if response.status_code == 200:
            scans = response.json()
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

    return render_template("partials/scan_details.html", 
                           scan=scan)

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

@get_bp.route("/templates/profiles")
def profiles_template():
    """Template endpoint to render profiles list via HTMX"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/profiles")
        if response.status_code == 200:
            templates = response.json()
            
            # Check status for each template
            for template_name, template in templates.items():
                url = f"{API_BASE_URL}/api/profiles/{template['id']}/status"
                try:
                    status_response = requests.get(url)
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        template['available'] = status_data.get('is_available', 'false')
                        template['rededr_available'] = status_data.get('rededr_available', '')
                    else:
                        template['available'] = "Error"
                        template['rededr_available'] = "Error"
                except requests.RequestException:
                    template['available'] = "Error"
                    template['rededr_available'] = "Error"
                
                # Add the name to the template for easier access in templates
                template['name'] = template_name

            # check for lock status for each template
            for template_name, template in templates.items():
                lock_url = f"{API_BASE_URL}/api/lock/{template['id']}/lock"
                try:
                    lock_response = requests.get(lock_url)
                    if lock_response.status_code == 200:
                        template['locked'] = lock_response.json().get('is_locked', 'false')
                    else:
                        template['locked'] = "Error"
                except requests.RequestException:
                    template['locked'] = "Error"
                
                # Add the name to the template for easier access in templates
                template['name'] = template_name
        else:
            templates = {}
    except requests.RequestException:
        templates = {}
    
    return render_template("partials/profiles_list.html", templates=templates)

@get_bp.route("/templates/profiles-overview")
def profiles_overview_template():
    """Template endpoint to render profiles overview for index page via HTMX"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/profiles")
        if response.status_code == 200:
            templates = response.json()
            # Add the name to each template for easier access in templates
            for template_name, template in templates.items():
                template['name'] = template_name
        else:
            templates = {}
    except requests.RequestException:
        templates = {}
    
    return render_template("partials/profiles_overview.html", templates=templates)

@get_bp.route("/templates/scans-table")
def scans_table_template():
    """Template endpoint to render scans table via HTMX"""
    try:
        # Build query parameters from request args
        params = {}
        
        # Handle pagination
        skip = request.args.get('skip', 0, type=int)
        limit = request.args.get('limit', 10, type=int)
        params['skip'] = skip
        params['limit'] = limit
        
        # Handle filters
        status = request.args.get('status')
        if status and status != 'all':
            params['status'] = status
            
        project = request.args.get('project')
        if project:
            params['project'] = project
            
        result = request.args.get('result')
        if result:
            params['result'] = result
            
        search = request.args.get('search')
        if search:
            params['search'] = search
        
        # Handle user filter
        user = request.args.get('user')
        if user:
            params['user'] = user
        
        # Legacy filter support (for backward compatibility)
        filter_status = request.args.get('filter')
        if filter_status and filter_status != 'all':
            params['status'] = filter_status
        
        response = requests.get(f"{API_BASE_URL}/api/scans", params=params)
        if response.status_code == 200:
            scans = response.json()
        else:
            scans = []
    except requests.RequestException:
        scans = []
    
    return render_template("partials/scans_table_list.html", scans=scans)


@get_bp.route("/templates/create-scan/<int:file_id>")
def create_file_scan_template(file_id):
    """Template endpoint to render scan creation form via HTMX"""
    try:
        # Fetch file details
        file_response = requests.get(f"{API_BASE_URL}/api/files/{file_id}")
        if file_response.status_code == 200:
            file_data = file_response.json()
        else:
            file_data = None
            
        # Fetch profiles
        profiles_response = requests.get(f"{API_BASE_URL}/api/profiles")
        if profiles_response.status_code == 200:
            profiles = profiles_response.json()
        else:
            profiles = {}
    except requests.RequestException:
        file_data = None
        profiles = {}
    
    return render_template("partials/file_create_scan.html", file=file_data, profiles=profiles)