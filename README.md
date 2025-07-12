# Detonator

Detonate your MalDev payload in a VM. 


## Quick Start

1) Install RedEdr somewhere (in a VM)
2) Configure `edr_templates.yaml` so it points to that VM

```yaml
myfirstvm:
  type: running
  edr_collector: defender
  rededr: true
  comment: My First Detonator VM
  port: 8080
  ip: 192.168.1.1
```

Run the server:
```bash
# Install dependencies
$ poetry install

# Run both servers
$ poetry run python -m detonator both

# Or run individually:
$ poetry run python -m detonator api   # FastAPI only
$ poetry run python -m detonator web   # Flask only
```

## Usage

To scan a file on the previously configured `myfirstvm`:

```bash
$ poetry run python -m detonatorcmd scan malware.exe --edr-template myfirstvm
```

