# Third-Party Data Policy

TonePilot Local may analyze public or user-provided LUT and Lightroom preset files to build low-dimensional style priors.

## What Is Stored

- Source registry entries with URL, source status, and license notes.
- Non-invertible derived profile JSON such as tone, color, HSL, tag, and risk-summary features.
- Aggregated style indexes used by the recommendation engine.

## What Is Not Stored

- Original `.cube`, `.xmp`, `.lrtemplate`, ZIP, RAW, or creator asset files from third parties.
- Reconstructable LUT or preset tables intended to replace the original download.
- Private user photos or local reference originals.

## Release Rule

Before publishing a release, keep only sources that satisfy all of these:

- The source is marked `allow` in the relevant `source_registry.json`.
- The registry includes a license or usage note.
- The committed artifact is a derived profile or aggregate index, not the original asset.
- The README and registry make attribution and non-redistribution clear.

Sources marked `unknown` are allowed to stay in the registry as candidates, but their originals and derived profiles should not be shipped in a public release until reviewed.

## Legal Caveat

Derived, non-invertible analysis data lowers redistribution risk, but it does not automatically override source licenses, creator terms, non-commercial restrictions, database rights, or platform terms. Treat this document as project policy, not legal advice.
