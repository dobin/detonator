import logging
import requests
from typing import Optional

from .database import get_background_db, Scan
from .edr_templates import get_edr_template_manager


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
    agent_url: Optional[str] = edr_template.get("ip")
    if not agent_url:
        logging.error(f"EDR template {edr_template_id} has no URL defined")
        return False

    try:
        response = requests.get("http://" + agent_url + ":8080", timeout=5)
        if response.status_code == 200:
            logging.info(f"Connected to agent at {agent_url}")
        else:
            logging.error(f"Failed to connect to agent at {agent_url}: {response.status_code}")
            return False
    except requests.RequestException as e:
        logging.error(f"Error connecting to agent at {agent_url}: {str(e)}")
        return False
    
    return True