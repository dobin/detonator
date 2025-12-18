from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import Optional
import logging
import json
import requests
import subprocess

from .database import get_db, Profile, Scan
from .schemas import ProfileResponse, ProfileStatusResponse
from .db_interface import db_list_profiles, db_create_profile, db_get_profile_by_id
from .agent.agent_api import AgentApi
from .agent.rededr_agent import RedEdrAgentApi as RedEdrApi
from .token_auth import require_auth
from .connectors.connectors import connectors
from .connectors.connector_proxmox import ConnectorProxmox

router = APIRouter()
logger = logging.getLogger(__name__)


def _parse_optional_int(value: Optional[str], field_name: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    value = value.strip()
    if value == "":
        return None
    try:
        return int(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} must be an integer")


@router.get("/profiles")
async def get_profiles(db: Session = Depends(get_db)):
    """Get available profiles"""
    profiles = db_list_profiles(db)

    # Convert to dict format similar to old templates
    result = {}
    for profile in profiles:
        requires_password: bool = len(profile.password) > 0
        result[profile.name] = {
            "id": profile.id,
            "connector": profile.connector,
            "port": profile.port,
            "rededr_port": profile.rededr_port,
            "edr_collector": profile.edr_collector,
            "default_drop_path": profile.default_drop_path,
            "comment": profile.comment,
            "data": profile.data,
            "require_password": requires_password,
        }
    return result


@router.post("/profiles")
async def create_profile(
    name: str = Form(...),
    connector: str = Form(...),
    port: int = Form(...),
    rededr_port: Optional[str] = Form(None),
    edr_collector: Optional[str] = Form(""),
    default_drop_path: Optional[str] = Form(""),
    comment: Optional[str] = Form(""),
    password: Optional[str] = Form(""),
    data: str = Form(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
    mde: Optional[str] = Form(None),
):
    """Create a new profile"""
    try:
        # Parse JSON data
        try:
            data_dict = json.loads(data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in data field")

        # Parse JSON in mde field if provided
        mde_dict: Optional[dict] = None
        if mde:
            try:
                mde_dict = json.loads(mde)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON in mde field")
            
        # Check if profile name is alphanumeric, no spaces
        if not name.isalnum():
            raise HTTPException(status_code=400, detail="Profile name must be alphanumeric with no spaces")
        
        # Check if profile name already exists
        existing_profile = db.query(Profile).filter(Profile.name == name).first()
        if existing_profile:
            raise HTTPException(status_code=400, detail=f"Profile with name '{name}' already exists")
        
        rededr_port_value = _parse_optional_int(rededr_port, "RedEdr port")

        # Create the profile
        profile_id = db_create_profile(
            db=db,
            name=name,
            connector=connector,
            port=port,
            rededr_port=rededr_port_value,
            edr_collector=edr_collector or "",
            data=data_dict,
            default_drop_path=default_drop_path or "",
            comment=comment or "",
            password=password or "",
            mde=mde_dict or {}
        )
        
        # Return the created profile
        created_profile = db.query(Profile).filter(Profile.id == profile_id).first()
        if not created_profile:
            raise HTTPException(status_code=500, detail="Failed to retrieve created profile")
            
        return {
            "id": created_profile.id,
            "name": created_profile.name,
            "connector": created_profile.connector,
            "port": created_profile.port,
            "edr_collector": created_profile.edr_collector,
            "default_drop_path": created_profile.default_drop_path,
            "comment": created_profile.comment,
            "data": created_profile.data,
            "mde": created_profile.data.get("edr_mde", {}),
            "created_at": created_profile.created_at
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create profile: {str(e)}")


@router.get("/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: int, db: Session = Depends(get_db)):
    """Get a specific profile by ID"""
    db_profile = db_get_profile_by_id(db, profile_id)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return db_profile


@router.get("/profiles/{profile_id}/status", response_model=ProfileStatusResponse)
async def get_profile_status(profile_id: int, db: Session = Depends(get_db)):
    """Get status which checks if the profile's IP and port are reachable"""
    db_profile: Profile = db_get_profile_by_id(db, profile_id)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    is_available = ""
    rededr_available = ""
    ip: str = ""
    port: int = db_profile.port
    status: str = ""
    if db_profile.connector == "Live": 
        ip = db_profile.data.get('ip', '')
    elif db_profile.connector == "Proxmox":
        ip = db_profile.data.get('ip', '')
        proxmox_id = db_profile.data.get('proxmox_id', '')
        if ip == "" or proxmox_id == "":
            raise HTTPException(status_code=400, detail="Profile does not have ip or proxmox_id configured")
        
        # Get Proxmox connector
        proxmox_connector = connectors.get("Proxmox")
        if not proxmox_connector or not isinstance(proxmox_connector, ConnectorProxmox):
            raise HTTPException(status_code=500, detail="Proxmox connector not available")
        proxmox_manager = proxmox_connector.proxmox_manager

        status = proxmox_manager.StatusVm(proxmox_id)
    elif db_profile.connector == "Azure":
        return {
            "id": db_profile.id,
            "ip": "",
            "port": 0,
            "rededr_port": 0,
            "is_available": "N/A",
            "rededr_available": "N/A",
            "status": status,
        }
    rededr_port = db_profile.rededr_port

    # Check agent port status
    agentApi: AgentApi = AgentApi(ip, port)
    if agentApi.IsReachable():
        if agentApi.IsInUse():
            is_available = "In use"
        else:
            is_available = "Reachable"
    else:
        is_available = "Not reachable"

    # Check rededr agent status
    rededrApi = RedEdrApi(ip, rededr_port)
    if rededrApi.IsReachable():
        rededr_available = "Reachable"
    else:
        rededr_available = "Not reachable"

    return {
        "id": db_profile.id,
        "ip": ip,
        "port": port,
        "rededr_port": rededr_port,
        "is_available": is_available,
        "rededr_available": rededr_available,
        "status": status,
    }


@router.put("/profiles/{profile_id}")
async def update_profile(
    profile_id: int,
    name: str = Form(...),
    connector: str = Form(...),
    port: int = Form(...),
    rededr_port: Optional[str] = Form(None),
    edr_collector: str = Form(...),
    default_drop_path: str = Form(""),
    comment: str = Form(""),
    data: str = Form(...),
    password: Optional[str] = Form(""),
    mde: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Update a profile"""
    try:
        # Find the profile
        profile = db.query(Profile).filter(Profile.id == profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        # Parse JSON data
        try:
            data_dict = json.loads(data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in data field")
        
        # Check if new name conflicts with existing profile (excluding current one)
        if name != profile.name:
            existing = db.query(Profile).filter(Profile.name == name, Profile.id != profile_id).first()
            if existing:
                raise HTTPException(status_code=400, detail=f"Profile with name '{name}' already exists")
        
        mde_dict: Optional[dict] = None
        if mde is not None:
            trimmed = mde.strip()
            if trimmed == "":
                mde_dict = {}
            else:
                try:
                    mde_dict = json.loads(trimmed)
                except json.JSONDecodeError:
                    raise HTTPException(status_code=400, detail="Invalid JSON in mde field")
        
        rededr_port_value = _parse_optional_int(rededr_port, "RedEdr port")

        # Update fields
        profile.name = name
        profile.connector = connector
        profile.port = port
        profile.edr_collector = edr_collector
        if rededr_port_value is not None or (rededr_port is not None and rededr_port.strip() == ""):
            profile.rededr_port = rededr_port_value
        profile.default_drop_path = default_drop_path
        profile.comment = comment
        profile.data = data_dict
        profile.password = password or ""
        if mde_dict is not None:
            profile.data["edr_mde"] = mde_dict
        
        db.commit()
        db.refresh(profile)
        
        return {
            "id": profile.id,
            "name": profile.name,
            "connector": profile.connector,
            "port": profile.port,
            "edr_collector": profile.edr_collector,
            "default_drop_path": profile.default_drop_path,
            "comment": profile.comment,
            "data": profile.data,
            "mde": profile.data.get("edr_mde", {}),
            "password": password or "",
            "created_at": profile.created_at
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating profile {profile_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")


@router.delete("/profiles/{profile_id}")
async def delete_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Delete a profile"""
    db_profile = db_get_profile_by_id(db, profile_id)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Check if profile is being used by any scans
    scans_using_profile = db.query(Scan).filter(Scan.profile_id == profile_id).count()
    if scans_using_profile > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete profile: {scans_using_profile} scans are using this profile")
    
    db.delete(db_profile)
    db.commit()
    return {"message": f"Profile '{db_profile.name}' deleted successfully"}


@router.post("/profiles/{profile_id}/release_lock")
async def release_profile_lock(
    profile_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Release lock for a profile"""
    db_profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Get IP and port from profile data
    # As this is usually just used by Live, take it from profile data
    ip = db_profile.data.get('ip', '')
    port = db_profile.port
    
    if not ip or not port:
        raise HTTPException(status_code=400, detail="Profile does not have IP or port configured")
    
    try:
        # Create agent API instance and release lock
        agentApi = AgentApi(ip, port)
        if agentApi.ReleaseLock():
            logger.info(f"Successfully released lock for profile {profile_id} ({db_profile.name}) at {ip}:{port}")
            return {"message": f"Lock released successfully for profile '{db_profile.name}'"}
        else:
            logger.warning(f"Failed to release lock for profile {profile_id} ({db_profile.name}) at {ip}:{port}")
            raise HTTPException(status_code=500, detail="Failed to release lock on agent")
    except Exception as e:
        logger.error(f"Error releasing lock for profile {profile_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error releasing lock: {str(e)}")


@router.post("/profiles/{profile_id}/reboot")
async def reboot(
    profile_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth)
):
    """Reboot the VM associated with the profile"""

    db_profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    ip = db_profile.data.get('ip', '')
    if ip == "":
        raise HTTPException(status_code=400, detail="Profile does not have ip configured")
    try:
        # Execute SSH reboot command
        subprocess.run(
            ["ssh", f"hacker@{ip}", "shutdown", "/r", "/t", "0"],
            check=True,
            timeout=30
        )
        logger.info(f"Reboot command issued for profile {profile_id} ({db_profile.name})")
        return {"message": "Reboot command issued"}
    except subprocess.TimeoutExpired:
        logger.warning(f"Reboot command timed out for profile {profile_id}")
        return {"message": "Reboot command issued (timeout waiting for response)"}
    except subprocess.CalledProcessError as e:
        logger.error(f"Reboot command failed for profile {profile_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to execute reboot command: {str(e)}")
    except Exception as e:
        logger.error(f"Error rebooting profile {profile_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error issuing reboot: {str(e)}")


@router.post("/profiles/{profile_id}/revert")
async def revert(
    profile_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth)
):
    """Revert the Proxmox VM to snapshot (stop, revert, start)"""

    db_profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    if db_profile.connector != "Proxmox":
        raise HTTPException(status_code=400, detail="Revert operation is only supported for Proxmox profiles")
    
    # Get VM configuration from profile data
    proxmox_id = db_profile.data.get('proxmox_id')
    proxmox_snapshot = db_profile.data.get('proxmox_snapshot')
    
    if not proxmox_id or not proxmox_snapshot:
        raise HTTPException(status_code=400, detail="Profile does not have proxmox_id or proxmox_snapshot configured")
    
    try:
        # Get Proxmox connector
        proxmox_connector = connectors.get("Proxmox")
        if not proxmox_connector or not isinstance(proxmox_connector, ConnectorProxmox):
            raise HTTPException(status_code=500, detail="Proxmox connector not available")
        
        proxmox_manager = proxmox_connector.proxmox_manager
        
        # Stop VM
        logger.info(f"Stopping VM {proxmox_id} for profile {profile_id} ({db_profile.name})")
        if not proxmox_manager.StopVm(proxmox_id):
            raise HTTPException(status_code=500, detail="Failed to stop VM")
        
        # Revert to snapshot
        logger.info(f"Reverting VM {proxmox_id} to snapshot '{proxmox_snapshot}' for profile {profile_id}")
        if not proxmox_manager.RevertVm(proxmox_id, proxmox_snapshot):
            raise HTTPException(status_code=500, detail="Failed to revert VM to snapshot")
        
        # Start VM
        logger.info(f"Starting VM {proxmox_id} for profile {profile_id}")
        if not proxmox_manager.StartVm(proxmox_id):
            raise HTTPException(status_code=500, detail="Failed to start VM after revert")
        
        logger.info(f"Successfully reverted and restarted VM {proxmox_id} for profile {profile_id} ({db_profile.name})")
        return {"message": f"VM successfully reverted to snapshot '{proxmox_snapshot}' and restarted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reverting VM for profile {profile_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reverting VM: {str(e)}")
