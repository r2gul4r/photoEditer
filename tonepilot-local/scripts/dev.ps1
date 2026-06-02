$ErrorActionPreference = "Stop"

Write-Host "Starting TonePilot Local backend and desktop."
Write-Host "If pnpm is missing, run: corepack enable"

$pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
if ($pnpm) {
  pnpm dev
} else {
  npx.cmd pnpm@10.14.0 dev
}
