# Install SSH on Windows
# And add a public key for the 'Administrators' group
# For Detonator remote upgrade for RedEdr
#
# https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement

# Replace <pubkey> with your actual public key
$authorizedKey = "<pubkey>"

# Install SSH on Windows
# And add a public key for the 'Administrators' group
# For Detonator remote upgrade for RedEdr
#
# https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement

# Replace <pubkey> with your actual public key
$authorizedKey = "<pubkey>"

# Resolve ProgramData reliably
$programData = [Environment]::GetFolderPath('CommonApplicationData')

$authorizedKeysFile = Join-Path $programData 'ssh\administrators_authorized_keys'

# Ensure directory exists
$sshDir = Split-Path $authorizedKeysFile -Parent
New-Item -ItemType Directory -Force -Path $sshDir | Out-Null

# Ensure file exists
New-Item -ItemType File -Force -Path $authorizedKeysFile | Out-Null

# Fix permissions (OpenSSH-required)
icacls.exe $authorizedKeysFile /inheritance:r `
    /grant "Administrators:F" `
    /grant "SYSTEM:F"

# Add key
Add-Content -Path $authorizedKeysFile -Value $authorizedKey


#################
# Add/Install SSH
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'
New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
