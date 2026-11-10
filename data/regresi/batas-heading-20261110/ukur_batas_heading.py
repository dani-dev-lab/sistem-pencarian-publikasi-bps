"""Dampak BATAS_HALAMAN_CARI = 25: heading DAFTAR TABEL/GAMBAR/LAMPIRAN yang
baru muncul SESUDAH halaman 25 tidak pernah dibaca jalur daftar.

Tidak mengubah parser maupun database (hanya SELECT). Per publikasi:
  1. saringan cepat pypdfium2: halaman > 25 yang teksnya memuat "DAFTAR";
  2. calon diperiksa dengan pemeriksa heading parser yang SAMA (RE_HEADING
     pada 6 baris teratas sesudah watermark dibuang, _tipe_dari_heading);
  3. tipe yang headingnya TIDAK ada di 25 halaman pertama = terlewat;
  4. daftar terlewat dibaca kering dengan _baca_daftar, entrinya dicocokkan
     ke entri DB publikasi itu menurut kunci (tipe, nomor).
Pemakaian: python ukur_batas_heading.py <keluaran.json> [jumlah_proses]
"""
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.getcwd())

TIPE = ("tabel", "gambar", "lampiran")


def periksa(arg):
    pid, domain, kunci_db = arg
    import pdfplumber
    import pypdfium2 as pdfium
    from app.services import ekstraksi_pdf as ep
    path = f"data/publikasi_pdf/{domain}/{pid}.pdf"
    if not os.path.exists(path):
        return {"pid": pid, "galat": "pdf tidak ada"}
    doc = pdfium.PdfDocument(path)
    n = len(doc)
    calon = [i for i in range(ep.BATAS_HALAMAN_CARI, n)
             if "daftar" in doc[i].get_textpage().get_text_range().lower()]
    doc.close()
    hasil = {"pid": pid, "domain": domain, "halaman": n, "calon": len(calon), "terlewat": []}
    if not calon:
        return hasil
    with pdfplumber.open(path) as pdf:
        awal = ep.cari_heading(pdf)                      # perilaku produksi (25 halaman)
        lambat = {}
        for i in calon:
            baris = ep._kelompokkan_baris(ep._kata_halaman(pdf.pages[i]))
            for b in baris[:6]:
                cocok = ep.RE_HEADING.match(ep._teks_baris(b).strip())
                if cocok:
                    for tipe in ep._tipe_dari_heading(cocok.group(1)):
                        lambat.setdefault(tipe, i)
        for tipe, i in sorted(lambat.items(), key=lambda x: x[1]):
            if tipe not in TIPE or tipe in awal:
                continue
            entri = ep._baca_daftar(pdf, i, tipe, pid)
            bernomor = [e for e in entri if e.get("nomor")]
            sudah = [e for e in bernomor if (tipe, e["nomor"]) in kunci_db]
            hasil["terlewat"].append({
                "tipe": tipe, "halaman_heading": i + 1, "entri_daftar": len(entri),
                "bernomor": len(bernomor), "sudah_di_db": len(sudah),
                "belum_di_db": [e["nomor"] for e in bernomor if (tipe, e["nomor"]) not in kunci_db],
                "tanpa_nomor": len(entri) - len(bernomor),
                "contoh": [(e.get("nomor"), (e.get("judul") or "")[:80], e.get("halaman")) for e in entri[:3]],
            })
    return hasil


def main():
    from app import create_app
    from app.config import KonfigurasiUji
    from app.models import db
    import sqlalchemy as sa
    app = create_app(KonfigurasiUji)
    with app.app_context():
        pubs = db.session.execute(sa.text("select id, domain, judul from publikasi")).fetchall()
        kunci = {}
        for pid, tipe, nomor in db.session.execute(sa.text(
                "select publikasi_id, tipe, nomor from entri_dokumen where nomor is not null")):
            kunci.setdefault(pid, set()).add((tipe, nomor))
    judul = {p.id: p.judul for p in pubs}
    tugas = [(p.id, p.domain, kunci.get(p.id, set())) for p in pubs]
    with Pool(int(sys.argv[2]) if len(sys.argv) > 2 else 4) as pool:
        hasil = pool.map(periksa, tugas, chunksize=4)
    for h in hasil:
        h["judul"] = judul.get(h["pid"])
    json.dump(hasil, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    kena = [h for h in hasil if h.get("terlewat")]
    print(f"publikasi diperiksa {len(hasil)}, galat {sum(1 for h in hasil if h.get('galat'))}, "
          f"punya heading tabel/gambar/lampiran terlewat: {len(kena)}")
    for h in kena:
        for t in h["terlewat"]:
            print(f"  {h['domain']} {h['pid'][:8]} {h['judul'][:50]:50} {t['tipe']:8} hal.{t['halaman_heading']:3} "
                  f"entri {t['entri_daftar']:3} bernomor {t['bernomor']:3} sudah-di-DB {t['sudah_di_db']:3} tanpa-nomor {t['tanpa_nomor']}")


if __name__ == "__main__":
    main()
