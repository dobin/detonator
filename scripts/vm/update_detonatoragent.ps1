# DetonatorAgent Download & Extract

$zipUrl = "https://detonator1.blob.core.windows.net/scripts/detonatoragent.zip"

# Kill existing DetonatorAgent (or we cant overwrite DetonatorAgent.exe)
Stop-Process -Name "DetonatorAgent" -Force

$zipPath = "C:\DetonatorAgent\detonatoragent_download.zip"
$extractPath = "C:\DetonatorAgent"

# Create the destination directory if it doesn't exist
if (-Not (Test-Path -Path $extractPath)) {
    New-Item -ItemType Directory -Path $extractPath -Force
}

# Download, unzip, delete zip
Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force
Remove-Item $zipPath
