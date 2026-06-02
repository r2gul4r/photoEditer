#!/usr/bin/env sh
set -eu

echo "Starting TonePilot Local backend and desktop."
echo "If pnpm is missing, run: corepack enable"

if command -v pnpm >/dev/null 2>&1; then
  pnpm dev
else
  npx pnpm@10.14.0 dev
fi
