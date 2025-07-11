
# RedEdr Download & Extract

# Define the URL of the ZIP file and the destination folder
$zipUrl = "https://detonator1.blob.core.windows.net/scripts/rededr.zip"
$zipPath = "C:\RedEdr\rededr_download.zip"
$extractPath = "C:\RedEdr"
$exePath = "C:\RedEdr\RedEdr.exe"

# Create the destination directory if it doesn't exist
if (-Not (Test-Path -Path $extractPath)) {
    New-Item -ItemType Directory -Path $extractPath -Force
}

# Exclude for defender
Add-MpPreference -ExclusionPath "C:\RedEdr"
Set-MpPreference -SubmitSamplesConsent 2  # 2 = never send

# Download the ZIP file
Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
# Extract the ZIP file
Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force
# Optionally remove the ZIP after extraction
Remove-Item $zipPath

# Allow RedEdr through Windows Firewall
$ruleName = "Allow RedEdr"
New-NetFirewallRule -DisplayName $ruleName `
                    -Direction Inbound `
                    -Program $exePath `
                    -Action Allow `
                    -Profile Any `
                    -Enabled True


                    
# This disables the "first logon animation" and suppresses OOBE experience
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name "EnableFirstLogonAnimation" -Value 0 -Type DWord -Force
# (Optional) Mark OOBE as complete (used in Sysprep/unattended deployments)
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Setup\State" -Name "ImageState" -Value "IMAGE_STATE_COMPLETE" -Force
# Optional: Skip Microsoft Account prompts
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\OOBE" -Name "SkipUserOOBE" -Value 1 -Type DWord -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\OOBE" -Name "SkipMachineOOBE" -Value 1 -Type DWord -Force


# User & Autologon
# Create a local user 'rededr' without admin rights
$user = "rededr"
$password = "rededr"
# Create the secure password object
$securePassword = ConvertTo-SecureString $password -AsPlainText -Force
# Create the user if not exists
if (-not (Get-LocalUser -Name $user -ErrorAction SilentlyContinue)) {
    New-LocalUser -Name $user -Password $securePassword -FullName "Red Edr User" -Description "Non-admin user for auto login"
}
# Ensure user is NOT part of Administrators group
#Remove-LocalGroupMember -Group "Administrators" -Member $user -ErrorAction SilentlyContinue


# Enable autologin for this user
#New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" -Name "AutoAdminLogon" -Value "1" -PropertyType String -Force
#New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" -Name "DefaultUsername" -Value $user -PropertyType String -Force
#New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" -Name "DefaultPassword" -Value $password -PropertyType String -Force


# RedEdr start

$taskName = "RedEdrBootTask"
$exePath = "C:\RedEdr\RedEdr.exe"
$myargs    = '--hide --web --etw --port 80 --trace malware'

# Scheduled task action with arguments
$action = New-ScheduledTaskAction -Execute $exePath -Argument $myargs

# Run at startup
# -AtLogOn
$trigger = New-ScheduledTaskTrigger -AtStartup

# Run as SYSTEM
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest

# Register the task
Register-ScheduledTask -TaskName $taskName `
                       -Action $action `
                       -Trigger $trigger `
                       -Principal $principal `
                       -Description "RedEdr for Detonator" `
                       -Force
