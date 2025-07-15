from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import logging

from .database import get_db, File, Scan
from .schemas import FileResponse, FileWithScans, NewScanResponse
from .db_interface import db_create_file, db_create_scan

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/files", response_model=FileResponse)
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


@router.post("/files/upload-and-scan", response_model=NewScanResponse)
async def upload_file_and_scan(
    file: UploadFile = FastAPIFile(...),
    source_url: Optional[str] = Form(None),
    file_comment: Optional[str] = Form(None),
    scan_comment: Optional[str] = Form(None),
    project: Optional[str] = Form(None),
    profile: str = Form(None),
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


@router.get("/files", response_model=List[FileWithScans])
async def get_files(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all files with their scans"""
    files = db.query(File).options(joinedload(File.scans).joinedload(Scan.profile)).offset(skip).limit(limit).all()
    return files


@router.get("/files/{file_id}", response_model=FileWithScans)
async def get_file(file_id: int, db: Session = Depends(get_db)):
    """Get a specific file with its scans"""
    db_file = db.query(File).filter(File.id == file_id).options(joinedload(File.scans).joinedload(Scan.profile)).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    return db_file


@router.delete("/files/{file_id}")
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
