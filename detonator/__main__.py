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
import logging

from detonatorapi.logging_config import setup_logging
from detonatorapi.azure_manager import initialize_azure_manager
from detonatorapi.db_interface import db_create_file, db_create_scan

from detonatorapi.fastapi_app import app as fastapi_app
from detonatorui.flask_app import app as flask_app
from detonatorapi.vm_monitor import vm_monitor, VMMonitorTask
from detonatorapi.database import get_db, get_db_for_thread


load_dotenv()
logger = logging.getLogger(__name__)

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
    db = get_db_for_thread()

    # Azure: Init
    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
    resource_group = os.getenv("AZURE_RESOURCE_GROUP", "detonator-rg")
    location = os.getenv("AZURE_LOCATION", "East US")
    if not subscription_id:
        logger.warning("AZURE_SUBSCRIPTION_ID not set - VM creation will not work")
        #return
    else:
        initialize_azure_manager(subscription_id, resource_group, location)
        logger.info("Azure Manager initialized successfully")

    # VM Monitor: Init
    vm_monitor.init()

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
        filename = sys.argv[2] if len(sys.argv) > 2 else "test_file.exe"
        edr_template_id = sys.argv[3] if len(sys.argv) > 3 else "running_rededr"
        print(f"Adding a new scan: {filename} with EDR template: {edr_template_id}")

        if not os.path.exists(filename):
            print(f"Error: File {filename} does not exist")
            return
        with open(filename, "rb") as f:
            file_content = f.read()

        file_id = db_create_file(db, filename, file_content)
        scan_id = db_create_scan(db, file_id, edr_template=edr_template_id)
        print(f"Created test scan with ID: {scan_id}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

    db.close()

if __name__ == "__main__":
    main()
