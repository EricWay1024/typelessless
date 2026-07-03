# Build typelessless as a standalone Windows app.
#   PS>  ./build.ps1
# Produces dist\typelessless.exe and, on first run, dist\config.toml to fill in.

$ErrorActionPreference = "Stop"

if (-not (Test-Path .\.venv)) {
    python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -e ".[build]"

pyinstaller --noconfirm --clean typelessless.spec

if (-not (Test-Path .\dist\config.toml)) {
    Copy-Item config.example.toml .\dist\config.toml
    Write-Host "Created dist\config.toml — open it and add your keys."
}

Write-Host ""
Write-Host "Built dist\typelessless.exe"
Write-Host "Next: edit dist\config.toml, then double-click dist\typelessless.exe."
