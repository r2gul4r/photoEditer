# TonePilot Backend

Local FastAPI backend for image analysis, recommendation generation, preview rendering, and JSON preset export.

## Run

```powershell
cd apps/backend
pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8765
```

## Test

```powershell
pytest
```
