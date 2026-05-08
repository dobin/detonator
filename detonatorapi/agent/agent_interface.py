import logging
import requests
from typing import Optional, Dict, List, Type
import os
from sqlalchemy.orm import Session, joinedload

from detonatorapi.schemas import EdrAlertsResponse
from detonatorapi.settings import UPLOAD_DIR
from detonatorapi.database import Submission, SubmissionAlert, get_db_direct
from detonatorapi.db_interface import db_submission_change_status_quick, db_submission_add_log
from detonatorapi.agent.agent_api import AgentApi, ExecutionFeedback, FeedbackContainer


logger = logging.getLogger(__name__)


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

    try:
        response = requests.get(url, timeout=3)
        db_submission_add_log(thread_db, db_submission, f"Connected to agent at {url}")
        thread_db.close()
        return True
    except requests.RequestException as e:
        db_submission_add_log(thread_db, db_submission, f"Could not connect to agent at {url}: {e}")
        thread_db.close()
        return False
 

def submit_file_to_agent(thread_db: Session, db_submission: Submission, agentApi: AgentApi) -> ExecutionFeedback:
    """Submit file to agent for execution. Returns ExecutionFeedback on success, or None on failure."""
    
    db_submission.agent_phase = "transmit"
    thread_db.commit()

    # get all required data into local variables
    filename = db_submission.file.filename
    exec_arguments = db_submission.file.exec_arguments
    runtime = db_submission.runtime
    drop_path = db_submission.drop_path
    execution_mode = db_submission.execution_mode
    
    # Read file content from disk
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.isfile(file_path):
        # Hard error, as we cant scan anything
        db_submission_add_log(thread_db, db_submission, f"Error: File {filename} not found on disk")
        thread_db.close()
        return ExecutionFeedback.ERROR
    with open(file_path, 'rb') as f:
        file_content = f.read()

    if len(file_content) == 0:
        db_submission_add_log(thread_db, db_submission, f"Error: File {filename} is empty (0 bytes), nothing to execute")
        return ExecutionFeedback.ERROR

    # Execute file on DetonatorAgent
    if not drop_path or drop_path == "":
        drop_path = "C:\\Users\\Public\\Downloads\\"
    if not exec_arguments:
        exec_arguments = ""
    db_submission_add_log(thread_db, db_submission, f"Executing file {filename} on DetonatorAgent at {db_submission.profile.vm_ip}")
    db_submission_add_log(thread_db, db_submission, f"Executing with for {runtime}s and path {drop_path}")
    exec_result = agentApi.ExecFile(filename, file_content, drop_path, exec_arguments, execution_mode)
    if not exec_result.success:
        db_submission_add_log(thread_db, db_submission, f"ExecFile failed: {exec_result.error_message}")
        return ExecutionFeedback.ERROR
    executionFeedback: ExecutionFeedback = exec_result.unwrap()
    return executionFeedback


def absorb_agent_edr_data(db, db_submission: Submission, agentApi: AgentApi):
    submission_id = db_submission.id

    # Gather logs from Agent
    edrAlertsResponse: Optional[EdrAlertsResponse] = agentApi.GetEdrAlertsResponse()
    if edrAlertsResponse is None:
        logger.warning(f"Submission {submission_id}: could not get EDR logs from Agent")
        return
    else:
        logger.info(f"Submission {submission_id}: got {len(edrAlertsResponse.alerts)} EDR alerts from Agent")

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

    if db_submission.edr_verdict == "file_detected":
        logger.info(f"Submission {db_submission.id}: EDR logs indicate: file_detected (already set)")
    else:
        if edrAlertsResponse.detected:
            logger.info(f"Submission {db_submission.id}: EDR logs indicate: detected")
            edr_verdict = "detected"
        else:
            logger.info(f"Submission {db_submission.id}: EDR logs indicate: not detected")
            edr_verdict = "not_detected"

        db_submission.edr_verdict = edr_verdict
    
    db.commit()