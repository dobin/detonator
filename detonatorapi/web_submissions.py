from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime
import logging

from detonatorapi.db_interface import db_submission_change_status_quick
from .database import get_db, File, Submission
from .schemas import SubmissionResponse, SubmissionUpdate, FileCreateSubmission
from .connectors.azure_manager import get_azure_manager
from .db_interface import db_create_submission, db_get_profile_by_name, db_submission_add_log
from .utils import sanitize_runtime_seconds
from .token_auth import require_auth, get_user_from_request

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/submissions/count")
async def get_submissions_count(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by submission status"),
    project: Optional[str] = Query(None, description="Filter by project name (case-insensitive partial match)"),
    edr_verdict: Optional[str] = Query(None, description="Filter by submission edr_verdict"),
    search: Optional[str] = Query(None, description="Search in project, submission comment, file comment, or filename"),
    user_filter: Optional[str] = Query(None, description="Filter by user (guest/admin/all)", alias="user"),
    db: Session = Depends(get_db)
):
    """Get count of submissions with filtering capabilities"""
    query = db.query(Submission).options(
        joinedload(Submission.file),
        joinedload(Submission.profile),
        joinedload(Submission.alerts),
    )
    
    # Filter by user if guest
    user = get_user_from_request(request)
    if user == "guest":
        query = query.filter(Submission.user == "guest")
    
    if user_filter and user_filter != "all":
        query = query.filter(Submission.user == user_filter)
    
    # Apply filters (same as in get_submissions)
    if status:
        query = query.filter(Submission.status == status)
    
    if project:
        query = query.filter(Submission.project.ilike(f"%{project}%"))
    
    if edr_verdict:
        query = query.filter(Submission.edr_verdict.ilike(f"%{edr_verdict}%"))
    
    if search:
        # Search across multiple fields
        search_filter = or_(
            Submission.project.ilike(f"%{search}%"),
            Submission.comment.ilike(f"%{search}%"),
            Submission.file.has(File.filename.ilike(f"%{search}%")),
            Submission.file.has(File.comment.ilike(f"%{search}%"))
        )
        query = query.filter(search_filter)
    
    count = query.count()
    return {"count": count}


@router.get("/submissions", response_model=List[SubmissionResponse])
async def get_submissions(
    request: Request,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    status: Optional[str] = Query(None, description="Filter by submission status"),
    project: Optional[str] = Query(None, description="Filter by project name (case-insensitive partial match)"),
    edr_verdict: Optional[str] = Query(None, description="Filter by submission edr_verdict"),
    search: Optional[str] = Query(None, description="Search in project, submission comment, file comment, or filename"),
    user_filter: Optional[str] = Query(None, description="Filter by user (guest/admin/all)", alias="user"),
    db: Session = Depends(get_db)
):
    """Get submissions with filtering capabilities"""
    query = db.query(Submission).options(joinedload(Submission.file), joinedload(Submission.profile), joinedload(Submission.alerts))
    
    # Filter by user if guest
    user = get_user_from_request(request)
    if user == "guest":
        query = query.filter(Submission.user == "guest")

    if user_filter and user_filter != "all":
        query = query.filter(Submission.user == user_filter)
    
    # Apply filters
    if status:
        query = query.filter(Submission.status == status)
    
    if project:
        query = query.filter(Submission.project.ilike(f"%{project}%"))
    
    if edr_verdict:
        query = query.filter(Submission.edr_verdict.ilike(f"%{edr_verdict}%"))
    
    if search:
        # Search across multiple fields
        search_filter = or_(
            Submission.project.ilike(f"%{search}%"),
            Submission.comment.ilike(f"%{search}%"),
            Submission.file.has(File.filename.ilike(f"%{search}%")),
            Submission.file.has(File.comment.ilike(f"%{search}%"))
        )
        query = query.filter(search_filter)
    
    # Order by ID descending (newest first) and apply pagination
    submissions = query.order_by(Submission.id.desc()).offset(skip).limit(limit).all()
    return submissions


@router.get("/submissions/{submission_id}", response_model=SubmissionResponse)
async def get_submission(submission_id: int, request: Request, db: Session = Depends(get_db)):
    """Get a specific submission with file information"""
    db_submission = db.query(Submission).options(joinedload(Submission.file), joinedload(Submission.profile)).filter(Submission.id == submission_id).first()
    if db_submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Check if user has access to this submission
    # Lets allow all for now
    #user = get_user_from_request(request)
    #if user == "guest" and db_submission.user != "guest":
    #    raise HTTPException(status_code=401, detail="Unauthorized access")
    
    return db_submission


@router.put("/submissions/{submission_id}", response_model=SubmissionResponse)
async def update_submission(
    submission_id: int,
    submission_update: SubmissionUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Update a submission"""
    db_submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if db_submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Update fields
    update_data = submission_update.dict(exclude_unset=True)
    if "runtime" in update_data:
        try:
            update_data["runtime"] = sanitize_runtime_seconds(update_data["runtime"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    for field, value in update_data.items():
        setattr(db_submission, field, value)
    
    db_submission.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_submission)
    return db_submission


@router.post("/files/{file_id}/createsubmission", response_model=SubmissionResponse)
async def file_create_submission(
    file_id: int,
    profile_name: str = Form(...),
    execution_mode: str = Form("exec"),
    runtime: int = Form(10),
    password: Optional[str] = Form(None),
    drop_path: Optional[str] = Form(""),
    comment: Optional[str] = Form(None),
    project: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Create a new submission for an existing file"""
    # Check if file exists
    db_file = db.query(File).filter(File.id == file_id).first()
    if db_file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if allowed
    profile = db_get_profile_by_name(db, profile_name)
    if not profile:
        raise HTTPException(status_code=400, detail="Profile not found")
    
    # Password check
    if len(profile.password) > 0:
        if not password or password != profile.password:
            raise HTTPException(status_code=403, detail="Invalid password for profile")

    # Extract data with defaults
    comment = comment or ""
    project = project or ""
    try:
        runtime_sanitized = sanitize_runtime_seconds(runtime)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    runtime_final = runtime_sanitized if runtime_sanitized is not None else 10
    drop_path = drop_path or ""
    execution_mode = execution_mode or "exec"
    
    if not profile_name:
        raise HTTPException(status_code=400, detail="Profile is required")
    
    # Create the submission
    submission_id = db_create_submission(
        db,
        file_id,
        profile_name,
        comment,
        project,
        runtime=runtime_final,
        drop_path=drop_path,
        execution_mode=execution_mode,
    )
    
    # Retrieve the created submission to return full details
    db_submission = db.query(Submission).options(joinedload(Submission.file), joinedload(Submission.profile)).filter(Submission.id == submission_id).first()
    return db_submission


@router.post("/submissions/{submission_id}/shutdown-vm")
async def shutdown_vm_for_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Manually shutdown VM for a submission (for testing purposes)"""
    db_submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if db_submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    db_submission_change_status_quick(db, db_submission, "stop")
    return {"message": "VM shutdown initiated"}


@router.post("/submissions/{submission_id}/resubmission")
async def resubmission(
    submission_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Resubmission a submission that's in error status by resetting it to fresh status"""
    db_submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if db_submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    if db_submission.status != "error":
        raise HTTPException(status_code=400, detail=f"Can only resubmission submissions in 'error' status. Current status: {db_submission.status}")
    
    # Reset submission to fresh status
    db_submission.status = "fresh"
    db_submission.updated_at = datetime.utcnow()

    # and all the possile fields
    db_submission.server_logs = ""
    db_submission.process_output = ""
    db_submission.agent_logs = ""
    db_submission.rededr_events = ""
    db_submission.rededr_logs = ""
    db_submission.edr_verdict = ""
    #db_submission.completed_at = None
    
    # Add log entry about the resubmission
    log_message = f"[{datetime.utcnow().isoformat()}] Submission reset to 'fresh' status for reprocessing"
    db_submission_add_log(db, db_submission, log_message)
    
    db.commit()
    db.refresh(db_submission)
    
    return {"message": "Submission status reset to 'fresh' for reprocessing", "submission_id": submission_id, "status": db_submission.status}


@router.post("/submissions/{submission_id}/stop_exec")
async def stop_submission_execution(
    submission_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Stop execution of a submission"""
    db_submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if db_submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Add log entry about the stop request
    log_message = f"User requested to stop submission execution"
    db_submission.agent_phase = "stop"
    db_submission_add_log(db, db_submission, log_message)
    
    db.commit()
    
    return {"message": "Stop execution request logged", "submission_id": submission_id}


@router.delete("/submissions/{submission_id}")
async def delete_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Delete a specific submission"""
    db_submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if db_submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    db.delete(db_submission)
    db.commit()
    return {"message": "Submission deleted successfully"}
