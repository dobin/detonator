# Install SSH on Windows
# And add a public key for the 'Administrators' group
# For Detonator remote upgrade for RedEdr
#
# https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement

# Replace <pubkey> with your actual public key
$authorizedKey = "<pubkey>"

# Add/Install SSH
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'
New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22

# Configure SSH to allow key-based authentication for Administrators group
$authorizedKeysFile = "$env:ProgramData\ssh\administrators_authorized_keys"
New-Item -ItemType Directory -Force -Path (Split-Path $authorizedKeysFile)
icacls.exe "$authorizedKeysFile" /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"

# Add the configured public key to the authorized_keys file
Add-Content -Path $authorizedKeysFile -Value $authorizedKey -Force
