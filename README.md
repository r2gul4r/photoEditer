<p align="right">
  <a href="README.ko.md">Korean</a>
</p>

# photoEditer

photoEditer, also known as TonePilot Local, is a RAW-first local photo correction recommendation tool built with Codex. It is designed for real photos you took, not AI-generated images.

The intended workflow is Lightroom-like: start from a RAW file whenever possible, analyze the original capture, find technical weaknesses, give objective feedback, interpret your desired mood, recommend correction values, preview the result, then export the corrected image as JPEG or PNG.

Core flow:

```text
RAW/JPEG/PNG photo -> image analysis -> style target -> histogram-aware candidates -> preview -> JPEG/PNG export
```

## What It Does

- Imports RAW files when `rawpy` is available
- Supports JPEG, PNG, and TIFF as fallback/import convenience formats
- Extracts available metadata
- Calculates luma, RGB, and saturation histograms
- Detects risks such as highlight clipping, crushed shadows, low contrast, over-saturation, and color cast
- Interprets Korean or English style prompts
- Uses clustered style priors derived from market/public LUT and public or YouTube-linked Lightroom preset behavior analysis, without storing or redistributing originals
- Generates three correction candidates: Natural, Style, and Bold
- Renders preview images locally
- Exports rendered correction results as JPEG or PNG
- Exports selected correction values as JSON

## What It Is Not

- It is not a cloud AI photo editor
- It does not generate anime or synthetic images
- It does not ship third-party LUT originals or act as a LUT redistribution library
- It is not a full Lightroom replacement yet, but it is designed around a similar RAW-to-output workflow
- It does not require accounts, payments, or cloud APIs

## Tech Stack

- Frontend: Vite, React, TypeScript, Tailwind CSS, Recharts
- Backend: Python, FastAPI, Pydantic, NumPy, Pillow
- Optional: rawpy for RAW import, exifread, OpenCV
- Workspace: pnpm monorepo

## Easiest Start

On Windows 10/11 PowerShell, install with one command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=Join-Path $env:TEMP 'photo-install.ps1'; Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/r2gul4r/photoEditer/main/install.ps1' -OutFile $p; & $p"
```

This remote command works after `install.ps1` is pushed to the GitHub `main` branch.

This command automatically:

- checks/installs Node.js LTS
- checks/installs Python 3.12
- downloads the photoEditer ZIP from GitHub
- extracts it to `~/TonePilot/photoEditer`
- registers the global `photo` command
- installs project dependencies automatically

You do not need to type `photo install` yourself during first install. After install, open PowerShell from any folder:

```powershell
photo dev
```

`photo dev` prints the local URL and opens the browser automatically. If it does not open, visit `http://127.0.0.1:5173/` manually. Codex is optional; without it, the app runs in local Rules mode.
If port `5173` is already occupied, `photo dev` selects another local port in `5173-5199` and prints the actual URL.

Developers who already cloned the repository on Windows can run `npm.cmd link`, `photo install`, then `photo dev` from the project folder.

## photo Commands

`photo` is the global command available from any folder after install.

| Command | Description |
| --- | --- |
| `photo install` | Reinstalls or repairs dependencies. The one-command installer runs this automatically. |
| `photo dev` | Starts the local web app and opens the browser. It also checks and repairs missing setup when possible. |
| `photo doctor` | Checks Node, Python, backend packages, and optional RAW support status. |
| `photo setup` | Rebuilds or refreshes only the backend Python environment. |
| `photo backend` | Starts only the backend API server. |
| `photo desktop` | Starts only the frontend Vite server. |
| `photo test` | Runs backend tests and the frontend production build. |

## Manual Setup

```powershell
corepack enable
pnpm install
pnpm run setup
```

If Corepack has permission issues on Windows:

```powershell
npx pnpm@10.14.0 install
npx pnpm@10.14.0 run setup
```

To check setup status:

```powershell
pnpm run doctor
```

If `rawpy` fails to install, setup falls back to JPEG/PNG/TIFF support so the app can still run. To retry RAW support later:

```powershell
pnpm run setup -- --retry-raw
```

## Run

Start frontend and backend together:

```powershell
pnpm dev
```

Backend only:

```powershell
pnpm backend:dev
```

Frontend only:

```powershell
pnpm desktop:dev
```

## Codex Connection

When started through `pnpm dev`, the backend automatically resolves the Codex command:

- `TONEPILOT_CODEX_COMMAND` if set
- `codex` from PATH
- Windows Codex app install path at `%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe`

If Codex is missing or not logged in, the app keeps running and falls back to local Rules recommendations. Check connection status without starting a model turn:

```powershell
pnpm backend:smoke:codex-status
```

To verify a real Codex recommendation turn:

```powershell
pnpm backend:smoke:codex
```

That second command can consume Codex usage or quota.

Future local AI providers should attach behind the same provider interface, so the beginner run flow can stay `pnpm dev` while the provider changes under the hood.

## Tests

```powershell
pnpm backend:test
pnpm desktop:build
```

Codex app-server smoke checks:

```powershell
pnpm backend:smoke:codex-status
pnpm backend:smoke:codex
```

The second command starts a real Codex recommendation turn and can consume Codex usage/quota.

## API Overview

- `GET /health`: backend health check
- `POST /api/images/analyze`: upload and analyze an image
- `POST /api/recommend`: generate correction candidates from a style prompt
- `POST /api/preview`: render a preview from selected adjustments
- `GET /api/previews/{filename}`: serve generated previews
- `GET /api/references`: inspect local reference manifests
- `GET /api/references/luts/style-index`: inspect clustered LUT-derived style priors
- `GET /api/references/presets/style-index`: inspect clustered Lightroom preset-derived style priors
- `POST /api/export/preset-json`: export selected correction values as JSON
- `POST /api/export/rendered-image`: export the corrected result as JPEG or PNG

See [docs/API.md](docs/API.md) for details.

## How Image Analysis Works

For RAW files, the backend uses optional `rawpy` to read RAW sensor data and produce a renderable RGB working image. It keeps RAW-specific stats such as black level, white level, mean, p99, and histogram data, then runs the same RGB/luma/saturation analysis used for JPEG, PNG, and TIFF imports.

JPEG, PNG, and TIFF files are also supported. They have less recovery latitude than RAW because tone and color are already baked into the image, but the app can still analyze them, recommend style-aware corrections, render previews, and export adjusted results.

## How Recommendations Work

The MVP uses rule-based style interpretation plus LUT-derived and Lightroom preset-derived style indexes. For example, a prompt such as `cool Japanese summer` maps to `cool_japanese_summer`, while prompts such as `warm wedding`, `Lumix real time LUT`, `cinematic teal orange`, or `black and white monochrome` can select matching style groups.

The LUT index is not a LUT pack. It is a low-dimensional style summary built from observed correction behavior across common public/market LUT concepts. Original `.cube` files are treated as temporary analysis inputs and are deleted after profile extraction. The recommendation engine uses only clustered priors such as tone range, color balance, HSL tendencies, prompt keywords, and risk notes.

The Lightroom preset index follows the same rule: original `.xmp`, `.lrtemplate`, and ZIP files are temporary analysis inputs only. The committed artifact is a clustered style summary of slider, HSL, tone curve, color grading, calibration, prompt keyword, and risk-note tendencies from public and YouTube-linked creator preset behavior.

See [docs/THIRD_PARTY_DATA_POLICY.md](docs/THIRD_PARTY_DATA_POLICY.md) for the release policy around third-party LUT and preset-derived data.

Current style groups include wedding, beauty/skintone, Lumix real-time, Panasonic Rec709 utility, teal-orange, cool night, warm sunset, film/vintage, monochrome, cinematic, pastel, vibrant, and clean natural.

## Current Limitations

- Preview rendering is approximate and does not match Lightroom exactly
- RAW support depends on optional `rawpy` and is still an early pipeline
- CLIP, aesthetic scoring, segmentation, and ONNX model integrations are future modules only
- Export currently supports rendered JPEG/PNG and correction JSON, not XMP or LUT

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md).
