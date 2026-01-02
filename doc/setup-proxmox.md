# Setup Proxmox


## Proxmox Access

Configure proxmox access: 
```
$ cat detonatorapi/connectors/proxmox.yaml
ip: 192.168.1.1
name: proxmox
user: rededr@pve
token_id: detonator
token_value: 1234567-1234-1234-1234-123467890
```

Use `scripts/proxmox/proxmox_create_user_permissions` as inspiration
to create a valid user/token which has the permissions to start/stop VMs
and revert them to snapshot. 

* Make sure that "name" in the `proxmox.yaml` is your correct proxmox instance name, or you will get weird TLS errors
* The token needs permission for each VM it manages


## Proxmox VM configuration

In your profiles config (e.g. via `profiles_init.yaml`), configure
the proxmox VM ID and snapshot name:

```
defender:
  connector: Proxmox
  ...
  data:
    ip: 10.10.10.100
    proxmox_id: 101
    proxmox_snapshot: latest
```

So after processing on `defender` profile, Detonator will automatically
reset the VM with id `101` (with ip `10.10.10.100`, where DetonatorAgent runs) 
to the snapshot with name `latest`. 


## VM Configuration

Before you do a snapshot `latest`, configure the VM: 
* DetonatorAgent autostart
* Windows Autologon

Use `scripts/vm/setup_detonator_windows.ps1` as inspiration. 
