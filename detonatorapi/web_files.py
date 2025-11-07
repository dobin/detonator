from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Form, Header, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import logging
import os

from .database import get_db, File, Scan
from .schemas import FileResponse, FileWithScans
from .db_interface import db_create_file, db_create_scan, db_get_profile_by_name
from .token_auth import require_auth, get_user_from_request
from .settings import UPLOAD_DIR

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/files", response_model=FileResponse)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    source_url: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    exec_arguments: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Upload a file without automatically creating a scan"""

    actual_filename = file.filename
    if not actual_filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty")
    # Read file content
    content = await file.read()
    file_id = db_create_file(db, actual_filename, content, source_url or "", comment or "", exec_arguments or "")

    db_file = db.query(File).filter(File.id == file_id).options(joinedload(File.scans)).first()
    
    return db_file


@router.get("/files", response_model=List[FileWithScans])
async def get_files(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all files with their scans"""
    files = db.query(File).options(joinedload(File.scans).joinedload(Scan.profile)).offset(skip).limit(limit).all()
    
    # Filter by user if guest
    user = get_user_from_request(request)
    if user == "guest":
        files = [f for f in files if f.user == "guest"]
    
    return files


@router.get("/files/{file_id}", response_model=FileWithScans)
async def get_file(file_id: int, request: Request, db: Session = Depends(get_db)):
    """Get a specific file with its scans"""
    db_file = db.query(File).filter(File.id == file_id).options(joinedload(File.scans).joinedload(Scan.profile)).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if user has access to this file
    user = get_user_from_request(request)
    if user == "guest" and db_file.user != "guest":
        raise HTTPException(status_code=404, detail="File not found")
    
    return db_file


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Delete a file and all its scans"""
    db_file = db.query(File).filter(File.id == file_id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete file from filesystem
    file_path = os.path.join(UPLOAD_DIR, db_file.filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"Deleted file from disk: {file_path}")
        except Exception as e:
            logger.error(f"Failed to delete file from disk: {file_path}, error: {e}")
    
    # Delete associated scans first
    db.query(Scan).filter(Scan.file_id == file_id).delete()
    db.delete(db_file)
    db.commit()
    return {"message": "File deleted successfully"}


@router.post("/files/{file_id}/download")
async def download_file(
    file_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Download a file (requires authentication)"""
    db_file = db.query(File).filter(File.id == file_id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if file exists on disk
    file_path = os.path.join(UPLOAD_DIR, db_file.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Read file content from disk
    with open(file_path, 'rb') as f:
        content = f.read()
    
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={db_file.filename}"
        }
    )
