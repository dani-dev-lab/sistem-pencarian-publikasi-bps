"""Diagnosis PDF di data/publikasi_pdf/<domain>/.

Menjawab: mana yang tidak bisa dibuka, mana yang tidak punya layer teks (kandidat
hasil scan), dan apakah isi folder cocok dengan tabel publikasi. Hanya membaca.

Jalankan:  venv/Scripts/python.exe scripts/cek_pdf.py
"""

import os
import sys

import pdfplumber

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.config import Config
from app.models import Publikasi


def mb(n):
    return f"{n / 1024 / 1024:.2f} MB"


def main():
    app = create_app()
    with app.app_context():
        judul_pub = {p.id: (p.judul, p.domain) for p in Publikasi.query.all()}

    akar_pdf = str(Config.DIR_PUBLIKASI_PDF)
    berkas = sorted(os.path.join(akar, n)
                    for akar, _, nama in os.walk(akar_pdf)
                    for n in nama if n.lower().endswith(".pdf"))

    print(f"{len(berkas)} berkas PDF di {akar_pdf}")
    print()

    gagal_buka = []
    tanpa_teks = []
    total_halaman = 0

    for i, path in enumerate(berkas, start=1):
        pub_id = os.path.basename(path)[:-4]
        judul = judul_pub.get(pub_id, ("(tidak ada di database)", None))[0].replace("\n", " ")
        print(f"[{i:>3}/{len(berkas)}] {judul[:48]:<48}", end=" ", flush=True)

        try:
            with pdfplumber.open(path) as pdf:
                jml_halaman = len(pdf.pages)
                teks_hal1 = pdf.pages[0].extract_text() if jml_halaman else None
        except Exception as e:  # noqa: BLE001 - script diagnosis, cukup catat pesannya
            print(f"GAGAL DIBUKA: {e}")
            gagal_buka.append((pub_id, str(e)))
            continue

        total_halaman += jml_halaman
        ada_teks = bool(teks_hal1 and teks_hal1.strip())
        if not ada_teks:
            tanpa_teks.append((pub_id, judul))
        print(f"{jml_halaman:>4} hal  {mb(os.path.getsize(path)):>9}  "
              f"{'teks OK' if ada_teks else 'TANPA TEKS'}")

    print()
    print("=" * 74)
    print("RINGKASAN")
    print("=" * 74)
    print(f"Bisa dibuka       : {len(berkas) - len(gagal_buka)}/{len(berkas)}")
    print(f"Gagal dibuka      : {len(gagal_buka)}")
    print(f"Tanpa teks hal. 1 : {len(tanpa_teks)}  (kandidat PDF hasil scan)")
    print(f"Total halaman     : {total_halaman}")

    if gagal_buka:
        print()
        print("Berkas yang gagal dibuka:")
        for pub_id, pesan in gagal_buka:
            print(f"  {pub_id}  -  {pesan}")

    if tanpa_teks:
        print()
        print("Berkas tanpa layer teks (perlu OCR atau dikeluarkan dari scope):")
        for pub_id, judul in tanpa_teks:
            print(f"  {pub_id}  -  {judul[:60]}")

    # Cek silang isi folder vs tabel publikasi.
    id_berkas = {os.path.basename(p)[:-4] for p in berkas}
    if set(judul_pub) - id_berkas:
        print()
        print(f"Ada di database tapi berkasnya tidak ada: {len(set(judul_pub) - id_berkas)}")
        for pid in sorted(set(judul_pub) - id_berkas):
            print(f"  {pid}  -  {judul_pub[pid][0][:60]}")
    if id_berkas - set(judul_pub):
        print()
        print(f"Ada berkas tapi tidak terdaftar di database: {len(id_berkas - set(judul_pub))}")
        for pid in sorted(id_berkas - set(judul_pub)):
            print(f"  {pid}.pdf")


if __name__ == "__main__":
    main()
