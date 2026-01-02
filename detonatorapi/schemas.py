from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


#################
# Profile

class ProfileBase(BaseModel):
    name: str
    connector: str
    vm_ip: Optional[str] = None
    port: int
    rededr_port: Optional[int] = None
    edr_collector: str
    default_drop_path: Optional[str] = ""
    comment: Optional[str] = None
    data: dict
    mde: Optional[dict] = None

class ProfileCreate(ProfileBase):
    pass

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    connector: Optional[str] = None
    vm_ip: Optional[str] = None
    port: Optional[int] = None
    rededr_port: Optional[int] = None
    edr_collector: Optional[str] = None
    default_drop_path: Optional[str] = None
    comment: Optional[str] = None
    data: Optional[dict] = None
    mde: Optional[dict] = None

class ProfileResponse(ProfileBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProfileStatusResponse(BaseModel):
    id: int
    vm_ip: Optional[str] = None
    port: Optional[int] = None
    rededr_port: Optional[int] = None
    is_available: str
    rededr_available: Optional[str] = None
    status: str


#################
# Submission and File 

# create_submission() response
class NewSubmissionResponse(BaseModel):
    submission_id: int
    file_id: int


#################
# File

# Abstract
class FileBase(BaseModel):
    filename: str
    source_url: Optional[str] = None
    comment: Optional[str] = None
    exec_arguments: Optional[str] = None
    user: str = ""
    created_at: Optional[datetime] = None

# Unused
class FileCreate(FileBase):
    pass

# upload_file() response
# get_files() response
class FileResponse(FileBase):
    id: int
    file_hash: str
    
    class Config:
        from_attributes = True


#################
# Submission

# create_submission() request
class FileCreateSubmission(BaseModel):
    # file_id comes from path parameter
    project: Optional[str] = None
    profile_name: str
    runtime: Optional[int] = 10
    drop_path: Optional[str] = ""
    execution_mode: Optional[str] = "exec"
    comment: Optional[str] = None
    password: Optional[str] = None

# update_submission() request
class SubmissionUpdate(BaseModel):
    comment: Optional[str] = None
    project: Optional[str] = None
    profile_id: Optional[str] = None
    edr_verdict: Optional[str] = None
    status: Optional[str] = None
    runtime: Optional[int] = None
    drop_path: Optional[str] = None
    execution_mode: Optional[str] = None
    completed_at: Optional[datetime] = None

# get_submission() response
# update_submission() response
class SubmissionResponse(BaseModel):
    id: int
    file_id: int
    profile_id: int
    project: Optional[str] = None
    comment: Optional[str] = None
    runtime: Optional[int] = None
    drop_path: Optional[str] = None
    execution_mode: Optional[str] = None

    server_logs: Optional[str] = None
    status: str
    user: str = ""

    agent_logs: Optional[str] = None
    process_output: Optional[str] = None
    rededr_events: Optional[str] = None
    rededr_logs: Optional[str] = None
    edr_verdict: Optional[str] = None

    vm_instance_name: Optional[str] = None
    vm_ip_address: Optional[str] = None
    alerts: List["SubmissionAlertResponse"] = []
    
    # Relationships
    file: Optional[FileResponse] = None
    profile: Optional[ProfileResponse] = None
    alerts: List["SubmissionAlertResponse"] = []

    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SubmissionAlertResponse(BaseModel):
    id: int
    alert_id: str

    source: str
    title: Optional[str] = None
    severity: Optional[str] = None
    category: Optional[str] = None
    detection_source: Optional[str] = None
    detected_at: Optional[datetime] = None
    additional_data: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Response from DetonatorAgent
class EdrAlertResponse(BaseModel):
    alertId: str
    source: str
    title: str
    severity: str
    category: str
    detectionSource: str
    detectedAt: datetime
    raw: str

    class Config:
        from_attributes = True

# Response from DetonatorAgent
class EdrAlertsResponse(BaseModel):
    success: bool
    alerts: List[EdrAlertResponse]
    detected: bool


SubmissionResponse.update_forward_refs()

# get_file() request
class FileWithSubmissions(FileResponse):
    submissions: List[SubmissionResponse] = []
