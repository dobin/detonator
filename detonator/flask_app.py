from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import requests
import os

app = Flask(__name__)
app.secret_key = "detonator-secret-key"  # Change this in production

# FastAPI service URL
API_BASE_URL = "http://localhost:8000"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/files")
def files_page():
    return render_template("files.html")

@app.route("/scans")
def scans_page():
    return render_template("scans.html")

@app.route("/upload")
def upload_page():
    return render_template("upload.html")

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

@app.route("/api/scans/<int:scan_id>", methods=["PUT"])
def update_scan(scan_id):
    """Proxy endpoint to update scan via FastAPI"""
    try:
        response = requests.put(f"{API_BASE_URL}/api/scans/{scan_id}", json=request.json)
        return response.json()
    except requests.RequestException:
        return {"error": "Could not update scan"}, 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
