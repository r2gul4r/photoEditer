# Reference Assets

This folder is for local photo-correction reference data. Real photos and RAW files are ignored by git.

Folder layout:

- `raw/`: RAW originals such as DNG, ARW, CR2, CR3, NEF, ORF, RAF, RW2.
- `jpeg/`: source JPEG/PNG/TIFF examples or exported previews.
- `edits/`: before/after pairs and rendered comparison files.
- `presets/`: XMP, JSON preset exports, or known slider settings.
- `presets/source_registry.json`: allow/unknown/deny registry for public and YouTube-linked Lightroom preset analysis sources.
- `presets/profiles/`: committed low-dimensional Lightroom preset-derived style profiles.
- `presets/tmp/`: ignored temporary archives or originals during ingest only. Originals are deleted after analysis.
- `manifests/`: metadata files that describe reference examples.
- `luts/source_registry.json`: allow/unknown/deny registry for LUT ingest sources.
- `luts/profiles/`: committed non-invertible LUT-derived style profiles for AI correction priors.
- `luts/tmp/`: temporary `.cube` originals during ingest only. Originals are deleted after analysis.

Keep private photos local. Commit only templates, notes, and non-sensitive manifests.
Do not commit third-party LUT originals. Commit only source metadata and low-dimensional style profiles.
Do not commit third-party Lightroom preset originals. Commit only source metadata and low-dimensional preset style priors.
Before public release, review `docs/THIRD_PARTY_DATA_POLICY.md` and keep `unknown` sources out of shipped derived profile data.

Suggested flow:

1. Put original files in `raw/` or `jpeg/`.
2. Put final/reference edits in `edits/`.
3. Store known sliders or XMP/JSON data in `presets/`.
4. Add a manifest entry linking the files and describing the target look.
5. Import `.cube` LUTs through the backend LUT importer when you want derived style data.
