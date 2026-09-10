---
name: media-triage
description: Triage photo and video folders keeping only worth-keeping media. Use when the user wants to deduplicate images, remove blurry or near-duplicate photos, or organize a media folder into selected and discarded sets.
---

# Media Triage

Separate good photos/videos from duplicates, near-duplicates, and low-quality shots — without ever deleting originals.

## Workflow

Follow these phases in order. Keep user friction minimal: at most one confirmation round before organizing.

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
- **Near-duplicates:** perceptual-hash (`pHash`) distance ≤ 12.
- **Low quality signals:** resolution, Laplacian-variance blur score, brightness. Treat scores as hints, never as final verdicts.
- **Videos:** extract 3 frames each for visual review.

### 3. Visual review (you decide)

Open every candidate group and pick the keeper. Read at most ~10 images per
message, in sequential turns — some free-tier providers cap images per request,
and pagination avoids hard errors at almost no extra time cost. If the model
imposes no such limit, larger batches are fine.

- Prefer sharper focus, open eyes, genuine smiles, clean framing, no intruders at the edges.
- Preserve meaningful variations (e.g. trio photo vs. group-of-six photo, different products on a shelf) — the user wants good variations kept.
- Unique scenes are always kept.

### 4. One-shot confirmation (minimal friction)

Present a short list per group, one line each:

```text
manter IMG_2741.HEIC | descartar IMG_2740.HEIC (criança de cara fechada)
```

The user replies in the fastest way they prefer:

- a. `ok` → execute as proposed;
- b. `troca A por B no grupo N` → swap before copying;
- c. Post-execution fix → `move ARQ para _selecionadas` (or the reverse); update the CSV. Originals are never touched, so corrections are trivial.

### 5. Organize (copy only)

Classify every keeper into exactly one subject bucket, and every discard into
exactly one reason bucket. Create any subfolder below **only if it has ≥1
file** — never empty folders:

- `_selecionadas/cenas/` — photos or videos with people and/or environment (the default bucket; videos are scenes in motion).
- `_selecionadas/objetos/` — isolated thing with no person and no scene: close-up, single item, product, ad still.
- `_selecionadas/prints/` — screenshots, screen photos, invites, and digital art.
- `_descartadas/duplicadas/` — byte-identical or UI-duplicated versions.
- `_descartadas/similares/` — near-duplicates where a better keeper exists.
- `_descartadas/baixa_qualidade/` — blurry, dark, or unusably cropped shots.
- `relatorio_triagem.csv` — columns `arquivo,decisao,motivo,categoria` (`cenas`/`objetos`/`prints`, empty for discarded), one row per original file.

Rules:

- **Copy** (never move, never delete originals).
- Verify afterwards: `selecionadas + descartadas == total`, and spot-check that copies match originals.
- Clean up temp files (`_tmp_*`).

## Edge cases

- Large folders (500+ files): process in batches and summarize per group to save context.
- HEIC without support / corrupt video: log as `img-erro` in the CSV and **keep** it (safe default).
- Missing `ffmpeg`: it is resolved via `imageio-ffmpeg`; if unavailable, note videos as `sem-preview` and still keep them.
