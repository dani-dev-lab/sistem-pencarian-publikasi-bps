"""Bersihkan kode HTML ("&nbsp;", "&amp;", ...) di judul/abstrak publikasi yang SUDAH ada.

  venv\\Scripts\\python.exe scripts\\bersihkan_kode_html.py --db-uji [--coba]
  venv\\Scripts\\python.exe scripts\\bersihkan_kode_html.py --produksi [--coba]

Publikasi baru sudah dibersihkan saat ditarik (pipeline_data.simpan_metadata,
19 Nov 2026). Skrip ini untuk data lama: judul/abstrak dibersihkan dengan
fungsi yang sama (normalisasi_data.bersihkan_html), teks_ternormalisasi
publikasi dihitung ulang (teks_publikasi), versi_data naik, semuanya SATU
transaksi. Hanya baris yang benar-benar berubah yang ditulis; idempoten.
Tujuan wajib disebut. Tidak berjalan selama pembaruan lain berjalan.
"""
import argparse
import os
import sys

DIR_PROYEK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR_PROYEK)
sys.path.insert(0, os.path.join(DIR_PROYEK, "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy.engine import make_url  # noqa: E402

from app import create_app  # noqa: E402
from app.config import Config, KonfigurasiUji  # noqa: E402
from app.models import Publikasi, db  # noqa: E402
from app.services import versi_data  # noqa: E402
from app.services.normalisasi_data import bersihkan_html, teks_publikasi  # noqa: E402
import perbarui  # noqa: E402  (kunci yang sama dengan pembaruan)


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = a.add_mutually_exclusive_group(required=True)
    g.add_argument("--db-uji", action="store_true", help="database uji")
    g.add_argument("--produksi", action="store_true", help="database produksi")
    a.add_argument("--coba", action="store_true", help="hitung dan tampilkan saja, tidak menulis")
    opsi = a.parse_args()

    konfigurasi = KonfigurasiUji if opsi.db_uji else Config
    print(f"Database tujuan: {make_url(konfigurasi.SQLALCHEMY_DATABASE_URI).database} "
          f"({'UJI' if opsi.db_uji else 'PRODUKSI'}){' - COBA, tidak menulis' if opsi.coba else ''}")
    if not perbarui.ambil_kunci():
        print("TIDAK DIJALANKAN: pembaruan lain sedang berjalan.")
        sys.exit(2)
    try:
        app = create_app(konfigurasi)
        with app.app_context():
            versi_data.pastikan_tabel()          # DDL sebelum transaksi penulis
            berubah = []
            for pub in Publikasi.query.order_by(Publikasi.id).all():
                judul = (bersihkan_html(pub.judul) or "").strip()
                abstrak = bersihkan_html(pub.abstrak)
                if judul == pub.judul and abstrak == pub.abstrak:
                    continue
                berubah.append((pub.id, pub.judul[:60]))
                pub.judul, pub.abstrak = judul, abstrak
                pub.teks_ternormalisasi = teks_publikasi(judul, abstrak)
            for pid, judul in berubah:
                print(f"  {pid}  {judul}")
            print(f"{len(berubah)} publikasi dibersihkan")
            if berubah and not opsi.coba:
                versi_data.naikkan()
                db.session.commit()
                print("Tersimpan; versi_data naik 1.")
            else:
                db.session.rollback()
    finally:
        perbarui.lepas_kunci()


if __name__ == "__main__":
    main()
