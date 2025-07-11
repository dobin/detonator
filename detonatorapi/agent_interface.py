import logging
import requests
from typing import Optional
import time

from .database import Scan
from .edr_templates import edr_template_manager
from .db_interface import db_change_status, db_scan_add_log


logger = logging.getLogger(__name__)


# For: If IP is defined in the template
def connect_to_agent_template(db, db_scan: Scan) -> bool:
    edr_template_id = db_scan.edr_template
    if not edr_template_id:
        logger.error(f"Scan {db_scan.id} has no EDR template defined")
        return False
    edr_template = edr_template_manager.get_template(edr_template_id)
    if not edr_template:
        logger.error(f"EDR template {edr_template_id} not found for scan {db_scan.id}")
        return False
    agent_port = edr_template.get("port", 8080)
    if not agent_port:
        logger.error(f"EDR template {edr_template_id} has no IP defined")
        return False
    
    # IP from template
    agent_ip: Optional[str] = edr_template.get("ip")
    if not agent_ip:
        logger.error(f"EDR template {edr_template_id} has no URL defined")
        return False
    
    url = "http://" + agent_ip + ":" + str(agent_port)
    return attempt_connect_to_agent(db, db_scan, url)


# For: If IP is dynamic by VM
def connect_to_agent_vm(db, db_scan: Scan) -> bool:
    edr_template_id = db_scan.edr_template
    if not edr_template_id:
        logger.error(f"Scan {db_scan.id} has no EDR template defined")
        return False
    edr_template = edr_template_manager.get_template(edr_template_id)
    if not edr_template:
        logger.error(f"EDR template {edr_template_id} not found for scan {db_scan.id}")
        return False
    agent_port = edr_template.get("port", 8080)
    if not agent_port:
        logger.error(f"EDR template {edr_template_id} has no IP defined")
        return False
    
    # IP from VM
    agent_ip: str = db_scan.vm_ip_address
    if not agent_ip:
        logger.error(f"Scan {db_scan.id} has no VM IP address defined")
        return False
    
    url = "http://" + agent_ip + ":" + str(agent_port)
    return attempt_connect_to_agent(db, db_scan, url)


def attempt_connect_to_agent(db, db_scan: Scan, url) -> bool:
    for attempt in range(60):  # 15 * (1 + 3) = 60s
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                db_scan_add_log(db, db_scan, [f"Connected to agent at {url} on attempt {attempt + 1}"])
                return True
            else:
                #db_scan_add_log(db, db_scan, [f"Attempt {attempt + 1}: Failed to connect to agent at {url}: {response.status_code}"])
                pass
        except requests.RequestException as e:
            db_scan_add_log(db, db_scan, [f"Attempt {attempt + 1}: Error connecting to agent at {url}: {str(e)}"])
        
        time.sleep(1)

    db_scan_add_log(db, db_scan, [f"Failed to connect to agent at {url} after 10 attempts"])
    return False
