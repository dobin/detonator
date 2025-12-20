from flask import Blueprint,  render_template, request, jsonify, redirect, url_for, flash
from typing import Optional, Dict
import requests
import logging
from .config import API_BASE_URL
import json
import logging


get_bp = Blueprint('get', __name__)
logger = logging.getLogger(__name__)


def _auth_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
    password = request.headers.get("X-Auth-Password")
    if password:
        headers["X-Auth-Password"] = password
    return headers


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

@get_bp.route("/submissions")
def submissions_page():
    return render_template("submissions.html")

@get_bp.route("/submissions/<int:submission_id>")
def submission_detail_page(submission_id):
    """Page to display details of a specific submission"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/submissions/{submission_id}", headers=_auth_headers())
        if response.status_code == 200:
            submission = response.json()
        else:
            logger.error(f"Failed to fetch submission {submission_id}: {response.status_code} {response.text}")
            submission = None
    except requests.RequestException as e:
        logger.exception(f"Exception while fetching submission {submission_id}: {e}")
        submission = None
    
    return render_template("submission_details.html", submission=submission)

@get_bp.route("/newsubmission")
def submission_page():
    # Fetch profiles list
    try:
        response = requests.get(f"{API_BASE_URL}/api/profiles", headers=_auth_headers())
        if response.status_code == 200:
            profiles = response.json()
        else:
            logger.error(f"Failed to fetch profiles: {response.status_code} {response.text}")
            profiles = []
    except requests.RequestException as e:
        logger.exception(f"Exception while fetching profiles: {e}")
        profiles = []
    
    return render_template("newsubmission.html", profiles=profiles)

@get_bp.route("/upload")
def upload_page():
    return render_template("upload.html")

@get_bp.route("/vms")
def vms_page():
    return render_template("vms.html")

@get_bp.route("/profiles")
def profiles_page():
    return render_template("profiles.html")

@get_bp.route("/submissions-table")
def submissions_table_page():
    return render_template("submissions_table.html")


@get_bp.route("/semidatasieve/<int:submission_id>")
def semidatasieve(submission_id):
    """Page to display semidatasieve results for a submission"""
    return render_template("semidatasieve.html", submission_id=submission_id)

# Template endpoints for HTMX (return HTML)

@get_bp.route("/templates/files")
def files_template():
    """Template endpoint to render files list via HTMX"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/files", headers=_auth_headers())
        if response.status_code == 200:
            files = response.json()
            # Sort submissions by ID in descending order (newest first)
            files = sorted(files, key=lambda file: file['id'], reverse=True)
        else:
            files = []
    except requests.RequestException:
        files = []
    
    return render_template("partials/files_list.html", files=files)

@get_bp.route("/templates/submissions")
def submissions_template():
    """Template endpoint to render submissions list via HTMX"""
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
            
        edr_verdict = request.args.get('edr_verdict')
        if edr_verdict:
            params['edr_verdict'] = edr_verdict
            
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
        
        response = requests.get(f"{API_BASE_URL}/api/submissions", params=params, headers=_auth_headers())
        if response.status_code == 200:
            submissions = response.json()
        else:
            submissions = []
    except requests.RequestException:
        submissions = []
    
    return render_template("partials/submissions_list.html", submissions=submissions)

@get_bp.route("/templates/submission-details/<int:submission_id>")
def submission_details_template(submission_id):
    """Template endpoint to render submission details via HTMX"""
    submission: Optional[Dict] = {}
    try:
        response = requests.get(f"{API_BASE_URL}/api/submissions/{submission_id}", headers=_auth_headers())
        if response.status_code == 200:
            submission = response.json()
        else:
            submission = None
    except requests.RequestException:
        submission = None

    return render_template("partials/submission_details.html", 
                           submission=submission)

@get_bp.route("/templates/vms")
def vms_template():
    """Template endpoint to render VMs list via HTMX"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/vms", headers=_auth_headers())
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
        response = requests.get(f"{API_BASE_URL}/api/profiles", headers=_auth_headers())
        if response.status_code == 200:
            templates = response.json()
            
            # Check status for each template
            for template_name, template in templates.items():
                url = f"{API_BASE_URL}/api/profiles/{template['id']}/status"
                try:
                    status_response = requests.get(url, headers=_auth_headers())
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
                    lock_response = requests.get(lock_url, headers=_auth_headers())
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

@get_bp.route("/templates/submissions-table")
def submissions_table_template():
    """Template endpoint to render submissions table via HTMX"""
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
            
        edr_verdict = request.args.get('edr_verdict')
        if edr_verdict:
            params['edr_verdict'] = edr_verdict
            
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
        
        response = requests.get(f"{API_BASE_URL}/api/submissions", params=params)
        if response.status_code == 200:
            submissions = response.json()
        else:
            submissions = []
    except requests.RequestException:
        submissions = []
    
    return render_template("partials/submissions_table_list.html", submissions=submissions)


@get_bp.route("/templates/create-submission/<int:file_id>")
def create_file_submission_template(file_id):
    """Template endpoint to render submission creation form via HTMX"""
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
    
    return render_template("partials/file_create_submission.html", file=file_data, profiles=profiles)
