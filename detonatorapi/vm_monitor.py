import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
import time

from .database import get_background_db, Scan
from .vm_manager import get_vm_manager
from .utils import mylog

logger = logging.getLogger(__name__)


class VMMonitorTask:
    """Background task to monitor VM status and lifecycle"""
    
    def __init__(self):
        self.running = False
        self.task = None
        self.db = get_background_db()
        self.vm_manager = get_vm_manager()
    

    def start_monitoring(self):
        """Start the background monitoring task"""
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info("VM monitoring task started")
    

    def stop_monitoring(self):
        """Stop the background monitoring task"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                self.task
            except asyncio.CancelledError:
                pass
        logger.info("VM monitoring task stopped")
    

    async def _monitor_loop(self):
        """Main monitoring loop - runs every 3 seconds"""
        while self.running:
            try:
                self._check_all_scans()
                await asyncio.sleep(3)  # Check every 3 seconds as requested
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in VM monitoring loop: {str(e)}")
                await asyncio.sleep(3)
    

    def _get_active_scans(self) -> List[Scan]:
        """Get all scans that need VM monitoring (Azure VM status)"""
        return self.db.query(Scan).filter(
            Scan.azure_status.not_like('not_found'),
        ).all()
    

    def _check_all_scans(self):
        """Check status of all VMs that need monitoring based on database"""
        
        try:
            # Get all scans that need monitoring from database
            #active_scans = self._get_active_scans()
            #if not active_scans:
            #    return
            active_scans = self.db.query(Scan).all()
            
            #logger.info(f"Found {len(active_scans)} active scans to monitor")

            vm_manager = get_vm_manager()
            current_time = datetime.utcnow()
            
            logger.debug(f"Monitoring {len(active_scans)} active scans")
            
            for db_scan in active_scans:
                try:
                    self._check_scan(db_scan, vm_manager, current_time)
                except Exception as e:
                    logger.error(f"Error monitoring scan {db_scan.id}: {str(e)}")
                    self._mark_scan_error(db_scan, str(e), current_time)
            
            self.db.commit()
                
        except Exception as e:
            logger.error(f"Error in _check_all_scans: {str(e)}")
        finally:
            self.db.close()
    

    def _check_scan(self, db_scan: Scan, vm_manager, current_time: datetime):
        """Monitor a single scan's VM"""
        vm_name = db_scan.vm_instance_name
        
        if not vm_name or db_scan.vm_status == "removed":
            return
        
        logger.info(f"Scan {db_scan.id}  VM: {vm_name} status: {db_scan.status} {db_scan.vm_status} {db_scan.azure_status}")
        
        # UPDATE: azure_status until we finished/error
        if db_scan.vm_status not in ["removed", "error"]:
            vm_status = vm_manager.get_vm_status(vm_name)
            if db_scan.azure_status != vm_status:
                db_scan.updated_at = current_time
                db_scan.detonator_srv_logs += mylog(f"VM Monitor: Azure VM status changed: {db_scan.azure_status} -> {vm_status}")
                db_scan.azure_status = vm_status
                self.db.commit()
        
        # CHECK azure running: if VM should be shut down (after 1 minute)
        time_elapsed = current_time - db_scan.created_at
        should_shutdown = (
            time_elapsed >= timedelta(minutes=1) and 
            db_scan.azure_status in ['running']
        )
        if should_shutdown:
            # FIXME this just makes it look like we finished scanning
            db_scan.status = "completed"
            self.db.commit()

            db_scan.detonator_srv_logs += mylog(f"VM {vm_name} has been running for 1 minute, scheduling shutdown")
            shutdown_success = vm_manager.shutdown_vm(vm_name)
            if shutdown_success:
                db_scan.detonator_srv_logs += mylog(f"VM {vm_name} shutdown successfully (deallocated)")
            else:
                db_scan.vm_status = "error"
                db_scan.detonator_srv_logs += mylog(f"VM {vm_name} shutdown failed")
            self.db.commit()
        
        # CHECK azure deallocated: VM remove
        should_cleanup = (
            db_scan.azure_status in ['deallocated' ]
        )
        if should_cleanup:
            db_scan.detonator_srv_logs += mylog(f"VM {vm_name} is deallocated, scheduling resource cleanup")
            cleanup_success = vm_manager.delete_vm_resources(vm_name)
            if cleanup_success:
                db_scan.vm_status = "removed"
                db_scan.completed_at = current_time
                db_scan.detonator_srv_logs += mylog("VM resources cleaned up successfully\n")
            else:
                db_scan.vm_status = "error"
                db_scan.detonator_srv_logs += mylog("VM resource cleanup failed\n")
            self.db.commit()
            

    def _mark_scan_error(self, db_scan: Scan, error_message: str, current_time: datetime):
        """Mark a scan as having an error"""
        db_scan.status = "error"
        error_log = f"[{current_time.isoformat()}] Error monitoring VM: {error_message}\n"
        if db_scan.detonator_srv_logs:
            db_scan.detonator_srv_logs += error_log
        else:
            db_scan.detonator_srv_logs = error_log
        db_scan.updated_at = current_time


# Global VM monitor instance
vm_monitor = VMMonitorTask()

def start_vm_monitoring():
    """Start the global VM monitoring task"""
    vm_monitor.start_monitoring()

def stop_vm_monitoring():
    """Stop the global VM monitoring task"""
    vm_monitor.stop_monitoring()
