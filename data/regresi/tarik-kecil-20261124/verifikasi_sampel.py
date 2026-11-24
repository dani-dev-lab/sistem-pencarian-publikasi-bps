"""HANYA MEMBACA. Bukti per entri sampel (seed sama dengan sampel_entri.py):
- DAFTAR: baris di halaman berleader yang DIAWALI nomor entri (+2 baris sesudahnya);
- BADAN: setiap halaman non-Daftar dengan baris yang diawali "<label> <nomor>" atau
  "<nomor> " tepat sesudah baris "Tabel/Gambar..." (label bertumpuk), plus folio
  (angka tunggal / angka di awal-akhir baris tepi).
Untuk entri isi: halaman yang memuat judulnya (awal 5 kata) sebagai baris.
python verifikasi_sampel.py <domain> <th_min> <th_maks> <n> <seed>
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
sampel = sorted(random.Random(seed).sample(baris, min(n, len(baris))), key=lambda r: (r[1], r[0]))
LABEL = {"tabel": r"tabel|table", "gambar": r"gambar|grafik|figure", "lampiran": r"lampiran|appendix"}
teks = {}


def halaman(pid):
    if pid not in teks:
        with pdfplumber.open(path_pdf(dom, pid)) as pdf:
            teks[pid] = [(pg.extract_text() or "").splitlines() for pg in pdf.pages]
    return teks[pid]


def berleader(t):
    return sum(b.count(".....") + b.count("…") for b in t) > 3


def folio(t):
    tepi = t[:2] + t[-3:]
    f = []
    for b in tepi:
        for x in re.findall(r"(?:^|\s)(\d{1,4}|[ivxlc]{1,7})(?=\s|$)", b.strip()):
            f.append(x)
    return f


def norm(s):
    return " ".join(re.sub(r"[^a-z0-9]", " ", (s or "").lower()).split())


for no, (eid, pid, pj, tipe, nomor, judul, hal, fisik, perk, sumber) in enumerate(sampel, 1):
    hs = halaman(pid)
    print("=" * 100)
    print(f"#{no} id {eid} | {pid[:8]} {pj[:60]} ({len(hs)} hal)")
    print(f"   {tipe} | nomor {nomor!r} | hal cetak {hal!r} | fisik {fisik}{' (PERKIRAAN)' if perk else ''} | {sumber}")
    print(f"   judul: {judul[:230]}")
    if tipe == "isi":
        kunci = norm(judul)[:40]
        for i, t in enumerate(hs, 1):
            if berleader(t):
                for j, b in enumerate(t):
                    if kunci[:25] and kunci[:25] in norm(b):
                        print(f"   DAFTAR hal {i}: {b[:140]}")
        dapat = [i for i, t in enumerate(hs, 1) if not berleader(t)
                 and any(kunci[:25] and norm(b).startswith(kunci[:25]) for b in t)]
        print(f"   BADAN (baris berawal judul): {dapat[:8]}")
        for i in dapat[:4]:
            print(f"      hal {i} folio {folio(hs[i - 1])}")
        continue
    pola_d = re.compile(rf"^(?:(?:{LABEL[tipe]})\s*)?{re.escape(nomor)}(?:\s|$)", re.I) if nomor else None
    if pola_d:
        for i, t in enumerate(hs, 1):
            if berleader(t) or i <= 60:
                for j, b in enumerate(t):
                    if pola_d.match(b.strip()) and (berleader(t)):
                        print(f"   DAFTAR hal {i}: " + " / ".join(x[:110] for x in t[j:j + 3]))
        badan = []
        pola_b = re.compile(rf"^(?:{LABEL[tipe]})\s*{re.escape(nomor)}(?:\s|$)", re.I)
        pola_t = re.compile(rf"^{re.escape(nomor)}(?:\s|$)")
        for i, t in enumerate(hs, 1):
            if berleader(t):
                continue
            for j, b in enumerate(t):
                b = b.strip()
                atas = t[j - 1].strip().lower() if j else ""
                if pola_b.match(b) or (pola_t.match(b) and re.match(LABEL[tipe], atas)):
                    badan.append(i)
                    break
        print(f"   BADAN (keterangan bernomor): {badan[:8]}")
        for i in badan[:3]:
            t = hs[i - 1]
            j = next(j for j, b in enumerate(t) if pola_b.match(b.strip()) or pola_t.match(b.strip()))
            print(f"      hal {i} folio {folio(t)} | " + " / ".join(x[:90] for x in t[max(0, j - 1):j + 2]))
    if fisik and fisik not in (locals().get("badan") or []):
        print(f"   hal fisik {fisik}: folio {folio(hs[fisik - 1])} | {' / '.join(x[:80] for x in hs[fisik - 1][:4])}")
