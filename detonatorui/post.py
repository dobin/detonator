from flask import Blueprint, request, jsonify
import requests
import logging
from .config import API_BASE_URL

logger = logging.getLogger(__name__)
post_bp = Blueprint('post', __name__)


@post_bp.route("/api/upload", methods=["POST"])
def upload_file():
    """Proxy endpoint to upload files to FastAPI"""
    try:
        files = {}
        data = {}
        
        if 'file' in request.files:
            uploaded_file = request.files['file']
            files['file'] = (uploaded_file.filename, uploaded_file.stream, uploaded_file.content_type)
        
        if 'source_url' in request.form:
            data['source_url'] = request.form['source_url']
        
        if 'comment' in request.form:
            data['comment'] = request.form['comment']
        
        response = requests.post(f"{API_BASE_URL}/api/files", files=files, data=data)
        return response.json()
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
            files['file'] = (uploaded_file.filename, uploaded_file.stream, uploaded_file.content_type)
        
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
        
        response = requests.post(f"{API_BASE_URL}/api/files/upload-and-scan", files=files, data=data)
        return response.json()
    except requests.RequestException as e:
        return {"error": f"Could not upload file: {str(e)}"}, 500

@post_bp.route("/api/vms/<vm_name>", methods=["DELETE"])
def delete_vm(vm_name):
    """Proxy endpoint to delete VM via FastAPI"""
    try:
        response = requests.delete(f"{API_BASE_URL}/api/vms/{vm_name}")
        return response.json()
    except requests.RequestException as e:
        return {"error": f"Could not delete VM: {str(e)}"}, 500

@post_bp.route("/api/files/<int:file_id>/createscan", methods=["POST"])
def file_create_scan(file_id):
    """Proxy endpoint to create scan via FastAPI"""
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
        
        logger.info(f"Creating scan for file {file_id} with data: {data}")
        response = requests.post(f"{API_BASE_URL}/api/files/{file_id}/createscan", json=data)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"FastAPI error: {response.status_code} - {response.text}")
            return {"error": f"FastAPI error: {response.text}"}, response.status_code
            
    except requests.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return {"error": f"Could not create scan: {str(e)}"}, 500
