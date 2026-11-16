"""Isi halaman fisik PERKIRAAN untuk entri yang sudah ada di database.

Entri baru mendapat perkiraannya sendiri saat dimuat (pipeline_data.simpan_entri).
Skrip ini untuk data yang dimuat sebelum fitur itu ada (16 Nov 2026), dan aman
dijalankan ulang kapan saja. Aturannya ada di app/services/perkiraan_halaman.py.

Yang dijamin:
  - hanya baris yang halaman_fisik-nya KOSONG atau yang memang perkiraan yang
    disentuh; halaman fisik hasil baca PDF tidak pernah diubah;
  - IDEMPOTEN: perkiraan lama dihitung ulang dari jangkar yang sama, jadi run
    kedua tidak mengubah apa pun;
  - satu transaksi, bersama kenaikan versi_data (korpus pencarian dimuat ulang).

Database tujuan WAJIB disebut, supaya produksi tidak tersentuh tanpa sengaja:

    venv/Scripts/python.exe scripts/isi_perkiraan_halaman.py --db-uji
    venv/Scripts/python.exe scripts/isi_perkiraan_halaman.py --produksi
    ... --coba     hitung dan laporkan saja, tanpa menulis

Kode keluar: 0 selesai, 1 galat, 2 pembaruan lain sedang berjalan.
"""

import argparse
import os
import sys
from collections import Counter, defaultdict

DIR_PROYEK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR_PROYEK)
sys.path.insert(0, os.path.join(DIR_PROYEK, "scripts"))

from sqlalchemy.engine import make_url  # noqa: E402

from app import create_app  # noqa: E402
from app.config import Config, KonfigurasiUji  # noqa: E402
from app.models import EntriDokumen, db  # noqa: E402
from app.services import versi_data  # noqa: E402
from app.services.perkiraan_halaman import TIPE_DIPERKIRAKAN, perkirakan  # noqa: E402
import perbarui  # noqa: E402  (kunci dan pastikan_skema yang sama dengan pembaruan)


def isi(cetak=print, tulis=True):
    """Hitung ulang perkiraan seluruh publikasi. Return dict ringkasan."""
    per_pub = defaultdict(list)
    for e in EntriDokumen.query.order_by(EntriDokumen.publikasi_id, EntriDokumen.id).all():
        per_pub[e.publikasi_id].append(e)

    n = Counter()
    per_tipe = Counter()
    sisa_kosong = Counter()
    for pub_id, entri in per_pub.items():
        # Perkiraan lama dianggap kosong: dihitung ulang dari jangkar asli.
        data = [{"tipe": e.tipe, "halaman": e.halaman,
                 "halaman_fisik": None if e.halaman_fisik_perkiraan else e.halaman_fisik}
                for e in entri]
        baru = perkirakan(data)
        for i, e in enumerate(entri):
            if e.halaman_fisik_perkiraan:
                if i not in baru:
                    e.halaman_fisik, e.halaman_fisik_perkiraan = None, False
                    n["dikosongkan"] += 1
                elif baru[i] != e.halaman_fisik:
                    e.halaman_fisik = baru[i]
                    n["diubah"] += 1
                else:
                    n["tetap"] += 1
            elif i in baru:
                e.halaman_fisik, e.halaman_fisik_perkiraan = baru[i], True
                n["diisi"] += 1
            if i in baru:
                per_tipe[e.tipe] += 1
            elif e.tipe in TIPE_DIPERKIRAKAN and not e.halaman_fisik:
                sisa_kosong["tanpa halaman cetak" if not e.halaman else "tidak diperkirakan"] += 1

    berubah = n["diisi"] + n["diubah"] + n["dikosongkan"]
    if tulis and berubah:
        versi_data.naikkan()
        db.session.commit()
    else:
        db.session.rollback()

    cetak(f"Publikasi           : {len(per_pub)}")
    cetak(f"Perkiraan sekarang  : {sum(per_tipe.values())}  "
          + ", ".join(f"{t} {per_tipe[t]}" for t in TIPE_DIPERKIRAKAN))
    cetak(f"  baru diisi        : {n['diisi']}")
    cetak(f"  perkiraan diubah  : {n['diubah']}")
    cetak(f"  perkiraan dihapus : {n['dikosongkan']}")
    cetak(f"  perkiraan tetap   : {n['tetap']}")
    cetak("Tabel/gambar/lampiran masih tanpa halaman fisik: "
          + ", ".join(f"{k} {v}" for k, v in sorted(sisa_kosong.items())))
    cetak("DITULIS ke database." if tulis and berubah
          else "Tidak ada yang ditulis (--coba)." if not tulis else "Tidak ada yang berubah.")
    return {"per_tipe": dict(per_tipe), **n, "sisa_kosong": dict(sisa_kosong)}


def main():
    arg = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    tujuan = arg.add_mutually_exclusive_group(required=True)
    tujuan.add_argument("--db-uji", action="store_true", help="database uji (KonfigurasiUji)")
    tujuan.add_argument("--produksi", action="store_true", help="database produksi")
    arg.add_argument("--coba", action="store_true", help="hitung saja, tanpa menulis")
    opsi = arg.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    konfigurasi = KonfigurasiUji if opsi.db_uji else Config
    url = make_url(konfigurasi.SQLALCHEMY_DATABASE_URI)
    print(f"Database tujuan: {url.database} @ {url.host or '-'}:{url.port or '-'}"
          f" ({'UJI - bukan produksi' if opsi.db_uji else 'PRODUKSI'})")

    os.chdir(DIR_PROYEK)
    if not perbarui.ambil_kunci():
        print(f"TIDAK DIJALANKAN: pembaruan lain sedang berjalan "
              f"(PID {perbarui.pembaruan_sedang_berjalan()}).")
        sys.exit(2)
    try:
        app = create_app(konfigurasi)
        with app.app_context():
            perbarui.pastikan_skema()       # kolom baru, SEBELUM transaksi
            isi(tulis=not opsi.coba)
    finally:
        perbarui.lepas_kunci()


if __name__ == "__main__":
    main()
