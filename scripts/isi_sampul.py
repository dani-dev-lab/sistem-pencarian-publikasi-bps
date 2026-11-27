"""Isi sampul publikasi yang SUDAH ada di database (sekali jalan, 19 Nov 2026).

  venv\\Scripts\\python.exe scripts\\isi_sampul.py --produksi [--coba]
  venv\\Scripts\\python.exe scripts\\isi_sampul.py --db-uji [--coba]

Untuk tiap publikasi yang belum punya berkas sampul di data/sampul/:
  1. unduh sampul resmi dari url_cover di database (token WebAPI masih
     berlaku pada hari pembaruan terakhir), jeda 1 detik antar unduhan;
  2. kalau gagal: cadangan dari halaman 1 PDF lokal;
  3. kalau itu juga gagal: dicatat gagal, publikasi tampil tanpa gambar.

Publikasi yang sudah punya berkas (resmi ATAU cadangan) dilewati, jadi skrip
bisa dihentikan dan dijalankan lagi untuk melanjutkan. --ulang-cadangan
mencoba lagi sampul resmi untuk yang baru punya cadangan.

Hanya menambah berkas di data/sampul/; database hanya DIBACA. Tidak berjalan
selama pembaruan lain berjalan (kunci yang sama dengan perbarui.py). Token
dan API key tidak pernah dicetak. Keluaran juga disalin ke
data/log_pembaruan/isi-sampul-<waktu>.log.
"""
import argparse
import os
import sys
import time
from datetime import datetime

DIR_PROYEK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR_PROYEK)
sys.path.insert(0, os.path.join(DIR_PROYEK, "scripts"))
sys.stdout.reconfigure(encoding="utf-8")
os.chdir(DIR_PROYEK)

from sqlalchemy.engine import make_url  # noqa: E402

from app import create_app  # noqa: E402
from app.config import Config, KonfigurasiUji  # noqa: E402
from app.models import Publikasi, db  # noqa: E402
from app.services import sampul, sumber_bps  # noqa: E402
import perbarui  # noqa: E402  (kunci, salinan log, cegah tidur: sama dengan pembaruan)

DETIK_PER_SAMPUL = 1.4      # jeda 1 detik + unduhan ±0,4 detik (diukur 19 Nov 2026)


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = a.add_mutually_exclusive_group(required=True)
    g.add_argument("--db-uji", action="store_true", help="baca daftar dari database uji")
    g.add_argument("--produksi", action="store_true", help="baca daftar dari database produksi")
    a.add_argument("--coba", action="store_true",
                   help="hitung yang akan dikerjakan saja; tanpa jaringan, tanpa menulis berkas")
    a.add_argument("--ulang-cadangan", action="store_true",
                   help="coba lagi sampul resmi untuk publikasi yang baru punya cadangan PDF")
    opsi = a.parse_args()

    os.makedirs(perbarui.DIR_LOG, exist_ok=True)
    log = open(os.path.join(perbarui.DIR_LOG, f"isi-sampul-{datetime.now():%Y%m%d-%H%M%S}.log"),
               "w", encoding="utf-8")
    sys.stdout = perbarui.Salin(sys.stdout, log)    # salinan log juga disamarkan

    konfigurasi = KonfigurasiUji if opsi.db_uji else Config
    print(f"Database sumber daftar: {make_url(konfigurasi.SQLALCHEMY_DATABASE_URI).database} "
          f"({'UJI' if opsi.db_uji else 'PRODUKSI'}, hanya dibaca)"
          f"{' - COBA, tanpa jaringan dan tanpa menulis' if opsi.coba else ''}")
    print(f"Folder sampul: {Config.DIR_SAMPUL}")
    if not perbarui.ambil_kunci():
        print("TIDAK DIJALANKAN: pembaruan lain sedang berjalan.")
        sys.exit(2)
    perbarui.jaga_tetap_bangun(True)
    try:
        app = create_app(konfigurasi)
        with app.app_context():
            daftar = (Publikasi.query
                      .with_entities(Publikasi.id, Publikasi.domain, Publikasi.judul,
                                     Publikasi.url_cover)
                      .order_by(Publikasi.domain, Publikasi.id).all())
            db.session.rollback()
        kerja, lewat = [], 0
        for p in daftar:
            if os.path.isfile(sampul.path_resmi(p.id)):
                lewat += 1
            elif sampul.berkas(p.id) and not opsi.ulang_cadangan:
                lewat += 1
            else:
                kerja.append(p)
        tanpa_url = sum(1 for p in kerja if not p.url_cover)
        print(f"{len(daftar)} publikasi; sudah punya berkas (dilewati) {lewat}; "
              f"dikerjakan {len(kerja)} (tanpa url_cover {tanpa_url}); "
              f"perkiraan {len(kerja) * DETIK_PER_SAMPUL / 60:.0f} menit")
        if opsi.coba or not kerja:
            return

        hitung = {"resmi": 0, "cadangan": 0, "cadangan_lama": 0, "gagal": 0}
        total_byte, mulai = 0, time.time()
        for i, p in enumerate(kerja, 1):
            time.sleep(sumber_bps.JEDA_DETIK)   # Term of Use: jeda antar unduhan
            r = sampul.lengkapi(p.id, p.url_cover, sumber_bps.path_pdf(p.domain, p.id))
            hitung[r["hasil"]] += 1
            total_byte += r["byte"]
            rinci = f"{r['byte'] / 1024:.0f} KB" if r["hasil"] == "resmi" else r["hasil"]
            if r["pesan"] and r["hasil"] != "resmi":
                rinci += f" ({r['pesan'][:90]})"
            print(f"[{i}/{len(kerja)}] {p.domain} {p.id[:8]} {p.judul[:44]:<44} {rinci}",
                  flush=True)
        detik = time.time() - mulai
        print("\nRINGKASAN")
        print(f"  berhasil (sampul resmi)      : {hitung['resmi']} ({total_byte / 1e6:.1f} MB)")
        print(f"  cadangan dari halaman 1 PDF  : {hitung['cadangan']}")
        if hitung["cadangan_lama"]:
            print(f"  cadangan lama dipertahankan  : {hitung['cadangan_lama']}")
        print(f"  gagal (tampil tanpa gambar)  : {hitung['gagal']}")
        print(f"  dilewati (sudah ada)         : {lewat}")
        print(f"  waktu                        : {detik / 60:.1f} menit")
        if hitung["gagal"] or hitung["cadangan"]:
            print("  Yang gagal/cadangan dicoba lagi otomatis oleh pembaruan data berikutnya.")
    finally:
        perbarui.jaga_tetap_bangun(False)
        perbarui.lepas_kunci()


if __name__ == "__main__":
    main()
