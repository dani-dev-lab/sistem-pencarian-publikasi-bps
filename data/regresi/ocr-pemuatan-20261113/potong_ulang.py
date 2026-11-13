"""Potong ulang bukti D menurut baris dengan kecocokan token judul terbanyak.
  python potong_ulang.py 8,12,15
"""
import json, sys, glob, re, os
import pypdfium2 as pdfium
S = os.path.dirname(os.path.abspath(__file__))  # folder laporan ini
os.chdir("C:/sistem-pencarian-bps")
sampel = {r["no"]: r for r in json.load(open(S + "/sampel/sampel.json", encoding="utf-8"))}
tsv = [l.rstrip("\n").split("\t") for l in open(S + "/bertambah.tsv", encoding="utf-8")][1:]
pid_of = {}
for r in tsv:
    pid_of.setdefault((r[1], r[4]), r[0])
def tok(s): return [t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) > 2]
for no in map(int, sys.argv[1].split(",")):
    r = sampel[no]; pid = pid_of[(r["publikasi"], r["judul"])]
    d = glob.glob(f"data/ocr_cache/*/{pid}")[0]
    tj = set(tok(r["judul"]))
    best = None
    for f in glob.glob(d + "/*-easyocr.json"):
        n = int(os.path.basename(f)[:4])
        if n > 40: continue  # halaman Daftar ada di depan
        kata = json.load(open(f, encoding="utf-8"))["kata"]
        baris = {}
        for k in kata: baris.setdefault(round(k["top"] / 7), []).append(k)
        keys = sorted(baris)
        for i, b in enumerate(keys):
            # jendela 3 baris
            ks = [k for j in keys[i:i+3] for k in baris[j]]
            s = len(tj & set(tok(" ".join(k["text"] for k in ks))))
            if not best or s > best[0]:
                best = (s, n, min(k["top"] for k in baris[b]))
    s, n, top = best
    pdf = pdfium.PdfDocument(glob.glob(f"data/publikasi_pdf/*/{pid}.pdf")[0])
    hal = pdf[n - 1]; w, h = hal.get_size(); sk = 150 / 72
    img = hal.render(scale=sk).to_pil().crop((0, max(0, (top - 30) * sk), w * sk, min(h, top + 75) * sk))
    out = f"{S}/sampel/{no:02d}-D2-hal{n}.png"; img.save(out)
    print(no, f"hal {n} skor {s}/{len(tj)}", out.split('/')[-1])
