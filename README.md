# Detonator

Detonate your MalDev payload in a VM. 


## Quick Start

1) Install RedEdr somewhere (in a VM)
2) Copy `profiles.yaml.sample` to `profiles.yaml`
3) Configure `profiles.yaml` so it points to that VM

```yaml
myfirstvm:
  type: live
  edr_collector: defender
  rededr: true
  comment: My First Detonator VM
  port: 8080
  ip: 192.168.1.1
```

4) Load the profiles from `profiles.yaml` into the DB:
```

```

Run the server:
```bash
# Install Deps
$ apt install python3-poetry

# Create DB
$ poetry run python3 migrate_to_profiles.py

# Install dependencies
$ poetry install

# Run both servers
$ poetry run python -m detonator
```

Access the web interface on `http://localhost:5000`.


## Usage

To scan a file on the previously configured `myfirstvm`:

```bash
$ poetry run python -m detonatorcmd scan malware.exe --edr-template myfirstvm
```


## Setup Guides

Depending on your needs, there is more or less configuration required.

* [Simple easy single user](https://github.com/dobin/detonator/doc/setup-singleuser.md)
* [Integrating with Azure](https://github.com/dobin/detonator/doc/setup-azure.md)
* [Public use](https://github.com/dobin/detonator/doc/setup-public.md)

There are some more docs: 

* [Overview](https://github.com/dobin/detonator/doc/overview) of architecture and stuff (mostly Claude generated. Probably obsolete)
* 