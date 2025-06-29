# Sysmon Installation and Configuration Script
# This script installs Sysmon for detailed system monitoring

Write-Host "Installing Sysmon for system monitoring..." -ForegroundColor Green

try {
    # Create download directory
    $downloadPath = "C:\DetonatorTools"
    if (!(Test-Path $downloadPath)) {
        New-Item -ItemType Directory -Path $downloadPath -Force
        Write-Host "Created directory: $downloadPath" -ForegroundColor Green
    }
    
    # Download Sysmon
    $sysmonUrl = "https://download.sysinternals.com/files/Sysmon.zip"
    $sysmonZip = "$downloadPath\Sysmon.zip"
    
    Write-Host "Downloading Sysmon..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $sysmonUrl -OutFile $sysmonZip
    Write-Host "Sysmon downloaded successfully" -ForegroundColor Green
    
    # Extract Sysmon
    Expand-Archive -Path $sysmonZip -DestinationPath $downloadPath -Force
    Write-Host "Sysmon extracted successfully" -ForegroundColor Green
    
    # Create Sysmon configuration
    $sysmonConfig = @"
<Sysmon schemaversion="4.50">
  <EventFiltering>
    <!-- Log all process creation events -->
    <ProcessCreate onmatch="exclude">
      <Image condition="is">C:\Windows\System32\svchost.exe</Image>
    </ProcessCreate>
    
    <!-- Log all file creation events -->
    <FileCreate onmatch="include">
      <TargetFilename condition="contains">.exe</TargetFilename>
      <TargetFilename condition="contains">.dll</TargetFilename>
      <TargetFilename condition="contains">.bat</TargetFilename>
      <TargetFilename condition="contains">.cmd</TargetFilename>
      <TargetFilename condition="contains">.ps1</TargetFilename>
      <TargetFilename condition="contains">.vbs</TargetFilename>
      <TargetFilename condition="contains">.js</TargetFilename>
    </FileCreate>
    
    <!-- Log all network connections -->
    <NetworkConnect onmatch="exclude">
      <Image condition="is">C:\Windows\System32\svchost.exe</Image>
    </NetworkConnect>
    
    <!-- Log all registry modifications -->
    <RegistryEvent onmatch="include">
      <TargetObject condition="contains">SOFTWARE\Microsoft\Windows\CurrentVersion\Run</TargetObject>
      <TargetObject condition="contains">SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce</TargetObject>
    </RegistryEvent>
    
    <!-- Log process access attempts -->
    <ProcessAccess onmatch="include">
      <TargetImage condition="contains">lsass.exe</TargetImage>
      <TargetImage condition="contains">winlogon.exe</TargetImage>
    </ProcessAccess>
  </EventFiltering>
</Sysmon>
"@
    
    $configPath = "$downloadPath\sysmon-config.xml"
    $sysmonConfig | Out-File -FilePath $configPath -Encoding UTF8
    Write-Host "Sysmon configuration created" -ForegroundColor Green
    
    # Install Sysmon
    $sysmonExe = "$downloadPath\Sysmon64.exe"
    if (Test-Path $sysmonExe) {
        Write-Host "Installing Sysmon with configuration..." -ForegroundColor Yellow
        & $sysmonExe -accepteula -i $configPath
        Write-Host "Sysmon installed successfully" -ForegroundColor Green
    } else {
        Write-Host "Sysmon executable not found, trying 32-bit version..." -ForegroundColor Yellow
        $sysmonExe = "$downloadPath\Sysmon.exe"
        if (Test-Path $sysmonExe) {
            & $sysmonExe -accepteula -i $configPath
            Write-Host "Sysmon (32-bit) installed successfully" -ForegroundColor Green
        } else {
            throw "Sysmon executable not found"
        }
    }
    
    # Verify Sysmon service
    $sysmonService = Get-Service -Name "Sysmon64" -ErrorAction SilentlyContinue
    if (!$sysmonService) {
        $sysmonService = Get-Service -Name "Sysmon" -ErrorAction SilentlyContinue
    }
    
    if ($sysmonService -and $sysmonService.Status -eq "Running") {
        Write-Host "Sysmon service is running successfully" -ForegroundColor Green
    } else {
        Write-Host "Warning: Sysmon service may not be running properly" -ForegroundColor Yellow
    }
    
    # Create log entry
    $logEntry = @"
[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Sysmon Installation Summary:
- Sysmon downloaded and extracted
- Configuration file created with malware analysis settings
- Sysmon service installed and started
- Event logging configured for:
  * Process creation events
  * File creation events (executables, scripts)
  * Network connections
  * Registry modifications (startup locations)
  * Process access attempts (sensitive processes)
"@
    
    $logPath = "C:\DetonatorLogs"
    if (!(Test-Path $logPath)) {
        New-Item -ItemType Directory -Path $logPath -Force
    }
    
    $logEntry | Out-File -FilePath "$logPath\sysmon_install.log" -Encoding UTF8 -Append
    Write-Host "Installation log saved to $logPath\sysmon_install.log" -ForegroundColor Green
    
    Write-Host "`nSysmon Installation Complete!" -ForegroundColor Green
    Write-Host "Sysmon is now monitoring system activity" -ForegroundColor Cyan
    Write-Host "Events will be logged to Windows Event Log under:" -ForegroundColor Cyan
    Write-Host "  Applications and Services Logs > Microsoft > Windows > Sysmon > Operational" -ForegroundColor White
    
} catch {
    Write-Host "Error during Sysmon installation: $($_.Exception.Message)" -ForegroundColor Red
    
    # Log the error
    $errorEntry = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: $($_.Exception.Message)"
    $logPath = "C:\DetonatorLogs"
    if (!(Test-Path $logPath)) {
        New-Item -ItemType Directory -Path $logPath -Force
    }
    $errorEntry | Out-File -FilePath "$logPath\sysmon_install.log" -Encoding UTF8 -Append
    
    exit 1
}

Write-Host "`nSysmon installation script completed successfully!" -ForegroundColor Green
