from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class FileBase(BaseModel):
    filename: str
    source_url: Optional[str] = None
    comment: Optional[str] = None

class FileCreate(FileBase):
    pass

class FileResponse(FileBase):
    id: int
    file_hash: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ScanBase(BaseModel):
    vm_template: Optional[str] = None
    edr_template: Optional[str] = None

class ScanCreate(ScanBase):
    file_id: int

class ScanUpdate(BaseModel):
    vm_template: Optional[str] = None
    edr_template: Optional[str] = None
    detonator_srv_logs: Optional[str] = None
    agent_logs: Optional[str] = None
    execution_logs: Optional[str] = None
    edr_logs: Optional[str] = None
    result: Optional[str] = None
    status: Optional[str] = None
    vm_instance_name: Optional[str] = None
    vm_ip_address: Optional[str] = None
    completed_at: Optional[datetime] = None

class ScanResponse(ScanBase):
    id: int
    file_id: int
    detonator_srv_logs: Optional[str] = None
    agent_logs: Optional[str] = None
    execution_logs: Optional[str] = None
    edr_logs: Optional[str] = None
    result: Optional[str] = None
    status: str
    vm_instance_name: Optional[str] = None
    vm_ip_address: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class FileWithScans(FileResponse):
    scans: List[ScanResponse] = []
