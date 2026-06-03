# TonePilot Backend

Local FastAPI backend for image analysis, recommendation generation, preview rendering, and JSON preset export.

## Run

```powershell
pnpm run setup
pnpm backend:dev
```

The root setup script creates `apps/backend/.venv` and installs backend dependencies. Start through `pnpm backend:dev` or `pnpm dev` so the launcher can auto-detect the Codex command when available.

## Test

```powershell
pnpm backend:test
```
