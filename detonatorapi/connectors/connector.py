from datetime import datetime
import logging
import threading
from typing import Dict, List, Optional
import time
from sqlalchemy.orm import Session, joinedload

from detonatorapi.database import get_db_direct, Submission
from detonatorapi.db_interface import db_submission_change_status_quick, db_submission_add_log, db_submission_change_status
from detonatorapi.agent.agent_interface import absorb_agent_edr_data, connect_to_agent, submit_file_to_agent
from detonatorapi.edr_cloud.edr_cloud import EdrCloud
from detonatorapi.edr_cloud.edr_cloud_manager import get_relevant_edr_cloud_plugin
from detonatorapi.agent.agent_api import AgentApi, ExecutionFeedback, FeedbackContainer
from detonatorapi.agent.rededr_agent import RedEdrAgentApi

DO_LOCKING = True
SLEEP_TIME_REDEDR_WARMUP = 3.0
SLEEP_TIME_POST_SUBMISSION = 10.0
SLEEP_INTERVAL_PROCESSING = 3  # seconds between absorb checks during execution

logger = logging.getLogger(__name__)


class ConnectorBase:
    def __init__(self,):
        pass

    def init(self) -> bool:
        raise NotImplementedError("This method should be overridden by subclasses")

    def get_description(self) -> str:
        """Return a description of what this connector does"""
        return "Base connector class"
    
    def get_comment(self) -> str:
        """Return additional comments about this connector"""
        return ""
    
    def get_sample_data(self) -> Dict[str, str]:
        """Return sample data for this connector"""
        return {}

    def is_available(self, submission_id: int) -> bool:
        """Check if the VM for this submission is available (reachable and not locked).
        
        The vm_monitor will only transition a submission from 'fresh' to 'instantiate'
        when this returns True. Subclasses should override to add connector-specific checks.
        """
        return True

    def instantiate(self, submission_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")


    def connect(self, submission_id: int):
        def connect_thread(submission_id: int):
            try:
                if connect_to_agent(submission_id):
                    db_submission_change_status(submission_id, "connected")
                else:
                    db_submission_change_status(submission_id, "error", "Could not connect")
            except Exception as e:
                logger.error(f"connect_thread unhandled exception for submission {submission_id}: {e}")
                db_submission_change_status(submission_id, "error", str(e))

        threading.Thread(target=connect_thread, args=(submission_id, )).start()


    def process(self, submission_id: int, pre_wait: int = 0):
        def process_thread(submission_id: int):
            # TODO This is to handle Azure VM startup weirdness
            # Just because we could connect, doesnt mean we want to immediately process
            # Let the VM start up for a bit
            time.sleep(pre_wait)

            # Get the db submission
            thread_db = get_db_direct()
            db_submission: Submission = thread_db.get(Submission, submission_id)
            if not db_submission:
                logger.error(f"Submission {submission_id} not found")
                return

            # Get Agent APIs
            agentApi: AgentApi
            rededrApi: Optional[RedEdrAgentApi]
            agentApi, rededrApi = create_agent_apis(db_submission, thread_db)

            # DetonatorAgent: Aquire Lock (reserve the VM for us)
            if DO_LOCKING and not agentApi.AcquireLock():
                db_submission_add_log(thread_db, db_submission, f"Error: Failed to acquire lock on DetonatorAgent at {agent_ip}")
                thread_db.close()
                return

            # DetonatorAgent: Clear previous logs
            if not agentApi.ClearAgentLogs():
                db_submission_add_log(thread_db, db_submission, f"Warning: Could not clear Agent logs on DetonatorAgent at {agent_ip}")

            # RedEdr: Set the new process name we gonna trace
            if rededrApi is not None:
                filename_trace = db_submission.file.filename
                #filename_trace = filename.rsplit('.', 1)[0] # remove file extension for trace
                trace_result = rededrApi.StartTrace([filename_trace])
                if not trace_result:
                    db_submission_add_log(thread_db, db_submission, f"RedEdr: Error could not start trace: {trace_result.error_message}")
                    rededrApi = None
                    # Ignore failed/missing RedEdr, lets still do the rest
                else:
                    db_submission_add_log(thread_db, db_submission, f"RedEdr: Start trace for process: {filename_trace}")
                    # let RedEdr boot up
                    #time.sleep(SLEEP_TIME_REDEDR_WARMUP)

            # DetonatorAgent: Submit file and start execution
            executionFeedback = submit_file_to_agent(thread_db, db_submission, agentApi)
  
            # boot cloud gatherer, if any
            #   E.g. for MDE, Elastic
            # It will grab the EDR events in the background
            #   even if the VM has been shutdown already
            # THREAD ENDS: based on time after submission ends
            if executionFeedback == ExecutionFeedback.VIRUS or executionFeedback == ExecutionFeedback.OK:
                edr_cloud_plugin: Optional[EdrCloud] = get_relevant_edr_cloud_plugin(db_submission.profile.data)
                if edr_cloud_plugin is not None:
                    db_submission_add_log(thread_db, db_submission, f"Starting EDR Cloud plugin: {edr_cloud_plugin.__class__.__name__}")
                    # It will start a new thread
                    # ENDS: on submission state change
                    edr_cloud_plugin.InitializeClient(db_submission.profile.data)
                    thread = threading.Thread(
                        target=edr_cloud_plugin.monitor_loop,
                        name=f"monitor-{submission_id}",
                        daemon=True,
                        args=(submission_id,)
                    )
                    thread.start()
                    logger.info("Alert monitoring thread started")

            if executionFeedback == ExecutionFeedback.VIRUS:
                # Not executed, detected on file-write
                db_submission.agent_phase = "no_execution"
                db_submission.edr_verdict = "file_detected"
                db_submission_add_log(thread_db, db_submission, f"File {db_submission.file.filename} is detected as malware when writing to disk (no execution)")
                thread_db.commit()
            elif executionFeedback is ExecutionFeedback.ERROR:
                # No write, no execution, something went wrong
                logger.error(f"Error when executing file: {db_submission.file.filename}")
                db_submission.agent_phase = "error"
                db_submission.edr_verdict = "error"
                db_submission_add_log(thread_db, db_submission, f"File {db_submission.file.filename} execution failed to start")
                thread_db.commit()
            elif executionFeedback == ExecutionFeedback.OK:
                # process is being executed. 
                db_submission.agent_phase = "executing"
                db_submission.edr_verdict = "pending"
                db_submission_add_log(thread_db, db_submission, f"Success executing file {db_submission.file.filename}")
                db_submission_add_log(thread_db, db_submission, f"Waiting, runtime of {db_submission.runtime} seconds...")
                thread_db.commit()

                # boot the agent local EDR data gatherer thread
                # this will regularly update: submission.alerts
                #   (especially for long running processes)
                # BUT: we gonna overwrite it at the end of the function
                # ALSO: we dont create submission.alerts and submission.edr_verdict in here
                # ENDS: on submission state change
                # With proxmox, this will only run as long as the VM is alive (i.e. processing = process executing)
                db_submission_add_log(thread_db, db_submission, f"Starting local EDR data gatherer")

                # let it cook
                runtime = db_submission.runtime
                elapsed = 0
                while elapsed < runtime:
                    time.sleep(SLEEP_INTERVAL_PROCESSING)
                    elapsed += SLEEP_INTERVAL_PROCESSING

                    # Refresh submission state to check if it's still executing
                    thread_db.refresh(db_submission)
                    if db_submission.agent_phase != "executing":
                        db_submission_add_log(thread_db, db_submission, f"Execution interrupted at {min(elapsed, runtime)}/{runtime} seconds - agent_phase changed to {db_submission.agent_phase}")
                        break

                    # absorb new events
                    # This will update: 
                    # - submission.alerts
                    # - submission.edr_verdict
                    absorb_agent_edr_data(thread_db, db_submission, agentApi)
                
                # enough execution.
                db_submission_add_log(thread_db, db_submission, f"Finished execution")
                if db_submission.agent_phase == "executing":
                    # keep "no_execution", "stop", and possibly others
                    db_submission.agent_phase = "finished"
                thread_db.commit()

                # give some time for windows to scan, deliver the virus ETW alert events n stuff
                # for short runtimes (or events at the end of runtime)
                time.sleep(SLEEP_TIME_POST_SUBMISSION)

                # Get RedEdr Events & Logs
                #   before killing the process (no shutdown events)
                if rededrApi is not None:
                    logger.info("Gather EDR events and logs from RedEdr")
                    db_submission.rededr_events = rededrApi.GetEvents() or ""
                    db_submission.rededr_logs = rededrApi.GetAgentLogs() or ""

                # kill process
                stop_result = agentApi.KillProcess()
                if stop_result:
                    db_submission_add_log(thread_db, db_submission, f"Process successfully killed")
                else:
                    db_submission_add_log(thread_db, db_submission, f"Error: Could not kill process: {stop_result.error_message}")

                # Grab process output
                db_submission.process_output = agentApi.GetProcessOutput() or ""

            # Gather logs from Agent
            db_submission.agent_logs = agentApi.GetAgentLogs() or ""
            
            # RedEdr: stop trace (probably doesnt do much)
            if rededrApi is not None:
                rededrApi.StopTrace()

            # DetonatorAgent: Unlock (the VM)
            if DO_LOCKING:
                logger.info("Attempt to release lock")
                release_result = agentApi.ReleaseLock()
                if not release_result:
                    db_submission_add_log(thread_db, db_submission, f"Error: Could not release lock on Agent at: {release_result.error_message}")
                else:
                    db_submission_add_log(thread_db, db_submission, f"Successfully released lock")

            db_submission.completed_at = datetime.utcnow()
            db_submission_add_log(thread_db, db_submission, f"All information gathered from Agents, processing logs...")

            db_submission_change_status(submission_id, "processed")
            thread_db.commit()
            thread_db.close()

        threading.Thread(target=process_thread, args=(submission_id, )).start()


    def stop(self, submission_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")

    def remove(self, submission_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")

    def kill(self, submission_id: int):
        raise NotImplementedError("This method should be overridden by subclasses")


def create_agent_apis(db_submission: Submission, thread_db: Session) -> tuple[AgentApi, RedEdrAgentApi|None]:
    """Factory function to initialize AgentApi and RedEdrAgentApi from a submission."""
    agent_ip = db_submission.profile.vm_ip
    agent_port = db_submission.profile.port
    rededr_port = db_submission.profile.rededr_port
    agentApi = AgentApi(agent_ip, agent_port)
    rededrApi: RedEdrAgentApi|None = None
    if rededr_port is not None:
        rededrApi = RedEdrAgentApi(agent_ip, rededr_port)
        if not rededrApi.IsReachable():
            db_submission_add_log(thread_db, db_submission, f"Warning: RedEdr Agent at {agent_ip}:{rededr_port} is not reachable")
            rededrApi = None  # disable
    return agentApi, rededrApi

