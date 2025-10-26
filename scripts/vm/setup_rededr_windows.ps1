# Script to setup RedEdr on Windows

# Definitions
$exePath = "C:\RedEdr\RedEdr.exe"
$user = "rededr"
$password = "rededr"

# Ensure the RedEdr directory exists
New-Item -ItemType Directory -Path "C:\RedEdr" -Force

# Exclude for Defender
# This is for the whole RedEdr directory
#   including malware in C:\RedEdr\data
Add-MpPreference -ExclusionPath "C:\RedEdr"
Set-MpPreference -SubmitSamplesConsent 2  # 2 = never send

# Allow RedEdr through Windows Firewall
New-NetFirewallRule -DisplayName "Allow RedEdr (80, 8080)" `
                    -Direction Inbound `
                    -Action Allow `
                    -Protocol TCP `
                    -LocalPort 80,8080 `
                    -Profile Any `
                    -Enabled True

# This disables the "first logon animation" and suppresses OOBE experience
#  and mark OOBE as complete
#  and skip microsoft account prompts
# This is basically just required for Azure or sysprep instanciations
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name "EnableFirstLogonAnimation" -Value 0 -Type DWord -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Setup\State" -Name "ImageState" -Value "IMAGE_STATE_COMPLETE" -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\OOBE" -Name "SkipUserOOBE" -Value 1 -Type DWord -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\OOBE" -Name "SkipMachineOOBE" -Value 1 -Type DWord -Force

# Create rededr user
$securePassword = ConvertTo-SecureString $password -AsPlainText -Force
if (-not (Get-LocalUser -Name $user -ErrorAction SilentlyContinue)) {
    New-LocalUser -Name $user -Password $securePassword -FullName "Red Edr User" -Description "Non-admin user for auto login"
}

# Enable autologin for the RedEdr user
New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" -Name "AutoAdminLogon" -Value "1" -PropertyType String -Force
New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" -Name "DefaultUsername" -Value $user -PropertyType String -Force
New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" -Name "DefaultPassword" -Value $password -PropertyType String -Force

# RedEdr start on boot
$taskName = "RedEdrBootTask"
$exePath = "C:\RedEdr\RedEdr.exe"
$myargs    = '--hide --web --etw --port 80 --trace malware'

# Scheduled task action with exec_arguments
$action = New-ScheduledTaskAction -Execute $exePath -Argument $myargs
$trigger = New-ScheduledTaskTrigger -AtStartup
#$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
Register-ScheduledTask -TaskName $taskName `
                       -Action $action `
                       -Trigger $trigger `
                       -Principal $principal `
                       -Description "RedEdr for Detonator" `
                       -Force

# Task can be enabled or disabled with:
# Disable-ScheduledTask -TaskName "RedEdrBootTask"
# Enable-ScheduledTask -TaskName "RedEdrBootTask"

# Disable hibernation (and with it fast startup)
# This is extremely important for Proxmox Revert-To-Snapshot style
# functionality for ETW-TI and Hooking (allow self-signed kernel drivers)
# Or else "reboot" or "shutdown" are not really performed, giving
# weird results
powercfg /h off
