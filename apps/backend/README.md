# TonePilot Backend

Local FastAPI backend for image analysis, recommendation generation, preview rendering, and JSON preset export.

## Run

```powershell
pnpm backend:dev
```

The backend launcher reuses an existing prepared venv. If no usable backend environment exists, it runs the root setup once and then starts the server. Start through `pnpm backend:dev` or `pnpm dev` so the launcher can auto-detect the Codex command when available.

## Test

```powershell
pnpm backend:test
```
