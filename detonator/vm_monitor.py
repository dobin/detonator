import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session

from .database import get_background_db, Scan
from .vm_manager import get_vm_manager

logger = logging.getLogger(__name__)

class VMMonitorTask:
    """Background task to monitor VM status and lifecycle"""
    
    def __init__(self):
        self.running = False
        self.task = None
    
    async def start_monitoring(self):
        """Start the background monitoring task"""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info("VM monitoring task started")
    
    async def stop_monitoring(self):
        """Stop the background monitoring task"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("VM monitoring task stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop - runs every 3 seconds"""
        while self.running:
            try:
                await self._check_all_vms()
                await asyncio.sleep(3)  # Check every 3 seconds as requested
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in VM monitoring loop: {str(e)}")
                await asyncio.sleep(3)
    
    def _get_active_scans(self, db: Session) -> List[Scan]:
        """Get all scans that need VM monitoring"""
        # Get scans that have VMs that need monitoring
        active_statuses = [
            'vm_creating', 'vm_running', 'vm_deallocating', 
            'vm_starting', 'vm_stopping', 'vm_provisioning'
        ]
        
        return db.query(Scan).filter(
            Scan.status.in_(active_statuses),
            Scan.vm_instance_name.isnot(None)
        ).all()
    
    async def _check_all_vms(self):
        """Check status of all VMs that need monitoring based on database"""
        db = get_background_db()
        
        try:
            # Get all scans that need monitoring from database
            active_scans = self._get_active_scans(db)
            
            if not active_scans:
                return
                
            vm_manager = get_vm_manager()
            current_time = datetime.utcnow()
            
            logger.debug(f"Monitoring {len(active_scans)} active scans")
            
            for db_scan in active_scans:
                try:
                    await self._monitor_single_scan(db_scan, vm_manager, current_time, db)
                except Exception as e:
                    logger.error(f"Error monitoring scan {db_scan.id}: {str(e)}")
                    self._mark_scan_error(db_scan, str(e), current_time, db)
            
            db.commit()
                
        except Exception as e:
            logger.error(f"Error in _check_all_vms: {str(e)}")
        finally:
            db.close()
    
    async def _monitor_single_scan(self, db_scan: Scan, vm_manager, current_time: datetime, db: Session):
        """Monitor a single scan's VM"""
        vm_name = db_scan.vm_instance_name
        time_elapsed = current_time - db_scan.created_at
        
        # Get current VM status from Azure
        vm_status = await vm_manager.get_vm_status(vm_name)
        
        # Update scan status based on VM status
        new_status = f"vm_{vm_status}"
        if db_scan.status != new_status:
            logger.info(f"Scan {db_scan.id} VM status changed: {db_scan.status} -> {new_status}")
            db_scan.status = new_status
        
        db_scan.updated_at = current_time
        
        # Log VM status changes
        status_log = f"[{current_time.isoformat()}] VM Status: {vm_status} (elapsed: {time_elapsed})\n"
        if db_scan.detonator_srv_logs:
            db_scan.detonator_srv_logs += status_log
        else:
            db_scan.detonator_srv_logs = status_log
        
        # Check if VM should be shut down (after 1 minute)
        should_shutdown = (
            time_elapsed >= timedelta(minutes=1) and 
            vm_status in ['running', 'starting'] and
            not db_scan.status.endswith('_shutting_down')
        )
        
        if should_shutdown:
            logger.info(f"VM {vm_name} has been running for 1 minute, scheduling shutdown")
            
            # Shutdown the VM
            shutdown_success = await vm_manager.shutdown_vm(vm_name)
            
            if shutdown_success:
                db_scan.status = "vm_shutting_down"
                shutdown_log = f"[{current_time.isoformat()}] VM shutdown initiated after 1 minute\n"
            else:
                db_scan.status = "vm_shutdown_failed"
                shutdown_log = f"[{current_time.isoformat()}] VM shutdown failed\n"
            
            if db_scan.detonator_srv_logs:
                db_scan.detonator_srv_logs += shutdown_log
            else:
                db_scan.detonator_srv_logs = shutdown_log
        
        # Check if VM has been deallocated and schedule cleanup
        should_cleanup = (
            vm_status in ['deallocated', 'not_found'] and 
            time_elapsed >= timedelta(minutes=2) and  # Wait 2 minutes total before cleanup
            db_scan.status != "completed" and
            db_scan.status != "cleanup_failed"
        )
        
        if should_cleanup:
            logger.info(f"VM {vm_name} is deallocated, scheduling resource cleanup")
            
            # Delete VM resources
            cleanup_success = await vm_manager.delete_vm_resources(vm_name)
            
            if cleanup_success:
                db_scan.status = "completed"
                db_scan.completed_at = current_time
                cleanup_log = f"[{current_time.isoformat()}] VM resources cleaned up successfully\n"
            else:
                db_scan.status = "cleanup_failed"
                cleanup_log = f"[{current_time.isoformat()}] VM resource cleanup failed\n"
            
            if db_scan.detonator_srv_logs:
                db_scan.detonator_srv_logs += cleanup_log
            else:
                db_scan.detonator_srv_logs = cleanup_log
    
    def _mark_scan_error(self, db_scan: Scan, error_message: str, current_time: datetime, db: Session):
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

async def start_vm_monitoring():
    """Start the global VM monitoring task"""
    await vm_monitor.start_monitoring()

async def stop_vm_monitoring():
    """Stop the global VM monitoring task"""
    await vm_monitor.stop_monitoring()
