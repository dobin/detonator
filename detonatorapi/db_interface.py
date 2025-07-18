from typing import Optional, List
from datetime import datetime
import logging

from .database import Scan, File, Profile
from .utils import mylog

logger = logging.getLogger(__name__)


def db_change_status(db, db_scan: Scan, status: str, log_message: str = ""):
    #db.refresh(db_scan)

    log = f"Scan {db_scan.id} status change from {db_scan.status} to {status}"
    logger.info(log)

    db_scan.detonator_srv_logs += mylog(log)
    db_scan.status = status

    if log_message != "":
        logger.info("  " + log_message)
        db_scan.detonator_srv_logs += mylog(log)

    #db_scan.updated_at = datetime.utcnow()
    db.commit()


def db_scan_add_log(db, db_scan, log_message: str):
    if log_message is None or log_message == "":
        return
    log = f"[{datetime.utcnow().isoformat()}] {log_message}"
    logger.info(log_message)
    db_scan.detonator_srv_logs += log + "\n"

    db.commit()


def db_create_file(db, filename: str, content: bytes, source_url: str = "", comment: str = "") -> int:
    file_hash = File.calculate_hash(content)

    # DB: Create file record
    db_file = File(
        content=content,
        filename=filename,
        file_hash=file_hash,
        source_url=source_url,
        comment=comment
    )
    db.add(db_file)
    db.commit()

    logger.info(f"DB: Created file {db_file.id} with filename: {filename}")
    return db_file.id


def db_create_profile(db, name: str, connector: str, port: int, edr_collector: str, data: dict, comment: str = "", password: str = ""):
    """Create a new profile in the database"""
    db_profile = Profile(
        name=name,
        connector=connector,
        port=port,
        edr_collector=edr_collector,
        comment=comment,
        data=data,
        password=password
    )
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    
    logger.info(f"DB: Created profile {db_profile.id} with name: {name}")
    return db_profile.id


def db_get_profile_id_by_name(db, name: str) -> Optional[int]:
    """Get profile ID by name"""
    profile = db.query(Profile).filter(Profile.name == name).first()
    if profile:
        return profile.id
    return None

def db_get_profile_by_name(db, name: str) -> Optional[Profile]:
    """Get a profile by name"""
    return db.query(Profile).filter(Profile.name == name).first()


def db_get_profile_by_id(db, profile_id: int) -> Optional[Profile]:
    """Get a profile by ID"""
    return db.query(Profile).filter(Profile.id == profile_id).first()


def db_list_profiles(db) -> List[Profile]:
    """List all profiles"""
    return db.query(Profile).all()


def db_create_scan(db, file_id: int, profile_name: str, comment: str = "", project: str = "", runtime: int =10, password: str = "") -> int:
    """Create a scan using a profile name instead of profile_id"""
    profile = db_get_profile_by_name(db, profile_name)
    if not profile:
        raise ValueError(f"Profile '{profile_name}' not found")
    
    # Create scan directly with the profile instance
    db_scan = Scan(
        file_id=file_id,
        profile_id=profile.id,
        comment=comment,
        project=project,
        runtime=runtime,
        detonator_srv_logs=mylog(f"DB: Scan created"),
        status="fresh",
    )
    db.add(db_scan)
    db.commit()
    logger.info(f"DB: Created scan {db_scan.id}")
    return db_scan.id

