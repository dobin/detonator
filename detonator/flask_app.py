from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import requests
import os

app = Flask(__name__)
app.secret_key = "detonator-secret-key"  # Change this in production

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
            files['file'] = request.files['file']
        
        if 'source_url' in request.form:
            data['source_url'] = request.form['source_url']
        
        if 'comment' in request.form:
            data['comment'] = request.form['comment']
            
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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
