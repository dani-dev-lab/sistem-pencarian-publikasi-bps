"""Salin publikasi Kecamatan Dalam Angka dari DATABASE UJI ke PRODUKSI (19 Nov 2026).

  python muat_kecamatan_terarah.py --coba                  # transaksi lalu ROLLBACK
  python muat_kecamatan_terarah.py --produksi-disetujui    # transaksi lalu COMMIT

Rencana disetujui pemilik project: data/regresi/rencana-muat-kecamatan-20261119.md.
- Sumber: publikasi berkolom `kecamatan` terisi di database uji, beserta entrinya,
  persis seperti yang sudah dinilai (sampel, regresi, uji_pipeline).
- SATU transaksi: INSERT publikasi (id = pub_id BPS) + INSERT entri_dokumen
  (tanpa id, urutan id sumber) + publikasi_kategori + versi_data naik 1.
  Aplikasi yang berjalan melihat semua atau tidak sama sekali.
- Pengaman sebelum menulis: kunci pembaruan (sama dengan perbarui.py), 0 target
  sudah ada di produksi, himpunan kolom produksi = database uji, jumlah sesuai
  sidik sumber yang dicatat di langkah 0.
"""
import argparse
import importlib.util
import os
import sys

DIR = "C:/sistem-pencarian-bps"
os.chdir(DIR)
sys.path.insert(0, DIR)
sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.config import Config, KonfigurasiUji  # noqa: E402

HARAP_PUBLIKASI, HARAP_ENTRI = 312, 19955      # sidik sumber, langkah 0

spec = importlib.util.spec_from_file_location("perbarui", os.path.join(DIR, "scripts", "perbarui.py"))
perbarui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(perbarui)               # hanya ambil_kunci / lepas_kunci

a = argparse.ArgumentParser()
g = a.add_mutually_exclusive_group(required=True)
g.add_argument("--coba", action="store_true")
g.add_argument("--produksi-disetujui", action="store_true")
opsi = a.parse_args()

PROD = make_url(Config.SQLALCHEMY_DATABASE_URI).database
UJI = make_url(KonfigurasiUji.SQLALCHEMY_DATABASE_URI).database
assert PROD != UJI and UJI.endswith("_uji")
print(f"Tujuan: {PROD} (PRODUKSI) | sumber: {UJI} | mode: {'COBA (rollback)' if opsi.coba else 'MUAT (commit)'}")

mesin = create_engine(Config.SQLALCHEMY_DATABASE_URI)


def kolom(k, db, tabel):
    return [r[0] for r in k.execute(text(
        "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=:d AND TABLE_NAME=:t "
        "ORDER BY ORDINAL_POSITION"), {"d": db, "t": tabel})]


if not perbarui.ambil_kunci():
    raise SystemExit("TIDAK DIJALANKAN: pembaruan lain sedang berjalan.")
try:
    with mesin.connect() as k:
        tx = k.begin()
        try:
            for t in ("publikasi", "entri_dokumen", "publikasi_kategori"):
                kp, ku = kolom(k, PROD, t), kolom(k, UJI, t)
                if set(kp) != set(ku):
                    raise SystemExit(f"Kolom {t} berbeda: produksi-uji {set(kp) ^ set(ku)}. Tidak ada yang ditulis.")
            target = [r[0] for r in k.execute(text(f"SELECT id FROM `{UJI}`.publikasi WHERE kecamatan IS NOT NULL"))]
            sudah = k.execute(text(f"SELECT COUNT(*) FROM `{PROD}`.publikasi p JOIN `{UJI}`.publikasi u "
                                   "ON u.id = p.id WHERE u.kecamatan IS NOT NULL")).scalar()
            n_entri_sumber = k.execute(text(f"SELECT COUNT(*) FROM `{UJI}`.entri_dokumen e JOIN `{UJI}`.publikasi p "
                                            "ON p.id = e.publikasi_id WHERE p.kecamatan IS NOT NULL")).scalar()
            print(f"target {len(target)} publikasi, {n_entri_sumber} entri; sudah di produksi: {sudah}")
            if sudah or len(target) != HARAP_PUBLIKASI or n_entri_sumber != HARAP_ENTRI:
                raise SystemExit("Pengaman gagal (target sudah ada / jumlah tidak sama dengan sidik sumber). "
                                 "Tidak ada yang ditulis.")

            kol_pub = ", ".join(f"`{c}`" for c in kolom(k, PROD, "publikasi"))
            n_pub = k.execute(text(
                f"INSERT INTO `{PROD}`.publikasi ({kol_pub}) SELECT {kol_pub} FROM `{UJI}`.publikasi "
                "WHERE kecamatan IS NOT NULL ORDER BY id")).rowcount
            kol_e = [c for c in kolom(k, PROD, "entri_dokumen") if c != "id"]
            kol_e_s = ", ".join(f"`{c}`" for c in kol_e)
            kol_e_e = ", ".join(f"e.`{c}`" for c in kol_e)
            n_entri = k.execute(text(
                f"INSERT INTO `{PROD}`.entri_dokumen ({kol_e_s}) SELECT {kol_e_e} FROM `{UJI}`.entri_dokumen e "
                f"JOIN `{UJI}`.publikasi p ON p.id = e.publikasi_id WHERE p.kecamatan IS NOT NULL ORDER BY e.id")).rowcount
            kol_pk = ", ".join(f"`{c}`" for c in kolom(k, PROD, "publikasi_kategori"))
            n_pk = k.execute(text(
                f"INSERT INTO `{PROD}`.publikasi_kategori ({kol_pk}) SELECT {', '.join('pk.' + c for c in kol_pk.split(', '))} "
                f"FROM `{UJI}`.publikasi_kategori pk JOIN `{UJI}`.publikasi p ON p.id = pk.publikasi_id "
                "WHERE p.kecamatan IS NOT NULL")).rowcount
            k.execute(text(f"UPDATE `{PROD}`.versi_data SET versi = versi + 1, diubah = UTC_TIMESTAMP() WHERE id = 1"))
            versi = k.execute(text(f"SELECT versi FROM `{PROD}`.versi_data WHERE id = 1")).scalar()
            print(f"disisipkan: publikasi {n_pub}, entri {n_entri}, publikasi_kategori {n_pk}; versi_data -> {versi}")
            if n_pub != HARAP_PUBLIKASI or n_entri != HARAP_ENTRI:
                raise SystemExit("Jumlah sisipan tidak sesuai. ROLLBACK.")
            if opsi.coba:
                tx.rollback()
                print("COBA: ROLLBACK, tidak ada yang tersimpan.")
            else:
                tx.commit()
                print("MUAT: COMMIT.")
        except BaseException:
            if tx.is_active:
                tx.rollback()
            raise
finally:
    perbarui.lepas_kunci()
