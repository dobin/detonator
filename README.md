# Detonator

A modern malware analysis platform with FastAPI backend for REST services and Flask frontend with HTMX for interactive web interfaces. Automatically provisions Azure Windows 11 VMs for safe malware analysis.

## Architecture

- **FastAPI Backend** (Port 8000): RESTful API services with automatic documentation and Azure VM management
- **Flask Frontend** (Port 5000): Web interface using HTMX for dynamic interactions
- **Azure Integration**: Automatic Windows 11 VM provisioning for malware analysis
- **Poetry**: Dependency management and virtual environment

## Azure Setup

1. **Copy the environment template:**
   ```bash
   cp .env.template .env
   ```

2. **Configure Azure credentials in `.env`:**
   ```bash
   # Required
   AZURE_SUBSCRIPTION_ID=your-subscription-id-here
   AZURE_RESOURCE_GROUP=detonator-rg
   AZURE_LOCATION=East US
   
   # Optional (for service principal auth)
   AZURE_CLIENT_ID=your-client-id-here
   AZURE_CLIENT_SECRET=your-client-secret-here
   AZURE_TENANT_ID=your-tenant-id-here
   ```

3. **Authenticate with Azure:**
   ```bash
   # Using Azure CLI (recommended for development)
   az login
   
   # Or set up service principal credentials in .env file
   ```

4. **Create resource group (if it doesn't exist):**
   ```bash
   az group create --name detonator-rg --location "East US"
   ```

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

### Malware Analysis
- **Automated VM Provisioning**: Creates fresh Azure Windows 11 VMs for each scan
- **VM Lifecycle Management**: Automatically shuts down VMs after 1 minute
- **Resource Cleanup**: Removes all Azure resources after analysis
- **Status Monitoring**: Real-time VM status updates every 3 seconds

### Web Interface
- Modern, responsive UI with Tailwind CSS
- HTMX for seamless frontend interactions
- File upload and scan management
- Real-time scan status updates

### API Features
- CORS-enabled FastAPI backend
- Automatic API documentation with Swagger UI
- RESTful endpoints for file and scan management
- Background task monitoring

## VM Analysis Workflow

1. **Upload File**: Upload a file through the web interface or API
2. **VM Creation**: System automatically creates an Azure Windows 11 VM
3. **Analysis**: VM runs for exactly 1 minute for analysis
4. **Shutdown**: VM is automatically shut down after 1 minute
5. **Cleanup**: All Azure resources are cleaned up after 2 minutes total

## API Endpoints

### Files
- `POST /api/files` - Upload file only
- `POST /api/files/upload-and-scan` - Upload file and create scan with VM
- `GET /api/files` - List all files
- `GET /api/files/{id}` - Get file details with scans
- `DELETE /api/files/{id}` - Delete file and scans

### Scans
- `POST /api/files/{id}/scans` - Create scan (provisions VM)
- `GET /api/scans` - List all scans
- `GET /api/scans/{id}` - Get scan details
- `PUT /api/scans/{id}` - Update scan
- `POST /api/scans/{id}/shutdown-vm` - Manual VM shutdown

## Development

The project structure:
```
detonator/
├── detonator/
│   ├── fastapi_app.py      # FastAPI REST API with Azure integration
│   ├── flask_app.py        # Flask web server
│   ├── vm_manager.py       # Azure VM management
│   ├── vm_monitor.py       # Background VM monitoring
│   ├── database.py         # SQLAlchemy models
│   ├── schemas.py          # Pydantic models
│   ├── templates/          # HTML templates
│   └── __main__.py         # Main entry point
├── pyproject.toml          # Poetry configuration
├── .env.template           # Azure configuration template
└── start.sh               # Quick start script
```

## Security Considerations

- VMs are isolated in their own virtual networks
- Network security groups restrict access
- VMs are automatically destroyed after analysis
- Use Azure Key Vault for production credentials
- Monitor Azure costs and set spending limits

## Troubleshooting

### Azure Authentication Issues
- Ensure you're logged in: `az login`
- Check subscription access: `az account list`
- Verify service principal permissions

### VM Creation Failures
- Check Azure quotas and limits
- Verify resource group exists
- Ensure sufficient permissions in subscription

### Environment Variables
- Copy `.env.template` to `.env`
- Set `AZURE_SUBSCRIPTION_ID` (required)
- Configure other Azure settings as needed

Both servers run concurrently, with Flask proxying API requests to FastAPI and serving the web interface with HTMX enhancements. The system automatically manages Azure VMs for safe malware analysis with configurable timeout and cleanup.
