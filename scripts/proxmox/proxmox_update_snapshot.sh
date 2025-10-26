#!/bin/bash
#
# Proxmox VM update script
# - Reverts the VM to a safe snapshot
# - Starts VM and updates the RedEdr components inside the VM via SSH
# - Stops VM and creates a new snapshot for further use
#
# To be used on proxmox-host as root (not Detonator container, 
# as its user does not have enough permissions, by design).
#
# Usage: ./update_template.sh <VMID> <VM_IP> <SSH_USER>
# Example: ./update_template.sh 100 192.168.1.50 root
#

set -e

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <VMID> <VM_HOST>"
    exit 1
fi


#######################################################
# Config
VMID="$1"
VM_HOST="$2"
SSH_USER="hacker"
UPDATE_SCRIPT="c:\users\hacker\Desktop\update_rededr.ps1"     # Path to update script inside the VM
SNAPSHOT_NAME="latest"


#######################################################
# Stop VM
echo "[1/8] Stopping VM $VMID..."
qm stop "$VMID" || true

echo "Waiting for VM to stop..."
until qm status "$VMID" | grep -q "status: stopped"; do
    sleep 2
    echo "  VM still running, waiting..."
done
echo "VM stopped successfully."


#######################################################
# Revert to safe snapshot
echo "[2/8] Reverting to snapshot '$SNAPSHOT_NAME'..."
qm rollback "$VMID" "$SNAPSHOT_NAME"

echo "Waiting for snapshot rollback to complete..."
until qm status "$VMID" | grep -q "status: stopped"; do
    sleep 2
    echo "  Rollback in progress, waiting..."
done
echo "Snapshot rollback completed."


#######################################################
# Start clean VM
echo "[3/8] Starting VM $VMID..."
qm start "$VMID"

echo "Waiting for VM to start..."
until qm status "$VMID" | grep -q "status: running"; do
    sleep 2
    echo "  VM still starting, waiting..."
done
echo "VM started successfully."


#######################################################
# Wait for VM to be reachable via SSH
echo "[4/8] Waiting for VM to be reachable via SSH..."
until ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no "$SSH_USER@$VM_HOST" 'echo "SSH ready"' &>/dev/null; do
    sleep 5
done


#######################################################
# Update VM
echo "[5/8] Running update script on VM..."
ssh -o StrictHostKeyChecking=no "$SSH_USER@$VM_HOST" "powershell.exe -ep bypass $UPDATE_SCRIPT"

echo "Let windows cook... press enter to continue"
read -r

#######################################################
# Shutdown VM 
echo "[6/8] Shutting down VM..."
ssh -o StrictHostKeyChecking=no "$SSH_USER@$VM_HOST" "shutdown /s /t 0"

echo "Waiting for VM to shutdown..."
until ! qm status "$VMID" | grep -q "status: running"; do
    sleep 5
    echo "  VM still running, waiting for shutdown..."
done
echo "VM shutdown completed."


#######################################################
# Delete old snapshot
echo "[7/8] Deleting old snapshot '$SNAPSHOT_NAME'..."
qm delsnapshot "$VMID" "$SNAPSHOT_NAME" || true


#######################################################
# Create new snapshot
echo "[8/8] Creating new snapshot '$SNAPSHOT_NAME'..."
qm snapshot "$VMID" "$SNAPSHOT_NAME" --description "Updated on $(date)"

echo "Waiting for snapshot creation to complete..."
sleep 3
echo "Snapshot creation completed."


#######################################################
# Start VM at the end
echo "[Done] Starting VM again..."
qm start "$VMID"

echo "Waiting for VM to start after snapshot..."
until qm status "$VMID" | grep -q "status: running"; do
    sleep 2
    echo "  VM still starting, waiting..."
done
echo "VM started successfully."


#######################################################
# Finished
echo "Update process complete for VM $VMID"
