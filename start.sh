#!/bin/bash

echo "Installing dependencies with Poetry..."
poetry install

echo ""
echo "Starting Detonator servers..."
echo "FastAPI (REST API): http://localhost:8000"
echo "Flask (Web UI): http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop both servers"

poetry run python -m detonator both
