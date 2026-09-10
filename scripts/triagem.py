"""Triagem de fotos e vídeos: inventário + similaridade + qualidade.

Uso:
    pip install -r scripts/requirements.txt
    python3 scripts/triagem.py "/caminho/da/pasta"

Saídas na pasta analisada:
    _tmp_metricas.csv  — métricas por arquivo (tipo, resolução, blur, brilho, phash)
    _tmp_frames/       — 3 frames por vídeo (para revisão visual)

O script NÃO move nem apaga nada. A decisão final é visual (ver SKILL.md).
"""

import csv
import hashlib
import os
import subprocess
import sys

PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".heic")
VIDEO_EXTS = (".mov", ".mp4")

try:
    from PIL import Image
except ImportError:
    sys.exit("Falta Pillow. Rode: pip install -r scripts/requirements.txt")

try:
    import pillow_heif  # noqa: F401

    pillow_heif.register_heif_opener()
except ImportError:
    pass  # HEIC pode falhar; arquivos com erro vão para img-erro

try:
    import imagehash  # type: ignore
except ImportError:
    imagehash = None

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except ImportError:
    cv2 = None


def sha256_of(path, chunk=1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def blur_score(img):
    """Variância do Laplaciano: maior = mais nítida. -1 se OpenCV ausente."""
    if cv2 is None:
        return -1.0
    g = np.array(img.convert("L").resize((512, 512)))
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


def brightness(img):
    g = np.array(img.convert("L").resize((256, 256))) if cv2 else None
    if g is None:
        try:
            import statistics

            px = list(img.convert("L").resize((256, 256)).getdata())
            return round(statistics.mean(px), 1)
        except Exception:
            return -1.0
    return round(float(g.mean()), 1)


def phash_of(img):
    if imagehash is None:
        return ""
    try:
        return str(imagehash.phash(img))
    except Exception:
        return ""


def hdist(a, b):
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except Exception:
        return 999


def extract_frames(video_path, out_dir):
    """Extrai 3 frames (início/meio/fim aproximados) via imageio-ffmpeg."""
    try:
        import imageio_ffmpeg  # type: ignore

        ff = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        print(f"  [aviso] imageio-ffmpeg ausente, sem preview de {os.path.basename(video_path)}")
        return []
    base = os.path.splitext(os.path.basename(video_path))[0]
    outs = []
    for t in (1, 5, 15):
        dst = os.path.join(out_dir, f"{base}_t{t:02d}s.jpg")
        subprocess.run(
            [ff, "-y", "-ss", str(t), "-i", video_path, "-frames:v", "1", "-q:v", "3", dst],
            capture_output=True,
        )
        if os.path.exists(dst):
            outs.append(dst)
    return outs


def main(folder):
    if not os.path.isdir(folder):
        sys.exit(f"Pasta não encontrada: {folder}")
    frames_dir = os.path.join(folder, "_tmp_frames")
    os.makedirs(frames_dir, exist_ok=True)

    files = sorted(
        f
        for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
        and not f.startswith(("_tmp", "_selecionadas", "_descartadas", "relatorio_"))
    )

    rows = []
    for f in files:
        p = os.path.join(folder, f)
        ext = os.path.splitext(f)[1].lower()
        if ext in VIDEO_EXTS:
            outs = extract_frames(p, frames_dir)
            print(f"[video] {f} ({os.path.getsize(p) // 1024 // 1024}MB) frames={len(outs)}")
            rows.append({"arquivo": f, "tipo": "video", "sha256": sha256_of(p),
                         "largura": "", "altura": "", "blur": "", "brilho": "", "phash": ""})
        elif ext in PHOTO_EXTS:
            try:
                im = Image.open(p)
                im.load()
            except Exception as e:
                print(f"[erro] {f}: {e}")
                rows.append({"arquivo": f, "tipo": "img-erro", "sha256": sha256_of(p),
                             "largura": "", "altura": "", "blur": "", "brilho": "", "phash": ""})
                continue
            w, h = im.size
            rows.append({"arquivo": f, "tipo": "foto", "sha256": sha256_of(p),
                         "largura": w, "altura": h,
                         "blur": round(blur_score(im), 1), "brilho": brightness(im),
                         "phash": phash_of(im)})
            print(f"[foto] {f} {w}x{h}")
        else:
            print(f"[ignorado] {f}")

    csv_path = os.path.join(folder, "_tmp_metricas.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["arquivo", "tipo", "sha256", "largura",
                                           "altura", "blur", "brilho", "phash"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nMétricas salvas em {csv_path}")

    seen, dups = {}, []
    for r in rows:
        if r["tipo"] not in ("foto", "video"):
            continue
        if r["sha256"] in seen:
            dups.append((r["arquivo"], seen[r["sha256"]]))
        else:
            seen[r["sha256"]] = r["arquivo"]
    print("\n=== DUPLICADAS EXATAS (sha256) ===")
    print(dups if dups else "nenhuma")

    photos = [r for r in rows if r["phash"]]
    print("\n=== PARES MUITO PARECIDOS (phash dist<=12) ===")
    found = False
    for i in range(len(photos)):
        for j in range(i + 1, len(photos)):
            d = hdist(photos[i]["phash"], photos[j]["phash"])
            if d <= 12:
                found = True
                print(f"dist {d}: {photos[i]['arquivo']} <-> {photos[j]['arquivo']}")
    if not found:
        print("nenhum")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python3 scripts/triagem.py \"/caminho/da/pasta\"")
    main(sys.argv[1])
