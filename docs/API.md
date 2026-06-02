# API

Base URL: `http://127.0.0.1:8765`

## GET /health

```json
{
  "ok": true,
  "service": "tonepilot-backend"
}
```

## POST /api/images/analyze

Multipart field: `file`

Returns image identity, metadata, luma/RGB/saturation histograms, and risk flags.

## POST /api/recommend

```json
{
  "image_id": "uuid",
  "style_prompt": "시원한 일본 여름 느낌",
  "strength": 0.7
}
```

Returns style interpretation and three candidates: `natural`, `style`, `bold`.

## POST /api/preview

```json
{
  "image_id": "uuid",
  "candidate_id": "natural",
  "adjustments": {}
}
```

Returns:

```json
{
  "preview_url": "/api/previews/{image_id}-natural.jpg"
}
```

## POST /api/export/preset-json

Returns selected correction values as downloadable JSON.

## POST /api/export/rendered-image

Exports the selected correction result as JPEG or PNG.

```json
{
  "image_id": "uuid",
  "candidate_id": "natural",
  "adjustments": {},
  "format": "jpeg"
}
```

Returns a downloadable image file. Supported formats: `jpeg`, `png`.
