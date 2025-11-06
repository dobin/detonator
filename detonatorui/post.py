from flask import Blueprint, request, jsonify
import requests
import logging
import json
from .config import API_BASE_URL

from detonatorapi.utils import filename_randomizer, RUNTIME_MIN_SECONDS, RUNTIME_MAX_SECONDS

logger = logging.getLogger(__name__)
post_bp = Blueprint('post', __name__)


def handle_api_response(response, operation_name="operation"):
    """Helper function to handle API responses consistently"""
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        return {
            "error": "Authentication required. Please log in.",
            "auth_required": True
        }, 401
    elif response.status_code == 403:
        return {
            "error": "Access forbidden. Check permissions or profile password.",
            "forbidden": True
        }, 403
    else:
        logger.error(f"API error for {operation_name}: {response.status_code} - {response.text}")
        return {"error": f"API error: {response.text}"}, response.status_code


@post_bp.route("/api/upload-and-scan", methods=["POST"])
def upload_file_and_scan():
    """Proxy endpoint to upload files with automatic scan creation to FastAPI"""
    try:
        files = {}
        data = {}
        
        # Forward authentication header from request
        headers = {}
        if 'X-Auth-Password' in request.headers:
            headers['X-Auth-Password'] = request.headers.get('X-Auth-Password')
        elif 'Authorization' in request.headers:
            headers['Authorization'] = request.headers.get('Authorization')
        
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
            
        if 'exec_arguments' in request.form:
            data['exec_arguments'] = request.form['exec_arguments']
            
        if 'project' in request.form:
            data['project'] = request.form['project']
            
        if 'profile_name' in request.form:
            data['profile_name'] = request.form['profile_name']
            
        if 'password' in request.form:
            data['password'] = request.form['password']

        if 'token' in request.form:
            data['token'] = request.form['token']
        
        if 'runtime' in request.form:
            raw_runtime = request.form['runtime'].strip()
            if raw_runtime:
                try:
                    runtime_value = int(raw_runtime)
                except ValueError:
                    return {"error": "Invalid runtime value"}, 400
                if runtime_value < RUNTIME_MIN_SECONDS or runtime_value > RUNTIME_MAX_SECONDS:
                    return {
                        "error": f"Runtime must be between {RUNTIME_MIN_SECONDS} and {RUNTIME_MAX_SECONDS} seconds"
                    }, 400
                data['runtime'] = runtime_value
        
        if 'drop_path' in request.form:
            data['drop_path'] = request.form['drop_path']
            
        response = requests.post(f"{API_BASE_URL}/api/upload-and-scan", files=files, data=data, headers=headers)
        return handle_api_response(response, "file upload and scan")
    except requests.RequestException as e:
        return {"error": f"Could not upload file: {str(e)}"}, 500
