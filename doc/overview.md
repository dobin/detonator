# Overview - Claude Generated

## Architecture

- **FastAPI Backend** (Port 8000): RESTful API services with automatic documentation and Azure VM management
- **Flask Frontend** (Port 5000): Web interface using HTMX for dynamic interactions
- **Azure Integration**: Automatic Windows 11 VM provisioning for malware analysis
- **Poetry**: Dependency management and virtual environment



## Access

- **Web Interface**: http://localhost:5000
- **API Documentation**: http://localhost:8000/docs
- **API Redoc**: http://localhost:8000/redoc


## Features

### Malware Analysis
- **Automated VM Provisioning**: Creates fresh Azure Windows 11 VMs for each scan
- **EDR Template Support**: Choose from pre-configured deployment scripts (OpenSSH, Sysmon, Windows Defender, etc.)
- **VM Lifecycle Management**: Automatically shuts down VMs after 1 minute
- **Database-driven Monitoring**: VM monitoring uses database as source of truth, no manual tracking required
- **Resource Cleanup**: Removes all Azure resources after analysis
- **Status Monitoring**: Real-time VM status updates every 3 seconds



## VM Analysis Workflow

1. **Upload File**: Upload a file through the web interface or API
2. **Select EDR Template**: Choose deployment script (OpenSSH, Sysmon, Windows Defender, etc.)
3. **VM Creation**: System automatically creates an Azure Windows 11 VM with selected tools
4. **Analysis**: VM runs for exactly 1 minute for analysis
5. **Monitoring**: System automatically monitors VM status via database queries
6. **Shutdown**: VM is automatically shut down after 1 minute
7. **Cleanup**: All Azure resources are cleaned up after 2 minutes total

## API Endpoints

### Files
- `POST /api/files` - Upload file only
- `POST /api/upload-and-scan` - Upload file and create scan with VM
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