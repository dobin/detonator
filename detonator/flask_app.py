from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)

# FastAPI service URL
API_BASE_URL = "http://localhost:8000"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/items")
def items_page():
    return render_template("items.html")

@app.route("/api/items")
def get_items():
    """Proxy endpoint to fetch items from FastAPI"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/items")
        return response.json()
    except requests.RequestException:
        return {"error": "Could not fetch items"}, 500

@app.route("/api/items", methods=["POST"])
def create_item():
    """Proxy endpoint to create items via FastAPI"""
    try:
        response = requests.post(f"{API_BASE_URL}/api/items", json=request.json)
        return response.json()
    except requests.RequestException:
        return {"error": "Could not create item"}, 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
