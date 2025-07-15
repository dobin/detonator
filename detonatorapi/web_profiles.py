from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import Optional
import logging
import json
import requests

from .database import get_db, Profile, Scan
from .schemas import ProfileResponse, ProfileStatusResponse
from .db_interface import db_list_profiles, db_create_profile, db_get_profile_by_id

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/profiles")
async def get_profiles(db: Session = Depends(get_db)):
    """Get available profiles"""
    profiles = db_list_profiles(db)
    # Convert to dict format similar to old templates
    result = {}
    for profile in profiles:
        result[profile.name] = {
            "id": profile.id,
            "connector": profile.connector,
            "port": profile.port,
            "edr_collector": profile.edr_collector,
            "comment": profile.comment,
            "data": profile.data
        }
    return result


@router.post("/profiles")
async def create_profile(
    name: str = Form(...),
    connector: str = Form(...),
    port: int = Form(...),
    edr_collector: Optional[str] = Form(""),
    comment: Optional[str] = Form(""),
    data: str = Form(...),
    db: Session = Depends(get_db)
):
    """Create a new profile"""
    try:
        # Parse JSON data
        try:
            data_dict = json.loads(data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in data field")
        
        # Check if profile name already exists
        existing_profile = db.query(Profile).filter(Profile.name == name).first()
        if existing_profile:
            raise HTTPException(status_code=400, detail=f"Profile with name '{name}' already exists")
        
        # Create the profile
        profile_id = db_create_profile(
            db=db,
            name=name,
            connector=connector,
            port=port,
            edr_collector=edr_collector or "",
            data=data_dict,
            comment=comment or ""
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
            "comment": created_profile.comment,
            "data": created_profile.data,
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
    db_profile = db_get_profile_by_id(db, profile_id)
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    is_available = ""

    ip = db_profile.data.get('ip', '')
    port = db_profile.port
    if ip == "" or port == 0:
        is_available = ""
    else:
        port = db_profile.port
        try:
            url = f"http://{ip}:{port}"
            test_response = requests.get(url, timeout=0.5)
            is_available = "true"
        except:
            is_available = "false"

    return {
        "id": db_profile.id,
        "ip": ip,
        "port": port,
        "is_available": is_available
    }


@router.put("/profiles/{profile_id}")
async def update_profile(
    profile_id: int,
    name: str = Form(...),
    connector: str = Form(...),
    port: int = Form(...),
    edr_collector: str = Form(...),
    comment: str = Form(""),
    data: str = Form(...),
    db: Session = Depends(get_db)
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
        
        # Update fields
        profile.name = name
        profile.connector = connector
        profile.port = port
        profile.edr_collector = edr_collector
        profile.comment = comment
        profile.data = data_dict
        
        db.commit()
        db.refresh(profile)
        
        return {
            "id": profile.id,
            "name": profile.name,
            "connector": profile.connector,
            "port": profile.port,
            "edr_collector": profile.edr_collector,
            "comment": profile.comment,
            "data": profile.data,
            "created_at": profile.created_at
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating profile {profile_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: int, db: Session = Depends(get_db)):
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
