
import os
import yaml
from pathlib import Path


# Load config from config.yaml
def load_config():
    config_file = Path(__file__).parent / "config.yaml"
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
            return config if isinstance(config, dict) else {}
    return {}

_config = load_config()

API_BASE_URL = _config.get("api_base_url", "http://localhost:8000")
