# Detonator

A modern web application with FastAPI backend for REST services and Flask frontend with HTMX for interactive web interfaces.

## Architecture

- **FastAPI Backend** (Port 8000): RESTful API services with automatic documentation
- **Flask Frontend** (Port 5000): Web interface using HTMX for dynamic interactions
- **Poetry**: Dependency management and virtual environment

## Quick Start

### Using the start script:
```bash
./start.sh
```

### Manual start:
```bash
# Install dependencies
poetry install

# Run both servers
poetry run python -m detonator both

# Or run individually:
poetry run python -m detonator api   # FastAPI only
poetry run python -m detonator web   # Flask only
```

## Access

- **Web Interface**: http://localhost:5000
- **API Documentation**: http://localhost:8000/docs
- **API Redoc**: http://localhost:8000/redoc

## Features

- Modern, responsive UI with Tailwind CSS
- HTMX for seamless frontend interactions
- CORS-enabled FastAPI backend
- Automatic API documentation with Swagger UI
- Easy development setup with Poetry

## Development

The project structure:
```
detonator/
├── detonator/
│   ├── fastapi_app.py      # FastAPI REST API
│   ├── flask_app.py        # Flask web server
│   ├── templates/          # HTML templates
│   └── __main__.py         # Main entry point
├── pyproject.toml          # Poetry configuration
└── start.sh               # Quick start script
```

Both servers run concurrently, with Flask proxying API requests to FastAPI and serving the web interface with HTMX enhancements.
