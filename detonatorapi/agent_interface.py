import logging
import requests
from typing import Optional

from .database import Scan
from .edr_templates import edr_template_manager
from .db_interface import db_change_status, db_scan_add_log


logger = logging.getLogger(__name__)

def connect_to_agent(db, db_scan: Scan) -> bool:
    edr_template_id = db_scan.edr_template
    if not edr_template_id:
        logger.error(f"Scan {db_scan.id} has no EDR template defined")
        return False
    edr_template = edr_template_manager.get_template(edr_template_id)
    if not edr_template:
        logger.error(f"EDR template {edr_template_id} not found for scan {db_scan.id}")
        return False
    agent_ip: Optional[str] = edr_template.get("ip")
    if not agent_ip:
        logger.error(f"EDR template {edr_template_id} has no URL defined")
        return False
    agent_port = edr_template.get("port", 8080)
    if not agent_ip:
        logger.error(f"EDR template {edr_template_id} has no IP defined")
        return False
    
    url = "http://" + agent_ip + ":" + str(agent_port)
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            db_scan_add_log(db, db_scan, [f"Connected to agent at {url}"])
        else:
            db_scan_add_log(db, db_scan, [f"Failed to connect to agent at {url}: {response.status_code}"])
            return False
    except requests.RequestException as e:
        db_scan_add_log(db, db_scan, [f"Error connecting to agent at {url}: {str(e)}"])
        return False
    
    return True
