# Read-Only Mode - Claude Generated

Detonator supports a read-only mode that disables most write operations while still allowing file uploads and scans to be created.

## Configuration

Set the environment variable `DETONATOR_READ_ONLY=true` before starting both the API and UI components.

```bash
export DETONATOR_READ_ONLY=true
```

Accepted values for enabling read-only mode:
- `true`
- `1` 
- `yes`
- `on`

Any other value (or no value) will disable read-only mode.

## What's Disabled in Read-Only Mode

When read-only mode is enabled, the following operations are blocked:

### API Level (FastAPI)
- Creating profiles (`POST /api/profiles`)
- Updating profiles (`PUT /api/profiles/{id}`)
- Deleting profiles (`DELETE /api/profiles/{id}`)
- Uploading individual files (`POST /api/files`)
- Creating scans (`POST /api/files/{id}/createscan`)
- Updating scans (`PUT /api/scans/{id}`)
- Deleting scans (`DELETE /api/scans/{id}`)
- Deleting files (`DELETE /api/files/{id}`)
- VM operations (`DELETE /api/vms/{name}`)

### UI Level (Flask)
- Delete buttons are automatically disabled and grayed out
- Edit buttons are automatically disabled and grayed out
- Create/Update forms are disabled with visual indicators
- Profile creation forms are disabled
- File upload forms are disabled (except upload-and-scan)
- Clear tooltips explain why buttons are disabled

## What's Still Allowed

The following operations remain available in read-only mode:

- **File upload and scan** (`POST /api/files/upload-and-scan`) - This is the primary workflow
- All GET endpoints (viewing data)
- VM status monitoring
- Reading scan results and logs

## Visual Indicators

When read-only mode is enabled:

1. **Banner**: An orange banner appears at the top of the UI indicating read-only mode
2. **Disabled Buttons**: Delete, edit, and update buttons are visually disabled
3. **Error Messages**: Clear messages explain when operations are blocked

## Use Cases

Read-only mode is useful for:

- **Production environments** where configuration changes should be restricted
- **Demo environments** where you want to show functionality without allowing modifications
- **Backup/monitoring systems** that need read access but shouldn't modify state
- **Temporary maintenance** where you want to prevent changes while investigating issues

## Health Check

The health endpoint includes read-only mode status:

```bash
curl http://localhost:8000/api/health
```

Response includes:
```json
{
  "status": "healthy",
  "service": "detonator-api", 
  "read_only_mode": true
}
```

## Implementation Details

- **FastAPI**: Middleware checks HTTP method and path, returns 403 for blocked operations
- **Flask UI**: Template-level conditionals disable buttons and forms based on `READ_ONLY_MODE` variable
- **Consistent behavior**: Both API and UI respect the same configuration
- **Exception handling**: Upload-and-scan endpoint has a specific exception to remain functional
- **Visual feedback**: Disabled buttons are clearly marked with appropriate styling and tooltips
