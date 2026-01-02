from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import requests
import os
import logging
from datetime import datetime
from pathlib import Path
from .post import post_bp
from .get import get_bp
from .config import API_BASE_URL
from detonatorapi.settings import AUTH_PASSWORD
from detonatorapi.edr_cloud.elastic_rule_resolver import ElasticRuleResolver


app = Flask(__name__)
app.secret_key = "detonator-secret-key"  # Change this in production

app.register_blueprint(post_bp)
app.register_blueprint(get_bp)

# Reduce Flask/Werkzeug HTTP request logging verbosity
logging.getLogger('werkzeug').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Initialize Elastic Rule Resolver
# CSV path is relative to the project root
csv_path = Path(__file__).parent.parent / "elastic_rules" / "elastic_rules.csv"
elastic_rule_resolver = ElasticRuleResolver(csv_path=str(csv_path))


# Make API_BASE_URL available to all templates
@app.context_processor
def inject_api_base_url():
    # Check if authentication is enabled
    auth_enabled = False
    if AUTH_PASSWORD != None and AUTH_PASSWORD != "":
        auth_enabled = True
    
    return {
        'API_BASE_URL': API_BASE_URL,
        'AUTH_ENABLED': auth_enabled
    }


# Helper function for Jinja2 templates
def get_status_color(status):
    """Get CSS classes for status badges"""
    if not status:
        return 'bg-gray-100 text-gray-800'
    status_colors = {
        'error': 'bg-red-100 text-red-800',
        'instantiating': 'bg-blue-100 text-blue-800',
        'finished': 'bg-blue-100 text-blue-800',
        'processing': 'bg-blue-300 text-blue-800',
        'polling': 'bg-yellow-100 text-yellow-800',
    }
    return status_colors.get(status.lower(), 'bg-gray-100 text-gray-800')
# Register the function for use in templates
app.jinja_env.globals.update(get_status_color=get_status_color)


def get_submission_status_color(status):
    if not status:
        return 'bg-gray-100 text-gray-800'
    status_colors = {
        'detected': 'bg-red-100 text-red-800',
        'file_detected': 'bg-red-100 text-red-800',
        'not_detected': 'bg-green-100 text-green-800',
        'clean': 'bg-green-100 text-green-800',
    }
    return status_colors.get(status.lower(), 'bg-gray-100 text-gray-800')
# Register the function for use in templates
app.jinja_env.globals.update(get_submission_status_color=get_submission_status_color)


def get_alert_severity_color(severity):
    if not severity:
        return 'bg-gray-100 text-gray-800'
    colors = {
        'informational': 'bg-gray-100 text-gray-800',
        'low': 'bg-green-100 text-green-800',
        'medium': 'bg-yellow-100 text-yellow-800',
        'high': 'bg-orange-100 text-orange-800',
        'severe': 'bg-red-100 text-red-800',
    }
    return colors.get(severity.lower(), 'bg-gray-200 text-gray-800')


app.jinja_env.globals.update(get_alert_severity_color=get_alert_severity_color)



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


# Resolve Elastic rule ID to GitHub path
@app.template_filter('resolve_elastic_rule')
def resolve_elastic_rule_filter(rule_id):
    """Resolve Elastic rule ID to relative GitHub path"""
    if not rule_id:
        return None
    path = elastic_rule_resolver.get_path(rule_id)
    if path:
        # Convert absolute path to relative path from detection-rules repo root
        # Example: /path/to/elastic_rules/detection-rules/rules/windows/file.toml
        # Should become: rules/windows/file.toml
        if "detection-rules/" in path:
            return path.split("detection-rules/", 1)[1]
    return None


# Serve the static files
@app.route("/static/<path:filename>")
def static_files(filename):
    """Serve static files from the static directory"""
    return app.send_static_file(filename)
