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
# Install Deps
$ apt install python3-poetry

# Install dependencies
$ poetry install
```

Create `profiles_init.yaml` (e.g. by copying `profiles_init.yaml.sample`) 
and configure it something like: 

```yaml
localdetonator:
  type: Live
  edr_collector: defender
  comment: My First Detonator VM
  port: 8080
  data:
    ip: 127.0.0.1
```

Then create the DB:
```
# Create DB
$ poetry run python migrate_profiles_yaml.py
```

And run the server:
```bash
$ poetry run python -m detonator
```

Access the web interface on `http://localhost:5000`. 
The REST API is at `http://localhost:8000`. 


## Usage

To submit a file on the previously configured `localdetonator`:

```bash
$ poetry run python -m detonatorcmd submission sample.exe --profile localdetonator
File ID: 1, Submission ID: 1
.........................
Submission Result: not_detected
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


## Architecture

You can use Detonator in three different setups: 
* **Live**: The simplest, just attach a running DetonatorAgent instance
* **Proxmox**: Using Proxmox to revert VMs to their snapshots
* **Azure**: Instantiate new VM for each submission (experimental)

## Setup Guides

More documentation:
* [Configure with reverse proxy](https://github.com/dobin/detonator/doc/setup-reverseproxy.md)
* [Configure MDE log gathering](https://github.com/dobin/detonator/doc/gather-mde.md)
* [Integrating with Proxmox](https://github.com/dobin/detonator/doc/setup-proxmox.md) (stable)
* [Integrating with Azure](https://github.com/dobin/detonator/doc/setup-azure.md) (experimental)
* [Overview](https://github.com/dobin/detonator/doc/overview) of code architecture (mostly Claude generated. Probably obsolete)


## Other EDRs than Defender/MDE

Only Defender/MDE is supported currently. 

There are two ways to get the EDR data: 
* Local log events gathered by DetonatorAgent, and then parsed by Detonator
* Cloud log events gathered by Detonator

To implement your own EDR, consult: 
* [Implementing a new EDR](https://github.com/dobin/detonator/doc/implement-edr.md). 



