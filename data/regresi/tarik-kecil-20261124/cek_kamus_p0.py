"""Hanya MEMBACA: entri/publikasi mana yang teks_ternormalisasi-nya berubah
kalau kamus sekarang (dengan p0) diterapkan. Argumen: uji | produksi."""
import sys
from collections import Counter, defaultdict
sys.path.insert(0, r"c:\sistem-pencarian-bps")
import sqlalchemy as sa
from app import create_app
from app.config import Config, KonfigurasiUji
from app.services.preprocessing import normalisasi
from app.services.normalisasi_data import teks_publikasi

uji = sys.argv[1] == "uji"
url = KonfigurasiUji.SQLALCHEMY_DATABASE_URI if uji else Config.SQLALCHEMY_DATABASE_URI
m = sa.create_engine(url)
per_pub = Counter()
dom = {}
contoh = []
with m.connect() as k:
    for pid, d, j, a, t in k.execute(sa.text("SELECT id, domain, judul, abstrak, teks_ternormalisasi FROM publikasi")):
        dom[pid] = d
        if teks_publikasi(j, a) != t:
            per_pub[(pid, "PUB")] += 1
    for pid, j, t in k.execute(sa.text("SELECT publikasi_id, judul, teks_ternormalisasi FROM entri_dokumen")):
        b = normalisasi(j)
        if b != t:
            per_pub[(pid, "entri")] += 1
            if len(contoh) < 6:
                contoh.append((pid[:8], j[:90], t[:90], b[:90]))
print("DB", url.rsplit("/", 1)[-1])
ringkas = defaultdict(dict)
for (pid, jenis), n in per_pub.items():
    ringkas[pid][jenis] = n
for pid, v in sorted(ringkas.items(), key=lambda x: dom[x[0]]):
    print(dom[pid], pid, v)
print("total publikasi", len(ringkas), "entri", sum(v.get("entri", 0) for v in ringkas.values()))
for c in contoh:
    print("\n", *c, sep="\n  ")
