"""Triagem de fotos e vídeos: inventário + similaridade + qualidade.

Uso:
    pip install -r scripts/requirements.txt
    python3 scripts/triagem.py "/caminho/da/pasta"

Saídas na pasta analisada:
    _tmp_metricas.csv  — métricas por arquivo (tipo, resolução, brilho, phash,
                         laplaciano, tenengrad, smd, ruido, pontos, rank_grupo, veto)
    _tmp_frames/       — 3 frames por vídeo (só para visualização)

Regras de medição (aprendidas no caso G7):
- Nitidez é SEMPRE medida com lado maior >= 1024px (só reduz, nunca amplia).
  Thumbnails <= 512px servem só para visualização, jamais como decisor.
- O ranking por grupo é SUGESTÃO (consenso de 3 métricas com penalidade de
  ruído). A decisão final é visual e os vetos têm precedência (ver SKILL.md).

O script NÃO move nem apaga nada.
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


MIN_SIDE_FOR_SHARPNESS = 1024


def sharpness_features(img):
    """Laplaciano + Tenengrad + SMD + ruído, sempre em lado maior >= 1024px.

    Retorna dict com valores brutos ou None se OpenCV ausente. Nenhuma
    métrica isolada de energia de gradiente é confiável sozinha (o Laplaciano
    full-res premia ruído) — por isso o ranking usa consenso das três com
    penalidade de ruído (ver rank_group).
    """
    if cv2 is None:
        return None
    g = img.convert("L")
    w, h = g.size
    m = max(w, h)
    if m > MIN_SIDE_FOR_SHARPNESS:
        s = MIN_SIDE_FOR_SHARPNESS / m
        g = g.resize((max(1, round(w * s)), max(1, round(h * s))))
    u8 = np.asarray(g)
    a = u8.astype(np.float64)
    lap = float(cv2.Laplacian(a, cv2.CV_64F).var())
    sx = cv2.Sobel(a, cv2.CV_64F, 1, 0, ksize=3)
    sy = cv2.Sobel(a, cv2.CV_64F, 0, 1, ksize=3)
    ten = float(np.mean(sx * sx + sy * sy))
    dx = np.abs(a[:, 1:] - a[:, :-1])
    dy = np.abs(a[1:, :] - a[:-1, :])
    smd = float(dx.mean() + dy.mean())
    med = cv2.medianBlur(u8, 3).astype(np.float64)
    noise = float(np.mean(np.abs(a - med)))
    return {"laplaciano": lap, "tenengrad": ten, "smd": smd, "ruido": noise}


def rank_group(members):
    """Consenso por contagem de Borda com penalidade de ruído.

    members: lista de dicts com laplaciano/tenengrad/smd/ruido. Cada métrica é
    normalizada min-max dentro do grupo; o valor penalizado é
    norma / (1 + ruido_norm). Por métrica, o melhor leva N pontos, o 2º N-1...
    A soma é `pontos`; `rank_grupo` é a posição por pontos (1 = melhor).
    Mutates members in place. Grupo unitário: pontos 0.0, rank 1.
    """
    n = len(members)
    if n == 0:
        return
    if n == 1:
        members[0]["pontos"] = 0.0
        members[0]["rank_grupo"] = 1
        return
    metrics = ("laplaciano", "tenengrad", "smd")
    rmin = {k: min(m[k] for m in members) for k in metrics + ("ruido",)}
    rmax = {k: max(m[k] for m in members) for k in metrics + ("ruido",)}

    def norm(v, k):
        return (v - rmin[k]) / (rmax[k] - rmin[k]) if rmax[k] > rmin[k] else 0.5

    for m in members:
        m["_pen"] = {k: norm(m[k], k) / (1.0 + norm(m["ruido"], "ruido")) for k in metrics}
        m["pontos"] = 0.0
    for k in metrics:
        for pos, m in enumerate(sorted(members, key=lambda d: d["_pen"][k], reverse=True)):
            m["pontos"] += n - pos
    for rank, m in enumerate(sorted(members, key=lambda d: d["pontos"], reverse=True), 1):
        m["pontos"] = round(m["pontos"], 1)
        m["rank_grupo"] = rank
        del m["_pen"]


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
                         "largura": "", "altura": "", "brilho": "", "phash": "",
                         "laplaciano": "", "tenengrad": "", "smd": "", "ruido": "",
                         "pontos": "", "rank_grupo": "", "veto": ""})
        elif ext in PHOTO_EXTS:
            try:
                im = Image.open(p)
                im.load()
            except Exception as e:
                print(f"[erro] {f}: {e}")
                rows.append({"arquivo": f, "tipo": "img-erro", "sha256": sha256_of(p),
                             "largura": "", "altura": "", "brilho": "", "phash": "",
                             "laplaciano": "", "tenengrad": "", "smd": "", "ruido": "",
                             "pontos": "", "rank_grupo": "", "veto": ""})
                continue
            w, h = im.size
            feat = sharpness_features(im)
            row = {"arquivo": f, "tipo": "foto", "sha256": sha256_of(p),
                   "largura": w, "altura": h, "brilho": brightness(im),
                   "phash": phash_of(im), "veto": ""}
            if feat is None:
                row.update({k: -1.0 for k in ("laplaciano", "tenengrad", "smd", "ruido")})
                row.update({"pontos": "", "rank_grupo": ""})
            else:
                row.update({k: round(feat[k], 1) for k in ("laplaciano", "tenengrad", "smd", "ruido")})
                row.update({"pontos": "", "rank_grupo": ""})
                row["_feat"] = feat
            rows.append(row)
            print(f"[foto] {f} {w}x{h}")
        else:
            print(f"[ignorado] {f}")

    photos = [r for r in rows if r["phash"]]
    pairs = []
    for i in range(len(photos)):
        for j in range(i + 1, len(photos)):
            d = hdist(photos[i]["phash"], photos[j]["phash"])
            if d <= 12:
                pairs.append((photos[i]["arquivo"], photos[j]["arquivo"], d))
    print("\n=== PARES MUITO PARECIDOS (phash dist<=12) ===")
    if pairs:
        for a, b, d in pairs:
            print(f"dist {d}: {a} <-> {b}")
    else:
        print("nenhum")

    # Grupos por componentes conectados dos pares (single-link). ATENÇÃO: o
    # encadeamento pode fundir cenas distintas no mesmo grupo — a checagem de
    # cena é feita na revisão visual (ver SKILL.md), nunca só pelo algoritmo.
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for r in photos:
        find(r["arquivo"])
    for a, b, _ in pairs:
        union(a, b)
    groups = {}
    for r in photos:
        groups.setdefault(find(r["arquivo"]), []).append(r)
    for members in groups.values():
        rank_group([m for m in members if "_feat" in m])

    print("\n=== RANKING POR GRUPO (sugestão — humano decide, vetos prevalecem) ===")
    for gid, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        print(f"-- grupo {gid} ({len(members)} fotos) --")
        for m in sorted(members, key=lambda d: (d.get("rank_grupo") or 999)):
            print(f"  rank {m.get('rank_grupo')}: {m['arquivo']} "
                  f"pontos={m.get('pontos')} lap={m.get('laplaciano')} "
                  f"ten={m.get('tenengrad')} smd={m.get('smd')} ruido={m.get('ruido')}")

    for r in rows:
        r.pop("_feat", None)
    csv_path = os.path.join(folder, "_tmp_metricas.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["arquivo", "tipo", "sha256", "largura",
                                           "altura", "brilho", "phash", "laplaciano",
                                           "tenengrad", "smd", "ruido", "pontos",
                                           "rank_grupo", "veto"])
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

    # (pares e grupos impressos acima, junto do ranking)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python3 scripts/triagem.py \"/caminho/da/pasta\"")
    main(sys.argv[1])
