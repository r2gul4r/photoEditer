#!/usr/bin/env sh
set -eu

echo "Starting TonePilot Local backend and desktop."
echo "First run installs Node and backend dependencies if needed."

if command -v pnpm >/dev/null 2>&1; then
  pnpm_cmd="pnpm"
else
  pnpm_cmd="npx pnpm@10.14.0"
fi

if [ ! -d "node_modules" ]; then
  echo "Installing frontend workspace dependencies..."
  $pnpm_cmd install
fi

echo "Checking backend Python environment..."
node scripts/setup.mjs

$pnpm_cmd dev
