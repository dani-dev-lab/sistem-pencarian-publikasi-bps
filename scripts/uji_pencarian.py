"""Uji mesin pencari dengan skenario nyata, untuk mengalibrasi ambang skor.

Bukan unit test - ini alat lihat-hasil. Tujuannya menilai apakah ambang 80/40
di CLAUDE.md masuk akal terhadap data sebenarnya, atau perlu digeser.

Jalankan:  venv/Scripts/python.exe scripts/uji_pencarian.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.mesin_pencari import AMBANG_DITEMUKAN, AMBANG_SARAN, cari

SKENARIO = [
    ("statistik ekspor impor", "harus memunculkan PUBLIKASI-nya"),
    ("negara tujuan ekspor", "istilah dari abstrak, bukan judul"),
    ("banyaknya akomodasi kabupaten kota", "contoh dari mentor"),
    ("jumlah hotel kabupaten kota 2024", "kata berbeda, konsep sama"),
    ("akomodasi kabupaten kota", "kueri tidak lengkap"),
    ("tingkat penghunian kamar", "harus ketemu TPK"),
    ("tpk", "akronim langsung"),
    ("penduduk miskin", "topik umum"),
    ("population by regency", "kueri Inggris"),
    ("ekspor batubara", "uji negatif - mungkin tidak ada"),
]

TOP = 5


def cetak(hasil):
    if hasil["publikasi"]:
        print(f"  PUBLIKASI ({len(hasil['publikasi'])}):")
        for p in hasil["publikasi"][:3]:
            rilis = p["tanggal_rilis"].year if p["tanggal_rilis"] else "-"
            print(f"    [{p['skor']:>5.1f} via {p['sumber_skor']:<13}] "
                  f"{p['judul'][:52]} ({rilis}, {p['jumlah_entri']} bagian)")
    else:
        print("  PUBLIKASI: tidak ada")

    print(f"  ternormalisasi : {hasil['kueri_ternormalisasi']!r}")
    print(f"  dinilai        : {hasil['jumlah_dinilai']} dari "
          f"{hasil['jumlah_entri']} entri")
    print(f"  waktu          : {hasil['waktu_ms']:.0f} ms")
    print(f"  ditemukan (>={AMBANG_DITEMUKAN}) : {len(hasil['ditemukan'])}   "
          f"saran ({AMBANG_SARAN}-{AMBANG_DITEMUKAN - 1}) : {len(hasil['saran'])}")

    gabungan = (hasil["ditemukan"] + hasil["saran"])[:TOP]
    if not gabungan:
        print("  -> tidak ada hasil di atas ambang")
        return

    print()
    for i, h in enumerate(gabungan, 1):
        label = "DITEMUKAN" if h["skor"] >= AMBANG_DITEMUKAN else "saran"
        nomor = h["nomor"] or "-"
        halaman = h["halaman"] or "-"
        rilis = h["tanggal_rilis"].isoformat() if h["tanggal_rilis"] else "-"
        print(f"   {i}. [{h['skor']:>5.1f} {label:<9}] "
              f"{h['tipe']:<8} nomor={nomor:<7} hal={halaman:<5}")
        print(f"      {h['judul'][:78]}")
        print(f"      dari: {h['judul_publikasi'][:58]} (rilis {rilis})")
        print(f"      set={h["skor_set"]:<5.1f} sort={h["skor_sort"]:<5.1f} cov={h["skor_coverage"]:<5.1f} panjang={h["panjang_entri"]}")


def main():
    app = create_app()
    with app.app_context():
        # Panggilan pertama sekaligus memanaskan cache stemmer.
        cari("pemanasan")

        total_ms = 0
        for kueri, catatan in SKENARIO:
            print()
            print("=" * 80)
            print(f"KUERI: {kueri!r}   ({catatan})")
            print("=" * 80)
            hasil = cari(kueri)
            total_ms += hasil["waktu_ms"]
            cetak(hasil)

        print()
        print("=" * 80)
        print(f"Rata-rata waktu per kueri: {total_ms / len(SKENARIO):.0f} ms")


if __name__ == "__main__":
    main()
