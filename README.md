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

Profiles can optionally include an `mde` block to let Detonator correlate alerts and auto-close incidents. Example:

```yaml
myfirstvm:
  connector: Live
  # ...
  mde:
    tenant_id: "00000000-0000-0000-0000-000000000000"
    client_id: "11111111-2222-3333-4444-555555555555"
    client_secret_env: "MDE_MYFIRSTVM_CLIENT_SECRET"
```

Store the corresponding client secret in the environment variable referenced by `client_secret_env`. When configured, Detonator will poll MDE for alerts tied to the scan’s device ID during the configured detection window and automatically resolve them once the window expires.

**Entra app**

1. In `https://entra.microsoft.com`, create an **App Registration** (single tenant is fine).  
2. Under **API permissions**, add application permissions for:  
   - `SecurityAlert.Read.All` and `SecurityAlert.ReadWrite.All`  
   - `SecurityIncident.Read.All` and `SecurityIncident.ReadWrite.All` *(needed if you want Detonator to auto-close related incidents)*  
   - `AdvancedHunting.Read.All` (Detonator uses Microsoft Graph advanced hunting to retrieve Defender alerts)  
   Grant admin consent.  
3. Under **Certificates & secrets**, create a **client secret**; copy the value into an environment variable (e.g., `export MDE_LAB_CLIENT_SECRET="..."`).  
4. Use the app’s **Application (client) ID**, tenant ID, and `client_secret_env` in each profile’s `mde` block as shown above. Detonator automatically requests the `https://api.security.microsoft.com/.default` scope, so you don’t need to configure it per profile.  
5. Ensure the Detonator API host has the environment variable set (or pull it from your secret manager) before starting the server.

Detonator uses Microsoft Graph advanced hunting to pull Defender alerts for each scan, then auto-resolves the corresponding alerts/incidents at the end of the detection window. If the Graph API denies a write (for example, missing incident permissions) Detonator simply logs a warning and leaves the alert/incident untouched.

## Setup Guides

Depending on your needs, there is more or less configuration required.

* [Simple easy single user](https://github.com/dobin/detonator/doc/setup-singleuser.md)
* [Integrating with Azure](https://github.com/dobin/detonator/doc/setup-azure.md)
* [Public use](https://github.com/dobin/detonator/doc/setup-public.md)

There are some more docs: 

* [Overview](https://github.com/dobin/detonator/doc/overview) of architecture and stuff (mostly Claude generated. Probably obsolete)
* 
