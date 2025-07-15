from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import os
from dotenv import load_dotenv

from .vm_monitor import start_vm_monitoring, stop_vm_monitoring
from .web_files import router as files_router
from .web_scans import router as scans_router
from .web_vms import router as vms_router
from .web_profiles import router as profiles_router

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
