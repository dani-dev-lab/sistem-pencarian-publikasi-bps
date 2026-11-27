"""Muat ulang 5 publikasi PRODUKSI yang membaik oleh parser pola 2+3 (19 Nov 2026).

  python muat_pola23_terarah.py --coba
  python muat_pola23_terarah.py --produksi-disetujui

Rencana langkah 5 (disetujui pemilik project). Publikasi: berubah_produksi.json
dari regresi penuh 18 Nov (SHK, IHK, PDRB Banjar dua edisi, PDRB Tabalong).
Tiap publikasi memakai fungsi yang sama dengan perbarui.py: ekstrak_berkas lalu
simpan_entri (perkiraan halaman dihitung ulang, versi_data naik), SATU transaksi
per publikasi.

Pemeriksaan (juga dengan --coba; tidak menulis apa pun):
  - publikasi ada di produksi, PDF utuh, sidik PDF = yang tercatat di produksi
    DAN di database uji;
  - entri produksi sekarang = potret database uji SEBELUM regresi (isi, urut):
    keadaan awalnya seperti yang diharapkan;
  - hasil ekstraksi kode sekarang = entri database uji sekarang (isi, urut).
Satu beda -> berhenti sebelum menulis publikasi itu.
"""
import argparse
import importlib.util
import json
import os
import sys

DIR = "C:/sistem-pencarian-bps"
os.chdir(DIR)
sys.path.insert(0, DIR)
sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import create_engine, text  # noqa: E402

from app import create_app  # noqa: E402
from app.config import KonfigurasiUji  # noqa: E402
from app.models import Publikasi, db  # noqa: E402
from app.services import perkiraan_halaman, pipeline_data, sumber_bps  # noqa: E402

REG = f"{DIR}/data/regresi/kecamatan-parser-20261118"
TARGET = json.load(open(f"{REG}/berubah_produksi.json"))
AWAL = json.load(open(f"{REG}/potret_awal.json", encoding="utf-8"))      # database uji sebelum regresi
KOLOM = ("tipe", "nomor", "judul", "halaman", "halaman_fisik", "halaman_fisik_perkiraan", "sumber")

spec = importlib.util.spec_from_file_location("perbarui", f"{DIR}/scripts/perbarui.py")
perbarui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(perbarui)

a = argparse.ArgumentParser()
g = a.add_mutually_exclusive_group(required=True)
g.add_argument("--coba", action="store_true")
g.add_argument("--produksi-disetujui", action="store_true")
opsi = a.parse_args()


def norm(baris):
    return [tuple(str(r[k]) if r[k] is not None else None for k in KOLOM) for r in baris]


def entri_db(koneksi, p):
    return norm([dict(r._mapping) for r in koneksi.execute(text(
        "SELECT tipe, nomor, judul, halaman, halaman_fisik, halaman_fisik_perkiraan, sumber "
        "FROM entri_dokumen WHERE publikasi_id = :p ORDER BY id"), {"p": p})])


uji = create_engine(KonfigurasiUji.SQLALCHEMY_DATABASE_URI)
app = create_app()
if not perbarui.ambil_kunci():
    raise SystemExit("TIDAK DIJALANKAN: pembaruan lain sedang berjalan.")
try:
    with app.app_context(), uji.connect() as ku:
        print(f"Tujuan: {db.engine.url.database} | mode: {'COBA' if opsi.coba else 'MUAT'} | {len(TARGET)} publikasi")
        for p in TARGET:
            pub = db.session.get(Publikasi, p)
            if pub is None:
                raise SystemExit(f"{p}: tidak ada di produksi. Berhenti.")
            path = f"data/publikasi_pdf/{pub.domain}/{p}.pdf"
            sidik = sumber_bps.sidik_pdf(path)
            su = ku.execute(text("SELECT sidik_ukuran, sidik_mtime FROM publikasi WHERE id=:p"), {"p": p}).one()
            if not sumber_bps.berkas_pdf_valid(path) or sidik != (pub.sidik_ukuran, pub.sidik_mtime) or sidik != tuple(su):
                raise SystemExit(f"{p}: PDF/sidik tidak cocok (berkas {sidik}, produksi "
                                 f"{(pub.sidik_ukuran, pub.sidik_mtime)}, uji {tuple(su)}). Berhenti.")
            sekarang = entri_db(db.session, p)
            if sekarang != norm(AWAL[p]):
                raise SystemExit(f"{p}: entri produksi != potret uji sebelum regresi. Berhenti.")
            entri, catatan = pipeline_data.ekstrak_berkas(path, p, ocr_aktif=True, log=lambda *x, **y: None)
            if (catatan.get("ocr") or {}).get("di_ocr", 0):
                raise SystemExit(f"{p}: ekstraksi menjalankan OCR baru. Berhenti.")
            prk = perkiraan_halaman.perkirakan(entri)
            hasil = norm([{"tipe": e["tipe"], "nomor": e.get("nomor"), "judul": e["judul"],
                           "halaman": e.get("halaman"), "halaman_fisik": e.get("halaman_fisik") or prk.get(i),
                           "halaman_fisik_perkiraan": int(i in prk), "sumber": e.get("sumber", "daftar")}
                          for i, e in enumerate(entri)])
            target_uji = entri_db(ku, p)
            if hasil != target_uji:
                raise SystemExit(f"{p}: hasil ekstraksi != database uji. Berhenti sebelum menulis.")
            print(f"  {p[:8]} {pub.judul[:55]}: {len(sekarang)} -> {len(hasil)} entri, = database uji")
            if not opsi.coba:
                pipeline_data.simpan_entri(p, entri, sidik, catatan)
                if entri_db(db.session, p) != target_uji:
                    raise SystemExit(f"{p}: sesudah simpan != database uji. Berhenti.")
                print("     dimuat")
        db.session.rollback()
finally:
    perbarui.lepas_kunci()
print("Selesai.")
