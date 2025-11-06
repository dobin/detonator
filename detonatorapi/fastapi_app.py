from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
import random
import string
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from .database import get_db, Profile
from .schemas import  NewScanResponse
from .db_interface import db_create_file, db_create_scan, db_get_profile_by_name
from .token_auth import tokenAuth
from .vm_monitor import start_vm_monitoring, stop_vm_monitoring
from .web_files import router as files_router
from .web_scans import router as scans_router
from .web_vms import router as vms_router
from .web_profiles import router as profiles_router
from .settings import CORS_ALLOW_ORIGINS, AUTH_PASSWORD
from .utils import sanitize_runtime_seconds


# Load environment variables
load_dotenv()

# Setup logging - reduce verbosity for HTTP requests
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("fastapi").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(title="Detonator API", version="0.1.0")


# Authentication helper
def check_auth(request: Request) -> bool:
    """Check if request is authenticated via password"""
    if not AUTH_PASSWORD or AUTH_PASSWORD == "":
        # No password configured - allow all requests
        return True
    
    # Check for X-Auth-Password header
    auth_password = request.headers.get("X-Auth-Password", "")
    if auth_password == AUTH_PASSWORD:
        return True
    
    # Check for Authorization header (Basic or Bearer)
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        # Support "Bearer <password>" format
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if token == AUTH_PASSWORD:
                return True
        # Support "Basic <base64>" format for curl compatibility
        elif auth_header.startswith("Basic "):
            import base64
            try:
                decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
                # Basic auth format is "username:password", we only care about password
                if ':' in decoded:
                    _, password = decoded.split(':', 1)
                    if password == AUTH_PASSWORD:
                        return True
                # Or just the password alone
                elif decoded == AUTH_PASSWORD:
                    return True
            except:
                pass
    
    return False


# Authentication middleware
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Allow GET, HEAD, OPTIONS without authentication
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        response = await call_next(request)
        return response
    
    # Check authentication for write operations
    if not check_auth(request):
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required. Provide password via X-Auth-Password header or Authorization header."}
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

    try:
        runtime = sanitize_runtime_seconds(runtime)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

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
    rand_str = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
    actual_filename = f"{rand_str}_{filename}"
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
