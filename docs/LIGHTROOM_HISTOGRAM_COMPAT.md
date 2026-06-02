# Lightroom Histogram Compatibility Notes

Target checked locally:

- `C:\Program Files\Adobe\Adobe Lightroom Classic\Lightroom.exe`
- Product version: `14.4 (202506051112-5918896a)`
- File version: `14.4`

## Boundary

Do not decompile, unpack, patch, or extract proprietary Lightroom binaries or assets. Compatibility work here is based on Adobe's public documentation and black-box comparison with user-owned images.

## Observable Contract

For SDR editing, Lightroom Classic's histogram behavior is documented as:

- Left side is 0% luminance and right side is 100% luminance.
- The histogram is shown as overlapping red, green, and blue channel layers.
- Overlap colors are meaningful: all three overlap as gray, two-channel overlaps as yellow, magenta, or cyan.
- RGB pixel readouts under the histogram are exposed as `0..255` values in SDR.
- Shadow clipping is indicated on the left, highlight clipping on the right.
- A white clipping indicator means all channels clip; a colored indicator means one or two channels clip.

HDR mode is a different target: Lightroom splits the histogram into SDR and HDR regions, uses f-stop style readouts for HDR-range values, and extends tone curve values beyond the SDR `0..255` range. The current app should treat that as a later mode, not mix it into the SDR histogram.

Sources:

- Adobe Lightroom Classic tone/color and histogram documentation: https://helpx.adobe.com/uk/lightroom-classic/help/image-tone-color.html
- Adobe Lightroom Classic HDR histogram documentation: https://helpx.adobe.com/lightroom-classic/help/hdr-output.html

## App Contract

For this app's SDR histogram:

- Use exactly 256 bins, indexed `0..255`.
- Quantize display RGB and luma values with `round(value * 255)` after clipping to `[0, 1]`.
- Keep luma/RGB/saturation analysis fields for recommendation logic.
- Add `display_histogram` for UI-compatible rendering and clipping readouts.
- Normalize the rendered graph against one shared `max_count`, not per-channel maxima.
- Render bins directly without smoothing, spline interpolation, or monotone curves.
- Track per-channel black/white clipping and aggregate shadow/highlight clipping when any RGB channel hits `0` or `255`.

## Black-Box Comparison Set

Use these files for future Lightroom side-by-side checks:

- 256-step grayscale ramp.
- 256-step red, green, and blue ramps.
- Four-patch image: pure black, pure white, pure RGB primaries, and neutral gray.
- Low-contrast mid-gray image.
- Image with isolated one-channel clipping.

The comparison target is not Lightroom's internal source code. It is the visible histogram shape, clipping indicator state, and SDR RGB readout behavior.
