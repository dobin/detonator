from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


#################
# EDR Template

class EDRTemplate(BaseModel):
    id: str
    name: str
    description: str
    category: str
    ports: List[int]
    available: bool

class EDRTemplateResponse(BaseModel):
    templates: List[EDRTemplate]
    all_templates: List[EDRTemplate]


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

# Abstract
class ScanBase(BaseModel):
    project: Optional[str] = None
    edr_template: Optional[str] = None
    comment: Optional[str] = None

# create_scan() request
class FileCreateScan(ScanBase):
    pass  # file_id comes from path parameter

# update_scan() request
class ScanUpdate(BaseModel):
    comment: Optional[str] = None
    project: Optional[str] = None
    edr_template: Optional[str] = None
    result: Optional[str] = None
    status: Optional[str] = None
    completed_at: Optional[datetime] = None

# get_scans() response
# get_scan() response
# update_scan() response
class ScanResponse(ScanBase):
    id: int
    file_id: int
    comment: Optional[str] = None
    detonator_srv_logs: Optional[str] = None
    agent_logs: Optional[str] = None
    rededr_events: Optional[str] = None
    edr_logs: Optional[str] = None
    edr_summary: Optional[str] = None
    result: Optional[str] = None
    status: str
    vm_instance_name: Optional[str] = None
    vm_ip_address: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    file: Optional[FileResponse] = None
    
    class Config:
        from_attributes = True

# get_file() request
class FileWithScans(FileResponse):
    scans: List[ScanResponse] = []
