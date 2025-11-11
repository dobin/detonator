import os
from datetime import datetime
import random
import string
from typing import Optional

RUNTIME_MIN_SECONDS = 10
RUNTIME_MAX_SECONDS = 7200
DETECTION_WINDOW_MIN_MINUTES = 0
DETECTION_WINDOW_MAX_MINUTES = 60


def mylog(s: str) -> str:
    return f"[{datetime.utcnow().isoformat()}] {s}\n"


def scanid_to_vmname(scan_id: int) -> str:
    return f"detonator-{scan_id}"


def filename_randomizer(filename, length=4):
    """Prepend random alphanumeric characters to filename"""
    random_prefix = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    return f"{random_prefix}_{filename}"


def sanitize_runtime_seconds(value: Optional[int]) -> Optional[int]:
    """Ensure runtime seconds are within supported bounds."""
    if value is None:
        return None
    if value < RUNTIME_MIN_SECONDS or value > RUNTIME_MAX_SECONDS:
        raise ValueError(f"Runtime must be between {RUNTIME_MIN_SECONDS} and {RUNTIME_MAX_SECONDS} seconds.")
    return value


def sanitize_detection_window_minutes(value: Optional[int]) -> Optional[int]:
    """Ensure detection window minutes are within supported bounds."""
    if value is None:
        return None
    if value < DETECTION_WINDOW_MIN_MINUTES or value > DETECTION_WINDOW_MAX_MINUTES:
        raise ValueError(
            f"Detection window must be between {DETECTION_WINDOW_MIN_MINUTES} and {DETECTION_WINDOW_MAX_MINUTES} minutes."
        )
    return value
