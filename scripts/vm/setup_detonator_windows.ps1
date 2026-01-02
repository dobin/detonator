# Script to setup RedEdr on Windows

####################################################
### Windows

# Definitions
$user = "rededr"
$password = "rededr"

# This disables the "first logon animation" and suppresses OOBE experience
#  and mark OOBE as complete
#  and skip microsoft account prompts
# This is basically just required for Azure or sysprep instanciations
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name "EnableFirstLogonAnimation" -Value 0 -Type DWord -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Setup\State" -Name "ImageState" -Value "IMAGE_STATE_COMPLETE" -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\OOBE" -Name "SkipUserOOBE" -Value 1 -Type DWord -Force
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\OOBE" -Name "SkipMachineOOBE" -Value 1 -Type DWord -Force

# Even more disabling of that "Windows Welcome Experience" shit which asks for microsoft account
New-Item -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent" -Force | Out-Null;
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent" -Name "DisableWindowsConsumerFeatures" -Value 1 -Type DWord;
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent" -Name "DisableSoftLanding" -Value 1 -Type DWord;
Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent" -Name "DisableWindowsSpotlightFeatures" -Value 1 -Type DWord;
New-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\UserProfileEngagement" -Force | Out-Null;
Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\UserProfileEngagement" -Name "ScoobeSystemSettingEnabled" -Value 0 -Type DWord


# Create rededr user
$securePassword = ConvertTo-SecureString $password -AsPlainText -Force
if (-not (Get-LocalUser -Name $user -ErrorAction SilentlyContinue)) {
    New-LocalUser -Name $user -Password $securePassword -FullName "Red Edr User" -Description "Non-admin user for auto login"
}
# dont expire the damn password
Get-LocalUser -Name "$user" | Set-LocalUser -PasswordNeverExpires $true


# Enable autologin for the RedEdr user
New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" -Name "AutoAdminLogon" -Value "1" -PropertyType String -Force
New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" -Name "DefaultUsername" -Value $user -PropertyType String -Force
New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" -Name "DefaultPassword" -Value $password -PropertyType String -Force

# Disable hibernation (and with it fast startup)
# This is extremely important for Proxmox Revert-To-Snapshot style
# functionality for ETW-TI and Hooking (allow self-signed kernel drivers)
# Or else "reboot" or "shutdown" are not really performed, giving
# weird results
powercfg /h off

# Defender General
Set-MpPreference -SubmitSamplesConsent 2  # 2 = never send


####################################################
### RedEdr

$RedEdrPort = 8081

# Ensure the RedEdr directory exists
New-Item -ItemType Directory -Path "C:\RedEdr" -Force

# Exclude for Defender - very important
# This is for the whole RedEdr directory
#   including malware in C:\RedEdr\data
Add-MpPreference -ExclusionPath "C:\RedEdr"

# just to make sure
Add-MpPreference -ExclusionProcess "DetonatorAgent.exe"

# Allow RedEdr through Windows Firewall
New-NetFirewallRule -DisplayName "Allow RedEdr ($RedEdrPort)" `
                    -Direction Inbound `
                    -Action Allow `
                    -Protocol TCP `
                    -LocalPort $RedEdrPort `
                    -Profile Any `
                    -Enabled True

# RedEdr start on boot
$taskName = "RedEdrBootTask"
$RedEdrExePath = "C:\RedEdr\RedEdr.exe"
$myargs    = "--etw --port $RedEdrPort"

# Scheduled task action with exec_arguments
$action = New-ScheduledTaskAction -Execute $RedEdrExePath -Argument $myargs
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


####################################################
### DetonatorAgent

$DetonatorAgentPort = 8080
$DetonatorAgentExePath = "C:\DetonatorAgent\DetonatorAgent.exe"
$myargs    = "--port $DetonatorAgentPort"

# Ensure the DetonatorAgent directory exists
New-Item -ItemType Directory -Path "C:\DetonatorAgent" -Force

# Exclude for Defender
# This is for the whole DetonatorAgent directory
Add-MpPreference -ExclusionPath "C:\DetonatorAgent"

# Process too - this is extremely important as DetonatorAgent.exe
# is dropping and/or containintg malware
Add-MpPreference -ExclusionProcess "DetonatorAgent.exe"

# Allow DetonatorAgent through Windows Firewall
New-NetFirewallRule -DisplayName "Allow DetonatorAgent ($DetonatorAgentPort)" `
                    -Direction Inbound `
                    -Action Allow `
                    -Protocol TCP `
                    -LocalPort $DetonatorAgentPort `
                    -Profile Any `
                    -Enabled True

# DetonatorAgent start on boot
$taskName = "DetonatorAgentBootTask"
$DetonatorAgentExePath = "C:\DetonatorAgent\DetonatorAgent.exe"
$myargs    = "--port $DetonatorAgentPort"

# Scheduled task action with exec_arguments
$action = New-ScheduledTaskAction -Execute $DetonatorAgentExePath -Argument $myargs
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId "$user"
Register-ScheduledTask -TaskName $taskName `
                       -Action $action `
                       -Trigger $trigger `
                       -Principal $principal `
                       -Description "DetonatorAgent for Detonator" `
                       -Force
