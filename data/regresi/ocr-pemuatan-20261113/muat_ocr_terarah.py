"""Muat ulang entri HANYA untuk publikasi hasil OCR (RANCANGAN, 13 Nov 2026).

  python muat_ocr_terarah.py <daftar_pid.json> --sasaran uji
  python muat_ocr_terarah.py <daftar_pid.json> --sasaran produksi --produksi-disetujui

Beda dengan `perbarui.py --paksa`: tidak menyentuh 298 publikasi lain, tidak
menarik metadata, tidak mengunduh. Per publikasi: ekstrak_berkas(ocr_aktif=True)
lalu simpan_entri - fungsi yang sama dengan perbarui.py, satu transaksi per
publikasi.

Pengaman:
  - baris pertama = nama database tujuan; produksi butuh --produksi-disetujui;
  - memakai berkas kunci pembaruan yang sama dengan perbarui.py, jadi tidak
    bisa berjalan bersamaan dengan pembaruan lain (web atau .bat);
  - SEBELUM menulis apa pun, semua publikasi diperiksa: PDF ada, memenuhi
    syarat OCR publikasi, dan cache OCR SETIAP halamannya lengkap. Satu saja
    kurang -> berhenti tanpa menulis (pemuatan tidak boleh memicu OCR baru);
  - sesudah ekstraksi, catatan["ocr"]["di_ocr"] harus 0.
"""
import argparse
import importlib.util
import json
import os
import sys

DIR_PROYEK = "C:/sistem-pencarian-bps"
os.chdir(DIR_PROYEK)                     # FILE_KUNCI perbarui.py relatif ke proyek
sys.path.insert(0, DIR_PROYEK)

from sqlalchemy.engine import make_url  # noqa: E402

from app import create_app  # noqa: E402
from app.config import Config, KonfigurasiUji  # noqa: E402
from app.models import Publikasi, db  # noqa: E402
from app.services import ocr, pipeline_data, sumber_bps, versi_data  # noqa: E402

spec = importlib.util.spec_from_file_location("perbarui", os.path.join(DIR_PROYEK, "scripts", "perbarui.py"))
perbarui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(perbarui)        # hanya untuk ambil_kunci / lepas_kunci

arg = argparse.ArgumentParser()
arg.add_argument("daftar")
arg.add_argument("--sasaran", choices=["uji", "produksi"], required=True)
arg.add_argument("--produksi-disetujui", action="store_true")
opsi = arg.parse_args()

konfigurasi = KonfigurasiUji if opsi.sasaran == "uji" else Config
url = make_url(konfigurasi.SQLALCHEMY_DATABASE_URI)
print(f"Database tujuan: {url.database} @ {url.host}:{url.port} "
      f"({'UJI - bukan produksi' if opsi.sasaran == 'uji' else 'PRODUKSI'})")
if opsi.sasaran == "produksi" and not opsi.produksi_disetujui:
    raise SystemExit("Produksi butuh --produksi-disetujui. Tidak dijalankan.")

pid = json.load(open(opsi.daftar, encoding="utf-8"))
app = create_app(konfigurasi)
if not perbarui.ambil_kunci():
    raise SystemExit("TIDAK DIJALANKAN: pembaruan lain sedang berjalan.")
try:
    with app.app_context():
        # 1. Periksa semuanya dulu, tulis belakangan.
        rencana = []
        for p in pid:
            pub = db.session.get(Publikasi, p)
            if pub is None:
                raise SystemExit(f"{p}: tidak ada di database. Tidak ada yang ditulis.")
            path = f"data/publikasi_pdf/{pub.domain}/{p}.pdf"
            halaman, n_kosong, n_hal = ocr.halaman_tanpa_teks(path)
            kurang = [h for h in halaman if not os.path.exists(ocr.berkas_cache(path, h))]
            if not halaman or kurang:
                raise SystemExit(f"{p}: syarat OCR {len(halaman)} hal, cache kurang {len(kurang)}. "
                                 "Tidak ada yang ditulis.")
            rencana.append((p, pub.judul, path, len(halaman), n_hal))
            print(f"  siap  {p}  OCR {len(halaman)}/{n_hal} hal, cache lengkap  {pub.judul[:50]}")

        # 2. Muat, satu transaksi per publikasi.
        versi_data.pastikan_tabel()      # CREATE TABLE memaksa commit: sebelum transaksi penulis
        for p, judul, path, n_ocr, n_hal in rencana:
            sidik = sumber_bps.sidik_pdf(path)
            entri, catatan = pipeline_data.ekstrak_berkas(path, p, ocr_aktif=True)
            if (catatan.get("ocr") or {}).get("di_ocr", 0):
                raise SystemExit(f"{p}: ekstraksi menjalankan OCR baru - dihentikan sebelum disimpan.")
            pipeline_data.simpan_entri(p, entri, sidik, catatan)
            print(f"  muat  {p}  {len(entri)} entri  {judul[:50]}")
finally:
    perbarui.lepas_kunci()
print("Selesai.")
