"""Catat setiap kata yang diubah _rapikan_nomor_halaman / _gabung_nomor_terbelah (hanya baca).
  python jejak_rapikan.py <pid> [pid ...]   atau   python jejak_rapikan.py @daftar.json
Dipakai untuk membuktikan bahwa publikasi yang berubah memang punya kata yang dirapikan."""
import glob, json, os, sys
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.stdout.reconfigure(encoding="utf-8")
import pdfplumber
from app.services import ekstraksi_pdf as E
pids = json.load(open(sys.argv[1][1:])) if sys.argv[1].startswith("@") else sys.argv[1:]
catat = []
asli_r = E._rapikan_nomor_halaman
def r(baris):
    hasil = asli_r(baris)
    if hasil is not baris:
        import re
        w = baris[len(hasil) - 1]["text"]
        jenis = "hal_menyatu" if re.match(r"[.…�]{3,}", w) else "hal_ditimpa"
        if len(hasil) < len(baris):
            jenis += "+buang_titik"
        catat.append((jenis, " ".join(k["text"] for k in baris[-3:]), hasil[-1]["text"]))
    return hasil
E._rapikan_nomor_halaman = r
if hasattr(E, "_gabung_nomor_terbelah"):
    asli_g = E._gabung_nomor_terbelah
    def g(semua):
        hasil = asli_g(semua)
        for a, b in zip(semua, hasil):
            if a is not b:
                catat.append(("nomor", " ".join(k["text"] for k in a[:2]), b[0]["text"]))
        return hasil
    E._gabung_nomor_terbelah = g
for p in pids:
    catat.clear()
    f = glob.glob(f"data/publikasi_pdf/*/{p}*.pdf")[0]
    with pdfplumber.open(f) as pdf:
        for t, h in E.cari_heading(pdf).items():
            E._baca_daftar(pdf, h, t, p)
    jenis = {}
    for c in catat:
        jenis.setdefault(c[0], []).append(c)
    print(p[:8], {k: len(v) for k, v in jenis.items()}, [f"{c[1][-40:]} -> {c[2]}" for c in catat[:4]])
