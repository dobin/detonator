from fastapi import FastAPI, Depends, HTTPException, UploadFile, File as FastAPIFile, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime
import logging
import os
from dotenv import load_dotenv

from .database import get_db, File, Scan
from .schemas import FileResponse, ScanResponse, FileWithScans, ScanCreate, ScanUpdate
from .vm_manager import initialize_vm_manager, get_vm_manager
from .vm_monitor import start_vm_monitoring
from .edr_templates import get_edr_template_manager
from .utils import mylog


# Setup logging - reduce verbosity for HTTP requests
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("fastapi").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(title="Detonator API", version="0.1.0")

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
        # Initialize VM manager with environment variables
        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        resource_group = os.getenv("AZURE_RESOURCE_GROUP", "detonator-rg")
        location = os.getenv("AZURE_LOCATION", "East US")
        
        if not subscription_id:
            logger.warning("AZURE_SUBSCRIPTION_ID not set - VM creation will not work")
        else:
            initialize_vm_manager(subscription_id, resource_group, location)
            logger.info("VM Manager initialized successfully")
        
        # Start VM monitoring
        start_vm_monitoring()
        logger.info("VM monitoring started")
        
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop VM monitoring on shutdown"""
    try:
        from .vm_monitor import stop_vm_monitoring
        await stop_vm_monitoring()
        logger.info("VM monitoring stopped")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")


@app.get("/api/edr-templates")
async def get_edr_templates():
    """Get available EDR templates"""
    edr_template_manager = get_edr_template_manager()
    templates = edr_template_manager.get_templates()
    return templates

@app.get("/")
async def root():
    return {"message": "Detonator API is running"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "detonator-api"}

# File endpoints
@app.post("/api/files", response_model=FileResponse)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    source_url: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload a file without automatically creating a scan"""
    # Read file content
    content = await file.read()
    file_hash = File.calculate_hash(content)
    
    # Check if file already exists
    existing_file = db.query(File).filter(File.file_hash == file_hash).first()
    if existing_file:
        raise HTTPException(status_code=400, detail="File with this hash already exists")
    
    # Create file record
    db_file = File(
        content=content,
        filename=file.filename,
        file_hash=file_hash,
        source_url=source_url,
        comment=comment
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    
    return db_file


@app.post("/api/files/upload-and-scan", response_model=FileResponse)
async def upload_file_and_scan(
    background_tasks: BackgroundTasks,
    file: UploadFile = FastAPIFile(...),
    source_url: Optional[str] = Form(None),
    file_comment: Optional[str] = Form(None),
    scan_comment: Optional[str] = Form(None),
    vm_template: Optional[str] = Form("Windows 11 Pro"),
    edr_template: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Upload a file and automatically create a scan with Azure VM"""
    # Debug file upload information
    actual_filename = file.filename

    # Read file content
    content = await file.read()
    file_hash = File.calculate_hash(content)

    logger.info(f"Uploading file: {actual_filename}, hash: {file_hash}")

    # DB: Create file record
    db_file = File(
        content=content,
        filename=actual_filename,
        file_hash=file_hash,
        source_url=source_url,
        comment=file_comment
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    logger.info(f"DB: Created file {db_file.id} with filename: {actual_filename}")

    # DB: Create scan record (auto-scan)
    db_scan = Scan(
        file_id=db_file.id,
        status="fresh",
        vm_status="none",
        vm_template=vm_template or "Windows 11 Pro",
        edr_template=edr_template,
        comment=scan_comment,
        detonator_srv_logs=mylog(f"DB: Scan created for file {actual_filename} (ID: {db_file.id})"),
    )
    db.add(db_scan)
    db.commit()
    db.refresh(db_scan)
    logger.info(f"DB: Created scan {db_scan.id}")

    # Azure: Create VM
    vm_manager = get_vm_manager()
    background_tasks.add_task(vm_manager.create_machine, db_scan.id)
    logger.info(f"Azure: Initiated VM creation for scan {db_scan.id}")
    
    return db_file


@app.get("/api/files", response_model=List[FileResponse])
async def get_files(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all files"""
    files = db.query(File).offset(skip).limit(limit).all()
    return files

@app.get("/api/files/{file_id}", response_model=FileWithScans)
async def get_file(file_id: int, db: Session = Depends(get_db)):
    """Get a specific file with its scans"""
    db_file = db.query(File).filter(File.id == file_id).first()
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
    scans = db.query(Scan).options(joinedload(Scan.file)).offset(skip).limit(limit).all()
    return scans

@app.get("/api/scans/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: int, db: Session = Depends(get_db)):
    """Get a specific scan with file information"""
    db_scan = db.query(Scan).options(joinedload(Scan.file)).filter(Scan.id == scan_id).first()
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

@app.post("/api/files/{file_id}/scans", response_model=ScanResponse)
async def create_scan(file_id: int, scan_data: ScanCreate, db: Session = Depends(get_db)):
    """Create a new scan for a file and automatically provision Azure Windows 11 VM"""
    # Check if file exists
    db_file = db.query(File).filter(File.id == file_id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Create scan record first
    db_scan = Scan(
        file_id=file_id, 
        **scan_data.dict(),
        status="initializing",
        vm_template="Windows 11 Pro"  # Set default template
    )
    db.add(db_scan)
    db.commit()
    db.refresh(db_scan)
    
    # Create Azure VM for the scan
    try:
        vm_manager = get_vm_manager()
        
        # Create VM with EDR template
        edr_template_id = db_scan.edr_template
        vm_info = await vm_manager.create_machine(db_scan.id, edr_template_id)
        
        # Update scan with VM information
        db_scan.vm_instance_name = vm_info["vm_name"]
        db_scan.vm_ip_address = vm_info["public_ip"]
        db_scan.status = "started"
        db_scan.vm_status = "creating"
        
        # Log VM creation
        creation_log = f"[{datetime.utcnow().isoformat()}] Azure Windows 11 VM creation initiated\n"
        creation_log += f"VM Name: {vm_info['vm_name']}\n"
        creation_log += f"Public IP: {vm_info['public_ip']}\n"
        creation_log += f"EDR Template: {edr_template_id or 'None'}\n"
        if vm_info.get("edr_template_info"):
            template_info = vm_info["edr_template_info"]
            creation_log += f"Template Description: {template_info.get('description', 'N/A')}\n"
            creation_log += f"Template Ports: {template_info.get('ports', [])}\n"
        creation_log += f"Status: {vm_info['status']}\n"
        db_scan.detonator_srv_logs = creation_log  # first log entry
        
        db.commit()
        db.refresh(db_scan)
        
        logger.info(f"Created scan {db_scan.id} with Azure VM {vm_info['vm_name']}")
        
    except Exception as e:
        logger.error(f"Failed to create VM for scan {db_scan.id}: {str(e)}")
        
        # Update scan status to reflect error
        db_scan.status = "vm_creation_failed"
        error_log = f"[{datetime.utcnow().isoformat()}] VM creation failed: {str(e)}\n"
        db_scan.detonator_srv_logs = error_log
        db.commit()
        
        # Still return the scan, but with error status
        # Don't raise HTTPException to allow user to see the scan record
    
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
        vm_manager = get_vm_manager()
        shutdown_success = await vm_manager.shutdown_vm(db_scan.vm_instance_name)
        
        if shutdown_success:
            db_scan.status = "completed"
            db_scan.vm_status = "removed"
            db_scan.detonator_srv_logs += f"Manual VM shutdown initiated\n"
        else:
            db_scan.status = "completed"
            db_scan.vm_status = "remove_failed"
            db_scan.detonator_srv_logs += f"Manual VM shutdown failed\n"
        db.commit()
        
        return {"message": "VM shutdown initiated" if shutdown_success else "VM shutdown failed"}
        
    except Exception as e:
        logger.error(f"Error shutting down VM for scan {scan_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to shutdown VM: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
