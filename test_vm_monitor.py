#!/usr/bin/env python3
"""
Test script for the updated VM monitoring functionality
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

async def test_vm_monitor():
    """Test the VM monitor functionality"""
    print("Testing Updated VM Monitor...")
    print("=" * 50)
    
    try:
        from detonator.vm_monitor import VMMonitorTask
        from detonator.database import get_background_db, Scan
        
        # Create VM monitor instance
        monitor = VMMonitorTask()
        print("✅ VM Monitor instance created")
        
        # Test database query for active scans
        db = get_background_db()
        try:
            active_scans = monitor._get_active_scans(db)
            print(f"📋 Found {len(active_scans)} active scans in database")
            
            for scan in active_scans:
                print(f"  - Scan {scan.id}: {scan.status}, VM: {scan.vm_instance_name}")
            
            if not active_scans:
                print("  (No active scans found - this is normal if no VMs are running)")
        
        finally:
            db.close()
        
        # Test monitor start/stop
        print("\n🔄 Testing monitor start/stop...")
        await monitor.start_monitoring()
        print("✅ Monitor started successfully")
        
        # Let it run for a few seconds
        await asyncio.sleep(1)
        
        await monitor.stop_monitoring()
        print("✅ Monitor stopped successfully")
        
        print("\n" + "=" * 50)
        print("✅ VM Monitor functionality test completed successfully!")
        print("\nKey improvements:")
        print("- No longer requires manual add_scan_to_monitoring() calls")
        print("- Uses database as source of truth for active scans")
        print("- Automatically discovers scans that need monitoring")
        print("- Simplified API - just start/stop monitoring")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_vm_monitor())
    sys.exit(0 if success else 1)
