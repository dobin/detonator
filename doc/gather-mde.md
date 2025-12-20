# Gather Microsoft Defender for Endpoint (MDE) logs

Profiles can optionally include an `edr_mde` block to let Detonator correlate alerts and incidents of
MDE. The configuration is a little bit tricky and may take some time.  

Example configuration:

```yaml
myfirstvm:
  connector: Live
  ...
  data:
    ...
    edr_mde:
      tenant_id: "00000000-0000-0000-0000-000000000000"
      client_id: "11111111-2222-3333-4444-555555555555"
      hostname: "DESKTOP-12356"
      device_id: "4234k4j2k3j4k23j4k2j43"
```

Store the corresponding Azure client secret in the environment variable `MDE_AZURE_CLIENT_SECRET`. When configured, Detonator will poll MDE for alerts tied to the scan’s device ID during the configured detection window and automatically resolve them once the window expires. 

Make sure that all components (Detonator Linux, VM etc.) have the correct time configured.


## Entra app configuration

1. In `https://entra.microsoft.com`, create an **App Registration** (single tenant is fine).  
2. Under **API permissions**, add application permissions for `Microsoft Graph`:  
   - `SecurityAlert.Read.All` and `SecurityAlert.ReadWrite.All`  
   - `SecurityIncident.Read.All` and `SecurityIncident.ReadWrite.All` *(needed if you want Detonator to auto-close related incidents)*  
   - `ThreatHunting.Read.All`
3. Under **Certificates & secrets**, create a **client secret**; copy the value into an environment variable (e.g., `export MDE_LAB_CLIENT_SECRET="..."`).  
4. Use the app’s **Application (client) ID**, tenant ID in each profile’s `mde` block as shown above, and export `MDE_AZURE_CLIENT_SECRET`. Detonator automatically requests the `https://api.security.microsoft.com/.default` scope, so you don’t need to configure it per profile.

You can test it using `tools/mde_log_test.py` (make sure there are some alerts for that machine). 


## Detection window & polling lifecycle

- The poll window always runs from *scan start → now*, deduping by `AlertId`, so late-arriving alerts are still collected.
- Right after the window closes Detonator performs a one-time “evidence hydration” query to capture the full `AlertEvidence` payload for every alert that fired.
- Once evidence is saved it automatically resolves the alerts/incidents using the `alerts_v2` endpoint. If your app registration lacks `SecurityAlert.ReadWrite.All` or `SecurityIncident.ReadWrite.All`, the auto-close step logs a warning but the scan still finishes.

In the UI you’ll see the scan’s badge flip to `polling` while the detection window is active. The scans list now shows a compact Defender summary (alert count + most recent alert metadata) so you can triage at a glance; click “View Details” to see the full evidence block per alert.
