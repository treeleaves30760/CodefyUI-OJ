# Stage the sandbox build context (cdui repo + sandbox scripts) and build the image.
#
# Usage:
#   .\build_sandbox.ps1                 # default cdui at ..\CodefyUI
#   .\build_sandbox.ps1 -CduiPath D:\path\to\CodefyUI
#   .\build_sandbox.ps1 -Tag codefyui-oj-sandbox:dev

param(
    [string]$CduiPath,
    [string]$Tag = "codefyui-oj-sandbox:latest"
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path "$PSScriptRoot\..\.."
if (-not $CduiPath) {
    $CduiPath = Resolve-Path "$root\..\CodefyUI"
}
if (-not (Test-Path $CduiPath)) {
    throw "cdui repo not found at $CduiPath"
}

$stage = New-Item -ItemType Directory -Path (Join-Path $env:TEMP "codefyui-oj-sandbox-$(Get-Random)") -Force
try {
    Write-Host "Staging build context in $stage"
    Copy-Item -Recurse -Path "$CduiPath" -Destination "$stage\cdui" `
        -Exclude @(".git", ".venv", "node_modules", "__pycache__", "frontend", ".worktrees")
    Copy-Item -Recurse -Path "$root\backend\sandbox" -Destination "$stage\sandbox"
    Copy-Item -Path "$root\backend\docker\sandbox.Dockerfile" -Destination "$stage\Dockerfile"

    Write-Host "Building $Tag"
    docker build -t $Tag "$stage"
}
finally {
    Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
}
