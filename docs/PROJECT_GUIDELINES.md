# Project Guidelines

## Product Target

photoEditer is a local-first photo correction application inspired by Lightroom Classic's editing workflow. The goal is not to clone Lightroom's proprietary UI, assets, names, or internals. The goal is to match useful editing concepts:

- non-destructive source + adjustment state
- RAW-first import and analysis
- histogram-aware correction
- preview/export from one ordered render pipeline
- AI-assisted correction candidates
- reference-image driven style learning later

Default UI language is English. Korean must be available through an in-app language toggle.

## Ports

- Backend API: `127.0.0.1:8765`
- Desktop dev server: `127.0.0.1:5173`
- Optional Codex app-server WebSocket: `127.0.0.1:8795`
- Reserved local range for this project: `8765-8799`

Do not bind non-loopback addresses for local AI or app-server features unless a separate security review approves it.

## Technology Stack

Frontend:

- Vite, React, TypeScript
- CSS/Tailwind utility support, but keep product UI mostly custom
- lucide-react for common icons
- Direct SVG or Canvas for histograms and photo interaction layers
- No heavy UI kit unless a specific workflow requires it

Frontend design workflow:

- Produce or update a design mockup before major frontend implementation.
- Current mockup: `docs/design/tonepilot-lightroom-inspired-mockup.png`
- Use Lightroom Classic only as a workflow/layout reference: module rail, central photo canvas, filmstrip/reference strip, inspector panels, histogram-first correction.
- Do not copy Lightroom's exact visual design, icons, text, panel names beyond generic editing terms, or pixel layout.
- Keep extension slots visible for future work such as denoise, lens correction, masks, alternate render stacks, and additional AI providers.

Backend:

- Python 3.11 preferred for dependency compatibility
- FastAPI, Pydantic, Uvicorn
- NumPy and Pillow for current rendering/analysis
- rawpy optional for RAW import
- exifread optional for metadata
- pytest/httpx for backend tests

AI integration:

- Primary assistant path: Codex app-server through local JSON-RPC stdio when enabled
- Fallback path: deterministic local rule engine
- Default Codex recommendation timeout: `90` seconds through `TONEPILOT_CODEX_TIMEOUT_SECONDS`
- Future local ML path: ONNX Runtime, OpenCV, PyTorch, or Hugging Face models only after a separate model/runtime decision
- Future image-specific AI modules should be isolated behind provider interfaces so denoise, upscaling, local style learning, and Codex recommendation can evolve independently.

Packaging target:

- Start as local web app
- Prefer Tauri for desktop packaging later
- Electron is fallback only if Tauri blocks required image workflows

## Lightroom Analysis Boundary

Allowed:

- Study Adobe public documentation
- Compare visible behavior with user-owned images
- Build black-box test images and compare histogram/readout/clipping states
- Document observable behavior and compatible app contracts

Not allowed:

- Decompile, unpack, patch, or extract proprietary Lightroom binaries/assets
- Copy Lightroom UI pixels, icons, names, or proprietary copy
- Depend on internal Lightroom implementation details

## Editing Pipeline Rule

Every correction feature should fit this model:

```text
original source
-> base RAW/profile/default interpretation
-> ordered global adjustments
-> local masks and retouch operations
-> preview render
-> export render
```

Preview and export must use the same renderer path. Do not stack a new correction on top of a previously rendered preview.

## AI Correction Rule

AI may suggest adjustment values, warnings, and rationale. AI must not directly mutate the source file.

The API should return a stable candidate set:

- `natural`: conservative correction
- `style`: balanced style match
- `bold`: stronger creative candidate

If Codex app-server is unavailable, not logged in, times out, or returns invalid JSON, the backend must fall back to the rule-based recommender and expose the fallback status in API metadata.

On Windows, `codex app-server daemon ...` lifecycle commands may be unsupported. The backend should use stdio by spawning `codex app-server` directly.

Recommendation mode defaults to `auto`:

- `auto`: try Codex app-server first, then fallback to local rules.
- `codex`: require Codex app-server and fail visibly when unavailable.
- `rules`: use deterministic local rules only.

The frontend should expose this mode as an editor control while keeping `auto` as the default.

Expose `GET /api/ai/status` for a model-free Codex app-server initialization probe. This endpoint may start `codex app-server` only long enough to verify stdio initialization; it must not start a model turn or consume model quota.

Use `scripts/smoke_codex_recommend.py` for Codex validation:

```powershell
# Model-free status probe only.
C:\tmp\photoediter-venv311-20260603\Scripts\python.exe scripts\smoke_codex_recommend.py

# Real Codex recommendation turn. Requires explicit approval because this can consume Codex usage/quota.
C:\tmp\photoediter-venv311-20260603\Scripts\python.exe scripts\smoke_codex_recommend.py --allow-codex-model-call
```

## Reference Data Layout

Reference assets are local-only and ignored by git by default:

```text
reference/
  raw/
  jpeg/
  edits/
  presets/
  manifests/
  README.md
```

Use manifests to describe reference photos, target looks, before/after pairs, camera metadata, and licensing. Do not commit personal RAW files.

## Environment Setup

Open-source default setup should keep the backend venv inside the repository and let scripts resolve it:

One-command Windows bootstrap:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Join-Path $env:TEMP 'photo-install.ps1'; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/r2gul4r/photoEditer/main/install.ps1' -OutFile $p; & $p"
photo dev
```

Developer-local setup after cloning:

```powershell
corepack enable
pnpm install
pnpm run setup
```

`pnpm run setup` creates `apps/backend/.venv` and installs backend dependencies. Python 3.11 or 3.12 is preferred for RAW dependency compatibility. If RAW dependency installation fails, setup may retry without `rawpy` so the app can still run with JPEG/PNG/TIFF and local rules. Retry RAW support with `pnpm run setup -- --retry-raw`.

Global CLI registration:

```powershell
npm link
photo install
photo dev
```

Windows quick start:

```powershell
.\scripts\dev.ps1
```

macOS/Linux quick start:

```sh
sh scripts/dev.sh
```

Repository scripts should prefer project-local venvs before system Python:

```powershell
pnpm dev
pnpm backend:dev
pnpm backend:test
pnpm backend:smoke:codex-status
```

`pnpm backend:smoke:codex` runs a real Codex recommendation turn and can consume Codex usage/quota.

Run frontend:

```powershell
pnpm desktop:dev
```

## Verification

Minimum checks before claiming done:

- `C:\tmp\photoediter-venv311\Scripts\python.exe -m pytest apps\backend\tests`
- `pnpm --filter @tonepilot/desktop build`
- Upload a JPEG/PNG and confirm analyze/recommend/preview/export flow manually or through an API test
- For histogram changes, use synthetic 0..255 ramp and clipping samples

If a check cannot run, record why and what remains unverified.
