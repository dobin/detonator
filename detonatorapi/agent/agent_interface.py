import logging
import requests
from typing import Optional, Dict, List, Type
import time
import json
from datetime import datetime
import os
from sqlalchemy.orm import Session, joinedload
import threading

from detonatorapi.schemas import EdrAlertsResponse
from detonatorapi.settings import UPLOAD_DIR, AGENT_DATA_GATHER_INTERVAL
from detonatorapi.database import Submission, SubmissionAlert, get_db_direct
from detonatorapi.db_interface import db_submission_change_status_quick, db_submission_add_log
from detonatorapi.agent.agent_api import AgentApi, ExecutionFeedback, FeedbackContainer
from detonatorapi.agent.rededr_agent import RedEdrAgentApi
from detonatorapi.edr_cloud.edr_cloud import EdrCloud
from detonatorapi.edr_cloud.edr_cloud_manager import get_relevant_edr_cloud_plugin


logger = logging.getLogger(__name__)

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
    agent_ip = db_submission.profile.vm_ip
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
    thread_db = get_db_direct()
    db_submission: Submission = thread_db.get(Submission, submission_id)
    if not db_submission:
        raise ValueError(f"Submission {submission_id} not found")
    
    # get agent IP and port
    agent_ip = db_submission.profile.vm_ip
    agent_port = db_submission.profile.port

    # get all required data into local variables
    filename = db_submission.file.filename
    exec_arguments = db_submission.file.exec_arguments
    runtime = db_submission.runtime
    drop_path = db_submission.drop_path
    execution_mode = db_submission.execution_mode
    rededr_port = db_submission.profile.rededr_port
    
    # Read file content from disk
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.isfile(file_path):
        # Hard error, as we cant scan anything
        db_submission_add_log(thread_db, db_submission, f"Error: File {filename} not found on disk")
        thread_db.close()
        return False
    with open(file_path, 'rb') as f:
        file_content = f.read()

    # Initialize Agent APIs    
    agentApi = AgentApi(agent_ip, agent_port)
    rededrApi: RedEdrAgentApi|None = None
    if rededr_port is not None:
        rededrApi = RedEdrAgentApi(agent_ip, rededr_port)
        if not rededrApi.IsReachable():
            db_submission_add_log(thread_db, db_submission, f"Warning: RedEdr Agent at {agent_ip}:{rededr_port} is not reachable")
            rededrApi = None  # disable

    # Acquire lock on DetonatorAgent
    if DO_LOCKING and not aquire_lock(thread_db, db_submission, agentApi):
        db_submission_add_log(thread_db, db_submission, f"Error: Failed to acquire lock on DetonatorAgent at {agent_ip} after 4 attempts")
        thread_db.close()
        return False
    
    # Clear logs on DetonatorAgent
    if not agentApi.ClearAgentLogs():
        db_submission_add_log(thread_db, db_submission, f"Warning: Could not clear Agent logs on DetonatorAgent at {agent_ip}")

    # RedEdr: Set the process name we gonna trace
    if rededrApi is not None:
        filename_trace = filename.rsplit('.', 1)[0] # remove file extension for trace
        db_submission_add_log(thread_db, db_submission, f"RedEdr: Start trace for process: {filename_trace}")
        trace_result = rededrApi.StartTrace([filename_trace])
        if not trace_result:
            db_submission_add_log(thread_db, db_submission, f"Error: Could not start trace on RedEdr, error: {trace_result.error_message}")
            rededrApi = None
            # Ignore failed/missing RedEdr, lets still do the rest
        else:
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
    if not exec_result:
        db_submission_add_log(thread_db, db_submission, f"Error: When executing file on DetonatorAgent: {exec_result.error_message}")
        # our main task failed. grab the logs from agent to see whats up
        logger.info("Gather Agent and Execution logs")
        agent_logs = agentApi.GetAgentLogs()
        process_output = agentApi.GetProcessOutput()
        db_submission.process_output = process_output
        db_submission.agent_logs = agent_logs
        db_submission.completed_at = datetime.utcnow()
        thread_db.commit()
        agentApi.ReleaseLock()
        thread_db.close()
        return False
    executionFeedback: ExecutionFeedback = exec_result.unwrap()
    if executionFeedback == ExecutionFeedback.VIRUS:
        db_submission_add_log(thread_db, db_submission, f"File {filename} is detected as malware when attempting to execute")
    elif executionFeedback == ExecutionFeedback.OK:
        # process is being executed. 
        db_submission_add_log(thread_db, db_submission, f"Success executing file {filename}")
        db_submission_add_log(thread_db, db_submission, f"Waiting, runtime of {runtime} seconds...")
        thread_db.commit()

        # boot the agent local EDR data gatherer thread
        # this will regularly update: submission.alerts
        #   (especially for long running processes)
        # BUT: we gonna overwrite it at the end of the function
        # ALSO: we dont create submission.alerts and submission.edr_verdict in here
        # ENDS: on submission state change
        db_submission_add_log(thread_db, db_submission, f"Starting local EDR data gatherer")
        threading.Thread(target=thread_local_edr_gatherer, args=(submission_id, agentApi )).start()

        # boot the relevant EDR Cloud monitoring plugin if any
        edr_cloud_plugin: Optional[EdrCloud] = get_relevant_edr_cloud_plugin(db_submission.profile.data)
        if edr_cloud_plugin is not None:
            db_submission_add_log(thread_db, db_submission, f"Starting EDR Cloud plugin: {edr_cloud_plugin.__class__.__name__}")
            # It will start a new thread
            # ENDS: on submission state change
            edr_cloud_plugin.start_monitoring_thread(submission_id)

        # let it cook
        time.sleep(runtime)
        
        # enough execution.
        db_submission_add_log(thread_db, db_submission, f"Runtime completed")
        thread_db.commit()

    # give some time for windows to scan, deliver the virus ETW alert events n stuff
    time.sleep(SLEEP_TIME_POST_SUBMISSION)

    # Get RedEdr Events (if exists)
    # before killing the process (no shutdown events)
    # & Agent logs themselves
    rededr_events = None
    rededr_logs = None
    if rededrApi is not None and executionFeedback == ExecutionFeedback.OK:
        logger.info("Gather EDR events from RedEdr")
        rededr_events = rededrApi.GetEvents()
        if rededr_events is None:  # single check for now
            db_submission_add_log(thread_db, db_submission, "Warning: could not get RedEdr logs from Agent - RedEdr crashed?")
            # no return, we still want to try to get other logs

        rededr_logs = rededrApi.GetAgentLogs()
        if rededr_logs is None:
            db_submission_add_log(thread_db, db_submission, "Warning: could not get RedEdr Agent logs from Agent")

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
    agent_logs = agentApi.GetAgentLogs()
    process_output = agentApi.GetProcessOutput()       # always for now

    # we finished 
    if DO_LOCKING:
        logger.info("Attempt to release lock")
        release_result = agentApi.ReleaseLock()
        if not release_result:
            db_submission_add_log(thread_db, db_submission, f"Error: Could not release lock on Agent at {agent_ip}: {release_result.error_message}")
        else:
            db_submission_add_log(thread_db, db_submission, f"Successfully released lock")
    db_submission_add_log(thread_db, db_submission, f"All information gathered from Agents, processing logs...")

    # EDR local telemetry processing
    absorb_agent_edr_data(submission_id, agentApi)

    # write all logs to the database
    db_submission.process_output = process_output
    db_submission.agent_logs = agent_logs
    db_submission.rededr_events = rededr_events
    db_submission.rededr_logs = rededr_logs
    db_submission.completed_at = datetime.utcnow()
    thread_db.commit()
    thread_db.close()

    return True


def thread_local_edr_gatherer(submission_id: int, agentApi: AgentApi):
    db = get_db_direct()

    while True:
        db_submission = db.get(Submission, submission_id)
        if not db_submission:
            break

        logger.info(f"Local EDR data gatherer for submission: {submission_id}: {db_submission.status}")

        # Force reload from database to bypass SQLAlchemy cache ffs
        db.refresh(db_submission)

        # If submission is finished, we are so too
        if db_submission.status in ("error", "finished"):
            logger.info(f"Submission {db_submission.id} is finished, stopping agent data gatherer")
            break
        # but actually, only when the VM is alive ("processing")
        if db_submission.status not in ("processing"):
            logger.info(f"Submission {db_submission.id} not processing anymore, stopping data gather")
            break
        
        # Update DB with latest EDR local logs
        logger.info(f"Gather local EDR logs for submission {db_submission.id}")
        absorb_agent_edr_data(submission_id, agentApi)

        # wait a bit for next time
        time.sleep(AGENT_DATA_GATHER_INTERVAL)

    db.close()


def absorb_agent_edr_data(submission_id, agentApi: AgentApi):
    # Gather logs from Agent
    edrAlertsResponse: Optional[EdrAlertsResponse] = agentApi.GetEdrAlertsResponse()
    if edrAlertsResponse is None:
        logger.warning(f"Submission {submission_id}: could not get EDR logs from Agent")
        return

    # insert all non-existing alerts into DB
    db = get_db_direct()
    db_submission: Submission = db.get(Submission, submission_id)
    if not db_submission:
        logger.error(f"Submission {submission_id} not found")
        db.close()
        return
    
    for alert in edrAlertsResponse.alerts:
        exists = False
        for existing_alert in db_submission.alerts:
            if existing_alert.alert_id == alert.alertId:
                exists = True
                break
        if exists:
            continue

        # Convert Pydantic schema to SQLAlchemy model
        db_alert = SubmissionAlert(
            alert_id=alert.alertId,
            source=alert.source, 
            title=alert.title,
            severity=alert.severity,
            category=alert.category,
            detection_source=alert.detectionSource,
            detected_at=alert.detectedAt,
            raw=alert.raw,
            submission_id=db_submission.id
        )
        db_submission.alerts.append(db_alert)

    if edrAlertsResponse.detected:
        logger.info(f"Submission {db_submission.id}: EDR logs indicate: detected")
        edr_verdict = "detected"
    else:
        logger.info(f"Submission {db_submission.id}: EDR logs indicate: not detected")
        edr_verdict = "not_detected"

    db_submission.edr_verdict = edr_verdict
    db.commit()
    db.close()


def aquire_lock(thread_db: Session, db_submission: Submission, agentApi: AgentApi) -> bool:
    logger.info("Attempt to acquire lock at DetonatorAgent")
    # Try to acquire lock 4 times with 30 second intervals
    lock_acquired = False
    attempts = 6
    for attempt in range(attempts):
        if agentApi.IsInUse():
            db_submission_add_log(thread_db, db_submission, f"Attempt {attempt + 1}: Agent is currently in use")
        else:
            lock_result = agentApi.AcquireLock()
            if lock_result:
                db_submission_add_log(thread_db, db_submission, f"Successfully acquired lock on attempt {attempt + 1}")
                lock_acquired = True
                break
            else:
                db_submission_add_log(thread_db, db_submission, f"Attempt {attempt + 1}: Could not lock Agent: {lock_result.error_message}")
        
        if attempt < attempts - 1:  # Don't sleep after the last attempt
            db_submission_add_log(thread_db, db_submission, f"Waiting 30 seconds before retry...")
            time.sleep(30)
    
    return lock_acquired