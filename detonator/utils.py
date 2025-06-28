import os
import datetime


def mylog(s: str) -> str:
    return f"{datetime.utcnow().isoformat()}] {s}\n"

