# Windows Defender Configuration Script
# This script configures Windows Defender with enhanced monitoring for malware analysis

Write-Host "Configuring Windows Defender for enhanced monitoring..." -ForegroundColor Green

try {
    # Enable Windows Defender real-time protection
    Set-MpPreference -DisableRealtimeMonitoring $false
    Write-Host "Real-time protection enabled" -ForegroundColor Green
    
    # Configure cloud protection
    Set-MpPreference -MAPSReporting Advanced
    Set-MpPreference -SubmitSamplesConsent SendAllSamples
    Write-Host "Cloud protection configured" -ForegroundColor Green
    
    # Enable network protection
    Set-MpPreference -EnableNetworkProtection Enabled
    Write-Host "Network protection enabled" -ForegroundColor Green
    
    # Configure scan settings
    Set-MpPreference -ScanAvgCPULoadFactor 50
    Set-MpPreference -ScanOnlyIfIdleEnabled $false
    Write-Host "Scan settings configured" -ForegroundColor Green
    
    # Enable controlled folder access (optional - may interfere with analysis)
    # Set-MpPreference -EnableControlledFolderAccess Enabled
    
    # Configure exclusions for analysis tools (if needed)
    # Add-MpPreference -ExclusionPath "C:\DetonatorTools"
    # Write-Host "Analysis tools excluded from scanning" -ForegroundColor Green
    
    # Enable PowerShell script block logging for better visibility
    $registryPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging"
    if (!(Test-Path $registryPath)) {
        New-Item -Path $registryPath -Force | Out-Null
    }
    Set-ItemProperty -Path $registryPath -Name "EnableScriptBlockLogging" -Value 1
    Write-Host "PowerShell script block logging enabled" -ForegroundColor Green
    
    # Enable Windows Event Forwarding for better log collection
    $registryPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\EventLog\EventForwarding\SubscriptionManager"
    if (!(Test-Path $registryPath)) {
        New-Item -Path $registryPath -Force | Out-Null
    }
    
    # Configure Windows Defender Advanced Threat Protection (if available)
    try {
        $defenderATP = Get-MpComputerStatus
        if ($defenderATP.AMServiceEnabled) {
            Write-Host "Windows Defender ATP is available and enabled" -ForegroundColor Green
        }
    } catch {
        Write-Host "Windows Defender ATP not available or not configured" -ForegroundColor Yellow
    }
    
    # Update threat definitions
    Write-Host "Updating threat definitions..." -ForegroundColor Yellow
    Update-MpSignature
    Write-Host "Threat definitions updated" -ForegroundColor Green
    
    # Get current status
    $defenderStatus = Get-MpComputerStatus
    
    # Create log entry
    $logEntry = @"
[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Windows Defender Configuration Summary:
- Real-time protection: $($defenderStatus.RealTimeProtectionEnabled)
- Cloud protection: Advanced MAPS reporting enabled
- Network protection: Enabled
- Script block logging: Enabled
- Threat definitions version: $($defenderStatus.AntivirusSignatureVersion)
- Last full scan: $($defenderStatus.FullScanStartTime)
- Last quick scan: $($defenderStatus.QuickScanStartTime)
"@
    
    $logPath = "C:\DetonatorLogs"
    if (!(Test-Path $logPath)) {
        New-Item -ItemType Directory -Path $logPath -Force
    }
    
    $logEntry | Out-File -FilePath "$logPath\defender_config.log" -Encoding UTF8 -Append
    Write-Host "Configuration log saved to $logPath\defender_config.log" -ForegroundColor Green
    
    Write-Host "`nWindows Defender Configuration Complete!" -ForegroundColor Green
    Write-Host "Current Protection Status:" -ForegroundColor Cyan
    Write-Host "  Real-time Protection: $($defenderStatus.RealTimeProtectionEnabled)" -ForegroundColor White
    Write-Host "  Cloud Protection: Enabled" -ForegroundColor White
    Write-Host "  Network Protection: Enabled" -ForegroundColor White
    Write-Host "  Threat Definitions: $($defenderStatus.AntivirusSignatureVersion)" -ForegroundColor White
    
} catch {
    Write-Host "Error during Windows Defender configuration: $($_.Exception.Message)" -ForegroundColor Red
    
    # Log the error
    $errorEntry = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: $($_.Exception.Message)"
    $logPath = "C:\DetonatorLogs"
    if (!(Test-Path $logPath)) {
        New-Item -ItemType Directory -Path $logPath -Force
    }
    $errorEntry | Out-File -FilePath "$logPath\defender_config.log" -Encoding UTF8 -Append
    
    exit 1
}

Write-Host "`nWindows Defender configuration script completed successfully!" -ForegroundColor Green
