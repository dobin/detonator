import logging
import requests
from typing import Optional

from .database import get_background_db, Scan
from .edr_templates import get_edr_template_manager
from .db_interface import db_change_status, db_scan_add_log, db_mark_scan_error


def connect_to_agent(scan_id: int):
    db_scan = get_background_db().query(Scan).get(scan_id)
    if not db_scan:
        logging.error(f"Scan with ID {scan_id} not found in database")
        return False
    
    edr_template_id = db_scan.edr_template
    if not edr_template_id:
        logging.error(f"Scan {scan_id} has no EDR template defined")
        return False
    edr_template = get_edr_template_manager().get_template(edr_template_id)
    if not edr_template:
        logging.error(f"EDR template {edr_template_id} not found for scan {scan_id}")
        return False
    agent_ip: Optional[str] = edr_template.get("ip")
    if not agent_ip:
        logging.error(f"EDR template {edr_template_id} has no URL defined")
        return False
    
    url = "http://" + agent_ip + ":8080"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            db_scan_add_log(scan_id, [f"Connected to agent at {url}"])
        else:
            db_scan_add_log(scan_id, [f"Failed to connect to agent at {url}: {response.status_code}"])
            return False
    except requests.RequestException as e:
        db_scan_add_log(scan_id, [f"Error connecting to agent at {url}: {str(e)}"])
        return False
    
    return True