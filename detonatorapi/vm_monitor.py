import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
import time
import threading

from .database import get_db_direct, Submission
from .db_interface import db_submission_change_status_quick
from .utils import mylog
from .settings import *

from .connectors.connector import ConnectorBase
from .connectors.connector_newazure import ConnectorNewAzure
from .connectors.connector_live import ConnectorLive
from .connectors.connectors import connectors

logger = logging.getLogger(__name__)



class VMMonitorTask:
    """Background task to monitor Submission status and lifecycle"""
    
    def __init__(self):
        self.running = False
        self.task = None


    def start_monitoring(self):
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info("VM monitoring task started")
    

    def stop_monitoring(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                self.task
            except asyncio.CancelledError:
                pass
        logger.info("VM monitoring task stopped")
    

    async def _monitor_loop(self):
        while self.running:
            db = None
            try:
                db = get_db_direct()
                self.check_all_submissions(db)
                db.commit()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in VM monitoring loop: {str(e)}")
                await asyncio.sleep(1)
            finally:
                if db:
                    db.close()
    

    def check_all_submissions(self, db: Session):
        submissions = db.query(Submission).all()
        for submission in submissions:
            submission_id: int = submission.id
            status: str = submission.status

            # Skip finished (nothing todo)
            if status in [ 'finished', 'error' ]:
                continue

            # get responsible VM manager, based on the profile->connector
            if not submission.profile.connector:
                logger.error(f"Submission {submission_id} has no profile connector")
                db_submission_change_status_quick(db, submission, "error")
                continue
            connector: ConnectorBase|None = connectors.get(submission.profile.connector)
            if not connector:
                logger.error(f"Submission {submission_id} has no valid VM manager defined for profile connector: {submission.profile.connector}")
                logger.error(f"VM Managers: {list(connectors.get_all().keys())}")
                db_submission_change_status_quick(db, submission, "error")
                continue

            # cleanup failed
            if status == "error" and submission.vm_exist == 1:
                db_submission_change_status_quick(db, submission, "killing")

            # State Machine
            match status:
                case "fresh":
                    # Start the process with instantiating the VM
                    db_submission_change_status_quick(db, submission, "instantiate")

                case "instantiate":
                    db_submission_change_status_quick(db, submission, "instantiating")
                    connector.instantiate(submission_id)
                case "instantiated":
                    db_submission_change_status_quick(db, submission, "connect")

                case "connect":
                    db_submission_change_status_quick(db, submission, "connecting")
                    connector.connect(submission_id)
                case "connected":
                    db_submission_change_status_quick(db, submission, "processing")

                case "processing":
                    db_submission_change_status_quick(db, submission, "process")
                    connector.submission(submission_id)

                case "processed":
                    db_submission_change_status_quick(db, submission, "stop")

                case "stop":
                    db_submission_change_status_quick(db, submission, "stopping")
                    connector.stop(submission_id)
                case "stopped":
                    db_submission_change_status_quick(db, submission, "remove")

                case "remove":
                    db_submission_change_status_quick(db, submission, "removing")
                    connector.remove(submission_id)
                case "removed":
                    db_submission_change_status_quick(db, submission, "finished")

                case "kill":
                    db_submission_change_status_quick(db, submission, "killing")
                    connector.kill(submission_id)


# Global VM monitor instance
vm_monitor = VMMonitorTask()

def start_vm_monitoring():
    """Start the global VM monitoring task"""
    vm_monitor.start_monitoring()

def stop_vm_monitoring():
    """Stop the global VM monitoring task"""
    vm_monitor.stop_monitoring()
