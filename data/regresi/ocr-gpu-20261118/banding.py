"""Bandingkan cache CPU asli vs OCR ulang (cpu, gpu): kata dipasangkan menurut IoU kotak."""
import json, os, sys, difflib, glob
S = os.path.dirname(os.path.abspath(__file__))
CACHE = r"C:\sistem-pencarian-bps\data\ocr_cache"

def iou(a, b):
    ix = max(0, min(a["x1"], b["x1"]) - max(a["x0"], b["x0"]))
    iy = max(0, min(a["bottom"], b["bottom"]) - max(a["top"], b["top"]))
    i = ix * iy
    u = (a["x1"]-a["x0"])*(a["bottom"]-a["top"]) + (b["x1"]-b["x0"])*(b["bottom"]-b["top"]) - i
    return i / u if u else 0

def banding(A, B):
    pas, pakai = [], set()
    for a in A:
        best = max(((iou(a, b), j) for j, b in enumerate(B) if j not in pakai), default=(0, None))
        if best[0] >= 0.5:
            pakai.add(best[1]); pas.append((a, B[best[1]]))
    teks_sama = sum(a["text"] == b["text"] for a, b in pas)
    geser = max((max(abs(a[k]-b[k]) for k in ("x0","x1","top","bottom")) for a, b in pas), default=0)
    beda = [(a["text"], b["text"]) for a, b in pas if a["text"] != b["text"]]
    tak_pasang = len(A) - len(pas), len(B) - len(pas)
    urut = lambda K: " ".join(k["text"] for k in sorted(K, key=lambda k: (round(k["top"]), k["x0"])))
    rasio = difflib.SequenceMatcher(None, urut(A), urut(B)).ratio()
    return len(pas), teks_sama, geser, tak_pasang, rasio, beda

tot = {}
for f in sorted(glob.glob(os.path.join(S, "hasil-gpu", "*.json"))):
    nama = os.path.basename(f)[:-5]
    pid, h = nama.rsplit("-", 1)
    asli = json.load(open(glob.glob(os.path.join(CACHE, "*", pid, f"{h}-easyocr.json"))[0], encoding="utf-8"))["kata"]
    for mode in ("cpu", "gpu"):
        lain = json.load(open(os.path.join(S, f"hasil-{mode}", nama + ".json"), encoding="utf-8"))["kata"]
        n, sama, geser, tp, rasio, beda = banding(asli, lain)
        t = tot.setdefault(mode, [0, 0, 0, 0, 0.0])
        t[0] += len(asli); t[1] += n; t[2] += sama; t[3] = max(t[3], geser)
        print(f"{pid[:8]} h{int(h):>3} cache vs {mode}: kata {len(asli)}/{len(lain)}, berpasangan {n}, "
              f"teks sama {sama}/{n}, geser kotak maks {geser:.2f} pt, tak berpasangan {tp}, kemiripan teks {rasio:.4f}")
        for b in beda:
            print(f"      {b[0]!r} -> {b[1]!r}")
for mode, t in tot.items():
    print(f"TOTAL {mode}: {t[2]}/{t[1]} kata berpasangan sama teks (dari {t[0]} kata cache), geser kotak maks {t[3]:.2f} pt")
