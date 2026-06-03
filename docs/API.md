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

`metadata` includes normalized summary fields plus `fields`, a list of every readable metadata tag extracted by Pillow and optional `exifread`:

```json
{
  "metadata": {
    "camera": "Panasonic DC-S9",
    "lens": "LUMIX S 20-60/F3.5-5.6",
    "iso": 100,
    "shutter": "1/50",
    "aperture": "11",
    "focal_length": "20",
    "created_at": "2025:10:18 12:15:11",
    "fields": [
      {
        "key": "EXIF ExposureTime",
        "value": "1/50",
        "source": "exifread"
      }
    ]
  }
}
```

`source_preview_url` is a browser-displayable JPEG generated from the decoded source. The frontend uses it so RAW files can be shown even though browsers cannot render RAW object URLs directly.

For RAW uploads, `rawpy` is required. If RAW support is unavailable or the file cannot be decoded, the API returns `422` with structured `detail`:

```json
{
  "detail": {
    "ok": false,
    "code": "rawpy_missing",
    "error": "rawpy is not installed. RAW analysis is disabled.",
    "install_hint": "Install optional backend dependencies with: pip install -e \"apps/backend[raw]\""
  }
}
```

## GET /api/raw/status

Returns RAW dependency availability without opening a RAW file.

```json
{
  "available": false,
  "dependency": "rawpy",
  "version": null,
  "message": "RAW import is disabled because rawpy is not installed.",
  "install_hint": "Install optional backend dependencies with: pip install -e \"apps/backend[raw]\""
}
```

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

## GET /api/references

Returns local reference manifests from `reference/manifests/*.json`.

```json
{
  "root": "reference",
  "count": 1,
  "items": [
    {
      "id": "example-reference-001",
      "manifest_path": "manifests/example.json",
      "source": {
        "path": "raw/example.dng",
        "format": "raw",
        "camera": null,
        "lens": null,
        "iso": null,
        "exists": false
      },
      "targets": [],
      "preset": null,
      "license": null
    }
  ]
}
```
