# Detonator

Detonate your MalDev payload in a VM. 


## Quick Start

1. Install DetonatorAgent on the analysis VM (RedEdr optional).
2. Copy `profiles_init.yaml.sample` to `profiles_init.yaml`.
3. Edit `profiles_init.yaml` so it points to the VM/connector you deployed.
4. Install Detonator’s Python dependencies and migrate the YAML profiles into the SQLite database.

```yaml
myfirstvm:
  type: live
  edr_collector: defender
  rededr: true
  comment: My First Detonator VM
  port: 8080
  ip: 192.168.1.1
```

Run the server:
```bash
# Install Deps
$ apt install python3-poetry

# Create DB
$ poetry run python migrate_profiles_yaml.py

# Install dependencies
$ poetry install

# (Optional) Configure authentication password
$ export DETONATOR_AUTH_PASSWORD="your-secure-password"
# Or add it to .env file (see .env.example)

# Run both servers
$ poetry run python -m detonator
```

Access the web interface on `http://localhost:5000`.

**Authentication**: If you set `DETONATOR_AUTH_PASSWORD`, you'll need to log in via the web interface or provide the password in API requests. See [doc/authentication.md](doc/authentication.md) for details.


## Usage

To scan a file on the previously configured `myfirstvm`:

```bash
$ poetry run python -m detonatorcmd scan malware.exe --edr-template myfirstvm
```

### Microsoft Defender (optional)

Profiles can optionally include an `mde` block to let Detonator correlate alerts, surface the evidence inside the UI, and auto-close the detections once the window expires. Example:

```yaml
myfirstvm:
  connector: Live
  # ...
  mde:
    tenant_id: "00000000-0000-0000-0000-000000000000"
    client_id: "11111111-2222-3333-4444-555555555555"
```

Store the corresponding client secret in the environment variable `MDE_AZURE_CLIENT_SECRET`. When configured, Detonator will poll MDE for alerts tied to the scan’s device ID during the configured detection window and automatically resolve them once the window expires.

**Entra app**

1. In `https://entra.microsoft.com`, create an **App Registration** (single tenant is fine).  
2. Under **API permissions**, add application permissions for `Microsoft Graph`:  
   - `SecurityAlert.Read.All` and `SecurityAlert.ReadWrite.All`  
   - `SecurityIncident.Read.All` and `SecurityIncident.ReadWrite.All` *(needed if you want Detonator to auto-close related incidents)*  
   - `ThreatHunting.Read.All`
3. Under **Certificates & secrets**, create a **client secret**; copy the value into an environment variable (e.g., `export MDE_LAB_CLIENT_SECRET="..."`).  
4. Use the app’s **Application (client) ID**, tenant ID in each profile’s `mde` block as shown above, and export `MDE_AZURE_CLIENT_SECRET`. Detonator automatically requests the `https://api.security.microsoft.com/.default` scope, so you don’t need to configure it per profile.  

#### Detection window & polling lifecycle

- Each scan stores `detection_window_minutes` (defaults to `1`). During that window Detonator keeps the scan in the `polling` state and re-queries Defender every minute.
- The poll window always runs from *scan start → now*, deduping by `AlertId`, so late-arriving alerts are still collected.
- Right after the window closes Detonator performs a one-time “evidence hydration” query to capture the full `AlertEvidence` payload for every alert that fired.
- Once evidence is saved it automatically resolves the alerts/incidents using the `alerts_v2` endpoint. If your app registration lacks `SecurityAlert.ReadWrite.All` or `SecurityIncident.ReadWrite.All`, the auto-close step logs a warning but the scan still finishes.

In the UI you’ll see the scan’s badge flip to `polling` while the detection window is active. The scans list now shows a compact Defender summary (alert count + most recent alert metadata) so you can triage at a glance; click “View Details” to see the full evidence block per alert.

## Setup Guides

Depending on your needs, there is more or less configuration required.

* [Simple easy single user](https://github.com/dobin/detonator/doc/setup-singleuser.md)
* [Integrating with Azure](https://github.com/dobin/detonator/doc/setup-azure.md)
* [Public use](https://github.com/dobin/detonator/doc/setup-public.md)

There are some more docs: 

* [Overview](https://github.com/dobin/detonator/doc/overview) of architecture and stuff (mostly Claude generated. Probably obsolete)
* 
