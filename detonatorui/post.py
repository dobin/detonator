from flask import Blueprint, request, jsonify
import requests
import logging
import json
from .config import API_BASE_URL, READ_ONLY_MODE

from detonatorapi.utils import filename_randomizer

logger = logging.getLogger(__name__)
post_bp = Blueprint('post', __name__)


def handle_api_response(response, operation_name="operation"):
    """Helper function to handle API responses consistently"""
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 403:
        return {
            "error": "Server is running in read-only mode. Write operations are not permitted.",
            "read_only_mode": True
        }, 403
    else:
        logger.error(f"API error for {operation_name}: {response.status_code} - {response.text}")
        return {"error": f"API error: {response.text}"}, response.status_code



@post_bp.route("/api/upload", methods=["POST"])
def upload_file():
    """Proxy endpoint to upload files to FastAPI"""
    if READ_ONLY_MODE:
        return {
            "error": "Upload disabled in read-only mode",
            "read_only_mode": True
        }, 403
        
    try:
        files = {}
        data = {}
        
        if 'file' in request.files:
            uploaded_file = request.files['file']
            filename = uploaded_file.filename
            
            # Check if filename randomization is enabled
            randomize = request.form.get('randomize_filename') == 'on'
            if randomize and filename:
                filename = filename_randomizer(filename)
            
            files['file'] = (filename, uploaded_file.stream, uploaded_file.content_type)
        
        if 'source_url' in request.form:
            data['source_url'] = request.form['source_url']
        
        if 'comment' in request.form:
            data['comment'] = request.form['comment']
        
        response = requests.post(f"{API_BASE_URL}/api/files", files=files, data=data)
        return handle_api_response(response, "file upload")
    except requests.RequestException as e:
        return {"error": f"Could not upload file: {str(e)}"}, 500


@post_bp.route("/api/upload-and-scan", methods=["POST"])
def upload_file_and_scan():
    """Proxy endpoint to upload files with automatic scan creation to FastAPI"""
    try:
        files = {}
        data = {}
        
        if 'file' in request.files:
            # fix filename handling
            uploaded_file = request.files['file']
            filename = uploaded_file.filename
            
            # Check if filename randomization is enabled
            randomize = request.form.get('randomize_filename') == 'on'
            if randomize and filename:
                filename = filename_randomizer(filename)
            
            files['file'] = (filename, uploaded_file.stream, uploaded_file.content_type)
        
        if 'source_url' in request.form:
            data['source_url'] = request.form['source_url']
        
        if 'file_comment' in request.form:
            data['file_comment'] = request.form['file_comment']
            
        if 'scan_comment' in request.form:
            data['scan_comment'] = request.form['scan_comment']
            
        if 'project' in request.form:
            data['project'] = request.form['project']
            
        if 'profile_name' in request.form:
            data['profile'] = request.form['profile_name']
            
        if 'password' in request.form:
            data['password'] = request.form['password']
        
        data['runtime'] = 12
        response = requests.post(f"{API_BASE_URL}/api/files/upload-and-scan", files=files, data=data)
        return handle_api_response(response, "file upload and scan")
    except requests.RequestException as e:
        return {"error": f"Could not upload file: {str(e)}"}, 500

@post_bp.route("/api/vms/<vm_name>", methods=["DELETE"])
def delete_vm(vm_name):
    """Proxy endpoint to delete VM via FastAPI"""
    try:
        response = requests.delete(f"{API_BASE_URL}/api/vms/{vm_name}")
        return handle_api_response(response, "VM deletion")
    except requests.RequestException as e:
        return {"error": f"Could not delete VM: {str(e)}"}, 500

@post_bp.route("/api/scans/<int:scan_id>", methods=["DELETE"])
def delete_scan(scan_id):
    """Proxy endpoint to delete scan via FastAPI"""
    try:
        response = requests.delete(f"{API_BASE_URL}/api/scans/{scan_id}")
        return handle_api_response(response, "scan deletion")
    except requests.RequestException as e:
        return {"error": f"Could not delete scan: {str(e)}"}, 500

@post_bp.route("/api/files/<int:file_id>/createscan", methods=["POST"])
def file_create_scan(file_id):
    """Proxy endpoint to create scan via FastAPI"""
    try:
        # Handle both JSON and form data
        data = {}
        if request.is_json:
            data = request.json or {}
        else:
            # Convert form data to dictionary
            data = {}
            for key, value in request.form.items():
                if value.strip():  # Only include non-empty values
                    data[key] = value
        
        logger.info(f"Creating scan for file {file_id} with data: {data}")
        data['runtime'] = 12
        response = requests.post(f"{API_BASE_URL}/api/files/{file_id}/createscan", json=data)
        
        return handle_api_response(response, "scan creation")
            
    except requests.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return {"error": f"Could not create scan: {str(e)}"}, 500

@post_bp.route("/api/profiles", methods=["POST"])
def create_profile():
    """Proxy endpoint to create profile via FastAPI"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.json
        else:
            # Convert form data to dictionary
            data = {}
            for key, value in request.form.items():
                if value.strip():  # Only include non-empty values
                    data[key] = value
        
        logger.info(f"Creating profile with data: {data}")
        response = requests.post(f"{API_BASE_URL}/api/profiles", data=data)
        
        return handle_api_response(response, "profile creation")
            
    except requests.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return {"error": f"Could not create profile: {str(e)}"}, 500

@post_bp.route("/api/profiles/<int:profile_id>", methods=["PUT"])
def update_profile(profile_id):
    """Proxy endpoint to update profile via FastAPI"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.json
        else:
            # Convert form data to dictionary
            data = {}
            for key, value in request.form.items():
                if value.strip():  # Only include non-empty values
                    data[key] = value
        
        logger.info(f"Updating profile {profile_id} with data: {data}")
        response = requests.put(f"{API_BASE_URL}/api/profiles/{profile_id}", data=data)
        
        return handle_api_response(response, "profile update")
            
    except requests.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return {"error": f"Could not update profile: {str(e)}"}, 500

@post_bp.route("/api/profiles/<int:profile_id>", methods=["DELETE"])
def delete_profile(profile_id):
    """Proxy endpoint to delete profile via FastAPI"""
    try:
        logger.info(f"Deleting profile {profile_id}")
        response = requests.delete(f"{API_BASE_URL}/api/profiles/{profile_id}")
        
        return handle_api_response(response, "profile deletion")
            
    except requests.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return {"error": f"Could not delete profile: {str(e)}"}, 500

@post_bp.route("/api/profiles/<int:profile_id>", methods=["GET"])
def get_profile(profile_id):
    """Proxy endpoint to get a single profile via FastAPI"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/profiles/{profile_id}")
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"FastAPI error: {response.status_code} - {response.text}")
            return {"error": f"FastAPI error: {response.text}"}, response.status_code
            
    except requests.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return {"error": f"Could not get profile: {str(e)}"}, 500

@post_bp.route("/api/profiles/submit", methods=["POST"])
def submit_profile():
    """Proxy endpoint to create or update profile via FastAPI"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.json or {}
        else:
            # Convert form data to dictionary
            data = {}
            for key, value in request.form.items():
                if value.strip():  # Only include non-empty values
                    data[key] = value
        
        profile_id = data.get('profile_id')
        
        if profile_id:
            # Update existing profile
            logger.info(f"Updating profile {profile_id} with data: {data}")
            response = requests.put(f"{API_BASE_URL}/api/profiles/{profile_id}", data=data)
        else:
            # Create new profile
            logger.info(f"Creating new profile with data: {data}")
            response = requests.post(f"{API_BASE_URL}/api/profiles", data=data)
        
        return handle_api_response(response, "profile submission")
            
    except requests.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return {"error": f"Could not submit profile: {str(e)}"}, 500
