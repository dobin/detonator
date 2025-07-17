#!/usr/bin/env python3

import sys
import subprocess
import threading
import time
import os
import uvicorn
import logging

from detonatorui.flask_app import app as flask_app

from detonatorapi.logging_config import setup_logging
from detonatorapi.fastapi_app import app as fastapi_app
from detonatorapi.connectors.connectors import connectors


logger = logging.getLogger(__name__)


def main():
    setup_logging()
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m detonator both     # Run both FastAPI and Flask servers")
        print("  python -m detonator api      # Run only FastAPI server")
        print("  python -m detonator web      # Run only Flask server")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    debug = False

    ui_host = "0.0.0.0"
    ui_port = 5000
    ui_url = f"http://{ui_host}:{ui_port}"
    api_host = "0.0.0.0"
    api_port = 8000
    api_url = f"http://{api_host}:{api_port}"

    # Connectors init
    for connectorName, connector in connectors.get_all().items():
        if connector.init():
            logger.info(f"Connector: {connectorName}")
        else:
            logger.error(f"Failed to initialize connector: {connectorName}")
            sys.exit(1)

    logger.info(f"Detonator API: {api_url}")

    # Start FastAPI in a separate thread
    log_level = "debug" if debug else "warning"
    def run_fastapi():
        uvicorn.run(fastapi_app, host=api_host, port=api_port, log_level=log_level)
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    
    # Start UI in the main thread
    logger.info(f"Detonator UI : {ui_url}")
    try:
        flask_app.run(debug=debug, host=ui_host, port=ui_port, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("\nShutting down servers...")
        sys.exit(0)


if __name__ == "__main__":
    main()
