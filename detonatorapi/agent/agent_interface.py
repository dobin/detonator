import logging
import requests
from typing import Optional, Dict
import time
import json
from datetime import datetime
from detonatorapi.edr_parser.edr_parser import EdrParser
from typing import List

from detonatorapi.database import Scan, get_db_for_thread
from detonatorapi.db_interface import db_scan_change_status_quick, db_scan_add_log
from detonatorapi.agent.agent_api import AgentApi
from detonatorapi.agent.rededr_agent import RedEdrAgentApi
from detonatorapi.edr_parser.parser_defender import DefenderParser
from detonatorapi.agent.agent_api import ExecutionResult

logger = logging.getLogger(__name__)

parsers: List[EdrParser] = [
    DefenderParser(),
]

SLEEP_TIME_REDEDR_WARMUP = 3.0
SLEEP_TIME_POST_SCAN = 10.0
DO_LOCKING = True


# Attempt to connect to the agent port to see if its up and running
def connect_to_agent(scan_id) -> bool:
    agent_ip: Optional[str] = None
    thread_db = get_db_for_thread()
    db_scan: Scan = thread_db.get(Scan, scan_id)
    if not db_scan:
        logger.error(f"Scan {scan_id} not found")
        return False
    # IP in template?
    if 'ip' in db_scan.profile.data:
        agent_ip = db_scan.profile.data['ip']
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
            # just connect
            #if response.status_code == 200:
            db_scan_add_log(thread_db, db_scan, f"Connected to agent at {url} on attempt {attempt + 1}")
            return True
        except requests.RequestException as e:
            db_scan_add_log(thread_db, db_scan, f"Attempt {attempt + 1}: Could not connect to agent at {url}")
        
        time.sleep(1)

    db_scan_add_log(thread_db, db_scan, f"Failed to connect to agent at {url} after 10 attempts")
    return False


def scan_file_with_agent(scan_id: int) -> bool:
    agent_ip: Optional[str] = None
    thread_db = get_db_for_thread()
    db_scan: Scan = thread_db.get(Scan, scan_id)
    if not db_scan:
        logger.error(f"Scan {scan_id} not found")
        return False
    # IP in template?
    if 'ip' in db_scan.profile.data:
        agent_ip = db_scan.profile.data['ip']
    else:
        # IP in VM?
        agent_ip = db_scan.vm_ip_address
    if not agent_ip:
        logger.error(f"Scan {db_scan.id} has no VM IP address defined")
        return False
    agent_port = db_scan.profile.port  # port is always defined in the profile

    filename = db_scan.file.filename
    exec_arguments = db_scan.file.exec_arguments
    file_content = db_scan.file.content
    runtime = db_scan.runtime
    drop_path = db_scan.drop_path
    rededr_port = db_scan.profile.rededr_port
    agentApi = AgentApi(agent_ip, agent_port)
    rededrApi: RedEdrAgentApi|None = None
    if rededr_port is not None:
        rededrApi = RedEdrAgentApi(agent_ip, rededr_port)

    if DO_LOCKING:
        logger.info("Attempt to acquire lock at DetonatorAgent")
        # Try to acquire lock 4 times with 30 second intervals
        lock_acquired = False
        attempts = 6
        for attempt in range(attempts):
            if agentApi.IsInUse():
                db_scan_add_log(thread_db, db_scan, f"Attempt {attempt + 1}: DetonatorAgent at {agent_ip} is currently in use")
            else:
                lock_result = agentApi.AcquireLock()
                if lock_result:
                    db_scan_add_log(thread_db, db_scan, f"Successfully acquired lock on attempt {attempt + 1}")
                    lock_acquired = True
                    break
                else:
                    db_scan_add_log(thread_db, db_scan, f"Attempt {attempt + 1}: Could not lock DetonatorAgent at {agent_ip}: {lock_result.error_message}")
            
            if attempt < attempts - 1:  # Don't sleep after the last attempt
                db_scan_add_log(thread_db, db_scan, f"Waiting 30 seconds before retry...")
                time.sleep(30)
        
        if not lock_acquired:
            db_scan_add_log(thread_db, db_scan, f"Error: Failed to acquire lock on DetonatorAgent at {agent_ip} after 4 attempts")
            return False

    # RedEdr (if exist): Set the process name we gonna trace
    if rededrApi is not None:
        filename_trace = filename.rsplit('.', 1)[0] # remove file extension for trace
        db_scan_add_log(thread_db, db_scan, f"RedEdr: Start trace for process: {filename_trace}")
        trace_result = rededrApi.StartTrace([filename_trace])
        if not trace_result:
            db_scan_add_log(thread_db, db_scan, f"Error: Could not start trace on RedEdr, error: {trace_result.error_message}")
            agentApi.ReleaseLock()
            return False
        
        # let RedEdr boot up
        time.sleep(SLEEP_TIME_REDEDR_WARMUP)
    thread_db.commit()

    # Execute file on DetonatorAgent
    if not drop_path or drop_path == "":
        drop_path = "C:\\Users\\Public\\Downloads\\"
    if not exec_arguments or exec_arguments == "":
        exec_arguments = ""

    db_scan_add_log(thread_db, db_scan, f"Executing file {filename} on DetonatorAgent at {agent_ip} with runtime {runtime} seconds and malware path {drop_path}")
    executionResult: ExecutionResult = agentApi.ExecFile(filename, file_content, drop_path, exec_arguments)
    is_malware = False
    if executionResult == ExecutionResult.ERROR:
        db_scan_add_log(thread_db, db_scan, f"Error: When executing file on DetonatorAgent")
        agentApi.ReleaseLock()
        return False
    elif executionResult == ExecutionResult.VIRUS:
        db_scan_add_log(thread_db, db_scan, f"File {filename} is detected as malware when writing to disk")
        is_malware = True
    elif executionResult == ExecutionResult.OK:
        db_scan_add_log(thread_db, db_scan, f"Success executing file {filename}")
        db_scan_add_log(thread_db, db_scan, f"Waiting, runtime of {runtime} seconds...")
        thread_db.commit()

        # process is being executed. 
        time.sleep(runtime)
        
        # enough execution.
        db_scan_add_log(thread_db, db_scan, f"Runtime completed")
        thread_db.commit()

    # give some time for windows to scan, deliver the virus ETW alert events n stuff
    time.sleep(SLEEP_TIME_POST_SCAN)

    # RedEdr (if exists): logs 
    # before killing the process
    rededr_events = None
    if rededrApi is not None:
        logger.info("Gather EDR events from RedEdr")
        rededr_events = rededrApi.GetEvents()
        if rededr_events is None:  # single check for now
            db_scan_add_log(thread_db, db_scan, "Warning: could not get RedEdr logs from Agent - RedEdr crashed?")
            # no return, we still want to try to get other logs
    
    # Get EDR logs
    edr_logs = agentApi.GetEdrLogs()

    # kill process (after gathering EDR events, so we dont have the shutdown events)
    logger.info("Attempt to kill process")
    stop_result = agentApi.KillProcess()
    if stop_result:
        db_scan_add_log(thread_db, db_scan, f"Process successfully killed")
    else:
        db_scan_add_log(thread_db, db_scan, f"Error: Could not kill process: {stop_result.error_message}")
        # no return, we dont care

    # Gather logs from Agent
    # After stopping the trace, so we have all the Agent logs (including the process killing)
    logger.info("Gather Agent and Execution logs")
    agent_logs = agentApi.GetAgentLogs()
    execution_logs = agentApi.GetExecutionLogs()

    # we finished 
    if DO_LOCKING:
        logger.info("Attempt to release lock")
        release_result = agentApi.ReleaseLock()
        if not release_result:
            db_scan_add_log(thread_db, db_scan, f"Error: Could not release lock on Agent at {agent_ip}: {release_result.error_message}")
        else:
            db_scan_add_log(thread_db, db_scan, f"Successfully released lock")
    db_scan_add_log(thread_db, db_scan, f"All information gathered from Agents, processing logs...")

    # Preparse all the logs
    edr_summary = []  # will be generated
    result_is_detected = ""  # will be generated
    if agent_logs is None:
        agent_logs = "No Agent logs available"
        db_scan_add_log(thread_db, db_scan, "Warning: could not get Agent logs from Agent")
    if rededr_events is None:
        rededr_events = "No RedEdr logs available"
        db_scan_add_log(thread_db, db_scan, "Warning: could not get RedEdr logs from Agent")
    if execution_logs is None:
        execution_logs = "No Execution logs available"
        db_scan_add_log(thread_db, db_scan, "Warning: could not get Execution logs from Agent")
    if edr_logs is None:
        result_is_detected = "N/A"
        edr_logs = ""
        db_scan_add_log(thread_db, db_scan, "Warning: could not get EDR logs from Agent")
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
                            db_scan_add_log(thread_db, db_scan, "EDR logs indicate: detected")
                        else:
                            result_is_detected = "not_detected"
                            db_scan_add_log(thread_db, db_scan, "EDR logs indicate: not detected")
                    else:
                        db_scan_add_log(thread_db, db_scan, "EDR logs could not be parsed")
                    break

        except Exception as e:
            logger.error(edr_logs)
            logger.error(f"Error parsing Defender XML logs: {e}")

    # overwrite previous detection for RedEdr, we dont care
    if db_scan.profile.edr_collector == "RedEdr":
        result_is_detected = ""

    # if its already detected as malware, make sure the status is set
    # as we might not have any EDR logs
    if is_malware:
        result_is_detected = "file_detected"

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
