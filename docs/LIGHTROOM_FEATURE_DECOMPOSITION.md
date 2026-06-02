# Lightroom Feature Decomposition

Scope: Lightroom Classic photo-editing behavior only. Account login, cloud sync, stock/library services, marketplace, and licensing flows are out of scope.

Local target checked:

- `C:\Program Files\Adobe\Adobe Lightroom Classic\Lightroom.exe`
- Product version: `14.4 (202506051112-5918896a)`

## Core Model

Lightroom is not primarily a destructive bitmap editor. Its core model is:

```text
source photo -> catalog record -> non-destructive edit instructions -> preview render -> export render
```

Adobe documents Develop edits as instructions applied in memory, with the original image left unmodified. For this app, the equivalent should be:

- Store original image separately from edits.
- Store adjustments as serializable preset/state data.
- Re-render preview/export from original + adjustment state.
- Avoid stacking edits into already-rendered previews.

## Import And Catalog

Lightroom import has three separate concerns:

- Source selection: card, folder, tethered camera, or existing disk files.
- File handling: copy, copy as DNG, add/move where applicable, duplicate detection.
- Apply during import: metadata, presets, and raw defaults.

For `photoEditer`, the MVP version should be:

- Keep direct file upload/open as the source.
- Save a local original record.
- Add duplicate detection by file hash later.
- Add import-time preset/raw-default application later.

## RAW Defaults And Profiles

Lightroom applies a starting interpretation before sliders matter:

- Raw defaults can be Adobe default, camera settings, or a preset.
- Defaults can vary by camera model and even ISO-adaptive preset rules.
- Profiles are a rendering foundation and do not overwrite slider values.

For this app:

- Treat RAW conversion, camera profile, white balance, and base tone curve as a first pipeline stage.
- Keep profile/base-render settings separate from user slider adjustments.
- Do not compare slider values to Lightroom unless the same profile/default assumptions are known.

## Develop Pipeline

Lightroom's Develop workflow is layered:

```text
profile/base render
-> white balance
-> global tone and presence
-> tone curve
-> color mixer / HSL
-> color grading
-> detail: sharpening/noise
-> lens/geometry corrections
-> crop/retouch/effects
-> local masks
-> soft proof / export transform
```

Implementation implication:

- The app should model adjustments as ordered operations, not independent UI values.
- Preview and export should share the same renderer path.
- Histogram should be computed from the current rendered preview state, not only from the untouched original, once preview rendering becomes mature.

## Histogram And Readouts

Lightroom uses the histogram as both analysis and control surface:

- 0% luminance on the left, 100% on the right.
- Overlapping RGB channel layers.
- RGB readouts under the histogram in SDR use `0..255`.
- Clipping indicators show shadow/highlight clipping and distinguish full-channel vs partial-channel clipping by color.

For this app:

- Use a separate `display_histogram` API model for graph-compatible 256-bin data.
- Render bins directly without smoothing.
- Track clipping per channel and aggregate clipping.
- Treat HDR histogram behavior as a separate future mode.

## Local Editing And Masks

Lightroom separates global adjustments from local corrections:

- Manual masks: brush, linear gradient, radial gradient, range masks.
- Automatic masks: subject, sky, background, landscape, objects, people.
- Mask adjustments remain non-destructive.

For this app:

- Start with global-only adjustments.
- Add masks as `{mask_geometry | mask_bitmap | mask_source} + local_adjustments`.
- Keep mask evaluation separate from recommendation generation.
- Avoid promising AI object masks until there is a local segmentation model or explicit cloud dependency.

## Retouching

Lightroom retouching tools cover crop/straighten, spot removal, red-eye/pet-eye, remove/distraction tools, sensor dust, vignette, and grain.

For this app:

- Crop/straighten is low-risk and should come before export.
- Spot removal requires source/target patch representation.
- Generative/remove-style tools need separate policy and model decisions; they are not part of basic tonal compatibility.

## Sync, History, Presets

Lightroom stores edit states and lets users reuse them:

- Presets apply predefined Develop settings.
- History returns to earlier edit states.
- Snapshots store named states.
- Copy/sync applies selected adjustments to other photos.

For this app:

- Current `CorrectionAdjustments` is the preset/state core.
- Add named snapshots before complex history.
- Add batch sync only after state serialization is stable.

## Export

Lightroom export is the final render pass:

- It applies current edit instructions to the source.
- It maps color/profile/format/output constraints.
- HDR export behaves differently from SDR export.

For this app:

- Keep JPEG/PNG export as SDR for now.
- Add XMP/preset export separately from rendered image export.
- Do not claim Lightroom slider compatibility until XMP naming/ranges and renderer order are tested.

## Priority For photoEditer

1. Lock SDR histogram/readout behavior.
2. Make preview/export share one ordered adjustment pipeline.
3. Separate base RAW/profile/default state from user adjustments.
4. Add preset/snapshot state.
5. Add crop/straighten.
6. Add local masks.
7. Add advanced detail/lens/color management.
8. Add HDR only as a separate mode.

Sources:

- Adobe Develop module basics: https://helpx.adobe.com/lightroom-classic/help/applying-adjustments-develop-module-basic.html
- Adobe tone/color and histogram docs: https://helpx.adobe.com/uk/lightroom-classic/help/image-tone-color.html
- Adobe import workflow docs: https://helpx.adobe.com/in/lightroom-classic/help/importing-photos-lightroom-basic-workflow.html
- Adobe raw defaults docs: https://helpx.adobe.com/lightroom-classic/help/raw-defaults.html
- Adobe masking docs: https://helpx.adobe.com/in_hi/lightroom-classic/help/masking.html
- Adobe HDR histogram/export docs: https://helpx.adobe.com/lightroom-classic/help/hdr-output.html
