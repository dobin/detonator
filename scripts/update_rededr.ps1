# RedEdr Download & Extract

# Define the URL of the ZIP file and the destination folder
$zipUrl = "https://detonator1.blob.core.windows.net/scripts/rededr.zip"
$zipPath = "C:\RedEdr\rededr_download.zip"
$extractPath = "C:\RedEdr"

# Create the destination directory if it doesn't exist
if (-Not (Test-Path -Path $extractPath)) {
    New-Item -ItemType Directory -Path $extractPath -Force
}

# Download the ZIP file
Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
# Extract the ZIP file
Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force
# Optionally remove the ZIP after extraction
Remove-Item $zipPath

