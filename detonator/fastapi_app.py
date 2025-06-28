from fastapi import FastAPI, Depends, HTTPException, UploadFile, File as FastAPIFile, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from .database import get_db, File, Scan
from .schemas import FileResponse, ScanResponse, FileWithScans, ScanCreate, ScanUpdate

app = FastAPI(title="Detonator API", version="0.1.0")

# Add CORS middleware to allow requests from Flask frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000"],  # Flask will run on port 5000
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    """Upload a file and automatically create a scan"""
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
    
    # Automatically create a scan with status "fresh"
    db_scan = Scan(
        file_id=db_file.id,
        status="fresh"
    )
    db.add(db_scan)
    db.commit()
    
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
    """Get all scans"""
    scans = db.query(Scan).offset(skip).limit(limit).all()
    return scans

@app.get("/api/scans/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: int, db: Session = Depends(get_db)):
    """Get a specific scan"""
    db_scan = db.query(Scan).filter(Scan.id == scan_id).first()
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
    """Create a new scan for a file"""
    # Check if file exists
    db_file = db.query(File).filter(File.id == file_id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    db_scan = Scan(file_id=file_id, **scan_data.dict())
    db.add(db_scan)
    db.commit()
    db.refresh(db_scan)
    return db_scan

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
