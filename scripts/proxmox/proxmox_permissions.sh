#!/bin/bash

# Add minimal permissions
pveum role add VM.ControlLimited -privs "VM.PowerMgmt VM.Snapshot.Rollback VM.Audit"

# Give USER rededr@pve the new role on a VM
pveum aclmod /vms/101 --user rededr@pve --role VM.ControlLimited

# or, Give TOKERN rededr@pve!detonator the new role on a VM
# tokens are prefered as they dont expire
pveum aclmod /vms/101 --token 'rededr@pve!detonator' --role VM.ControlLimited

# Check
pveum user permissions rededr@pve
#┌──────────┬──────────────────────────┐
#│ ACL path │ Permissions              │
#╞══════════╪══════════════════════════╡
#│ /vms/101 │ VM.Audit (*)             │
#│          │ VM.PowerMgmt (*)         │
#│          │ VM.Snapshot.Rollback (*) │
#└──────────┴──────────────────────────┘

