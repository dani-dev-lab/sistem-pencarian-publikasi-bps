"""Bukti: isi publikasi + entri kecamatan di PRODUKSI = database uji, baris demi baris (multiset
terurut, bukan sidik XOR). Juga 5 publikasi pola 2+3. Hanya membaca."""
import os, sys
from collections import Counter
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy import create_engine, text
from app.config import Config, KonfigurasiUji
import json
TG = json.load(open("data/regresi/kecamatan-parser-20261118/berubah_produksi.json"))
Q_PUB = ("SELECT id, domain, judul, abstrak, tanggal_rilis, url_pdf, teks_ternormalisasi, halaman_ocr, kecamatan, "
         "updt_date_api, updt_date_diproses, sidik_ukuran, sidik_mtime, wilayah, diekstrak_pada, catatan_ekstraksi "
         "FROM publikasi WHERE kecamatan IS NOT NULL")
Q_ENT = ("SELECT e.publikasi_id, e.tipe, e.nomor, e.judul, e.halaman, e.halaman_fisik, e.halaman_fisik_perkiraan, "
         "e.sumber, e.teks_ternormalisasi FROM entri_dokumen e JOIN publikasi p ON p.id=e.publikasi_id "
         "WHERE {syarat} ORDER BY e.publikasi_id, e.id")
def ambil(url, q, **kw):
    with create_engine(url).connect() as k:
        return [tuple(r) for r in k.execute(text(q), kw)]
P, U = Config.SQLALCHEMY_DATABASE_URI, KonfigurasiUji.SQLALCHEMY_DATABASE_URI
for nama, q in [("publikasi kecamatan", Q_PUB), ("entri kecamatan", Q_ENT.format(syarat="p.kecamatan IS NOT NULL"))]:
    a, b = ambil(P, q), ambil(U, q)
    print(f"{nama}: produksi {len(a)}, uji {len(b)}, sama berurutan {a == b}, sama multiset {Counter(a) == Counter(b)}")
q5 = Q_ENT.format(syarat="e.publikasi_id IN :t").replace(":t", "(" + ",".join(f"'{t}'" for t in TG) + ")")
a, b = ambil(P, q5), ambil(U, q5)
print(f"entri 5 publikasi pola 2+3: produksi {len(a)}, uji {len(b)}, sama berurutan {a == b}")
