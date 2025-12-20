import logging
import requests
from typing import Optional, Dict
import time
import json
from datetime import datetime
from typing import List
import os
from sqlalchemy.orm import Session, joinedload

from detonatorapi.settings import UPLOAD_DIR, AGENT_DATA_GATHER_INTERVAL
from detonatorapi.database import Submission, get_db_direct
from detonatorapi.db_interface import db_submission_change_status_quick, db_submission_add_log
from detonatorapi.agent.agent_api import AgentApi, ExecutionFeedback, FeedbackContainer
from detonatorapi.agent.rededr_agent import RedEdrAgentApi

# Parsers
from detonatorapi.edr_parser.edr_parser import EdrParser
from detonatorapi.edr_parser.parser_defender import DefenderParser
from detonatorapi.edr_parser.example_parser import ExampleParser

logger = logging.getLogger(__name__)

parsers: List[EdrParser] = [
    DefenderParser(),
    ExampleParser(),
]

SLEEP_TIME_REDEDR_WARMUP = 3.0
SLEEP_TIME_POST_SUBMISSION = 10.0
DO_LOCKING = True


# Attempt to connect to the agent port to see if its up and running
def connect_to_agent(submission_id) -> bool:
    agent_ip: Optional[str] = None
    thread_db = get_db_direct()
    db_submission: Submission = thread_db.get(Submission, submission_id)
    if not db_submission:
        logger.error(f"Submission {submission_id} not found")
        thread_db.close()
        return False
    # IP in template?
    if 'ip' in db_submission.profile.data:
        agent_ip = db_submission.profile.data['ip']
    else:
        # IP in VM?
        agent_ip = db_submission.vm_ip_address
    if not agent_ip:
        logger.error(f"Submission {db_submission.id} has no VM IP address defined")
        thread_db.close()
        return False
    agent_port = db_submission.profile.port
    
    url = "http://" + agent_ip + ":" + str(agent_port)

    for attempt in range(15):  # 15 * (1 + 3) = 60s
        try:
            response = requests.get(url, timeout=3)
            # just connect
            #if response.status_code == 200:
            db_submission_add_log(thread_db, db_submission, f"Connected to agent at {url} on attempt {attempt + 1}")
            thread_db.close()
            return True
        except requests.RequestException as e:
            db_submission_add_log(thread_db, db_submission, f"Attempt {attempt + 1}: Could not connect to agent at {url}")
        
        time.sleep(1)

    db_submission_add_log(thread_db, db_submission, f"Failed to connect to agent at {url} after 10 attempts")
    thread_db.close()
    return False


def submit_file_to_agent(submission_id: int) -> bool:
    agent_ip: Optional[str] = None
    thread_db = get_db_direct()
    db_submission: Submission = thread_db.get(Submission, submission_id)
    if not db_submission:
        logger.error(f"Submission {submission_id} not found")
        thread_db.close()
        return False
    # IP in template?
    if 'ip' in db_submission.profile.data:
        agent_ip = db_submission.profile.data['ip']
    else:
        # IP in VM?
        agent_ip = db_submission.vm_ip_address
    if not agent_ip:
        logger.error(f"Submission {db_submission.id} has no VM IP address defined")
        thread_db.close()
        return False
    agent_port = db_submission.profile.port  # port is always defined in the profile

    filename = db_submission.file.filename
    exec_arguments = db_submission.file.exec_arguments
    
    # Read file content from disk
    file_path = os.path.join(UPLOAD_DIR, db_submission.file.filename)
    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    runtime = db_submission.runtime
    drop_path = db_submission.drop_path
    execution_mode = db_submission.execution_mode
    rededr_port = db_submission.profile.rededr_port
    agentApi = AgentApi(agent_ip, agent_port)
    rededrApi: RedEdrAgentApi|None = None
    if rededr_port is not None:
        rededrApi = RedEdrAgentApi(agent_ip, rededr_port)
        if not rededrApi.IsReachable():
            db_submission_add_log(thread_db, db_submission, f"Warning: RedEdr Agent at {agent_ip}:{rededr_port} is not reachable")
            rededrApi = None  # disable

    if DO_LOCKING:
        logger.info("Attempt to acquire lock at DetonatorAgent")
        # Try to acquire lock 4 times with 30 second intervals
        lock_acquired = False
        attempts = 6
        for attempt in range(attempts):
            if agentApi.IsInUse():
                db_submission_add_log(thread_db, db_submission, f"Attempt {attempt + 1}: DetonatorAgent at {agent_ip} is currently in use")
            else:
                lock_result = agentApi.AcquireLock()
                if lock_result:
                    db_submission_add_log(thread_db, db_submission, f"Successfully acquired lock on attempt {attempt + 1}")
                    lock_acquired = True
                    break
                else:
                    db_submission_add_log(thread_db, db_submission, f"Attempt {attempt + 1}: Could not lock DetonatorAgent at {agent_ip}: {lock_result.error_message}")
            
            if attempt < attempts - 1:  # Don't sleep after the last attempt
                db_submission_add_log(thread_db, db_submission, f"Waiting 30 seconds before retry...")
                time.sleep(30)
        
        if not lock_acquired:
            db_submission_add_log(thread_db, db_submission, f"Error: Failed to acquire lock on DetonatorAgent at {agent_ip} after 4 attempts")
            thread_db.close()
            return False

    # RedEdr (if exist): Set the process name we gonna trace
    if rededrApi is not None:
        filename_trace = filename.rsplit('.', 1)[0] # remove file extension for trace
        db_submission_add_log(thread_db, db_submission, f"RedEdr: Start trace for process: {filename_trace}")
        trace_result = rededrApi.StartTrace([filename_trace])
        if not trace_result:
            db_submission_add_log(thread_db, db_submission, f"Error: Could not start trace on RedEdr, error: {trace_result.error_message}")

            # Gather logs so the user can see what failed
            logger.info("Gather Agent and Execution logs")
            agent_logs = agentApi.GetAgentLogs()
            process_output = agentApi.GetExecutionLogs()
            db_submission.process_output = process_output
            db_submission.agent_logs = agent_logs
            db_submission.completed_at = datetime.utcnow()
            thread_db.commit()

            agentApi.ReleaseLock()
            thread_db.close()

            # Will be put into error state
            return False
        
        # let RedEdr boot up
        time.sleep(SLEEP_TIME_REDEDR_WARMUP)
    thread_db.commit()

    # Execute file on DetonatorAgent
    if not drop_path or drop_path == "":
        drop_path = "C:\\Users\\Public\\Downloads\\"
    if not exec_arguments or exec_arguments == "":
        exec_arguments = ""
    db_submission_add_log(thread_db, db_submission, f"Executing file {filename} on DetonatorAgent at {agent_ip}")
    db_submission_add_log(thread_db, db_submission, f"Executing with for {runtime}s and path {drop_path}")
    exec_result = agentApi.ExecFile(filename, file_content, drop_path, exec_arguments, execution_mode)
    is_malware = False
    if not exec_result:
        db_submission_add_log(thread_db, db_submission, f"Error: When executing file on DetonatorAgent: {exec_result.error_message}")
        agentApi.ReleaseLock()
        thread_db.close()
        return False
    
    executionFeedback: ExecutionFeedback = exec_result.unwrap()
    if executionFeedback == ExecutionFeedback.VIRUS:
        db_submission_add_log(thread_db, db_submission, f"File {filename} is detected as malware when writing to disk")
        is_malware = True
    elif executionFeedback == ExecutionFeedback.OK:
        db_submission_add_log(thread_db, db_submission, f"Success executing file {filename}")
        db_submission_add_log(thread_db, db_submission, f"Waiting, runtime of {runtime} seconds...")
        thread_db.commit()

        # process is being executed. 
        time.sleep(runtime)
        
        # enough execution.
        db_submission_add_log(thread_db, db_submission, f"Runtime completed")
        thread_db.commit()

    # give some time for windows to submission, deliver the virus ETW alert events n stuff
    time.sleep(SLEEP_TIME_POST_SUBMISSION)

    # Get RedEdr Logs (if exists)
    # before killing the process (no shutdown events)
    rededr_events = None
    rededr_telemetry_raw = ""
    if rededrApi is not None and executionFeedback == ExecutionFeedback.OK:
        logger.info("Gather EDR events from RedEdr")
        rededr_events = rededrApi.GetEvents()
        if rededr_events is None:  # single check for now
            db_submission_add_log(thread_db, db_submission, "Warning: could not get RedEdr logs from Agent - RedEdr crashed?")
            # no return, we still want to try to get other logs

        rededr_agent_logs = rededrApi.GetAgentLogs()
        if rededr_agent_logs is None:
            db_submission_add_log(thread_db, db_submission, "Warning: could not get RedEdr Agent logs from Agent")
        else:
            rededr_telemetry_raw = rededr_agent_logs

    # kill process
    if executionFeedback == ExecutionFeedback.OK:
        logger.info("Attempt to kill process")
        stop_result = agentApi.KillProcess()
        if stop_result:
            db_submission_add_log(thread_db, db_submission, f"Process successfully killed")
        else:
            db_submission_add_log(thread_db, db_submission, f"Error: Could not kill process: {stop_result.error_message}")
            # no return, we dont care

    # Gather logs from Agent
    # After killing the process, so we have all the Agent logs
    edr_telemetry_raw = agentApi.GetEdrLogs()
    agent_logs = agentApi.GetAgentLogs()
    process_output = agentApi.GetExecutionLogs()  # always for now

    # we finished 
    if DO_LOCKING:
        logger.info("Attempt to release lock")
        release_result = agentApi.ReleaseLock()
        if not release_result:
            db_submission_add_log(thread_db, db_submission, f"Error: Could not release lock on Agent at {agent_ip}: {release_result.error_message}")
        else:
            db_submission_add_log(thread_db, db_submission, f"Successfully released lock")
    db_submission_add_log(thread_db, db_submission, f"All information gathered from Agents, processing logs...")

    # Preparse all the logs
    edr_alerts = []  # will be generated
    result_is_detected = ""  # will be generated
    if agent_logs is None:
        agent_logs = "No Agent logs available"
        db_submission_add_log(thread_db, db_submission, "Warning: could not get Agent logs from Agent")
    if rededr_events is None:
        rededr_events = "No RedEdr logs available"
        db_submission_add_log(thread_db, db_submission, "Warning: could not get RedEdr logs from Agent")
    if process_output is None:
        process_output = {}
        db_submission_add_log(thread_db, db_submission, "Warning: could not get Execution logs from Agent")
    if edr_telemetry_raw is None:
        result_is_detected = "N/A"
        edr_telemetry_raw = ""
        db_submission_add_log(thread_db, db_submission, "Warning: could not get EDR logs from Agent")
    else:
        # get the actual EDR log
        edr_plugin_log: str = ""
        try:
            edr_plugin_log = json.loads(edr_telemetry_raw).get("logs", "")

            # EDR logs summary
            for parser in parsers:
                parser.load(edr_plugin_log)
                if parser.is_relevant():
                    db_submission_add_log(thread_db, db_submission, f"Using parser {parser.__class__.__name__} for EDR logs")
                    if parser.parse():
                        edr_alerts = parser.get_summary()
                        if parser.is_detected():
                            result_is_detected = "detected"
                            db_submission_add_log(thread_db, db_submission, "EDR logs indicate: detected")
                        else:
                            result_is_detected = "not_detected"
                            db_submission_add_log(thread_db, db_submission, "EDR logs indicate: not detected")
                    else:
                        db_submission_add_log(thread_db, db_submission, "EDR logs could not be parsed")
                    break

        except Exception as e:
            logger.error(edr_telemetry_raw)
            logger.error(f"Error parsing Defender XML logs: {e}")

    # overwrite previous detection for RedEdr, we dont care
    if db_submission.profile.edr_collector == "RedEdr":
        result_is_detected = ""

    # if its already detected as malware, make sure the status is set
    # as we might not have any EDR logs
    if is_malware:
        result_is_detected = "file_detected"

    # write all logs to the database
    db_submission.process_output = process_output
    db_submission.edr_telemetry_raw = edr_telemetry_raw
    db_submission.edr_alerts = edr_alerts
    db_submission.agent_logs = agent_logs
    db_submission.rededr_events = rededr_events
    db_submission.rededr_telemetry_raw = rededr_telemetry_raw
    db_submission.edr_verdict = result_is_detected
    db_submission.completed_at = datetime.utcnow()
    thread_db.commit()
    thread_db.close()

    return True


def thread_gatherer(submission_id: int):
    db = get_db_direct()

    submission = db.get(Submission, submission_id)
    if not submission:
        logger.error(f"Submission {submission_id} not found")
        db.close()
        return

    # IP in template?
    if 'ip' in submission.profile.data:
        agent_ip = submission.profile.data['ip']
    else:
        # IP in VM?
        agent_ip = submission.vm_ip_address
    if not agent_ip:
        logger.error(f"Submission {submission.id} has no VM IP address defined")
        db.close()
        return False
    agent_port = submission.profile.port  # port is always defined in the profile
    agentApi = AgentApi(agent_ip, agent_port)

    while True:
        submission = db.get(Submission, submission_id)
        if not submission:
            break

        # If submission is finished, we are so too
        if submission.status in ("error", "finished"):
            logger.warning(f"Submission {submission.id} is finished, stopping agent data gatherer")
            break
        # but actually, only when the VM is alive ("processing")
        if submission.status not in ("processing"):
            logger.info(f"Submission {submission.id} not processing anymore, stopping data gather")
            break
        
        # Update DB with latest EDR local logs
        logger.info(f"Gather local EDR logs for submission {submission.id}")
        edr_telemetry_raw = agentApi.GetEdrLogs()
        submission.edr_telemetry_raw = edr_telemetry_raw
        db.commit()

        # wait a bit for next time
        time.sleep(AGENT_DATA_GATHER_INTERVAL)

    db.close()

