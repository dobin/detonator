# Detonator

Orchestrate detonating your MalDev in VMs with different EDRs to see their detection surface. 

Detonator provides a Web and REST interface for [DetonatorAgents](https://github.com/dobin/DetonatorAgent). It lets you choose one of your VM's with a installed EDR to execute your
malware or inital access chain, and see what detection occur. 

You can freely use it on [detonator.r00ted.ch](https://detonator.r00ted.ch). 


## Installation

First, install and setup [DetonatorAgent](https://github.com/dobin/DetonatorAgent) 
on your analysis VM. I assume its localhost:

```bash
# Test if DetonatorAgent is reachable
$ curl http://127.0.0.1:8080/api/lock/status
{"in_use":false}
```

Install python stuff:

```bash
# Install uv
$ pip install uv

# Create a virtual environment
$ uv venv
$ source .venv/bin/activate

# Install dependencies
(detonator) $ uv pip install -r requirements.txt
```

Create `profiles_init.yaml` (e.g. by copying `profiles_init.yaml.sample`) 
and configure it something like: 

```yaml
localdetonator:
  type: Live
  comment: My First Detonator VM
  port: 8080
  vm_ip: 127.0.0.1
```

Then create the DB:
```
# Create DB
$ python migrate_profiles_yaml.py
```

And run the server:
```bash
(detonator) $ python -m detonator
```

Access the web interface on `http://localhost:5000`. 
The REST API is at `http://localhost:8000`. 

## Usage

To submit a file on the previously configured `localdetonator`:

```bash
(detonator) $ python -m detonatorcmd --profile localdetonator test.exe
File ID: 1, Submission ID: 1
Polling for alerts until submission is complete...

[ALERT] [Severe] Trojan:Win32/Ravartar!rfn (Source: Defender Local)

Submission Result: file_detected
```

All the gathered data:
```
$ curl http://localhost:8000/api/submissions/1 | jq
{
  "id": 1,
  "file_id": 1,
  "profile_id": 2,
  "project": "",
  "comment": "",
  "runtime": 10,
  "drop_path": "",
  "execution_mode": "exec",
  "server_logs": "[2025-12-25T15:54:19.106464] DB: Submission created\n...",
  "status": "finished",
  "user": "admin",
  "agent_logs": "[2025-12-25 15:54:39.306 UTC] information: Exec: Execute request received for file: 74As_U3lf_mimikatz.exe\n...",
  "process_output": "",
  "rededr_events": null,
  "rededr_logs": null,
  "edr_verdict": "detected",
  "vm_instance_name": null,
  "vm_ip_address": null,
  "alerts": [
    {
      "id": 2,
      "alert_id": "{2A4B3551-632C-4CB6-8363-553BF2B43FFB}",
      "source": "Defender Local Plugin",
      "title": "HackTool:Win32/Mimikatz!pz",
      "severity": "High",
      "category": "Tool",
      "detection_source": "Real-Time Protection",
      "detected_at": "2025-12-25T15:54:39.617000",
      "created_at": "2025-12-25T15:54:49.880929"
    }
  ],
  "file": {
    "filename": "74As_U3lf_mimikatz.exe",
    "source_url": "",
    "comment": "",
    "exec_arguments": "",
    "user": "admin",
    "created_at": "2025-12-25T15:54:19.090903",
    "id": 14,
    "file_hash": "61c0810a23580cf492a6ba4f7654566108331e7a4134c968c2d6a05261b2d8a1"
  },
  "profile": {...},
  "created_at": "2025-12-25T15:54:19.106841",
  "updated_at": "2025-12-25T15:54:52.415311",
  "completed_at": "2025-12-25T15:54:49.896003"
}
```

## Detailed DetonatorCmd Usage

```
(detonator) $ python -m detonatorcmd  --help
usage: __main__.py [-h] [--url URL] [--profilepassword PROFILEPASSWORD] [--adminpassword ADMINPASSWORD] [--profile PROFILE] [--file-comment FILE_COMMENT]
                   [--submission-comment SUBMISSION_COMMENT] [--project PROJECT] [--source-url SOURCE_URL] [--exec_arguments EXEC_ARGUMENTS] [--runtime RUNTIME]
                   [--exec-mode {exec,autoit,clickfix}] [--no-randomize-filename] [--drop-path DROP_PATH] [--debug]
                   [filename]

Detonator Command Line Client

positional arguments:
  filename              File to submit

options:
  -h, --help            show this help message and exit
  --url URL             API base URL
  --profilepassword PROFILEPASSWORD
                        Password for the profile (if required)
  --adminpassword ADMINPASSWORD
                        Admin password for API authentication
  --profile PROFILE, -p PROFILE
                        Profile to use
  --file-comment FILE_COMMENT, -c FILE_COMMENT
                        Comment for the file
  --submission-comment SUBMISSION_COMMENT, -sc SUBMISSION_COMMENT
                        Comment for the submission
  --project PROJECT, -j PROJECT
                        Project name for the submission
  --source-url SOURCE_URL, -s SOURCE_URL
                        Source URL of the file
  --exec_arguments EXEC_ARGUMENTS, -a EXEC_ARGUMENTS
                        Command line arguments (parameter or dll function) to pass to the executable
  --runtime RUNTIME, -r RUNTIME
                        Runtime in seconds
  --exec-mode {exec,autoit,clickfix}, -e {exec,autoit,clickfix}
                        Execution mode (default: exec)
  --no-randomize-filename
                        Randomize filename before upload
  --drop-path DROP_PATH
                        Path to drop malware files
  --debug               Enable debug output
```


## Extended Setup

More documentation:
* [Configure with reverse proxy](https://github.com/dobin/detonator/doc/setup-reverseproxy.md)
* [Configure MDE log gathering](https://github.com/dobin/detonator/doc/gather-mde.md)
* [Integrating with Proxmox](https://github.com/dobin/detonator/doc/setup-proxmox.md) (stable)
* [Integrating with Azure](https://github.com/dobin/detonator/doc/setup-azure.md) (experimental)
* [Overview](https://github.com/dobin/detonator/doc/overview) of code architecture (mostly Claude generated. Probably obsolete)


### Setup VMs

The following scripts are optimized for my usage. Read through them and copy paste what you need. 

[setup_detonator_windows.ps1](https://github.com/dobin/detonator/blob/main/scripts/vm/setup_detonator_windows.ps1) will help you configure Windows, and correctly install and configure RedEdr and Detonator:
* Enabling Autologon
* Disable OOBE, Windows Welcome Experience, and more annoyances
* Create rededr user
* Install RedEdr and DetonatorAgent, configure startup and firewall rules

[update_detonatoragent.ps1](https://github.com/dobin/detonator/blob/main/scripts/vm/update_detonatoragent.ps1) and [update_rededr.ps1](https://github.com/dobin/detonator/blob/main/scripts/vm/update_rededr.ps1) are scripts to deploy onto the VM, which when executed (e.g. via SSH) will update the RedEdr and DetonatorAgent installation. 

[ssh_install.ps1](https://github.com/dobin/detonator/blob/main/scripts/vm/ssh_install.ps1) shows how you install SSH on Windows for root remote access. Helpful for updating the installation. 


### Setup Proxmox

The following scripts are to be executed on the Proxmox host. 

[proxmox_create_user_permission.sh](https://github.com/dobin/detonator/blob/main/scripts/proxmox/proxmox_create_user_permissions.sh) will create an API
user/key to be used with Detonator so it can start/stop/revert VMs. Note the permissions are set per-VM. 

[proxmox_update_snapshot.sh](https://github.com/dobin/detonator/blob/main/scripts/proxmox/proxmox_update_snapshot.sh) helps updating a VM by
stopping & reverting it, running the update scripts (stored on the desktop), and then creating a new snapshot. 


### Authentication

There is an admin login on DetonatorUi & DetonatorApi.
* No password means everyone is admin (default)
* Password can be configured in `detonatorapi/settings.yaml`
* If enabled, only admins can change things (all POST basically)
* If enabled, everyone can still submit files (with a max runtime of 12s)
* For detonatorcmd: Use `--adminpassword`

There is also a per-profile password for each profile: 
* in DB profile.password
* If set, users need the password to submit a file to this profile
* Completely independant of the admin-password above
* For detonatorcmd: Use `--profilepassword`



## Supported EDRs

Supported EDRs: 
* Defender
* MDE
* Elastic Defend
* Crowdstrike
* Fibratus

There are two ways to get the EDR data: 
* Local log events gathered by DetonatorAgent, and then parsed by Detonator
* Cloud log events gathered by Detonator

To implement your own EDR, consult: 
* [Implementing a new EDR](https://github.com/dobin/detonator/doc/implement-edr.md). 



