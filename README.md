# Detonator

Detonate your MalDev payload in a VM. 


## Quick Start

1) Install RedEdr somewhere (in a VM)
2) Copy `profiles.yaml.sample` to `profiles.yaml`
3) Configure `profiles.yaml` so it points to that VM

```yaml
myfirstvm:
  type: running
  edr_collector: defender
  rededr: true
  comment: My First Detonator VM
  port: 8080
  ip: 192.168.1.1
```

4) Load the profiles from `profiles.yaml` into the DB:
```
$ poetry run python3 migrate_to_profiles.py
```


Run the server:
```bash
# Install dependencies
$ poetry install

# Run both servers
$ poetry run python -m detonator both
```

Access the web interface on `http://localhost:5000`.


## Usage

To scan a file on the previously configured `myfirstvm`:

```bash
$ poetry run python -m detonatorcmd scan malware.exe --edr-template myfirstvm
```

