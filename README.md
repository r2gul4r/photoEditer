<p align="right">
  <a href="README.ko.md">한국어</a>
</p>

# photoEditer

photoEditer, also known as TonePilot Local, is a RAW-first local photo correction recommendation tool built with Codex. It is designed for real photos you took, not AI-generated images.

The intended workflow is Lightroom-like: start from a RAW file whenever possible, analyze the original capture, find technical weaknesses, give objective feedback, interpret your desired mood, recommend correction values, preview the result, then export the corrected image as JPEG or PNG.

Core flow:

```text
RAW photo -> image analysis -> style target -> histogram-aware candidates -> preview -> JPEG/PNG export
```

## What It Does

- Imports RAW files when `rawpy` is available
- Supports JPEG, PNG, and TIFF as fallback/import convenience formats
- Extracts available metadata
- Calculates luma, RGB, and saturation histograms
- Detects risks such as highlight clipping, crushed shadows, low contrast, over-saturation, and color cast
- Interprets Korean or English style prompts
- Generates three correction candidates: Natural, Style, and Bold
- Renders preview images locally
- Exports rendered correction results as JPEG or PNG
- Exports selected correction values as JSON

## What It Is Not

- It is not a cloud AI photo editor
- It does not generate anime or synthetic images
- It is not a full Lightroom replacement yet, but it is designed around a similar RAW-to-output workflow
- It does not require accounts, payments, or cloud APIs

## Tech Stack

- Frontend: Vite, React, TypeScript, Tailwind CSS, Recharts
- Backend: Python, FastAPI, Pydantic, NumPy, Pillow
- Optional: rawpy for RAW import, exifread, OpenCV
- Workspace: pnpm monorepo

## Local Setup

```powershell
corepack enable
pnpm install
```

If Corepack has permission issues on Windows:

```powershell
npx pnpm@10.14.0 install
```

## Run Backend

```powershell
cd apps/backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8765
```

Install optional RAW support with:

```powershell
pip install -e ".[dev,raw]"
```

## Run Frontend

In another terminal:

```powershell
pnpm --filter @tonepilot/desktop dev
```

Or run both from the repository root:

```powershell
pnpm dev
```

## Tests

```powershell
cd apps/backend
pytest
```

## API Overview

- `GET /health`: backend health check
- `POST /api/images/analyze`: upload and analyze an image
- `POST /api/recommend`: generate correction candidates from a style prompt
- `POST /api/preview`: render a preview from selected adjustments
- `GET /api/previews/{filename}`: serve generated previews
- `POST /api/export/preset-json`: export selected correction values as JSON
- `POST /api/export/rendered-image`: export the corrected result as JPEG or PNG

See [docs/API.md](docs/API.md) for details.

## How Image Analysis Works

For RAW files, the backend uses optional `rawpy` to read RAW sensor data and produce a renderable RGB working image. It keeps RAW-specific stats such as black level, white level, mean, p99, and histogram data, then runs the same RGB/luma/saturation analysis used for JPEG, PNG, and TIFF imports.

## How Recommendations Work

The MVP uses rule-based style interpretation. For example, a prompt such as `시원한 일본 여름 느낌` maps to `cool_japanese_summer`. The recommendation engine combines that style target with histogram analysis and risk flags to produce Natural, Style, and Bold candidates.

## Current Limitations

- Preview rendering is approximate and does not match Lightroom exactly
- RAW support depends on optional `rawpy` and is still an early pipeline
- CLIP, aesthetic scoring, segmentation, and ONNX model integrations are future modules only
- Export currently supports rendered JPEG/PNG and correction JSON, not XMP or LUT

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md).
