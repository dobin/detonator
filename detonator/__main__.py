#!/usr/bin/env python3

import sys
import subprocess
import threading
import time
import os
import uvicorn
import logging
import argparse
import requests

from detonatorui.flask_app import app as flask_app

from detonatorapi.logging_config import setup_logging
from detonatorapi.fastapi_app import app as fastapi_app
from detonatorapi.connectors.connectors import connectors

from detonatorapi.settings import CORS_ALLOW_ORIGINS
from detonatorui.config import API_BASE_URL

from detonatorapi.database import get_db_direct
from detonatorapi.db_interface import db_list_profiles

logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Detonator - Run FastAPI and/or Flask servers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python -m detonator                          # Run both servers with defaults
  python -m detonator api                      # Run only API server
  python -m detonator web                      # Run only web server
  python -m detonator both --debug             # Run both with debug enabled
  python -m detonator api --api-port 9000     # Run API on port 9000
  python -m detonator web --web-host 127.0.0.1 --web-port 3000
  python -m detonator both --api-host 127.0.0.1 --api-port 9000 --web-port 3000"""
    )
    
    parser.add_argument(
        'mode', 
        nargs='?', 
        choices=['both', 'api', 'web'], 
        default='both',
        help='Server mode: both (default), api only, or web only'
    )
    
    parser.add_argument(
        '--debug', 
        action='store_true',
        help='Enable debug mode'
    )
    
    # API server options
    parser.add_argument(
        '--api-host',
        default='0.0.0.0',
        help='API server host (default: 0.0.0.0)'
    )
    
    parser.add_argument(
        '--api-port',
        type=int,
        default=8000,
        help='API server port (default: 8000)'
    )
    
    # Web server options
    parser.add_argument(
        '--web-host',
        default='0.0.0.0',
        help='Web server host (default: 0.0.0.0)'
    )
    
    parser.add_argument(
        '--web-port',
        type=int,
        default=5000,
        help='Web server port (default: 5000)'
    )
    
    return parser.parse_args()

def print_cors_help():
    """Print helpful information about CORS configuration."""
    print("\n" + "="*70)
    print("⚠️  CORS CONFIGURATION")
    print("="*70)
    print(f"\nThe Browser UI JavaScript will attempt to connect to the API:")
    print(f"  - {API_BASE_URL}")
    print(f"")
    print(f"Where the API current CORS allowed value:")
    print(f"  - {CORS_ALLOW_ORIGINS}")
    print(f"")
    print(f"To change CORS settings:")
    print(f"  Option A - Environment variable:")
    print(f"    export DETONATOR_CORS_ORIGINS='http://detonator.r00ted.ch'")
    print(f"  Option B - Edit detonatorapi/settings.py:")
    print(f"    CORS_ALLOW_ORIGINS = [ 'http://detonator.r00ted.ch' ] ")
    print("\n" + "="*70 + "\n")


def main():
    setup_logging()
    args = parse_arguments()
    
    # Set debug mode
    debug = args.debug

    # Server configuration
    ui_host = args.web_host
    ui_port = args.web_port
    ui_url = f"http://{ui_host}:{ui_port}"
    api_host = args.api_host
    api_port = args.api_port
    api_url = f"http://{api_host}:{api_port}"

    # Connectors init
    for connectorName, connector in connectors.get_all().items():
        if connector.init():
            logger.info(f"Connector: {connectorName}")
        else:
            logger.error(f"Failed to initialize connector: {connectorName}")
            sys.exit(1)

    # Determine what to start based on mode
    start_api = args.mode in ['both', 'api']
    start_web = args.mode in ['both', 'web']
    
    fastapi_thread = None
    print_cors_help()

    # check if we have a profile with data.edr_mde configured
    db = get_db_direct()
    profiles = db_list_profiles(db)
    mde_configured = None
    for profile in profiles:
        if profile.data and "edr_mde" in profile.data:
            mde_configured = profile.name
            break
    db.close()

    if mde_configured:
        secret = os.getenv("MDE_AZURE_CLIENT_SECRET")
        if not secret or secret.strip() == "":
            logger.error(f"MDE configuration detected in profile \"{mde_configured}\", but MDE_AZURE_CLIENT_SECRET environment variable is not set")
            sys.exit(1)
        

    
    if start_api:
        logger.info(f"Detonator API: {api_url}")
        # Start FastAPI in a separate thread
        log_level = "debug" if debug else "warning"
        def run_fastapi():
            uvicorn.run(fastapi_app, host=api_host, port=api_port, log_level="warning")
        fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
        fastapi_thread.start()
    if start_web:
        # Start UI in the main thread
        logger.info(f"Detonator UI : {ui_url}")
        try:
            flask_app.run(debug=debug, host=ui_host, port=ui_port, use_reloader=False)
        except KeyboardInterrupt:
            logger.info("\nShutting down servers...")
            sys.exit(0)
    elif start_api:
        # If only API is running, keep the main thread alive
        logger.info("Running API server only. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\nShutting down API server...")
            sys.exit(0)


if __name__ == "__main__":
    main()
