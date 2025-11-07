from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime
import logging

from detonatorapi.db_interface import db_scan_change_status_quick
from .database import get_db, File, Scan
from .schemas import ScanResponse, ScanUpdate, FileCreateScan, ScanResponseShort
from .connectors.azure_manager import get_azure_manager
from .db_interface import db_create_scan, db_get_profile_by_name, db_scan_add_log
from .utils import sanitize_runtime_seconds, sanitize_detection_window_minutes

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/scans/count")
async def get_scans_count(
    status: Optional[str] = Query(None, description="Filter by scan status"),
    project: Optional[str] = Query(None, description="Filter by project name (case-insensitive partial match)"),
    result: Optional[str] = Query(None, description="Filter by scan result"),
    search: Optional[str] = Query(None, description="Search in project, scan comment, file comment, or filename"),
    db: Session = Depends(get_db)
):
    """Get count of scans with filtering capabilities"""
    query = db.query(Scan).options(joinedload(Scan.file), joinedload(Scan.profile))
    
    # Apply filters (same as in get_scans)
    if status:
        query = query.filter(Scan.status == status)
    
    if project:
        query = query.filter(Scan.project.ilike(f"%{project}%"))
    
    if result:
        query = query.filter(Scan.result.ilike(f"%{result}%"))
    
    if search:
        # Search across multiple fields
        search_filter = or_(
            Scan.project.ilike(f"%{search}%"),
            Scan.comment.ilike(f"%{search}%"),
            Scan.file.has(File.filename.ilike(f"%{search}%")),
            Scan.file.has(File.comment.ilike(f"%{search}%"))
        )
        query = query.filter(search_filter)
    
    count = query.count()
    return {"count": count}


@router.get("/scans", response_model=List[ScanResponseShort])
async def get_scans(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    status: Optional[str] = Query(None, description="Filter by scan status"),
    project: Optional[str] = Query(None, description="Filter by project name (case-insensitive partial match)"),
    result: Optional[str] = Query(None, description="Filter by scan result"),
    search: Optional[str] = Query(None, description="Search in project, scan comment, file comment, or filename"),
    db: Session = Depends(get_db)
):
    """Get scans with filtering capabilities"""
    query = db.query(Scan).options(joinedload(Scan.file), joinedload(Scan.profile))
    
    # Apply filters
    if status:
        query = query.filter(Scan.status == status)
    
    if project:
        query = query.filter(Scan.project.ilike(f"%{project}%"))
    
    if result:
        query = query.filter(Scan.result.ilike(f"%{result}%"))
    
    if search:
        # Search across multiple fields
        search_filter = or_(
            Scan.project.ilike(f"%{search}%"),
            Scan.comment.ilike(f"%{search}%"),
            Scan.file.has(File.filename.ilike(f"%{search}%")),
            Scan.file.has(File.comment.ilike(f"%{search}%"))
        )
        query = query.filter(search_filter)
    
    # Order by ID descending (newest first) and apply pagination
    scans = query.order_by(Scan.id.desc()).offset(skip).limit(limit).all()

    # Scan overview need this information too
    for scan in scans:
        # workaround, there is always one line generated
        if len(scan.rededr_events) > 220:
            scan.has_rededr_events = True
        else:
            scan.has_rededr_events = False

    return scans


@router.get("/scans/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: int, db: Session = Depends(get_db)):
    """Get a specific scan with file information"""
    db_scan = db.query(Scan).options(joinedload(Scan.file), joinedload(Scan.profile)).filter(Scan.id == scan_id).first()
    if db_scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return db_scan


@router.put("/scans/{scan_id}", response_model=ScanResponse)
async def update_scan(scan_id: int, scan_update: ScanUpdate, db: Session = Depends(get_db)):
    """Update a scan"""
    db_scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if db_scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    # Update fields
    update_data = scan_update.dict(exclude_unset=True)
    if "runtime" in update_data:
        try:
            update_data["runtime"] = sanitize_runtime_seconds(update_data["runtime"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    for field, value in update_data.items():
        setattr(db_scan, field, value)
    
    db_scan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_scan)
    return db_scan


@router.post("/files/{file_id}/createscan", response_model=ScanResponse)
async def file_create_scan(file_id: int, scan_data: FileCreateScan, db: Session = Depends(get_db)):
    """Create a new scan for an existing file"""
    # Check if file exists
    db_file = db.query(File).filter(File.id == file_id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if allowed
    profile = db_get_profile_by_name(db, scan_data.profile_name)
    if not profile:
        raise HTTPException(status_code=400, detail="Profile not found")
    
    # Password check
    if len(profile.password) > 0:
        if not scan_data.password or scan_data.password != profile.password:
            raise HTTPException(status_code=403, detail="Invalid password for profile")

    # Extract data with defaults
    profile_name = scan_data.profile_name or ""
    comment = scan_data.comment or ""
    project = scan_data.project or ""
    try:
        runtime_override = sanitize_runtime_seconds(scan_data.runtime)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    runtime = runtime_override if runtime_override is not None else 10

    try:
        detection_window_override = sanitize_detection_window_minutes(scan_data.detection_window_minutes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    detection_window_minutes = detection_window_override if detection_window_override is not None else 10
    drop_path = scan_data.drop_path or ""
    
    if not profile_name:
        raise HTTPException(status_code=400, detail="Profile is required")
    
    # Create the scan
    scan_id = db_create_scan(
        db,
        file_id,
        profile_name,
        comment,
        project,
        runtime=runtime,
        drop_path=drop_path,
        detection_window_minutes=detection_window_minutes,
    )
    
    # Retrieve the created scan to return full details
    db_scan = db.query(Scan).options(joinedload(Scan.file), joinedload(Scan.profile)).filter(Scan.id == scan_id).first()
    return db_scan


@router.post("/scans/{scan_id}/shutdown-vm")
async def shutdown_vm_for_scan(scan_id: int, db: Session = Depends(get_db)):
    """Manually shutdown VM for a scan (for testing purposes)"""
    db_scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if db_scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    db_scan_change_status_quick(db, db_scan, "stop")
    return {"message": "VM shutdown initiated"}


@router.post("/scans/{scan_id}/rescan")
async def rescan(scan_id: int, db: Session = Depends(get_db)):
    """Rescan a scan that's in error status by resetting it to fresh status"""
    db_scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if db_scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    if db_scan.status != "error":
        raise HTTPException(status_code=400, detail=f"Can only rescan scans in 'error' status. Current status: {db_scan.status}")
    
    # Reset scan to fresh status
    db_scan.status = "fresh"
    db_scan.updated_at = datetime.utcnow()

    # and all the possile fields
    db_scan.detonator_srv_logs = ""
    db_scan.execution_logs = ""
    db_scan.agent_logs = ""
    db_scan.rededr_events = ""
    db_scan.edr_logs = ""
    db_scan.edr_summary = []
    db_scan.result = ""
    db_scan.completed_at = None
    db_scan.vm_exist = 0
    db_scan.vm_instance_name = None
    db_scan.vm_ip_address = None
    
    # Add log entry about the rescan
    log_message = f"[{datetime.utcnow().isoformat()}] Scan reset to 'fresh' status for rescanning"
    db_scan_add_log(db, db_scan, log_message)
    
    db.commit()
    db.refresh(db_scan)
    
    return {"message": "Scan status reset to 'fresh' for rescanning", "scan_id": scan_id, "status": db_scan.status}


@router.delete("/scans/{scan_id}")
async def delete_scan(scan_id: int, db: Session = Depends(get_db)):
    """Delete a specific scan"""
    db_scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if db_scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    db.delete(db_scan)
    db.commit()
    return {"message": "Scan deleted successfully"}
