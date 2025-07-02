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
import uvicorn

from detonatorapi.logging_config import setup_logging
from detonatorapi.azure_manager import initialize_azure_manager
from detonatorapi.db_interface import db_create_file, db_create_scan

from detonatorapi.fastapi_app import app as fastapi_app
from detonatorui.flask_app import app as flask_app
from detonatorapi.vm_monitor import VMMonitorTask

load_dotenv()

def run_fastapi():
    """Run the FastAPI server"""
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000, log_level="warning")


def run_flask():
    """Run the Flask server"""
    flask_app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)


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

    elif command == "monitor_once":
        print("Running VM monitor once...")
        monitor_task = VMMonitorTask()
        monitor_task.check_all_scans()
    elif command == "add_test_scan":
        print("Adding a new scan for testing...")
        file_id = db_create_file("test.txt", b"Test")
        scan_id = db_create_scan(file_id, edr_template="new_defender")
        print(f"Created test scan with ID: {scan_id}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
