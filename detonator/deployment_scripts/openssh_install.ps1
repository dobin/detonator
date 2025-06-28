# OpenSSH Server Installation Script for Windows 11
# This script installs and configures OpenSSH server for remote access

Write-Host "Installing OpenSSH Server..." -ForegroundColor Green

try {
    # Install OpenSSH Server feature
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
    Write-Host "OpenSSH Server installed successfully" -ForegroundColor Green
    
    # Start and enable SSH service
    Start-Service sshd
    Set-Service -Name sshd -StartupType 'Automatic'
    Write-Host "SSH service started and set to automatic startup" -ForegroundColor Green
    
    # Start and enable SSH Agent service (optional)
    Start-Service ssh-agent
    Set-Service -Name ssh-agent -StartupType 'Automatic'
    Write-Host "SSH Agent service started and set to automatic startup" -ForegroundColor Green
    
    # Configure Windows Firewall
    if (!(Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue | Select-Object Name, Enabled)) {
        Write-Host "Firewall rule for SSH not found. Creating firewall rule..." -ForegroundColor Yellow
        New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
        Write-Host "Firewall rule created successfully" -ForegroundColor Green
    } else {
        Write-Host "Firewall rule for SSH already exists" -ForegroundColor Yellow
    }
    
    # Set PowerShell as default shell for SSH (optional)
    New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force
    Write-Host "PowerShell set as default SSH shell" -ForegroundColor Green
    
    # Create SSH configuration directory if it doesn't exist
    $sshConfigDir = "C:\ProgramData\ssh"
    if (!(Test-Path $sshConfigDir)) {
        New-Item -ItemType Directory -Path $sshConfigDir -Force
        Write-Host "SSH config directory created" -ForegroundColor Green
    }
    
    # Create basic SSH configuration
    $sshConfig = @"
# Basic SSH configuration for Detonator analysis environment
Port 22
Protocol 2
PermitRootLogin no
MaxAuthTries 3
ClientAliveInterval 60
ClientAliveCountMax 3
PasswordAuthentication yes
PubkeyAuthentication yes
"@
    
    $sshConfig | Out-File -FilePath "$sshConfigDir\sshd_config" -Encoding UTF8 -Force
    Write-Host "SSH configuration file created" -ForegroundColor Green
    
    # Restart SSH service to apply configuration
    Restart-Service sshd
    Write-Host "SSH service restarted with new configuration" -ForegroundColor Green
    
    # Create a log entry
    $logEntry = @"
[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] OpenSSH Server Configuration Summary:
- OpenSSH Server installed and started
- SSH service set to automatic startup
- Firewall rule configured for port 22
- PowerShell set as default shell
- Basic SSH configuration applied
- SSH service restarted
"@
    
    $logPath = "C:\DetonatorLogs"
    if (!(Test-Path $logPath)) {
        New-Item -ItemType Directory -Path $logPath -Force
    }
    
    $logEntry | Out-File -FilePath "$logPath\openssh_install.log" -Encoding UTF8 -Append
    Write-Host "Installation log saved to $logPath\openssh_install.log" -ForegroundColor Green
    
    # Display connection information
    $computerName = $env:COMPUTERNAME
    $ipAddress = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Ethernet*" | Where-Object {$_.IPAddress -ne "127.0.0.1"}).IPAddress
    
    Write-Host "`nOpenSSH Server Installation Complete!" -ForegroundColor Green
    Write-Host "Connection Information:" -ForegroundColor Cyan
    Write-Host "  Computer Name: $computerName" -ForegroundColor White
    Write-Host "  IP Address: $ipAddress" -ForegroundColor White
    Write-Host "  SSH Port: 22" -ForegroundColor White
    Write-Host "  Default User: $env:USERNAME" -ForegroundColor White
    Write-Host "`nTo connect via SSH:" -ForegroundColor Cyan
    Write-Host "  ssh $env:USERNAME@$ipAddress" -ForegroundColor White
    
} catch {
    Write-Host "Error during OpenSSH installation: $($_.Exception.Message)" -ForegroundColor Red
    
    # Log the error
    $errorEntry = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: $($_.Exception.Message)"
    $logPath = "C:\DetonatorLogs"
    if (!(Test-Path $logPath)) {
        New-Item -ItemType Directory -Path $logPath -Force
    }
    $errorEntry | Out-File -FilePath "$logPath\openssh_install.log" -Encoding UTF8 -Append
    
    exit 1
}

Write-Host "`nOpenSSH Server installation script completed successfully!" -ForegroundColor Green
