# RedEdr Download & Extract

$zipUrl = "https://detonator1.blob.core.windows.net/scripts/rededr.zip"

# Kill existing RedEdr (or we cant overwrite RedEdr.exe)
Stop-Process -Name "RedEdr" -Force

# Stop the RedEdr PPL (or we cant overwrite RedEdrPplService.exe)
C:\RedEdr\RedEdr.exe --pplstop

$zipPath = "C:\RedEdr\rededr_download.zip"
$extractPath = "C:\RedEdr"

# Create the destination directory if it doesn't exist
if (-Not (Test-Path -Path $extractPath)) {
    New-Item -ItemType Directory -Path $extractPath -Force
}

# Download, unzip, delete zip
Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force
Remove-Item $zipPath
