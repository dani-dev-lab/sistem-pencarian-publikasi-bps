"""Ukur kinerja pencarian dan ukuran data - angka pembanding sebelum/sesudah revisi.

Dibuat untuk menjawab dua pertanyaan tim PST secara terukur:
  1. Apakah waktu pencarian bertambah signifikan setelah data membesar
     (13 kabupaten/kota)?
  2. Seberapa besar data yang disimpan (JSON, PDF, tabel MySQL)?

Tiap kueri dijalankan berulang kali, lalu yang dilaporkan MEDIAN dan P95
(waktu pada 5% kasus terlambat) - satu kali ukur bisa meleset karena hal lain
yang sedang berjalan di laptop. Panggilan pertama dibuang sebagai pemanasan
(memuat kamus dan cache stemmer).

Waktu dipecah dua supaya kelihatan bagian mana yang membesar:
  - ambil korpus : query SELECT seluruh entri dari MySQL
  - total cari() : ambil korpus + normalisasi + skor + urutkan

Hasil ditulis ke data/ukur_kinerja/<tanggal>-<label>.json. Jalankan dengan
label berbeda sebelum dan sesudah revisi, lalu bandingkan kedua berkasnya.

TIDAK menulis ke log_pencarian (memanggil cari() langsung, bukan lewat
halaman /hasil), jadi log kueri petugas tidak tercemar kueri uji.

Jalankan:  venv/Scripts/python.exe scripts/ukur_kinerja.py --label sebelum
           venv/Scripts/python.exe scripts/ukur_kinerja.py --label sesudah --ulang 30
"""

import argparse
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime

DIR_PROYEK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR_PROYEK)

import sqlalchemy as sa

from app import create_app
from app.models import EntriDokumen, Publikasi, db
from app.services import mesin_pencari
from app.services.mesin_pencari import cari

DIR_HASIL = os.path.join(DIR_PROYEK, "data", "ukur_kinerja")

# Kueri uji yang sama dengan scripts/uji_pencarian.py, ditambah kueri bernama
# wilayah - jenis kueri yang akan banyak muncul setelah 13 kabupaten/kota
# masuk. Daftar ini JANGAN diubah antara pengukuran sebelum dan sesudah,
# kalau tidak perbandingannya tidak adil.
KUERI = [
    "statistik ekspor impor",
    "negara tujuan ekspor",
    "banyaknya akomodasi kabupaten kota",
    "jumlah hotel kabupaten kota 2024",
    "tingkat penghunian kamar",
    "tpk",
    "penduduk miskin",
    "population by regency",
    "ekspor batubara",
    "jumlah penduduk menurut kecamatan",
    "penduduk tanah laut",
    "luas panen padi kotabaru",
]


def ringkas(sampel_ms):
    urut = sorted(sampel_ms)
    # P95 dengan metode "nearest rank": cukup untuk 20-30 sampel, dan mudah
    # dijelaskan (nilai ke-ceil(0,95*n) setelah diurutkan).
    idx = max(0, -(-95 * len(urut) // 100) - 1)
    return {
        "median_ms": round(statistics.median(urut), 1),
        "p95_ms": round(urut[idx], 1),
        "min_ms": round(urut[0], 1),
        "maks_ms": round(urut[-1], 1),
    }


def ukur(fungsi, ulang):
    sampel = []
    for _ in range(ulang):
        mulai = time.perf_counter()
        fungsi()
        sampel.append((time.perf_counter() - mulai) * 1000)
    return sampel


def ukuran_berkas():
    data = os.path.join(DIR_PROYEK, "data")
    json_ = {n: os.path.getsize(os.path.join(data, n))
             for n in sorted(os.listdir(data)) if n.endswith(".json")}
    dir_pdf = os.path.join(data, "publikasi_pdf")
    pdf = [os.path.getsize(os.path.join(dir_pdf, n))
           for n in os.listdir(dir_pdf) if n.lower().endswith(".pdf")] \
        if os.path.isdir(dir_pdf) else []
    return {
        "json_bytes": json_,
        "json_total_bytes": sum(json_.values()),
        "pdf_jumlah": len(pdf),
        "pdf_total_bytes": sum(pdf),
    }


def ukuran_tabel():
    """Ukuran tiap tabel MySQL (data + indeks).

    ANALYZE TABLE dulu: MySQL 8 menyimpan statistik information_schema di
    cache sampai 24 jam, jadi tanpa ini angkanya bisa angka kemarin.
    """
    with db.engine.connect() as c:
        nama = [r[0] for r in c.execute(sa.text(
            "SELECT TABLE_NAME FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE()"))]
        for n in nama:
            c.execute(sa.text(f"ANALYZE TABLE `{n}`")).fetchall()
        baris = c.execute(sa.text(
            "SELECT TABLE_NAME, DATA_LENGTH, INDEX_LENGTH "
            "FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() "
            "ORDER BY TABLE_NAME")).fetchall()
    return {t: {"data_bytes": int(d or 0), "indeks_bytes": int(i or 0)}
            for t, d, i in baris}


def mb(n):
    return f"{n / 1024 / 1024:,.1f} MB"


def main():
    arg = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    arg.add_argument("--label", default="ukur",
                     help="Penanda pengukuran, misalnya 'sebelum' atau 'sesudah'.")
    arg.add_argument("--ulang", type=int, default=20,
                     help="Berapa kali tiap kueri dijalankan (default 20).")
    opsi = arg.parse_args()

    app = create_app()
    with app.app_context():
        n_pub = Publikasi.query.count()
        n_entri = EntriDokumen.query.count()

        print(f"Data      : {n_pub} publikasi, {n_entri} entri")
        print(f"Ulangan   : {opsi.ulang} kali per kueri (+1 pemanasan)")
        print()

        cari("pemanasan")   # muat kamus + cache stemmer, tidak dihitung

        korpus = ringkas(ukur(mesin_pencari._ambil_korpus, opsi.ulang))
        print(f"Ambil korpus dari MySQL: median {korpus['median_ms']} ms, "
              f"p95 {korpus['p95_ms']} ms")
        print()
        print(f"{'kueri':<38}{'median':>9}{'p95':>9}{'dinilai':>9}{'hasil':>7}")
        print("-" * 72)

        per_kueri = []
        for k in KUERI:
            hasil = cari(k)
            r = ringkas(ukur(lambda k=k: cari(k), opsi.ulang))
            r.update(kueri=k, dinilai=hasil["jumlah_dinilai"],
                     hasil=len(hasil["ditemukan"]) + len(hasil["saran"]),
                     publikasi=len(hasil["publikasi"]))
            per_kueri.append(r)
            print(f"{k[:37]:<38}{r['median_ms']:>7.0f}ms{r['p95_ms']:>7.0f}ms"
                  f"{r['dinilai']:>9}{r['hasil']:>7}")

        semua_median = [r["median_ms"] for r in per_kueri]
        semua_p95 = [r["p95_ms"] for r in per_kueri]
        print("-" * 72)
        print(f"{'RATA-RATA':<38}{statistics.mean(semua_median):>7.0f}ms"
              f"{statistics.mean(semua_p95):>7.0f}ms")
        print(f"{'TERLAMBAT':<38}{max(semua_median):>7.0f}ms{max(semua_p95):>7.0f}ms")

        berkas = ukuran_berkas()
        tabel = ukuran_tabel()

    print()
    print("Ukuran penyimpanan:")
    print(f"  JSON di data/        : {mb(berkas['json_total_bytes'])}")
    for n, b in berkas["json_bytes"].items():
        print(f"      {n:<40}{mb(b):>12}")
    print(f"  PDF ({berkas['pdf_jumlah']} berkas)      : {mb(berkas['pdf_total_bytes'])}")
    total_db = sum(t["data_bytes"] + t["indeks_bytes"] for t in tabel.values())
    print(f"  Tabel MySQL          : {mb(total_db)}")
    for n, t in tabel.items():
        print(f"      {n:<40}{mb(t['data_bytes'] + t['indeks_bytes']):>12}")

    sekarang = datetime.now()
    keluaran = {
        "label": opsi.label,
        "diukur_pada": sekarang.isoformat(timespec="seconds"),
        "lingkungan": {
            "komputer": platform.node(),
            "os": platform.platform(),
            "prosesor": platform.processor(),
            "python": platform.python_version(),
        },
        "data": {"publikasi": n_pub, "entri": n_entri},
        "ulang": opsi.ulang,
        "ambil_korpus": korpus,
        "per_kueri": per_kueri,
        "rata_rata_median_ms": round(statistics.mean(semua_median), 1),
        "rata_rata_p95_ms": round(statistics.mean(semua_p95), 1),
        "berkas": berkas,
        "tabel_mysql": tabel,
    }
    os.makedirs(DIR_HASIL, exist_ok=True)
    nama = f"{sekarang:%Y%m%d-%H%M}-{opsi.label}.json"
    with open(os.path.join(DIR_HASIL, nama), "w", encoding="utf-8") as f:
        json.dump(keluaran, f, ensure_ascii=False, indent=2)
    print()
    print(f"Hasil -> data/ukur_kinerja/{nama}")


if __name__ == "__main__":
    main()
