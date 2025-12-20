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
  "user": "admin",
  "vm_instance_name": null,
  "vm_ip_address": null,
  "created_at": "2025-12-19T09:18:14.201803",
  "updated_at": "2025-12-19T09:20:43.141671",
  "completed_at": "2025-12-19T09:18:38.121769",

  "status": "finished",
  "result": "not_detected",

  "server_logs": "[2025-12-19T09:18:14.200832] DB: Submission created...",
  "agent_logs": "[\"[2025-12-18 20:03:41.772 UTC] DetonatorAgent 0.4 - Starting up..." ],
  "process_output": {
    "pid": 78352,
    "stdout": "\r\nPsExec v2.43 - Execute processes remotely\r\nCopyright (C) 2001-2023 Mark Russinovich\r\n...",
    "stderr": ""
  },
  "rededr_events": "No RedEdr logs available",
  "rededr_telemetry_raw": "",
  "edr_telemetry_raw": "{\"logs\":\"<Events>\\r\\n</Events>\\r\\n\",\"edr_version\":\"Windows Defender 1.0\",\"plugin_version\":\"1.0\"}",
  "edr_alerts": [],
  "alerts": [],
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



