from typing import Optional, List
from datetime import datetime
import logging
import os
from .settings import UPLOAD_DIR
import random
import string
from werkzeug.utils import secure_filename

from .database import Scan, File, Profile, get_db_direct
from .utils import mylog

logger = logging.getLogger(__name__)


#
def db_scan_change_status(scan_id: int, status: str, log_message: str = ""):
    thread_db = get_db_direct()
    db_scan = thread_db.get(Scan, scan_id)

    ret = db_scan_change_status_quick(thread_db, db_scan, status, log_message)
    thread_db.close()
    return ret


# Change the status of a scan in the database
# Only use this when you know what you are doing:
# - as a shortcut
# - and not use the db_scan after this
# - or before this
def db_scan_change_status_quick(db, db_scan: Scan, status: str, log_message: str = ""):
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


def db_create_file(db, filename: str, content: bytes, source_url: str = "", comment: str = "", exec_arguments: str = "", user: str = "") -> int:
    file_hash = File.calculate_hash(content)
 
    # prepend 4 random chars to filename to avoid collisions
    filename = secure_filename(filename)
    rand_str = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
    actual_filename = f"{rand_str}_{filename}"

    # Write file content to disk
    file_path = os.path.join(UPLOAD_DIR, f"{actual_filename}")
    with open(file_path, 'wb') as f:
        f.write(content)
    
    # DB: Create file record with path instead of content
    db_file = File(
        filename=actual_filename,
        file_hash=file_hash,
        source_url=source_url,
        comment=comment,
        exec_arguments=exec_arguments,
        user=user
    )
    db.add(db_file)
    db.commit()

    logger.info(f"DB: Created file {db_file.id} with filename: {actual_filename}")
    return db_file.id


def db_create_profile(db, name: str, connector: str, port: int, rededr_port: int, edr_collector: str, data: dict, default_drop_path: str = "", comment: str = "", password: str = "", mde: Optional[dict] = None):
    """Create a new profile in the database"""
    # Handle backward compatibility: if mde is provided, put it in data["edr_mde"]
    if mde is not None:
        data = dict(data)  # Create a copy to avoid modifying the original
        data["edr_mde"] = mde
    
    db_profile = Profile(
        name=name,
        connector=connector,
        port=port,
        rededr_port=rededr_port,
        edr_collector=edr_collector,
        default_drop_path=default_drop_path,
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


def db_create_scan(
    db,
    file_id: int,
    profile_name: str,
    comment: str = "",
    project: str = "",
    runtime: int = 10,
    drop_path: str = "",
    execution_mode: str = "exec",
    user: str = "",
) -> int:
    """Create a scan using a profile name instead of profile_id"""
    profile = db_get_profile_by_name(db, profile_name)
    if not profile:
        raise ValueError(f"Profile '{profile_name}' not found")
    
    # get default_drop_path from profile if none given
    # always make sure drop_path is set
    if drop_path == "" and profile.default_drop_path != "":
        drop_path = profile.default_drop_path

    # Create scan directly with the profile instance
    db_scan = Scan(
        file_id=file_id,
        profile_id=profile.id,
        comment=comment,
        project=project,
        runtime=runtime,
        drop_path=drop_path,
        execution_mode=execution_mode,
        user=user,
        detonator_srv_logs=mylog(f"DB: Scan created"),
        status="fresh",
    )
    db.add(db_scan)
    db.commit()
    logger.info(f"DB: Created scan {db_scan.id}")
    return db_scan.id
