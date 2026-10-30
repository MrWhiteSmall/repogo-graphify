$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 run.py
} else {
    & python run.py
}
exit $LASTEXITCODE
