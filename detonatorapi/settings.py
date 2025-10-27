import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

VM_DESTROY_AFTER = 60  # minutes
AUTH_TOKEN = ""

# Authentication Configuration
# Set a password to protect write operations
# export DETONATOR_AUTH_PASSWORD="your-secure-password-here"
AUTH_PASSWORD = os.getenv("DETONATOR_AUTH_PASSWORD", "")

# CORS Configuration
# Add allowed origins for Cross-Origin Resource Sharing
# export DETONATOR_CORS_ORIGINS="http://localhost:5000,http://192.168.1.100:5000,https://detonator.example.com"
CORS_ALLOW_ORIGINS = os.getenv(
    "DETONATOR_CORS_ORIGINS", 
    "http://localhost:5000,http://127.0.0.1:5000"
).split(",")

