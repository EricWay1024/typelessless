# Run typelessless from source (dev), no build step.
#   PS>  ./run.ps1

$ErrorActionPreference = "Stop"

if (-not (Test-Path .\.venv)) {
    python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1
pip install -e . | Out-Null

if (-not (Test-Path .\config.toml)) {
    Copy-Item config.example.toml config.toml
    Write-Host "Created config.toml — add your keys, then run ./run.ps1 again."
    exit
}

python -m typelessless
