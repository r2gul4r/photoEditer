# Local AI Training Options For Photo Correction

Short answer: yes, local AI for photo correction is possible, but full Lightroom-quality learning needs a staged approach. The practical path is not to train a giant model first. Start with local scoring, retrieval, and lightweight regression from reference edits.

## Best Practical Path

1. Reference library
   - Store before/after pairs, RAW/JPEG source, target style tags, and known adjustment values.
   - Use this data for retrieval and evaluation before training.

2. Local image/style embeddings
   - Use CLIP/SigLIP-style image embeddings to find similar reference photos.
   - This can run locally through ONNX Runtime, PyTorch, or a small Hugging Face model.
   - It does not directly edit photos, but it helps choose the right reference look.

3. Lightweight adjustment predictor
   - Train a small regressor that maps image stats + prompt/style embedding to slider values.
   - Inputs: histogram stats, metadata, exposure/color metrics, retrieved reference style.
   - Outputs: exposure, contrast, highlights, shadows, whites, blacks, temperature, tint, vibrance, saturation, HSL.
   - This is realistic on a local machine.

4. Local aesthetic/technical scorer
   - Score candidates for clipping, skin tone drift, contrast, color cast, and style match.
   - Use it to rank multiple generated candidates.

5. Optional segmentation
   - Add local segmentation for sky/skin/green/water masks.
   - Candidates: Segment Anything variants, BiRefNet, MODNet, or smaller ONNX segmentation models.

## Heavy Training To Avoid Initially

Avoid starting with diffusion fine-tuning or full RAW-to-final neural rendering. It is expensive, hard to control, and unnecessary for the first useful version of this app.

## Candidate Local Runtimes

- ONNX Runtime: best default for shipping small local inference models.
- PyTorch: best for experimentation and training.
- OpenCV: useful for deterministic image metrics and classical vision.
- scikit-learn / LightGBM: useful for lightweight slider regression.
- Ollama / llama.cpp: useful for local text reasoning, but not image correction by itself.
- CLIP/SigLIP models: useful for image-text style matching.

## Data Needed

Use `reference/` for local assets:

- RAW originals
- exported before/after JPEGs
- XMP/preset JSON when available
- style labels
- camera/lens metadata
- notes about desired look and failure cases

Do not commit private reference photos. Keep only README/manifests/templates in git.

## MVP Recommendation

For the current MVP:

- Use Codex app-server to generate correction candidates from image analysis and style prompt.
- Keep rule-based fallback.
- Add reference-data storage now.
- Add retrieval/scoring later after enough reference examples exist.

This gives a useful AI correction workflow now while keeping a clean path to local learning later.
