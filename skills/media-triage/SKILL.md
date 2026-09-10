---
name: media-triage
description: Triage photo and video folders keeping only worth-keeping media. Use when the user wants to deduplicate images, remove blurry or near-duplicate photos, or organize a media folder into selected and discarded sets.
---

# Media Triage

Separate good photos/videos from duplicates, near-duplicates, and low-quality shots — without ever deleting originals.

## Workflow

Follow these phases in order. The flow is fully automatic: do not ask for
confirmation before organizing. If the user later disagrees with any choice,
they just ask ("move X to _selecionadas/cenas") and you fix it — originals are
never touched, so corrections are trivial.

### 1. Inventory (read-only)

- List all files in the target folder: photos (`JPG`, `JPEG`, `PNG`, `HEIC`) and videos (`MOV`, `MP4`).
- Compute `sha256` for exact duplicates.
- Record size, resolution, and dates.

### 2. Automated pre-analysis

Run the bundled script (install deps first if missing):

```bash
pip install -r scripts/requirements.txt
python3 scripts/triagem.py "/path/to/media/folder"
```

The script outputs `_tmp_metricas.csv` plus candidate groups:

- **Exact duplicates:** identical `sha256`.
- **Near-duplicates:** perceptual-hash (`pHash`) distance ≤ 12, grouped by connected components.
- **Sharpness signals (suggestion only):** Laplacian variance + Tenengrad + SMD, always measured at longer side ≥ 1024px, normalized per group with noise penalty and Borda-count consensus (`pontos`, `rank_grupo`). Per-metric values are in the CSV for auditing. No single gradient-energy metric is trustworthy alone — full-res Laplacian rewards noise.
- **Brightness:** histogram mean (context only).
- **Videos:** extract 3 frames each for visual review (visualization only).

Explicit rule: thumbnails ≤ 512px are for visualization only, never the decider.

### 3. Visual review (you decide — metrics suggest, human decides)

Open every candidate group and pick the keeper. Read at most ~10 images per
message, in sequential turns — some free-tier providers cap images per request,
and pagination avoids hard errors at almost no extra time cost. If the model
imposes no such limit, larger batches are fine.

Perceived quality in people photos is face/expression (open eyes, looking at
the camera, smile), not global texture — a photo can lead every sharpness
metric and still lose to a better expression. Apply this veto list with
precedence over ANY sharpness ranking, and record the veto reason in the CSV
`veto` column:

- Closed eyes, gaze away from the camera, hidden face.
- Moving intruder at the edge / cut-off person.

Other rules:

- Prefer sharper focus, open eyes, genuine smiles, clean framing, no intruders at the edges.
- Preserve meaningful variations (e.g. trio photo vs. group-of-six photo, different products on a shelf) — the user wants good variations kept.
- Unique scenes are always kept.

Scene check (greedy pHash grouping can merge distinct scenes): if a group
contains 2+ distinct scenes (e.g. solo under the arch vs. duo on the track),
elect one keeper PER SCENE. If two groups contain the same scene, keep only
the best across them and document the link in the CSV `motivo`.

### 4. Organize immediately (copy only, no confirmation round)

Classify every keeper into exactly one subject bucket, and every discard into
exactly one reason bucket. Create any subfolder below **only if it has ≥1
file** — never empty folders:

- `_selecionadas/cenas/` — photos or videos with people and/or environment (the default bucket; videos are scenes in motion).
- `_selecionadas/objetos/` — isolated thing with no person and no scene: close-up, single item, product, ad still.
- `_selecionadas/prints/` — screenshots, screen photos, invites, and digital art.
- `_descartadas/duplicadas/` — byte-identical or UI-duplicated versions.
- `_descartadas/similares/` — near-duplicates where a better keeper exists.
- `_descartadas/baixa_qualidade/` — blurry, dark, or unusably cropped shots.
- `relatorio_triagem.csv` — columns `arquivo,decisao,motivo,categoria,veto` (`cenas`/`objetos`/`prints`, empty for discarded), one row per original file.

Rules:

- **Copy** (never move, never delete originals).
- Verify afterwards: `selecionadas + descartadas == total`, and spot-check that copies match originals.
- Clean up temp files (`_tmp_*`).
- Post-execution swaps: if the user later asks (`move X para _selecionadas/cenas`, or the reverse), do it and update the CSV.

## Edge cases

- Large folders (500+ files): process in batches and summarize per group to save context.
- HEIC without support / corrupt video: log as `img-erro` in the CSV and **keep** it (safe default).
- Missing `ffmpeg`: it is resolved via `imageio-ffmpeg`; if unavailable, note videos as `sem-preview` and still keep them.
