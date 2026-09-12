$ErrorActionPreference = "Stop"
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
# pack lives in WindowsComputerUse/CONSULTATION_PACK → root is WindowsComputerUse
$root = Split-Path $PSScriptRoot -Parent
$pack = Join-Path $root "CONSULTATION_PACK"
$robotSrc = "C:\Users\AkarTech\Downloads\MatrixRobot_Handoff_Clean-3\MatrixRobot\artifacts\python-agents\quantconnect\MatrixRobotQC\main.py"
$execSrc = Join-Path $root "APOS\cos\execution\qc_executor.py"

New-Item -ItemType Directory -Force -Path (Join-Path $pack "robot"), (Join-Path $pack "code") | Out-Null
if (Test-Path $robotSrc) { Copy-Item $robotSrc (Join-Path $pack "robot\MatrixRobotQC_main.py") -Force }
if (Test-Path $execSrc) { Copy-Item $execSrc (Join-Path $pack "code\qc_executor.py") -Force }

$zip = Join-Path ([Environment]::GetFolderPath("Downloads")) "COS_CONSULTATION_PACK.zip"
$desk = Join-Path ([Environment]::GetFolderPath("Desktop")) "COS_CONSULTATION_PACK.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $pack "*") -DestinationPath $zip -Force
Copy-Item $zip $desk -Force
Write-Host "Created:" $zip
Write-Host "Also on Desktop:" $desk
