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
            files['file'] = request.files['file']
        
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
            
        if 'vm_template' in request.form:
            data['vm_template'] = request.form['vm_template']
            
        if 'edr_template' in request.form:
            data['edr_template'] = request.form['edr_template']
        
        response = requests.post(f"{API_BASE_URL}/api/files/upload-and-scan", files=files, data=data)
        return response.json()
    except requests.RequestException as e:
        return {"error": f"Could not upload file: {str(e)}"}, 500
