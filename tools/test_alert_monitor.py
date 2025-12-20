#!/usr/bin/env python3
"""
Test tool for AlertMonitorMde
Usage: python tools/test_alert_monitor.py <submission_id>
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from detonatorapi.edr_cloud.mde_alert_monitor import AlertMonitorMde
from detonatorapi.database import get_db, Submission

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_alert_monitor(submission_id: int):
    """Test AlertMonitorMde with the given submission ID"""
    
    # Verify submission exists
    db = get_db()
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        logger.error(f"Submission {submission_id} not found in database")
        db.close()
        return
    
    logger.info(f"Found submission {submission_id}: status={submission.status}, result={submission.result}")
    logger.info(f"Submission created at: {submission.created_at}")
    if submission.profile:
        logger.info(f"Profile: {submission.profile.name}")
        edr_mde_config = submission.profile.data.get("edr_mde")
        if edr_mde_config:
            logger.info(f"MDE device_id: {edr_mde_config.get('device_id')}")
            logger.info(f"MDE hostname: {edr_mde_config.get('hostname')}")
        else:
            logger.warning("No edr_mde configuration found in profile")
    else:
        logger.warning("Submission has no profile")
    
    db.close()
    
    # Create and start monitor
    logger.info("Starting AlertMonitorMde...")
    monitor = AlertMonitorMde(submission_id)
    monitor.start_monitoring()
    
    try:
        # Wait for the monitoring task to complete or timeout after 5 minutes
        await asyncio.wait_for(monitor.task, timeout=300)
        logger.info("Alert monitoring completed")
    except asyncio.TimeoutError:
        logger.warning("Alert monitoring timed out after 5 minutes")
        monitor.task.cancel()
    except Exception as e:
        logger.error(f"Alert monitoring failed: {e}", exc_info=True)
    
    logger.info("Test completed")


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/test_alert_monitor.py <submission_id>")
        print("Example: python tools/test_alert_monitor.py 123")
        sys.exit(1)
    
    try:
        submission_id = int(sys.argv[1])
    except ValueError:
        print(f"Error: '{sys.argv[1]}' is not a valid submission ID (must be an integer)")
        sys.exit(1)
    
    logger.info(f"Testing AlertMonitorMde with submission_id={submission_id}")
    asyncio.run(test_alert_monitor(submission_id))


if __name__ == "__main__":
    main()
