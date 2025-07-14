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
from detonatorapi.connectors.azure_manager import initialize_azure_manager
from detonatorapi.db_interface import db_create_file, db_create_scan, db_get_profile_id_by_name
from detonatorapi.fastapi_app import app as fastapi_app
from detonatorui.flask_app import app as flask_app
from detonatorapi.vm_monitor import vm_monitor, VMMonitorTask
from detonatorapi.database import get_db, get_db_for_thread

from detonatorapi.settings import AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, AZURE_LOCATION


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
    if not AZURE_SUBSCRIPTION_ID or AZURE_SUBSCRIPTION_ID == "":
        logger.warning("AZURE_SUBSCRIPTION_ID not set - VM creation will not work")
    else:
        initialize_azure_manager(AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, AZURE_LOCATION)
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
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

    db.close()

if __name__ == "__main__":
    main()
