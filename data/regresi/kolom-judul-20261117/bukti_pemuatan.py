"""Bukti pemuatan terarah perbaikan kolom judul ke produksi (17 Nov 2026; salinan versi 16 Nov).

  python bukti_pemuatan.py <potret_produksi_sebelum_per_id.tsv>

(a) Seluruh publikasi produksi = database uji per kunci (tipe, nomor, judul,
    halaman, halaman_fisik, penanda perkiraan, sumber). Harus 0 beda.
(b) Baris milik publikasi BUKAN target identik per id dengan sebelum
    pemuatan (potret `mysql --batch`, dibandingkan dengan potret sesudah yang
    dibuat dengan cara yang sama di sini).
"""
import csv
import os
import subprocess
import sys
from collections import Counter

DIR_INI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "C:/sistem-pencarian-bps")
import sqlalchemy as sa  # noqa: E402
from app.config import Config, KonfigurasiUji  # noqa: E402

TARGET = {l.strip() for l in open(os.path.join(DIR_INI, "publikasi-berubah.txt")) if l.strip()}
Q = ("SELECT publikasi_id, tipe, nomor, judul, halaman, halaman_fisik, halaman_fisik_perkiraan, sumber "
     "FROM entri_dokumen")


def per_pub(url):
    hasil = {}
    with sa.create_engine(url).connect() as k:
        for p, t, n, j, h, f, perk, s in k.execute(sa.text(Q)):
            hasil.setdefault(p, Counter())[(t, n or "", j, h or "", str(f or ""), int(perk), s)] += 1
    return hasil


prod, uji = per_pub(Config.SQLALCHEMY_DATABASE_URI), per_pub(KonfigurasiUji.SQLALCHEMY_DATABASE_URI)
hanya_prod = sorted(set(prod) - set(uji))
beda = sorted(p for p in (set(prod) | set(uji)) - set(hanya_prod) if prod.get(p) != uji.get(p))
print(f"(a) publikasi produksi {len(prod)}, uji {len(uji)}; hanya di produksi {hanya_prod} "
      f"(dibuktikan lewat (b)); berbeda per kunci: {len(beda)} {beda[:5]}")

# (b) per id, bukan target
mysql = os.path.join(os.environ.get("MYSQL_BIN", "C:/laragon/bin/mysql/mysql-8.0.30-winx64/bin"), "mysql")
q_id = ("SELECT id, publikasi_id, tipe, nomor, MD5(judul), halaman, halaman_fisik, sumber, "
        "MD5(teks_ternormalisasi), halaman_fisik_perkiraan FROM entri_dokumen ORDER BY id")
keluar = subprocess.run([mysql, "-u", "root", "--batch", "-e", q_id, "db_pencarian_bps"],
                        capture_output=True, text=True, encoding="utf-8").stdout.replace("\r", "")
sesudah = {r[0]: r for r in csv.reader(keluar.splitlines()[1:], delimiter="\t")}
sebelum = {r[0]: r for r in list(csv.reader(open(sys.argv[1], encoding="utf-8"), delimiter="\t"))[1:]}
lain_a = {i: r for i, r in sebelum.items() if r[1] not in TARGET}
lain_b = {i: r for i, r in sesudah.items() if r[1] not in TARGET}
berubah = [i for i in set(lain_a) | set(lain_b) if lain_a.get(i) != lain_b.get(i)]
print(f"(b) baris publikasi bukan target: sebelum {len(lain_a)}, sesudah {len(lain_b)}; berubah per id: {len(berubah)}")
print(f"    baris publikasi target: sebelum {sum(1 for r in sebelum.values() if r[1] in TARGET)}, "
      f"sesudah {sum(1 for r in sesudah.values() if r[1] in TARGET)}")
print("LULUS" if not beda and not berubah else "TIDAK LULUS")
