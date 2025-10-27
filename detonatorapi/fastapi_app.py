from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import logging

from .database import get_db, Profile
from .schemas import  NewScanResponse
from .db_interface import db_create_file, db_create_scan, db_get_profile_by_name
from .token_auth import tokenAuth

from .vm_monitor import start_vm_monitoring, stop_vm_monitoring
from .web_files import router as files_router
from .web_scans import router as scans_router
from .web_vms import router as vms_router
from .web_profiles import router as profiles_router
from .settings import CORS_ALLOW_ORIGINS


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
        if request.url.path == "/api/upload-and-scan" and request.method == "POST":
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
    allow_origins=CORS_ALLOW_ORIGINS,
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
    except Exception as e:
        logger.error(f"Error during starting vm_monitoring: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop VM monitoring on shutdown"""
    try:
        stop_vm_monitoring()
        logger.info("VM monitoring stopped")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")


# Include routers
app.include_router(files_router, prefix="/api")
app.include_router(scans_router, prefix="/api") 
app.include_router(vms_router, prefix="/api")
app.include_router(profiles_router, prefix="/api")


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


@app.get("/api/connectors")
async def get_connectors():
    """Get available connector types with descriptions"""
    from .vm_monitor import connectors
    conns = {}
    for name, connector in connectors.get_all().items():
        conns[name] = {
            "name": name,
            "description": connector.get_description(),
            "comment": connector.get_comment(),
            "sample_data": connector.get_sample_data()
        }
    return conns


@app.post("/api/upload-and-scan", response_model=NewScanResponse)
async def upload_file_and_scan(
    file: UploadFile = FastAPIFile(...),
    source_url: Optional[str] = Form(None),
    file_comment: Optional[str] = Form(None),
    scan_comment: Optional[str] = Form(None),
    project: Optional[str] = Form(None),
    profile_name: str = Form(...),
    password: Optional[str] = Form(None),
    runtime: Optional[int] = Form(None),
    drop_path: Optional[str] = Form(None),
    exec_arguments: Optional[str] = Form(None),
    token: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # Check if allowed: token
    permissions = tokenAuth.get_permissions(token)
    if permissions.is_anonymous:
        logger.info("User: anonymous")
        runtime = 12
    else:
        logger.info("User: authenticated")

    # Check if allowed: profile password
    profile: Profile = db_get_profile_by_name(db, profile_name)
    if not profile:
        raise HTTPException(status_code=400, detail=f"Profile not found: {profile_name}")
    if len(profile.password) > 0:
        if not password or password != profile.password:
            raise HTTPException(status_code=400, detail="Invalid password for profile")

    # DB: Create File
    actual_filename = file.filename
    if not actual_filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty")
    logger.info(f"Uploading file: {actual_filename}")
    file_content = await file.read()
    file_id = db_create_file(db, actual_filename, file_content, source_url or "", file_comment or "", exec_arguments or "")

    # DB: Create scan record (auto-scan)
    scan_id = db_create_scan(db, file_id, profile_name, scan_comment or "", project or "", runtime or 10, drop_path or "")

    data = { 
        "file_id": file_id,
        "scan_id": scan_id,
    }

    return data


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
