from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import requests
import os
import logging
from datetime import datetime

app = Flask(__name__)
app.secret_key = "detonator-secret-key"  # Change this in production

# Reduce Flask/Werkzeug HTTP request logging verbosity
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Setup logger for this module
logger = logging.getLogger(__name__)

# Helper function for Jinja2 templates
def get_status_color(status):
    """Get CSS classes for status badges"""
    if not status:
        return 'bg-gray-100 text-gray-800'
    status_colors = {
        'fresh': 'bg-blue-100 text-blue-800',
        'started': 'bg-yellow-100 text-yellow-800', 
        'running': 'bg-yellow-100 text-yellow-800',
        'completed': 'bg-green-100 text-green-800',
        'failed': 'bg-red-100 text-red-800',
        'none': 'bg-gray-100 text-gray-800',
        'creating': 'bg-blue-100 text-blue-800',
        'running': 'bg-green-100 text-green-800',
        'stopped': 'bg-red-100 text-red-800',
    }
    return status_colors.get(status.lower(), 'bg-gray-100 text-gray-800')

# Register the function for use in templates
app.jinja_env.globals.update(get_status_color=get_status_color)

# Add datetime formatting filter
def strftime_filter(value, format='%Y-%m-%d %H:%M:%S'):
    """Format datetime objects in templates"""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value
    return value.strftime(format)

app.jinja_env.filters['strftime'] = strftime_filter

# FastAPI service URL
API_BASE_URL = "http://localhost:8000"


# static
@app.route("/static/<path:filename>")
def static_files(filename):
    """Serve static files from the static directory"""
    return app.send_static_file(filename)


@app.route("/")
def index():
    # Fetch EDR templates from FastAPI
    try:
        response = requests.get(f"{API_BASE_URL}/api/edr-templates")
        if response.status_code == 200:
            edr_data = response.json()
            edr_templates = edr_data.get("templates", [])
        else:
            edr_templates = []
    except requests.RequestException:
        edr_templates = []
    
    return render_template("index.html", edr_templates=edr_templates)

@app.route("/files")
def files_page():
    return render_template("files.html")

@app.route("/scans")
def scans_page():
    return render_template("scans.html")

@app.route("/upload")
def upload_page():
    # Fetch EDR templates from FastAPI
    try:
        response = requests.get(f"{API_BASE_URL}/api/edr-templates")
        if response.status_code == 200:
            edr_data = response.json()
            edr_templates = edr_data.get("templates", [])
        else:
            edr_templates = []
    except requests.RequestException:
        edr_templates = []
    
    return render_template("upload.html", edr_templates=edr_templates)

# Template endpoints for HTMX
@app.route("/templates/files")
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

@app.route("/templates/scans")
def scans_template():
    """Template endpoint to render scans list via HTMX"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/scans")
        if response.status_code == 200:
            scans = response.json()
            # Sort scans by ID in descending order (newest first)
            scans = sorted(scans, key=lambda scan: scan['id'], reverse=True)
        else:
            scans = []
    except requests.RequestException:
        scans = []
    
    return render_template("partials/scans_list.html", scans=scans)

@app.route("/templates/scan-details/<int:scan_id>")
def scan_details_template(scan_id):
    """Template endpoint to render scan details via HTMX"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/scans/{scan_id}")
        if response.status_code == 200:
            scan = response.json()
        else:
            scan = None
    except requests.RequestException:
        scan = None
    
    return render_template("partials/scan_details.html", scan=scan)

# API proxy endpoints
@app.route("/api/files")
def get_files():
    """Proxy endpoint to fetch files from FastAPI"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/files")
        return response.json()
    except requests.RequestException:
        return {"error": "Could not fetch files"}, 500

@app.route("/api/files/<int:file_id>")
def get_file(file_id):
    """Proxy endpoint to fetch a specific file from FastAPI"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/files/{file_id}")
        return response.json()
    except requests.RequestException:
        return {"error": "Could not fetch file"}, 500

@app.route("/api/scans")
def get_scans():
    """Proxy endpoint to fetch scans from FastAPI"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/scans")
        return response.json()
    except requests.RequestException:
        return {"error": "Could not fetch scans"}, 500

@app.route("/api/scans/<int:scan_id>")
def get_scan(scan_id):
    """Proxy endpoint to fetch a specific scan from FastAPI"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/scans/{scan_id}")
        return response.json()
    except requests.RequestException:
        return {"error": "Could not fetch scan"}, 500

@app.route("/api/upload", methods=["POST"])
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

@app.route("/api/upload-and-scan", methods=["POST"])
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

@app.route("/api/scans/<int:scan_id>", methods=["PUT"])
def update_scan(scan_id):
    """Proxy endpoint to update scan via FastAPI"""
    try:
        response = requests.put(f"{API_BASE_URL}/api/scans/{scan_id}", json=request.json)
        return response.json()
    except requests.RequestException:
        return {"error": "Could not update scan"}, 500

@app.route("/api/edr-templates")
def get_edr_templates():
    """Proxy endpoint to fetch EDR templates from FastAPI"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/edr-templates")
        return response.json()
    except requests.RequestException:
        return {"error": "Could not fetch EDR templates", "templates": [], "all_templates": []}, 500

