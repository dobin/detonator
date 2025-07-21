from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import requests
import os
import logging
from datetime import datetime
from .post import post_bp
from .get import get_bp
from .config import READ_ONLY_MODE


app = Flask(__name__)
app.secret_key = "detonator-secret-key"  # Change this in production

app.register_blueprint(post_bp)
app.register_blueprint(get_bp)

# Reduce Flask/Werkzeug HTTP request logging verbosity
logging.getLogger('werkzeug').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

if READ_ONLY_MODE:
    logger.warning("🔒 FLASK UI RUNNING IN READ-ONLY MODE - Write operations are disabled")


# Helper function for Jinja2 templates
def get_status_color(status):
    """Get CSS classes for status badges"""
    if not status:
        return 'bg-gray-100 text-gray-800'
    status_colors = {
        'error': 'bg-red-100 text-red-800',
        'instantiating': 'bg-blue-100 text-blue-800',
        'finished': 'bg-blue-100 text-blue-800',
        'scanning': 'bg-green-100 text-green-800',
    }
    return status_colors.get(status.lower(), 'bg-gray-100 text-gray-800')
# Register the function for use in templates
app.jinja_env.globals.update(get_status_color=get_status_color)
app.jinja_env.globals.update(READ_ONLY_MODE=READ_ONLY_MODE)


def get_scan_status_color(status):
    if not status:
        return 'bg-gray-100 text-gray-800'
    status_colors = {
        'detected': 'bg-red-100 text-red-800',
        'clean': 'bg-green-100 text-green-800',
    }
    return status_colors.get(status.lower(), 'bg-gray-100 text-gray-800')
# Register the function for use in templates
app.jinja_env.globals.update(get_scan_status_color=get_scan_status_color)



# Add datetime formatting filter
@app.template_filter('strftime')
def strftime_filter(value, format='%Y-%m-%d %H:%M:%S'):
    """Format datetime objects in templates"""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value
    return value.strftime(format)

# decode JSON strings in templates
@app.template_filter('from_json')
def from_json_filter(s):
    import json
    return json.loads(s)

# Pretty print JSON in templates
@app.template_filter('pretty_json')
def pretty_json_filter(s):
    import json
    try:
        obj = json.loads(s)
        return json.dumps(obj, indent=4)
    except Exception:
        return s  # fallback: return original string if invalid


# Serve the static files
@app.route("/static/<path:filename>")
def static_files(filename):
    """Serve static files from the static directory"""
    return app.send_static_file(filename)


@app.context_processor
def inject_global_vars():
    return {
        'READ_ONLY': os.getenv("DETONATOR_READ_ONLY", "false").lower() in ("true", "1", "yes", "on")
    }