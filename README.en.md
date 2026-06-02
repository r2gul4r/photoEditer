# photoEditer

[한국어로 보기](README.ko.md)

photoEditer, also known as TonePilot Local, is a local photo correction recommendation tool built with Codex. It is designed for real photos you took, not AI-generated images.

The app analyzes an imported photo, finds technical weaknesses, gives objective feedback, interprets your desired mood, and recommends correction values with an actual before/after preview.

Core flow:

```text
Photo -> image analysis -> style target -> histogram-aware candidates -> preview -> feedback
```

## What It Does

- Imports local JPEG, PNG, and TIFF images
- Extracts available metadata
- Calculates luma, RGB, and saturation histograms
- Detects risks such as highlight clipping, crushed shadows, low contrast, over-saturation, and color cast
- Interprets Korean or English style prompts
- Generates three correction candidates: Natural, Style, and Bold
- Renders preview images locally
- Exports selected correction values as JSON

## What It Is Not

- It is not a cloud AI photo editor
- It does not generate anime or synthetic images
- It does not replace Lightroom or professional color grading tools yet
- It does not require accounts, payments, or cloud APIs

## Tech Stack

- Frontend: Vite, React, TypeScript, Tailwind CSS, Recharts
- Backend: Python, FastAPI, Pydantic, NumPy, Pillow
- Optional: rawpy, exifread, OpenCV
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

See [docs/API.md](docs/API.md) for details.

## How Image Analysis Works

The backend converts each image to RGB float data in `[0, 1]`, then calculates luma, RGB channel, and HSV saturation statistics. It reports percentiles, 256-bin histograms, and simple risk flags for common correction problems.

## How Recommendations Work

The MVP uses rule-based style interpretation. For example, a prompt such as `시원한 일본 여름 느낌` maps to `cool_japanese_summer`. The recommendation engine combines that style target with histogram analysis and risk flags to produce Natural, Style, and Bold candidates.

## Current Limitations

- Preview rendering is approximate and does not match Lightroom exactly
- RAW support is scaffolded and depends on optional `rawpy`
- CLIP, aesthetic scoring, segmentation, and ONNX model integrations are future modules only
- Export currently supports JSON, not XMP or LUT

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md).

