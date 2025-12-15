import os
import yaml
from pathlib import Path

UPLOAD_DIR = "upload/"


# Load settings from settings.yaml
def load_settings():
    settings_file = Path(__file__).parent / "settings.yaml"
    if settings_file.exists():
        with open(settings_file, 'r') as f:
            settings = yaml.safe_load(f)
            return settings if settings else {}
    return {}

_settings = load_settings()

VM_DESTROY_AFTER = _settings.get("vm_destroy_after", 60)  # minutes
AUTH_PASSWORD = _settings.get("auth_password", "")
CORS_ALLOW_ORIGINS = _settings.get(
    "cors_allowed_origins", 
    "http://localhost:5000,http://127.0.0.1:5000"
).split(",")
DISABLE_REVERT_VM = _settings.get("disable_revert_vm", False)
