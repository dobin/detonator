from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from .database import get_db, Profile
from .schemas import  NewScanResponse
from .db_interface import db_create_file, db_create_scan, db_get_profile_by_name
from .token_auth import require_auth, get_user_from_request
from .vm_monitor import start_vm_monitoring, stop_vm_monitoring
from .alert_monitor import start_alert_monitoring, stop_alert_monitoring
from .web_files import router as files_router
from .web_scans import router as scans_router
from .web_vms import router as vms_router
from .web_profiles import router as profiles_router
from .settings import CORS_ALLOW_ORIGINS, AUTH_PASSWORD
from .utils import sanitize_runtime_seconds, sanitize_detection_window_minutes


# Load environment variables
load_dotenv()

# Setup logging - reduce verbosity for HTTP requests
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("fastapi").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(title="Detonator API", version="0.1.0")


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
        start_alert_monitoring()
    except Exception as e:
        logger.error(f"Error during starting vm_monitoring: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop VM monitoring on shutdown"""
    try:
        stop_vm_monitoring()
        stop_alert_monitoring()
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
        "auth_enabled": bool(AUTH_PASSWORD)
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
    request: Request,
    file: UploadFile = FastAPIFile(...),
    source_url: Optional[str] = Form(None),
    file_comment: Optional[str] = Form(None),
    scan_comment: Optional[str] = Form(None),
    project: Optional[str] = Form(None),
    profile_name: str = Form(...),
    password: Optional[str] = Form(None),
    runtime: Optional[int] = Form(None),
    drop_path: Optional[str] = Form(None),
    detection_window_minutes: Optional[int] = Form(None),
    exec_arguments: Optional[str] = Form(None),
    token: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # Determine user status based on authentication
    user = get_user_from_request(request)
    logger.info(f"User: {user}")
    if user == "guest":
        logger.info("Guest user")
        runtime = 12

    try:
        runtime = sanitize_runtime_seconds(runtime)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        detection_window_minutes = sanitize_detection_window_minutes(detection_window_minutes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    detection_window_minutes = detection_window_minutes if detection_window_minutes is not None else 1

    # Check if allowed: profile password
    profile: Profile = db_get_profile_by_name(db, profile_name)
    if not profile:
        raise HTTPException(status_code=400, detail=f"Profile not found: {profile_name}")
    if len(profile.password) > 0:
        if not password or password != profile.password:
            raise HTTPException(status_code=400, detail="Invalid password for profile")

    # DB: Create File
    # Prepend 4 random chars to filename to avoid collisions
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty")
    file_content = await file.read()
    file_id = db_create_file(db, 
                             filename=filename, 
                             content=file_content, 
                             source_url=source_url or "", 
                             comment=file_comment or "", 
                             exec_arguments=exec_arguments or "", 
                             user=user)

    # DB: Create scan record (auto-scan)
    scan_id = db_create_scan(
        db,
        file_id=file_id,
        profile_name=profile_name,
        comment=scan_comment or "",
        project=project or "",
        runtime=runtime or 10,
        drop_path=drop_path or "",
        detection_window_minutes=detection_window_minutes,
        user=user,
    )

    data = { 
        "file_id": file_id,
        "scan_id": scan_id,
    }

    return data


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
