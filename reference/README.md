# Reference Assets

This folder is for local photo-correction reference data. Real photos and RAW files are ignored by git.

Folder layout:

- `raw/`: RAW originals such as DNG, ARW, CR2, CR3, NEF, ORF, RAF, RW2.
- `jpeg/`: source JPEG/PNG/TIFF examples or exported previews.
- `edits/`: before/after pairs and rendered comparison files.
- `presets/`: XMP, JSON preset exports, or known slider settings.
- `manifests/`: metadata files that describe reference examples.

Keep private photos local. Commit only templates, notes, and non-sensitive manifests.

Suggested flow:

1. Put original files in `raw/` or `jpeg/`.
2. Put final/reference edits in `edits/`.
3. Store known sliders or XMP/JSON data in `presets/`.
4. Add a manifest entry linking the files and describing the target look.
