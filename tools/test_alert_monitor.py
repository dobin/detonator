#!/usr/bin/env python3
"""
Test tool for AlertMonitorMde
Usage: python tools/test_alert_monitor.py <scan_id>
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from detonatorapi.edr_cloud.mde_alert_monitor import AlertMonitorMde
from detonatorapi.database import get_db, Scan

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_alert_monitor(scan_id: int):
    """Test AlertMonitorMde with the given scan ID"""
    
    # Verify scan exists
    db = get_db()
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        logger.error(f"Scan {scan_id} not found in database")
        db.close()
        return
    
    logger.info(f"Found scan {scan_id}: status={scan.status}, result={scan.result}")
    logger.info(f"Scan created at: {scan.created_at}")
    if scan.profile:
        logger.info(f"Profile: {scan.profile.name}")
        edr_mde_config = scan.profile.data.get("edr_mde")
        if edr_mde_config:
            logger.info(f"MDE device_id: {edr_mde_config.get('device_id')}")
            logger.info(f"MDE hostname: {edr_mde_config.get('hostname')}")
        else:
            logger.warning("No edr_mde configuration found in profile")
    else:
        logger.warning("Scan has no profile")
    
    db.close()
    
    # Create and start monitor
    logger.info("Starting AlertMonitorMde...")
    monitor = AlertMonitorMde(scan_id)
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
        print("Usage: python tools/test_alert_monitor.py <scan_id>")
        print("Example: python tools/test_alert_monitor.py 123")
        sys.exit(1)
    
    try:
        scan_id = int(sys.argv[1])
    except ValueError:
        print(f"Error: '{sys.argv[1]}' is not a valid scan ID (must be an integer)")
        sys.exit(1)
    
    logger.info(f"Testing AlertMonitorMde with scan_id={scan_id}")
    asyncio.run(test_alert_monitor(scan_id))


if __name__ == "__main__":
    main()
