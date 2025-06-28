#!/usr/bin/env python3
"""
Detonator - File analysis system with FastAPI backend and Flask frontend
"""

import sys
import subprocess
import threading
import time
import os
from dotenv import load_dotenv

from .logging_config import setup_logging
from .vm_manager import initialize_vm_manager


load_dotenv()

def run_fastapi():
    """Run the FastAPI server"""
    import uvicorn
    from .fastapi_app import app
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


def run_flask():
    """Run the Flask server"""
    from .flask_app import app
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)


def run_both():
    """Run both servers concurrently"""
    print("Starting Detonator servers...")
    print("FastAPI (REST API): http://localhost:8000")
    print("Flask (Web UI): http://localhost:5000")
    print("Press Ctrl+C to stop both servers")
    
    # Start FastAPI in a separate thread
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    
    # Give FastAPI a moment to start
    #time.sleep(2)
    
    # Start Flask in the main thread
    try:
        run_flask()
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        sys.exit(0)


def main():
    setup_logging()
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m detonator both     # Run both FastAPI and Flask servers")
        print("  python -m detonator api      # Run only FastAPI server")
        print("  python -m detonator web      # Run only Flask server")
        sys.exit(1)
    
    command = sys.argv[1].lower()

    # Azure: Init
    if not os.getenv("AZURE_SUBSCRIPTION_ID"):
        print("Error: AZURE_SUBSCRIPTION_ID environment variable is not set.")
        sys.exit(1)

    if command == "both":
        run_both()
    elif command == "api":
        print("Starting FastAPI server on http://localhost:8000")
        run_fastapi()
    elif command == "web":
        print("Starting Flask server on http://localhost:5000")
        run_flask()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
