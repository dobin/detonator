from typing import Optional, List
from datetime import datetime
import logging

from .database import Scan, File
from .utils import mylog

logger = logging.getLogger(__name__)


def db_change_status(db, db_scan: Scan, status: str, log_message: str = ""):
    #db.refresh(db_scan)

    log = f"Scan {db_scan.id} status change from {db_scan.status} to {status}"
    logger.info(log)

    db_scan.detonator_srv_logs += mylog(log)
    db_scan.status = status

    if log_message != "":
        logger.info("  " + log_mesage)
        db_scan.detonator_srv_logs += mylog(log)

    #db_scan.updated_at = datetime.utcnow()
    db.commit()


def db_scan_add_log(db, db_scan, log_messages: List[str]):
    for log_message in log_messages:
        if log_message is None or log_message == "":
            continue
        log = f"[{datetime.utcnow().isoformat()}] {log_message}"
        logger.info(log)
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


def db_create_scan(db, file_id: int, edr_template: str, comment: str = "", project: str = "") -> int:
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
