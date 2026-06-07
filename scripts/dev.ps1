$ErrorActionPreference = "Stop"

Write-Host "Starting TonePilot Local backend and desktop."
Write-Host "First run installs Node and backend dependencies if needed; later runs reuse them."

$pnpm = Get-Command pnpm.cmd -ErrorAction SilentlyContinue

function Invoke-ProjectPnpm {
  param([string[]] $Arguments)
  if ($pnpm) {
    & $pnpm.Source @Arguments
  } else {
    & npx.cmd pnpm@10.14.0 @Arguments
  }
}

if (-not (Test-Path "node_modules")) {
  Write-Host "Installing frontend workspace dependencies..."
  Invoke-ProjectPnpm @("install")
}

Write-Host "Checking/reusing backend Python environment..."
& node "scripts/setup.mjs"

Invoke-ProjectPnpm @("dev")
