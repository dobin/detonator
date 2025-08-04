from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


#################
# Profile

class ProfileBase(BaseModel):
    name: str
    connector: str
    port: int
    edr_collector: str
    default_malware_path: Optional[str] = ""
    comment: Optional[str] = None
    data: dict

class ProfileCreate(ProfileBase):
    pass

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    connector: Optional[str] = None
    port: Optional[int] = None
    edr_collector: Optional[str] = None
    default_malware_path: Optional[str] = None
    comment: Optional[str] = None
    data: Optional[dict] = None

class ProfileResponse(ProfileBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProfileStatusResponse(BaseModel):
    id: int
    ip: Optional[str] = None
    port: Optional[int] = None
    is_available: str


#################
# Scan and File 

# upload_file_and_scan() response
class NewScanResponse(BaseModel):
    scan_id: int
    file_id: int


#################
# File

# Abstract
class FileBase(BaseModel):
    filename: str
    source_url: Optional[str] = None
    comment: Optional[str] = None

# Unused
class FileCreate(FileBase):
    pass

# upload_file() response
# get_files() response
class FileResponse(FileBase):
    id: int
    file_hash: str
    created_at: datetime
    
    class Config:
        from_attributes = True


#################
# Scan

# create_scan() request
class FileCreateScan(BaseModel):
    # file_id comes from path parameter
    project: Optional[str] = None
    profile_name: str
    runtime: Optional[int] = 10
    malware_path: Optional[str] = ""
    comment: Optional[str] = None
    password: Optional[str] = None

# update_scan() request
class ScanUpdate(BaseModel):
    comment: Optional[str] = None
    project: Optional[str] = None
    profile_id: Optional[str] = None
    result: Optional[str] = None
    status: Optional[str] = None
    runtime: Optional[int] = None
    malware_path: Optional[str] = None
    completed_at: Optional[datetime] = None

# get_scans() response
# get_scan() response
# update_scan() response
class ScanResponse(BaseModel):
    id: int
    file_id: int
    profile_id: int
    project: Optional[str] = None
    comment: Optional[str] = None
    runtime: Optional[int] = None
    malware_path: Optional[str] = None

    detonator_srv_logs: Optional[str] = None
    status: str

    agent_logs: Optional[str] = None
    execution_logs: Optional[str] = None
    rededr_events: Optional[str] = None
    edr_logs: Optional[str] = None
    edr_summary: Optional[str] = None
    result: Optional[str] = None

    vm_instance_name: Optional[str] = None
    vm_ip_address: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    file: Optional[FileResponse] = None
    profile: Optional[ProfileResponse] = None
    
    class Config:
        from_attributes = True

# get_file() request
class FileWithScans(FileResponse):
    scans: List[ScanResponse] = []
