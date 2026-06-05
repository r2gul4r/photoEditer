# TonePilot Local Design QA

Date: 2026-06-05

## Source

- Target direction: `docs/design/tonepilot-lightroom-inspired-mockup.png`
- Current implementation capture: `output/playwright/photopixer-final-desktop.png`
- Mobile implementation capture: `output/playwright/photopixer-final-mobile.png`

## Checks

- Desktop layout keeps the requested editor structure: top app bar, left module rail, central image stage, lower candidate strip, and right correction inspector.
- The active editing path is visually emphasized with blue accents, compact controls, thumbnail candidates, rating tools, and a before/after split handle.
- Placeholder feature areas that are not implemented yet are visible but disabled, so they do not imply working behavior.
- The empty library state no longer overlays instructional text over the drop area while idle.
- Responsive layout keeps the rail, canvas, candidate strip, and inspector readable on narrow screens.
- Browser console was checked after reload with no frontend errors or warnings.

## Intentional Differences

- The screenshot photo content is not baked into the app; the center stage uses the user's loaded local photo.
- Window chrome controls are visual-only in the web prototype and remain disabled.
- Advanced tabs such as masks, export, and tone curve are shown as planned surfaces until real behavior exists.
