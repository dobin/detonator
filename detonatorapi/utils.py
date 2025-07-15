import os
from datetime import datetime
import random
import string


def mylog(s: str) -> str:
    return f"[{datetime.utcnow().isoformat()}] {s}\n"


def scanid_to_vmname(scan_id: int) -> str:
    return f"detonator-{scan_id}"


def filename_randomizer(filename, length=4):
    """Prepend random alphanumeric characters to filename"""
    random_prefix = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    return f"{random_prefix}_{filename}"
