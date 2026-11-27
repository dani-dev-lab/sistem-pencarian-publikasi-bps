"""Periksa sidik PDF sesudah folder data dipindahkan ke komputer lain (26 Nov 2026).

HANYA MEMBACA: tidak mengubah database, PDF, maupun cache OCR.

Aplikasi mengenali PDF dari (ukuran, detik waktu ubah). Kalau waktu ubah
bergeser saat menyalin (ZIP, flashdisk FAT32/exFAT, unduhan awan), pembaruan
berikutnya membaca ulang PDF itu dan membuang cache OCR-nya. Skrip ini
memeriksanya SEBELUM pembaruan pertama di komputer baru:

  - tiap publikasi di database: PDF ada di data/publikasi_pdf/<domain>/<id>.pdf
    dan sidiknya = sidik_ukuran/sidik_mtime di database;
  - tiap cache OCR (data/ocr_cache/<domain>/<id>/_meta.json): sidik = PDF;
  - jumlah sampul di data/sampul/.

  Windows: venv\\Scripts\\python.exe scripts\\periksa_sidik.py [--db-uji]
  Linux  : venv/bin/python scripts/periksa_sidik.py [--db-uji]

Kode keluar: 0 semua cocok; 1 ada yang berbeda atau hilang (rinciannya
tercetak). Publikasi yang belum pernah diproses (sidik kosong di database)
dihitung terpisah dan tidak membuat gagal.
"""
import argparse
import json
import os
import sys

DIR_PROYEK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR_PROYEK)

import sqlalchemy as sa  # noqa: E402

from app.config import Config, KonfigurasiUji  # noqa: E402
from app.services.sumber_bps import path_pdf, sidik_pdf  # noqa: E402

DIR_OCR = os.path.join(DIR_PROYEK, "data", "ocr_cache")
DIR_SAMPUL = os.path.join(DIR_PROYEK, "data", "sampul")
CONTOH = 10


def main():
    arg = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    arg.add_argument("--db-uji", action="store_true", help="periksa terhadap DATABASE UJI")
    opsi = arg.parse_args()
    url = (KonfigurasiUji if opsi.db_uji else Config).SQLALCHEMY_DATABASE_URI
    mesin = sa.create_engine(url)
    with mesin.connect() as c:
        baris = c.execute(sa.text(
            "SELECT id, domain, sidik_ukuran, sidik_mtime FROM publikasi ORDER BY domain, id")).all()
    print(f"database : {mesin.url.database} ({len(baris)} publikasi)")

    cocok, beda, hilang, belum = 0, [], [], 0
    for pub_id, domain, ukuran, mtime in baris:
        path = path_pdf(domain, pub_id)
        if not os.path.isfile(path):
            hilang.append(f"{domain}/{pub_id}.pdf")
            continue
        if ukuran is None or mtime is None:
            belum += 1
            continue
        sekarang = sidik_pdf(path)
        if sekarang == (ukuran, mtime):
            cocok += 1
        else:
            beda.append(f"{domain}/{pub_id}.pdf: database {ukuran}/{mtime}, berkas "
                        f"{sekarang[0]}/{sekarang[1]} (selisih waktu {sekarang[1] - mtime:+d} detik)")

    ocr_cocok, ocr_beda = 0, []
    if os.path.isdir(DIR_OCR):
        for domain in sorted(os.listdir(DIR_OCR)):
            for pub_id in sorted(os.listdir(os.path.join(DIR_OCR, domain))):
                meta = os.path.join(DIR_OCR, domain, pub_id, "_meta.json")
                pdf = path_pdf(domain, pub_id)
                if not os.path.isfile(meta) or not os.path.isfile(pdf):
                    continue
                with open(meta, encoding="utf-8") as f:
                    tercatat = json.load(f).get("sidik")
                st = os.stat(pdf)
                if tercatat == [st.st_size, int(st.st_mtime)]:
                    ocr_cocok += 1
                else:
                    ocr_beda.append(f"{domain}/{pub_id}: cache {tercatat}, PDF {[st.st_size, int(st.st_mtime)]}")

    sampul = len([n for n in os.listdir(DIR_SAMPUL) if n.endswith(".jpg")]) if os.path.isdir(DIR_SAMPUL) else 0

    print(f"PDF cocok          : {cocok}")
    print(f"PDF berbeda        : {len(beda)}")
    for x in beda[:CONTOH]:
        print("   ", x)
    print(f"PDF tidak ada      : {len(hilang)}")
    for x in hilang[:CONTOH]:
        print("   ", x)
    print(f"belum pernah diproses (tanpa sidik di database): {belum}")
    print(f"cache OCR cocok    : {ocr_cocok}")
    print(f"cache OCR berbeda  : {len(ocr_beda)}")
    for x in ocr_beda[:CONTOH]:
        print("   ", x)
    print(f"sampul (.jpg)      : {sampul}")
    if beda or hilang or ocr_beda:
        print("\nADA YANG BERBEDA: jangan jalankan pembaruan dulu. Salin ulang folder data "
              "dengan cara yang menjaga waktu ubah (PANDUAN bagian 2, jalur A).")
        return 1
    print("\nSEMUA COCOK: pembaruan berikutnya tidak akan membaca ulang PDF yang sudah ada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
