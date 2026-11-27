"""HANYA MEMBACA database uji + PDF: sampel acak entri untuk dibaca manual.

python sampel_entri.py <domain> <tahun_rilis_min> <tahun_rilis_maks> <n> <seed>

Untuk tiap entri dicetak bukti yang dipakai menilai:
- entri (tipe, nomor, judul, halaman cetak, halaman fisik, perkiraan, sumber);
- halaman PDF yang DITUJU tombol (halaman_fisik): baris yang memuat penanda
  "<label> <nomor>" atau awal judul, plus baris folio (angka di tepi atas/bawah);
- baris halaman Daftar (20+ halaman pertama) yang memuat nomor DAN awal judul,
  untuk menilai halaman cetak.
"""
import random
import re
import sys

sys.path.insert(0, r"c:\sistem-pencarian-bps")
import pdfplumber
import sqlalchemy as sa

from app.config import KonfigurasiUji
from app.services.sumber_bps import path_pdf

dom, t0, t1, n, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
m = sa.create_engine(KonfigurasiUji.SQLALCHEMY_DATABASE_URI)
with m.connect() as k:
    baris = k.execute(sa.text(
        "SELECT e.id, e.publikasi_id, p.judul, e.tipe, e.nomor, e.judul, e.halaman, e.halaman_fisik, "
        "e.halaman_fisik_perkiraan, e.sumber FROM entri_dokumen e JOIN publikasi p ON p.id=e.publikasi_id "
        "WHERE p.domain=:d AND YEAR(p.tanggal_rilis) BETWEEN :a AND :b ORDER BY e.id"),
        {"d": dom, "a": t0, "b": t1}).fetchall()
print(f"{len(baris)} entri; sampel {n}, seed {seed}")
sampel = sorted(random.Random(seed).sample(baris, min(n, len(baris))), key=lambda r: (r[1], r[0]))

LABEL = {"tabel": "tabel", "gambar": "gambar|grafik", "lampiran": "lampiran", "isi": ""}


def teks_halaman(pdf, i):
    try:
        return (pdf.pages[i - 1].extract_text() or "").splitlines()
    except Exception as e:  # noqa: BLE001
        return [f"<galat {e}>"]


def norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())


cache = {}
for no, (eid, pid, pjudul, tipe, nomor, judul, hal, fisik, perk, sumber) in enumerate(sampel, 1):
    print("=" * 100)
    print(f"#{no} id {eid} | {pid[:8]} {pjudul[:70]}")
    print(f"   {tipe} | nomor {nomor!r} | hal {hal!r} | fisik {fisik}{' (PERKIRAAN)' if perk else ''} | {sumber}")
    print(f"   judul: {judul}")
    if pid not in cache:
        cache[pid] = pdfplumber.open(path_pdf(dom, pid))
    pdf = cache[pid]
    awal = " ".join(norm(judul).split()[:4])
    if fisik:
        t = teks_halaman(pdf, fisik)
        lab = LABEL[tipe]
        pola = re.compile(rf"\b({lab})\s*{re.escape(nomor)}\b", re.I) if nomor and lab else None
        print(f"   -- hal PDF {fisik}/{len(pdf.pages)} ({len(t)} baris). tepi: {t[:2]} ... {t[-2:]}")
        for b in t:
            if (pola and pola.search(b)) or (awal and awal in norm(b)):
                print(f"      > {b[:150]}")
    # Daftar: cari baris berawal nomor / berisi awal judul di 40 halaman pertama
    if hal and tipe != "isi" and nomor:
        kena = []
        for i in range(1, min(45, len(pdf.pages)) + 1):
            for b in teks_halaman(pdf, i):
                nb = norm(b)
                if "....." in b or "…" in b or re.search(rf"\b{re.escape(hal)}\s*$", b):
                    if re.search(rf"(^|\s){re.escape(nomor)}(\s|$)", b) and (not awal or awal.split()[0] in nb):
                        kena.append((i, b[:150]))
        for i, b in kena[:3]:
            print(f"   -- Daftar hal {i}: {b}")
        if not kena:
            print("   -- Daftar: baris tidak ditemukan otomatis (periksa manual)")
