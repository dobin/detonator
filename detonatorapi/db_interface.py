from typing import Optional, List
from datetime import datetime
import logging

from .database import get_background_db, Scan, File
from .utils import mylog

logger = logging.getLogger(__name__)


def db_change_status(scan_id: int, status: str, log_message: str = ""):
    db = get_background_db()

    db_scan: Optional[Scan] = db.query(Scan).get(scan_id)
    if not db_scan:
        logger.error(f"Scan with ID {scan_id} not found in database")
        return None

    log = f"Scan {db_scan.id} status change from {db_scan.status} to {status}"
    logger.info(log)

    db_scan.detonator_srv_logs += mylog(log)
    db_scan.status = status

    if log_message != "":
        log = f"[{datetime.utcnow().isoformat()}] {log_message}\n"
        logger.info(log)
        db_scan.detonator_srv_logs += log

    #db_scan.updated_at = datetime.utcnow()
    db.commit()


def db_scan_add_log(scan_id: int, log_messages: List[str]):
    db = get_background_db()

    db_scan: Optional[Scan] = db.query(Scan).get(scan_id)
    if not db_scan:
        logger.error(f"Scan with ID {scan_id} not found in database")
        return None

    for log_message in log_messages:
        if log_message is None or log_message == "":
            continue
        log = f"[{datetime.utcnow().isoformat()}] {log_message}"
        logger.info(log)
        db_scan.detonator_srv_logs += log + "\n"

    db.commit()


def db_mark_scan_error(scan_id: int, error_message: str):
    db = get_background_db()

    db_scan: Optional[Scan] = db.query(Scan).get(scan_id)
    if not db_scan:
        logger.error(f"Scan with ID {scan_id} not found in database")
        return None

    log = f"[{datetime.utcnow().isoformat()}] Error VM: {error_message}\n"
    db_scan.detonator_srv_logs += mylog(log)
    db_scan.status = "error"
    db.commit()
    logger.error(f"DB: Marked scan {db_scan.id} as error: {error_message}")


def db_create_file(filename: str, content: bytes, source_url: str = "", comment: str = "") -> int:
    db = get_background_db()
    
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


def db_create_scan(file_id: int, edr_template: str, comment: str = "", project: str = "") -> int:
    db = get_background_db()

    db_scan = Scan(
        file_id=file_id,
        comment=comment,
        edr_template=edr_template,
        project=project,
        detonator_srv_logs=mylog(f"DB: Scan created"),
        status="fresh",
    )
    db.add(db_scan)
    db.commit()
    logger.info(f"DB: Created scan {db_scan.id}")
    return db_scan.id

