from flask import Blueprint,  render_template, request, jsonify, redirect, url_for, flash
import requests
import logging
from .config import API_BASE_URL

get_bp = Blueprint('get', __name__)


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
        else:
            scans = []
    except requests.RequestException:
        scans = []
    
    return render_template("partials/scans_list.html", scans=scans)

@get_bp.route("/templates/scan-details/<int:scan_id>")
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

