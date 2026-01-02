# Detonator Authentication

## Overview

Detonator now supports password-based authentication to protect write operations (POST, PUT, DELETE, PATCH). Read operations (GET) remain accessible without authentication.

## Configuration

Set the authentication password via environment variable:

```bash
export DETONATOR_AUTH_PASSWORD="your-secure-password-here"
```

Or add it to your `.env` file:

```
DETONATOR_AUTH_PASSWORD=your-secure-password-here
```

If `DETONATOR_AUTH_PASSWORD` is not set or empty, authentication is disabled and all operations are allowed.

## Web Interface Authentication

### Login
1. Navigate to `/login` in your browser
2. Enter your password
3. The password is stored in browser's localStorage
4. You'll be redirected to the main application

### Logout
Click the "Logout" button in the sidebar navigation. This will:
- Clear the password from localStorage
- Redirect you to the logout confirmation page

### Auto-redirect
If you try to access a write operation without authentication, you'll automatically be redirected to the login page.

## API Authentication with curl

### Method 1: Custom Header (Recommended)

```bash
curl -X POST http://localhost:8000/api/create-submission \
  -H "X-Auth-Password: your-secure-password-here" \
  -F "file=@malware.exe" \
  -F "profile_name=windows-defender"
```

### Method 2: Bearer Token

```bash
curl -X POST http://localhost:8000/api/create-submission \
  -H "Authorization: Bearer your-secure-password-here" \
  -F "file=@malware.exe" \
  -F "profile_name=windows-defender"
```

### Method 3: Basic Authentication

```bash
# Using Basic auth (username:password format, we only check the password part)
curl -X POST http://localhost:8000/api/create-submission \
  -u ":your-secure-password-here" \
  -F "file=@malware.exe" \
  -F "profile_name=windows-defender"
```

Or with explicit base64 encoding:

```bash
# The password alone (most common)
PASSWORD_B64=$(echo -n "your-secure-password-here" | base64)
curl -X POST http://localhost:8000/api/create-submission \
  -H "Authorization: Basic $PASSWORD_B64" \
  -F "file=@malware.exe" \
  -F "profile_name=windows-defender"

# Or with colon prefix (matches Basic auth format)
PASSWORD_B64=$(echo -n ":your-secure-password-here" | base64)
curl -X POST http://localhost:8000/api/create-submission \
  -H "Authorization: Basic $PASSWORD_B64" \
  -F "file=@malware.exe" \
  -F "profile_name=windows-defender"
```

## Windows curl Examples

### PowerShell with Custom Header

```powershell
curl.exe -X POST http://localhost:8000/api/create-submission `
  -H "X-Auth-Password: your-secure-password-here" `
  -F "file=@malware.exe" `
  -F "profile_name=windows-defender"
```

### PowerShell with Bearer Token

```powershell
curl.exe -X POST http://localhost:8000/api/create-submission `
  -H "Authorization: Bearer your-secure-password-here" `
  -F "file=@malware.exe" `
  -F "profile_name=windows-defender"
```

### PowerShell with Basic Auth

```powershell
# Using -u flag
curl.exe -X POST http://localhost:8000/api/create-submission `
  -u ":your-secure-password-here" `
  -F "file=@malware.exe" `
  -F "profile_name=windows-defender"

# Or with manual base64
$password = "your-secure-password-here"
$bytes = [System.Text.Encoding]::UTF8.GetBytes($password)
$base64 = [Convert]::ToBase64String($bytes)

curl.exe -X POST http://localhost:8000/api/create-submission `
  -H "Authorization: Basic $base64" `
  -F "file=@malware.exe" `
  -F "profile_name=windows-defender"
```
