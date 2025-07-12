import logging
import requests
from typing import Optional, Dict
import time
import json
from datetime import datetime

from detonatorapi.database import Scan
from detonatorapi.edr_templates import edr_template_manager
from detonatorapi.db_interface import db_change_status, db_scan_add_log
from detonatorapi.agent.agent_api import AgentApi
from detonatorapi.edr_parser.parser_defender import DefenderParser

logger = logging.getLogger(__name__)


# Attempt to connect to the agent port to see if its up and running
def connect_to_agent(db, db_scan: Scan) -> bool:
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
    agent_ip: Optional[str] = edr_template.get("ip", None)
    if not agent_ip:
        # IP from VM
        agent_ip: str = db_scan.vm_ip_address
        if not agent_ip:
            logger.error(f"Scan {db_scan.id} has no VM IP address defined")
            return False
    
    url = "http://" + agent_ip + ":" + str(agent_port)

    for attempt in range(15):  # 15 * (1 + 3) = 60s
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


def scan_file_with_agent(thread_db, db_scan: Scan) -> bool:
    scan_id = db_scan.id
    edr_template_id = db_scan.edr_template
    if not edr_template_id:
        logger.error(f"Scan {scan_id} has no EDR template defined")
        return False
    edr_template = edr_template_manager.get_template(edr_template_id)
    if not edr_template:
        logger.error(f"EDR template {edr_template_id} not found for scan {scan_id}")
        return False
    agent_ip = edr_template.get("ip", None)
    if not agent_ip:
        agent_ip = db_scan.vm_ip_address
        if not agent_ip:
                logger.error(f"EDR template {edr_template_id} and vm_ip_address has no IP defined")
                return False
    agent_port = edr_template.get("port", 8080)
    if not agent_port:
        logger.error(f"EDR template {edr_template_id} has no port defined")
        return False

    filename = db_scan.file.filename
    file_content = db_scan.file.content
    agentApi = AgentApi(agent_ip, agent_port)

    if not agentApi.StartTrace(filename):
        db_scan_add_log(thread_db, db_scan, [f"Could not start trace on Agent"])
        return False
    db_scan_add_log(thread_db, db_scan, [f"Started trace for file {filename} on Agent at {agent_ip}"])
    time.sleep(1.0)

    if not agentApi.ExecFile(filename, file_content):
        db_scan_add_log(thread_db, db_scan, [f"Could not exec file on Agent"])
        return False
    db_scan_add_log(thread_db, db_scan, [f"Executed file {filename} on Agent at {agent_ip}"])
    time.sleep(10.0)

    rededr_events = agentApi.GetRedEdrEvents()  # FIXME only if edr_template["rededr"] is True?
    agent_logs = agentApi.GetAgentLogs()  # { 'log': [ 'logline', ],  'output': '...' }
    edr_logs = agentApi.GetEdrLogs()
    edr_summary = ""
    is_detected = ""

    if agent_logs is None:
        agent_logs = "No logs available"
        db_scan_add_log(thread_db, db_scan, ["could not get logs from Agent"])
    if rededr_events is None:
        rededr_events = "No results available"
        db_scan_add_log(thread_db, db_scan, ["could not get results from Agent"])
    if edr_logs is None:
        is_detected = "N/A"
        edr_logs = ""
        db_scan_add_log(thread_db, db_scan, ["could not get EDR logs from Agent"])
    else:
        # EDR logs summary
        if edr_template.get("edr_collector", '') == "defender":
            xml_events: str = ""
            try:
                edr_logs_obj: Dict = json.loads(edr_logs)
                xml_events = edr_logs_obj.get("xml_events", "")
            except Exception as e:
                logger.error(edr_logs)
                logger.error(f"Error parsing Defender XML logs: {e}")

            defenderParser = DefenderParser(xml_events)
            defenderParser.parse()
            edr_summary = defenderParser.get_summary()
            if defenderParser.is_detected():
                is_detected = "detected"
                db_scan_add_log(thread_db, db_scan, ["EDR logs indicate suspicious activity detected"])
            else:
                is_detected = "clean"
                db_scan_add_log(thread_db, db_scan, ["EDR logs indicate clean"])
                
    db_scan.edr_logs = edr_logs
    db_scan.edr_summary = edr_summary
    db_scan.agent_logs = agent_logs
    db_scan.rededr_events = rededr_events
    db_scan.result = is_detected
    db_scan.completed_at = datetime.utcnow()
    thread_db.commit()

    return True

