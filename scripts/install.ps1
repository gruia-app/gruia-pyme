$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
  Copy-Item ".env.example" ".env"
}

python cli.py init
python -m unittest discover -s tests -v
python cli.py doctor
Write-Host "Listo. Arranca con: python run.py"
