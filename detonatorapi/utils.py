import os
from datetime import datetime


def mylog(s: str) -> str:
    return f"[{datetime.utcnow().isoformat()}] {s}\n"


def scanid_to_vmname(scan_id: int) -> str:
    return f"detonator-{scan_id}"

