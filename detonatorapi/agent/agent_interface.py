import logging
import requests
from typing import Optional, Dict
import time
import json
from datetime import datetime
from detonatorapi.edr_parser.edr_parser import EdrParser
from typing import List

from detonatorapi.database import Scan
from detonatorapi.db_interface import db_change_status, db_scan_add_log
from detonatorapi.agent.agent_api import AgentApi
from detonatorapi.edr_parser.parser_defender import DefenderParser
from detonatorapi.agent.agent_api import ScanResult

logger = logging.getLogger(__name__)

parsers: List[EdrParser] = [
    DefenderParser(),
]

SLEEP_TIME_REDEDR_WARMUP = 3.0
SLEEP_TIME_POST_SCAN = 10.0
DO_LOCKING = True


# Attempt to connect to the agent port to see if its up and running
def connect_to_agent(db, db_scan: Scan) -> bool:
    agent_ip = None
    # IP in template?
    if 'ip' in db_scan.profile.data:
        agent_ip: Optional[str] = db_scan.profile.data['ip']
    else:
        # IP in VM?
        agent_ip = db_scan.vm_ip_address
        if not agent_ip:
            logger.error(f"Scan {db_scan.id} has no VM IP address defined")
            return False
    agent_port = db_scan.profile.port
    
    url = "http://" + agent_ip + ":" + str(agent_port)

    for attempt in range(15):  # 15 * (1 + 3) = 60s
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                db_scan_add_log(db, db_scan, f"Connected to agent at {url} on attempt {attempt + 1}")
                return True
            else:
                #db_scan_add_log(db, db_scan, f"Attempt {attempt + 1}: Failed to connect to agent at {url}: {response.status_code}")
                pass
        except requests.RequestException as e:
            db_scan_add_log(db, db_scan, f"Attempt {attempt + 1}: Error connecting to agent at {url}: {str(e)}")
        
        time.sleep(1)

    db_scan_add_log(db, db_scan, f"Failed to connect to agent at {url} after 10 attempts")
    return False


def scan_file_with_agent(thread_db, db_scan: Scan) -> bool:
    agent_ip = None
    # IP in template?
    if 'ip' in db_scan.profile.data:
        agent_ip: Optional[str] = db_scan.profile.data['ip']
    else:
        # IP in VM?
        agent_ip = db_scan.vm_ip_address
        if not agent_ip:
            logger.error(f"Scan {db_scan.id} has no VM IP address defined")
            return False
    agent_port = db_scan.profile.port

    filename = db_scan.file.filename
    file_content = db_scan.file.content
    runtime = db_scan.runtime
    agentApi = AgentApi(agent_ip, agent_port)

    if DO_LOCKING:
        # Try to acquire lock 4 times with 30 second intervals
        lock_acquired = False
        attempts = 6
        for attempt in range(attempts):
            if agentApi.IsInUse():
                db_scan_add_log(thread_db, db_scan, f"Attempt {attempt + 1}: Agent at {agent_ip} is currently in use")
            elif agentApi.AcquireLock():
                db_scan_add_log(thread_db, db_scan, f"Successfully acquired lock on Agent at {agent_ip} on attempt {attempt + 1}")
                lock_acquired = True
                break
            else:
                db_scan_add_log(thread_db, db_scan, f"Attempt {attempt + 1}: Could not lock Agent at {agent_ip}")
            
            if attempt < attempts - 1:  # Don't sleep after the last attempt
                db_scan_add_log(thread_db, db_scan, f"Waiting 30 seconds before retry...")
                time.sleep(30)
        
        if not lock_acquired:
            db_scan_add_log(thread_db, db_scan, f"Failed to acquire lock on Agent at {agent_ip} after 4 attempts")
            return False

    # remove file extension for trace
    filename_trace = filename.rsplit('.', 1)[0]

    # Set the process name we gonna trace
    if not agentApi.StartTrace(filename_trace):
        db_scan_add_log(thread_db, db_scan, f"Could not start trace on Agent")
        agentApi.ReleaseLock()  # no check, we just release the lock
        return False
    db_scan_add_log(thread_db, db_scan, f"Configured trace for file {filename_trace} on Agent at {agent_ip}")

    # let RedEdr boot up
    time.sleep(SLEEP_TIME_REDEDR_WARMUP)

    # Execute our malware
    scanResult: ScanResult = agentApi.ExecFile(filename, file_content)
    is_malware = False
    if scanResult == ScanResult.ERROR:
        db_scan_add_log(thread_db, db_scan, f"Could not exec file on Agent")
        agentApi.ReleaseLock()  # no check, we just release the lock
        return False
    elif scanResult == ScanResult.VIRUS:
        db_scan_add_log(thread_db, db_scan, f"File {filename} is detected as malware")
        is_malware = True
    elif scanResult == ScanResult.OK:
        db_scan_add_log(thread_db, db_scan, f"Executed file {filename} on Agent at {agent_ip} runtime {runtime} seconds")
        thread_db.commit()

        # process is being executed. 
        time.sleep(runtime)
        
        # enough execution.
        db_scan_add_log(thread_db, db_scan, f"Runtime of {runtime} seconds completed, gathering results")
        thread_db.commit()

    # give some time for windows to scan, deliver the virus ETW alert events n stuff
    time.sleep(SLEEP_TIME_POST_SCAN)

    # Gather all logs
    rededr_events = agentApi.GetRedEdrEvents()
    agent_logs = agentApi.GetAgentLogs()
    execution_logs = agentApi.GetExecutionLogs()
    edr_logs = agentApi.GetEdrLogs()
    edr_summary = ""  # will be generated
    result_is_detected = ""  # will be generated

    # kill process (after gathering all logs, so we dont have the shutdown logs)
    if agentApi.StopTrace():
        db_scan_add_log(thread_db, db_scan, f"Agent: killed the process")
    else:
        db_scan_add_log(thread_db, db_scan, f"Agent: Could not kill process")
        # no return, we dont care

    # we finished 
    if DO_LOCKING:
        if not agentApi.ReleaseLock():
            db_scan_add_log(thread_db, db_scan, f"Could not release lock on Agent at {agent_ip}")
        else:
            db_scan_add_log(thread_db, db_scan, f"Released lock on Agent at {agent_ip}")

    # Preparse all the logs
    if agent_logs is None:
        agent_logs = "No Agent logs available"
        db_scan_add_log(thread_db, db_scan, "could not get Agent logs from Agent")
    if rededr_events is None:
        rededr_events = "No RedEdr logs available"
        db_scan_add_log(thread_db, db_scan, "could not get RedEdr logs from Agent")
    if execution_logs is None:
        execution_logs = "No Execution logs available"
        db_scan_add_log(thread_db, db_scan, "could not get Execution logs from Agent")
    if edr_logs is None:
        result_is_detected = "N/A"
        edr_logs = ""
        db_scan_add_log(thread_db, db_scan, "No EDR logs from Agent")
    else:
        # get the actual EDR log
        edr_plugin_log: str = ""
        try:
            edr_plugin_log = json.loads(edr_logs).get("logs", "")

            # EDR logs summary
            for parser in parsers:
                parser.load(edr_plugin_log)
                if parser.is_relevant():
                    db_scan_add_log(thread_db, db_scan, f"Using parser {parser.__class__.__name__} for EDR logs")
                    if parser.parse():
                        edr_summary = parser.get_summary()
                        if parser.is_detected():
                            result_is_detected = "detected"
                            db_scan_add_log(thread_db, db_scan, "EDR logs indicate suspicious activity detected")
                        else:
                            result_is_detected = "clean"
                            db_scan_add_log(thread_db, db_scan, "EDR logs indicate clean")
                    else:
                        db_scan_add_log(thread_db, db_scan, "EDR logs could not be parsed")
                    break

        except Exception as e:
            logger.error(edr_logs)
            logger.error(f"Error parsing Defender XML logs: {e}")

    # if its already detected as malware, make sure the status is set
    # as we might not have any EDR logs
    if is_malware:
        result_is_detected = "virus"

    # write all logs to the database
    db_scan.execution_logs = execution_logs
    db_scan.edr_logs = edr_logs
    db_scan.edr_summary = edr_summary
    db_scan.agent_logs = agent_logs
    db_scan.rededr_events = rededr_events
    db_scan.result = result_is_detected
    db_scan.completed_at = datetime.utcnow()
    thread_db.commit()

    return True

