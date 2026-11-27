"""Sampel acak entri BARU/BERUBAH (judul atau halaman cetak) hasil uji kering vs DB uji.
  python sampel_baru.py <hasil.json> [n] [seed]
Bukti per entri sama dengan kecamatan-mutu-20261118/sampel_mutu.py."""
import json, os, random, re, sys
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.stdout.reconfigure(encoding="utf-8")
import importlib.util
import pdfplumber
from app.services.ekstraksi_pdf import _bukan_watermark
spec = importlib.util.spec_from_file_location("uk", f"{DIR}/data/regresi/kecamatan-parser-20261118/uji_kering.py")
g = {}; exec(open(spec.origin, encoding="utf-8").read().split('if sys.argv[1] == "daftar"')[0], g)
baru = json.load(open(sys.argv[1], encoding="utf-8"))
n = int(sys.argv[2]) if len(sys.argv) > 2 else 30
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 20261118
lama = g["dari_db"](list(baru))
with g["mesin"]().connect() as c:
    info = {r[0]: (r[1], r[2]) for r in c.execute(g["text"]("select id, domain, judul from publikasi"))}
populasi = []
for p, es in baru.items():
    kl = {(e["tipe"], e["nomor"]): e for e in lama[p] if e["nomor"]}
    for e in es:
        if not e["nomor"]:
            continue
        a = kl.get((e["tipe"], e["nomor"]))
        if a is None or a["judul"] != e["judul"] or a["halaman"] != e["halaman"]:
            populasi.append((p, e, a))
print(f"populasi {len(populasi)} entri baru/berubah; seed {seed}")
def baris_hal(pdf, i):
    t = pdf.pages[i - 1].filter(_bukan_watermark).extract_text() or ""
    return [x.strip() for x in t.splitlines() if x.strip()]
for k, (p, e, a) in enumerate(random.Random(seed).sample(populasi, n), 1):
    dom, pj = info[p]
    print(f"\n#{k} {pj} [{p[:8]}] {e['tipe']} {e['nomor']} | hal {e['halaman']} | fisik {e['halaman_fisik']}"
          f"{' (perkiraan)' if e['halaman_fisik_perkiraan'] else ''} | {e['sumber']}"
          f" | LAMA: {'baru' if a is None else (a['halaman'], a['sumber'])}")
    print(f"   JUDUL: {e['judul']}")
    with pdfplumber.open(f"data/publikasi_pdf/{dom}/{p}.pdf") as pdf:
        cari = re.compile(r"(^|\s)" + re.escape(e["nomor"]) + r"(?![\d.]\d)")
        for i in range(1, min(40, len(pdf.pages)) + 1):
            ls = baris_hal(pdf, i)
            if sum(1 for x in ls if re.search(r"\.{4,}|…", x)) < 3:
                continue
            for j, x in enumerate(ls):
                y = re.sub(r"(\d)\.\s(\d)", r"\1.\2", x)
                if cari.search(y):
                    print(f"   DAFTAR p{i}: " + " // ".join(z[:100] for z in ls[j:j + 3]))
        if e["halaman_fisik"]:
            ls = baris_hal(pdf, int(e["halaman_fisik"]))
            cocok = [x[:100] for x in ls if cari.search(re.sub(r"(\d)\.\s(\d)", r"\1.\2", x))][:2]
            kop = [x[:50] for x in ls if re.search(r"DALAM ANGKA|IN FIGURE", x, re.I)] + [x[:50] for x in ls[-2:]]
            print(f"   FISIK p{e['halaman_fisik']}: cocok={cocok} folio/kop={kop[:3]}")
