import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Set
from sqlalchemy.orm import Session

from .database import get_background_db, Scan
from .vm_manager import get_vm_manager

logger = logging.getLogger(__name__)

class VMMonitorTask:
    """Background task to monitor VM status and lifecycle"""
    
    def __init__(self):
        self.monitored_scans: Dict[int, dict] = {}  # scan_id -> {vm_name, created_at, status}
        self.running = False
        self.task = None
    
    def add_scan_to_monitor(self, scan_id: int, vm_name: str):
        """Add a scan to the monitoring list"""
        self.monitored_scans[scan_id] = {
            'vm_name': vm_name,
            'created_at': datetime.utcnow(),
            'status': 'creating',
            'shutdown_scheduled': False
        }
        logger.info(f"Added scan {scan_id} with VM {vm_name} to monitoring")
    
    def remove_scan_from_monitor(self, scan_id: int):
        """Remove a scan from monitoring"""
        if scan_id in self.monitored_scans:
            vm_name = self.monitored_scans[scan_id]['vm_name']
            del self.monitored_scans[scan_id]
            logger.info(f"Removed scan {scan_id} with VM {vm_name} from monitoring")
    
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
    
    async def _check_all_vms(self):
        """Check status of all monitored VMs"""
        if not self.monitored_scans:
            return
        
        vm_manager = get_vm_manager()
        db = get_background_db()
        
        try:
            current_time = datetime.utcnow()
            scans_to_remove = []
            
            for scan_id, scan_info in self.monitored_scans.items():
                try:
                    vm_name = scan_info['vm_name']
                    created_at = scan_info['created_at']
                    time_elapsed = current_time - created_at
                    
                    # Get current VM status
                    vm_status = await vm_manager.get_vm_status(vm_name)
                    
                    # Update scan info
                    scan_info['status'] = vm_status
                    
                    # Update database
                    db_scan = db.query(Scan).filter(Scan.id == scan_id).first()
                    if db_scan:
                        db_scan.status = f"vm_{vm_status}"
                        db_scan.updated_at = current_time
                        
                        # Log VM status changes
                        status_log = f"[{current_time.isoformat()}] VM Status: {vm_status}\n"
                        if db_scan.detonator_srv_logs:
                            db_scan.detonator_srv_logs += status_log
                        else:
                            db_scan.detonator_srv_logs = status_log
                    
                    # Check if VM should be shut down (after 1 minute)
                    if time_elapsed >= timedelta(minutes=1) and not scan_info['shutdown_scheduled']:
                        logger.info(f"VM {vm_name} has been running for 1 minute, scheduling shutdown")
                        scan_info['shutdown_scheduled'] = True
                        
                        # Shutdown the VM
                        shutdown_success = await vm_manager.shutdown_vm(vm_name)
                        
                        if db_scan:
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
                    elif (scan_info['shutdown_scheduled'] and 
                          vm_status in ['deallocated', 'not_found'] and 
                          time_elapsed >= timedelta(minutes=2)):  # Wait 2 minutes total before cleanup
                        
                        logger.info(f"VM {vm_name} is deallocated, scheduling resource cleanup")
                        
                        # Delete VM resources
                        cleanup_success = await vm_manager.delete_vm_resources(vm_name)
                        
                        if db_scan:
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
                        
                        # Remove from monitoring
                        scans_to_remove.append(scan_id)
                    
                    db.commit()
                    
                except Exception as e:
                    logger.error(f"Error checking VM for scan {scan_id}: {str(e)}")
                    # Mark scan as error
                    db_scan = db.query(Scan).filter(Scan.id == scan_id).first()
                    if db_scan:
                        db_scan.status = "error"
                        error_log = f"[{current_time.isoformat()}] Error monitoring VM: {str(e)}\n"
                        if db_scan.detonator_srv_logs:
                            db_scan.detonator_srv_logs += error_log
                        else:
                            db_scan.detonator_srv_logs = error_log
                        db.commit()
                    
                    scans_to_remove.append(scan_id)
            
            # Remove completed scans from monitoring
            for scan_id in scans_to_remove:
                self.remove_scan_from_monitor(scan_id)
                
        finally:
            db.close()


# Global VM monitor instance
vm_monitor = VMMonitorTask()

async def start_vm_monitoring():
    """Start the global VM monitoring task"""
    await vm_monitor.start_monitoring()

async def stop_vm_monitoring():
    """Stop the global VM monitoring task"""
    await vm_monitor.stop_monitoring()

def add_scan_to_monitoring(scan_id: int, vm_name: str):
    """Add a scan to the global VM monitoring"""
    vm_monitor.add_scan_to_monitor(scan_id, vm_name)

def remove_scan_from_monitoring(scan_id: int):
    """Remove a scan from the global VM monitoring"""
    vm_monitor.remove_scan_from_monitor(scan_id)
