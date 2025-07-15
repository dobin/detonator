
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_BASE_URL = "http://localhost:8000"

# Read-only mode configuration (should match FastAPI)
READ_ONLY_MODE = os.getenv("DETONATOR_READ_ONLY", "false").lower() in ("true", "1", "yes", "on")
