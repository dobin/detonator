from fastapi import FastAPI, Depends, HTTPException, UploadFile, File as FastAPIFile, Form, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime
import logging
import os
from dotenv import load_dotenv
import requests

from .database import get_db, File, Scan, Profile
from .schemas import FileResponse, ScanResponse, FileWithScans, FileCreateScan, ScanUpdate, NewScanResponse, ProfileCreate, ProfileUpdate, ProfileResponse, ProfileStatusResponse
from .connectors.azure_manager import get_azure_manager
from .vm_monitor import start_vm_monitoring, stop_vm_monitoring, connectors
from .utils import mylog
from .db_interface import db_create_file, db_create_scan, db_list_profiles, db_create_profile, db_get_profile_by_id

# Load environment variables
load_dotenv()

# Configuration
READ_ONLY_MODE = os.getenv("DETONATOR_READ_ONLY", "false").lower() in ("true", "1", "yes", "on")

# Setup logging - reduce verbosity for HTTP requests
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("fastapi").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

if READ_ONLY_MODE:
    logger.warning("🔒 DETONATOR RUNNING IN READ-ONLY MODE - All write operations are disabled")

app = FastAPI(title="Detonator API", version="0.1.0")


# Read-only mode middleware
# Instead of authentication LOL
@app.middleware("http")
async def read_only_middleware(request: Request, call_next):
    if READ_ONLY_MODE and request.method not in ["GET", "HEAD", "OPTIONS"]:
        # Allow exception for upload_file_and_scan endpoint
        if request.url.path == "/api/files/upload-and-scan" and request.method == "POST":
            # This endpoint is allowed even in read-only mode
            pass
        else:
            return JSONResponse(
                status_code=403,
                content={"detail": "Server is running in read-only mode. Write operations are not permitted."}
            )
    response = await call_next(request)
    return response


# Add CORS middleware to allow requests from Flask frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000"],  # Flask will run on port 5000
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize VM manager and start monitoring on startup"""
    try:
        # Start VM monitoring
        start_vm_monitoring()
        logger.info("VM monitoring started")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop VM monitoring on shutdown"""
    try:
        stop_vm_monitoring()
        logger.info("VM monitoring stopped")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")


@app.get("/api/profiles")
async def get_profiles(db: Session = Depends(get_db)):
    """Get available profiles"""
    profiles = db_list_profiles(db)
    # Convert to dict format similar to old templates
    result = {}
    for profile in profiles:
        result[profile.name] = {
            "id": profile.id,
            "connector": profile.connector,
            "port": profile.port,
            "edr_collector": profile.edr_collector,
            "comment": profile.comment,
            "data": profile.data
        }
    return result

@app.get("/api/connectors")
async def get_connectors():
    """Get available connector types with descriptions"""
    conns = {}
    for name, connector in connectors.get_all().items():
        conns[name] = {
            "name": name,
            "description": connector.get_description(),
            "comment": connector.get_comment(),
            "sample_data": connector.get_sample_data()
        }
    return conns

@app.get("/")
async def root():
    return {"message": "Detonator API is running"}

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": "detonator-api",
        "read_only_mode": READ_ONLY_MODE
    }


# File endpoints
@app.post("/api/files", response_model=FileResponse)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    source_url: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload a file without automatically creating a scan"""

    actual_filename = file.filename
    if not actual_filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty")
    # Read file content
    content = await file.read()
    file_id = db_create_file(db, actual_filename, content, source_url or "", comment or "")

    db_file = db.query(File).filter(File.id == file_id).options(joinedload(File.scans)).first()
    
    return db_file


@app.post("/api/files/upload-and-scan", response_model=NewScanResponse)
async def upload_file_and_scan(
    file: UploadFile = FastAPIFile(...),
    source_url: Optional[str] = Form(None),
    file_comment: Optional[str] = Form(None),
    scan_comment: Optional[str] = Form(None),
    project: Optional[str] = Form(None),
    profile: Optional[str] = Form(None),
    runtime: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    """Upload a file and automatically create a scan with Azure VM"""
    
    # DB: Create File
    actual_filename = file.filename
    if not actual_filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty")
    logger.info(f"Uploading file: {actual_filename}")

    content = await file.read()
    file_id = db_create_file(db, actual_filename, content, source_url or "", file_comment or "")

    # DB: Create scan record (auto-scan)
    if profile:
        scan_id = db_create_scan(db, file_id, profile, scan_comment or "", project or "", runtime or 10)
    else:
        raise HTTPException(status_code=400, detail="Profile is required")

    data = { 
        "file_id": file_id,
        "scan_id": scan_id,
    }

    return data


@app.get("/api/files", response_model=List[FileWithScans])
async def get_files(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all files with their scans"""
    files = db.query(File).options(joinedload(File.scans).joinedload(Scan.profile)).offset(skip).limit(limit).all()
    return files

@app.get("/api/files/{file_id}", response_model=FileWithScans)
async def get_file(file_id: int, db: Session = Depends(get_db)):
    """Get a specific file with its scans"""
    db_file = db.query(File).filter(File.id == file_id).options(joinedload(File.scans).joinedload(Scan.profile)).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    return db_file

@app.delete("/api/files/{file_id}")
async def delete_file(file_id: int, db: Session = Depends(get_db)):
    """Delete a file and all its scans"""
    db_file = db.query(File).filter(File.id == file_id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete associated scans first
    db.query(Scan).filter(Scan.file_id == file_id).delete()
    db.delete(db_file)
    db.commit()
    return {"message": "File deleted successfully"}

# Scan endpoints
@app.get("/api/scans", response_model=List[ScanResponse])
async def get_scans(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all scans with file information"""
    scans = db.query(Scan).options(joinedload(Scan.file), joinedload(Scan.profile)).offset(skip).limit(limit).all()
    return scans

@app.get("/api/scans/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: int, db: Session = Depends(get_db)):
    """Get a specific scan with file information"""
    db_scan = db.query(Scan).options(joinedload(Scan.file), joinedload(Scan.profile)).filter(Scan.id == scan_id).first()
    if db_scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return db_scan

@app.put("/api/scans/{scan_id}", response_model=ScanResponse)
async def update_scan(scan_id: int, scan_update: ScanUpdate, db: Session = Depends(get_db)):
    """Update a scan"""
    db_scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if db_scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Update fields
    for field, value in scan_update.dict(exclude_unset=True).items():
        setattr(db_scan, field, value)
    
    db_scan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_scan)
    return db_scan

@app.post("/api/files/{file_id}/createscan", response_model=ScanResponse)
async def file_create_scan(file_id: int, scan_data: FileCreateScan, db: Session = Depends(get_db)):
    """Create a new scan for a file and automatically provision Azure Windows 11 VM"""
    # Check if file exists
    db_file = db.query(File).filter(File.id == file_id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Extract data with defaults
    profile_name = scan_data.profile_name or ""
    comment = scan_data.comment or ""
    project = scan_data.project or ""
    runtime = scan_data.runtime or 10
    
    if not profile_name:
        raise HTTPException(status_code=400, detail="Profile is required")
    
    # Create the scan
    scan_id = db_create_scan(db, file_id, profile_name, comment, project, runtime=runtime)
    
    # Retrieve the created scan to return full details
    db_scan = db.query(Scan).options(joinedload(Scan.file), joinedload(Scan.profile)).filter(Scan.id == scan_id).first()
    return db_scan


@app.post("/api/scans/{scan_id}/shutdown-vm")
async def shutdown_vm_for_scan(scan_id: int, db: Session = Depends(get_db)):
    """Manually shutdown VM for a scan (for testing purposes)"""
    db_scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if db_scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    if not db_scan.vm_instance_name:
        raise HTTPException(status_code=400, detail="No VM associated with this scan")
    
    try:
        azure_manager = get_azure_manager()
        if not azure_manager:
            return {"message": "Azure not configured"}
        shutdown_success = azure_manager.shutdown_vm(db_scan.vm_instance_name)
        
        if shutdown_success:
            db_scan.detonator_srv_logs += f"Manual VM shutdown initiated\n"
        else:
            db_scan.detonator_srv_logs += f"Manual VM shutdown failed\n"
        db.commit()
        
        return {"message": "VM shutdown initiated" if shutdown_success else "VM shutdown failed"}
        
    except Exception as e:
        logger.error(f"Error shutting down VM for scan {scan_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to shutdown VM: {str(e)}")


@app.delete("/api/scans/{scan_id}")
async def delete_scan(scan_id: int, db: Session = Depends(get_db)):
    """Delete a specific scan"""
    db_scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if db_scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # If scan has a VM running, attempt to shut it down first
    if db_scan.vm_instance_name and db_scan.status == "running":
        try:
            azure_manager = get_azure_manager()
            if azure_manager:
                azure_manager.shutdown_vm(db_scan.vm_instance_name)
        except Exception as e:
            logger.warning(f"Failed to shutdown VM {db_scan.vm_instance_name} when deleting scan {scan_id}: {str(e)}")
    
    db.delete(db_scan)
    db.commit()
    return {"message": "Scan deleted successfully"}


# VM management endpoints
@app.get("/api/vms")
async def get_vms():
    """Get all VMs in the resource group"""
    try:
        azure_manager = get_azure_manager()
        if not azure_manager:
            return {}
        vms = azure_manager.list_all_vms()
        return vms
    except Exception as e:
        logger.error(f"Error getting VMs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get VMs: {str(e)}")


@app.delete("/api/vms/{vm_name}")
async def delete_vm(vm_name: str, background_tasks: BackgroundTasks):
    """Stop and delete a VM and all its resources"""
    try:
        azure_manager = get_azure_manager()
        if not azure_manager:
            return {"message": f"Azure not configured"}
        # Run deletion in background to avoid blocking
        background_tasks.add_task(azure_manager.stop_and_delete_vm, vm_name)
        return {"message": f"VM {vm_name} deletion initiated"}
    except Exception as e:
        logger.error(f"Error deleting VM {vm_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete VM: {str(e)}")


@app.post("/api/profiles")
async def create_profile(
    name: str = Form(...),
    connector: str = Form(...),
    port: int = Form(...),
    edr_collector: Optional[str] = Form(""),
    comment: Optional[str] = Form(""),
    data: str = Form(...),
    db: Session = Depends(get_db)
):
    """Create a new profile"""
    try:
        # Parse JSON data
        import json
        try:
            data_dict = json.loads(data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in data field")
        
        # Check if profile name already exists
        existing_profile = db.query(Profile).filter(Profile.name == name).first()
        if existing_profile:
            raise HTTPException(status_code=400, detail=f"Profile with name '{name}' already exists")
        
        # Create the profile
        profile_id = db_create_profile(
            db=db,
            name=name,
            connector=connector,
            port=port,
            edr_collector=edr_collector or "",
            data=data_dict,
            comment=comment or ""
        )
        
        # Return the created profile
        created_profile = db.query(Profile).filter(Profile.id == profile_id).first()
        if not created_profile:
            raise HTTPException(status_code=500, detail="Failed to retrieve created profile")
            
        return {
            "id": created_profile.id,
            "name": created_profile.name,
            "connector": created_profile.connector,
            "port": created_profile.port,
            "edr_collector": created_profile.edr_collector,
            "comment": created_profile.comment,
            "data": created_profile.data,
            "created_at": created_profile.created_at
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create profile: {str(e)}")

@app.get("/api/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: int, db: Session = Depends(get_db)):
    """Get a specific profile by ID"""
    db_profile = db_get_profile_by_id(db, profile_id)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return db_profile


@app.get("/api/profiles/{profile_id}/status", response_model=ProfileStatusResponse)
async def get_profile_status(profile_id: int, db: Session = Depends(get_db)):
    db_profile = db_get_profile_by_id(db, profile_id)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    is_available = ""

    ip = db_profile.data.get('ip', '')
    port = db_profile.port
    if ip == "" or port == 0:
        is_available = ""
    else:
        port = db_profile.port
        try:
            url = f"http://{ip}:{port}"
            test_response = requests.get(url, timeout=0.5)
            is_available = "true"
        except:
            is_available = "false"

    return {
        "id": db_profile.id,
        "ip": ip,
        "port": port,
        "is_available": is_available
    }


@app.put("/api/profiles/{profile_id}")
async def update_profile(
    profile_id: int,
    name: str = Form(...),
    connector: str = Form(...),
    port: int = Form(...),
    edr_collector: str = Form(...),
    comment: str = Form(""),
    data: str = Form(...),
    db: Session = Depends(get_db)
):
    """Update a profile"""
    try:
        # Find the profile
        profile = db.query(Profile).filter(Profile.id == profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # Parse JSON data
        import json
        try:
            data_dict = json.loads(data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in data field")
        
        # Check if new name conflicts with existing profile (excluding current one)
        if name != profile.name:
            existing = db.query(Profile).filter(Profile.name == name, Profile.id != profile_id).first()
            if existing:
                raise HTTPException(status_code=400, detail=f"Profile with name '{name}' already exists")
        
        # Update fields
        profile.name = name
        profile.connector = connector
        profile.port = port
        profile.edr_collector = edr_collector
        profile.comment = comment
        profile.data = data_dict
        
        db.commit()
        db.refresh(profile)
        
        return {
            "id": profile.id,
            "name": profile.name,
            "connector": profile.connector,
            "port": profile.port,
            "edr_collector": profile.edr_collector,
            "comment": profile.comment,
            "data": profile.data,
            "created_at": profile.created_at
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating profile {profile_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")

@app.delete("/api/profiles/{profile_id}")
async def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    """Delete a profile"""
    db_profile = db_get_profile_by_id(db, profile_id)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Check if profile is being used by any scans
    scans_using_profile = db.query(Scan).filter(Scan.profile_id == profile_id).count()
    if scans_using_profile > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete profile: {scans_using_profile} scans are using this profile")
    
    db.delete(db_profile)
    db.commit()
    return {"message": f"Profile '{db_profile.name}' deleted successfully"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
