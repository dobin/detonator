#!/bin/bash
#
# Detonator Proxmox user and permission initial setup script
# So Detonator can start/stop VMs and manage snapshots (but not more)
#
# - Creates user & token
# - Creates limited role for it
#
# Usage: ./proxmox_create_user_permissions.sh
#
# Permissions:
# - Start/Stop VMs: VM.PowerMgmt (this includes start, stop, shutdown, reset, suspend, resume).
# - Revert to snapshot: VM.Snapshot.Rollback.
# - Visibility / listing: At minimum, VM.Audit so the webserver can see the VM and its snapshot list.
# Note: VM.Snapshot.Create is NOT needed for security reasons
#

# === CONFIG ===
USER="rededr@pve"
TOKEN_NAME="detonator"
VMID="101"

# === CREATE USER ===
# Add user if it doesn't exist
if ! pveum user list | grep -q "^$USER"; then
  echo "Creating user $USER..."
  pveum user add "$USER" --comment "Limited control user"
else
  echo "User $USER already exists."
fi

# === CREATE TOKEN (optional, recommended) ===
# Tokens are preferred since they don’t expire unless set to
if ! pveum user token list "$USER" | grep -q "^$TOKEN_NAME"; then
  echo "Creating token $USER!$TOKEN_NAME..."
  pveum user token add "$USER" "$TOKEN_NAME" --comment "API token for VM control"
else
  echo "Token $USER!$TOKEN_NAME already exists."
fi

# === CREATE ROLE WITH MINIMAL PRIVS ===
if ! pveum role list | grep -q "^VM.ControlLimited"; then
  echo "Creating role VM.ControlLimited..."
  pveum role add VM.ControlLimited -privs "VM.PowerMgmt VM.Snapshot.Rollback VM.Audit"
else
  echo "Role VM.ControlLimited already exists."
fi

# === ASSIGN ROLE TO USER ===
echo "Assigning role to user..."
pveum aclmod "/vms/$VMID" --user "$USER" --role VM.ControlLimited

# === ASSIGN ROLE TO TOKEN (optional) ===
echo "Assigning role to token..."
pveum aclmod "/vms/$VMID" --token "$USER!$TOKEN_NAME" --role VM.ControlLimited

# === VERIFY PERMISSIONS ===
echo "Checking permissions for $USER..."
pveum user permissions "$USER"
