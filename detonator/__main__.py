#!/usr/bin/env python3

import sys
import subprocess
import threading
import time
import os
import uvicorn
import logging
import argparse

from detonatorui.flask_app import app as flask_app

from detonatorapi.logging_config import setup_logging
from detonatorapi.fastapi_app import app as fastapi_app
from detonatorapi.connectors.connectors import connectors


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
    
    if start_api:
        logger.info(f"Detonator API: {api_url}")
        # Start FastAPI in a separate thread
        log_level = "debug" if debug else "warning"
        def run_fastapi():
            uvicorn.run(fastapi_app, host=api_host, port=api_port, log_level=log_level)
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
