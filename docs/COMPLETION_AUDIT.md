# Goal Completion Audit

This document maps the active project goal to current evidence in the repository. It is intentionally strict: a requirement is marked complete only when current files or command output can prove it.

## Scope

Goal:

- Analyze Lightroom photo-editing features, not account/login behavior.
- Define all required technology stack choices and project guidelines.
- Build the local working environment.
- Implement the first-priority AI correction feature.
- Use a Lightroom-inspired frontend layout/design without copying Lightroom 1:1.
- Support English first and Korean as an in-app language.
- Use local Codex app-server when Codex is logged in.
- Choose a local port range.
- Provide reference photo and RAW storage for future photo-correction learning.
- Answer whether local AI training for photo correction is possible.

## Requirement Matrix

| Requirement | Evidence | Status |
| --- | --- | --- |
| Lightroom feature/workflow analysis, excluding login/cloud/account flows | `docs/LIGHTROOM_FEATURE_DECOMPOSITION.md`, `docs/LIGHTROOM_HISTOGRAM_COMPAT.md` | Complete |
| Technology stack and project guidelines saved | `docs/PROJECT_GUIDELINES.md` | Complete |
| Port range selected | `docs/PROJECT_GUIDELINES.md` uses `8765-8799`, backend `8765`, frontend `5173` | Complete |
| Local working environment established | `pnpm install` completed, Python 3.11 venv at `C:\tmp\photoediter-venv311-20260603`, backend dependencies installed | Complete |
| Reference/RAW learning space exists | `reference/README.md`, `reference/raw/.gitkeep`, `reference/jpeg/.gitkeep`, `reference/edits/.gitkeep`, `reference/presets/.gitkeep`, `reference/manifests/example.json` | Complete |
| Local AI training question answered | `docs/LOCAL_AI_TRAINING_OPTIONS.md` | Complete |
| English first, Korean available | `apps/desktop/src/i18n.ts`, language toggle in `apps/desktop/src/App.tsx` | Complete |
| Lightroom-inspired but non-copy frontend | `docs/design/tonepilot-lightroom-inspired-mockup.png`, `apps/desktop/src/App.tsx`, `apps/desktop/src/styles.css` | Complete |
| AI correction backend implemented | `apps/backend/app/services/codex_app_server.py`, `apps/backend/app/routers/recommend.py` | Complete |
| Rule fallback implemented | `apps/backend/app/routers/recommend.py`, `apps/backend/tests/test_api.py` | Complete |
| Codex automatic mode implemented | `RecommendRequest.ai_mode = "auto"`, frontend AI mode toggle, `/api/ai/status` | Complete |
| Model-free Codex connection status verified | `scripts/smoke_codex_recommend.py` default mode returned `available: true`, `model_turn: skipped` | Complete |
| Actual Codex model recommendation turn verified | `pnpm backend:smoke:codex` returned `model_turn: used`, `candidate_ids: ["natural", "style", "bold"]`, `ai_status.status: used`, and a preview URL | Complete |
| Analyze/recommend/preview/export API flow verified | `apps/backend/tests/test_api.py` smoke flow | Complete |
| Histogram compatibility tests | `apps/backend/tests/test_histograms.py` | Complete |
| Frontend build verified | `pnpm --filter @tonepilot/desktop build` | Complete |
| Backend tests verified | `C:\tmp\photoediter-venv311-20260603\Scripts\python.exe -m pytest apps\backend\tests` | Complete |
| Runtime frontend/backend reachable | `http://127.0.0.1:5173`, `http://127.0.0.1:8765` | Complete |

## Final Codex Model Verification

The approval-gated Codex model smoke was run successfully after explicit user approval.

Command:

```powershell
pnpm backend:smoke:codex
```

Observed success criteria:

- `model_turn` is `used`
- `candidate_ids` is `["natural", "style", "bold"]`
- `ai_status.provider` is `codex-app-server`
- `ai_status.status` is `used`
- `preview_url` starts with `/api/previews/`

The active goal can be marked complete after the normal backend/frontend checks pass.
