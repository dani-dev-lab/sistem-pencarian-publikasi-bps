"""Uji parser produksi terhadap 5 sampel, bandingkan dengan hasil spike lama.

Fokus pada dua kegagalan yang tercatat di CLAUDE.md:
  1. 05_pdrb GAGAL TOTAL di spike (layout dua kolom) - apakah sekarang berisi?
  2. Penggabungan multi-baris: apakah judul yang membungkus tergabung penuh?
     (Lampiran 3 perhotelan, yang memang membungkus ke baris kedua)

Jalankan:  venv/Scripts/python.exe scripts/uji_ekstraksi.py
"""

import glob
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ekstraksi_pdf import ekstrak_struktur

DIR_SAMPEL = "data/sampel_pdf"
FILE_SPIKE = "data/hasil_spike.json"


def muat_spike():
    """Ringkas hasil spike lama jadi {nama_file: {tipe: jumlah_entri}}."""
    if not os.path.exists(FILE_SPIKE):
        return {}
    with open(FILE_SPIKE, encoding="utf-8") as f:
        data = json.load(f)
    return {h["file"]: {t: d["jumlah"] for t, d in h["entri"].items()} for h in data}


def main():
    spike = muat_spike()
    daftar = sorted(glob.glob(os.path.join(DIR_SAMPEL, "*.pdf")))
    if not daftar:
        print(f"Tidak ada PDF di {DIR_SAMPEL}/")
        return

    total_baru = 0
    total_lama = 0
    semua_entri = {}

    for path in daftar:
        nama = os.path.basename(path)
        pub_id = os.path.splitext(nama)[0]
        entri = ekstrak_struktur(path, pub_id)
        semua_entri[nama] = entri

        per_tipe = Counter(e["tipe"] for e in entri)
        lama = spike.get(nama, {})

        print()
        print("=" * 78)
        print(nama)
        print("=" * 78)
        print(f"  {'tipe':<10} {'spike lama':>12} {'parser baru':>12}   selisih")
        for tipe in ("isi", "tabel", "gambar", "lampiran"):
            n_lama = lama.get(tipe, 0)
            n_baru = per_tipe.get(tipe, 0)
            if not n_lama and not n_baru:
                continue
            selisih = n_baru - n_lama
            tanda = f"{selisih:+d}" if selisih else "sama"
            print(f"  {tipe:<10} {n_lama:>12} {n_baru:>12}   {tanda}")
            total_lama += n_lama
            total_baru += n_baru

        # Mutu hasil: entri dianggap utuh kalau judul dan halaman terisi.
        utuh = sum(1 for e in entri if e["judul"] and e["halaman"])
        tanpa_halaman = [e for e in entri if not e["halaman"]]
        print(f"  -> {len(entri)} entri, {utuh} punya judul + halaman, "
              f"{len(tanpa_halaman)} tanpa nomor halaman")

        for e in entri[:3]:
            nomor = f"{e['nomor']} " if e["nomor"] else ""
            print(f"     [{e['tipe']}] {nomor}{e['judul'][:62]} | hal {e['halaman']}")

    # ---------------- Pemeriksaan dua kegagalan spike ----------------
    print()
    print("=" * 78)
    print("PEMERIKSAAN KEGAGALAN SPIKE")
    print("=" * 78)

    # 1. PDRB: dulu 0 entri untuk tabel & gambar.
    pdrb = next((n for n in semua_entri if "pdrb" in n.lower()), None)
    print()
    print("1. 05_pdrb (dulu GAGAL TOTAL: 0 entri tabel & gambar)")
    if pdrb:
        per_tipe = Counter(e["tipe"] for e in semua_entri[pdrb])
        lama = spike.get(pdrb, {})
        for tipe in ("tabel", "gambar"):
            print(f"   {tipe:<8} spike={lama.get(tipe, 0):>3}  "
                  f"baru={per_tipe.get(tipe, 0):>3}  "
                  f"{'BERHASIL' if per_tipe.get(tipe, 0) else 'MASIH KOSONG'}")
        for e in semua_entri[pdrb]:
            if e["tipe"] == "tabel":
                print(f"   contoh: {e['nomor']} {e['judul'][:56]} | hal {e['halaman']}")
                break
    else:
        print("   file PDRB tidak ada di sampel")

    # 2. Penggabungan multi-baris: Lampiran 3 perhotelan memang membungkus ke
    #    baris kedua ("...pada Hotel Bintang" / "dan Nonbintang Menurut Bulan,
    #    2023-2025 ... 21"). Lampiran 1 TIDAK dipakai sebagai acuan: di edisi
    #    2025 judulnya memang berhenti di "Klasifikasi" - satu baris utuh.
    print()
    print("2. Penggabungan multi-baris: Lampiran 3 perhotelan")
    hotel = next((n for n in semua_entri if "perhotelan" in n.lower()), None)
    if hotel:
        lamp3 = next((e for e in semua_entri[hotel]
                      if e["tipe"] == "lampiran" and e["nomor"] == "3"), None)
        if lamp3:
            judul = lamp3["judul"]
            print(f"   judul   : {judul}")
            print(f"   halaman : {lamp3['halaman']}")
            # Potongan baris kedua harus ikut tergabung, bukan berhenti di
            # "...pada Hotel Bintang".
            tergabung = "nonbintang" in judul.lower() and "bulan" in judul.lower()
            print(f"   {'TERGABUNG (baris 2 ikut)' if tergabung else 'MASIH TERPOTONG'}")
        else:
            print("   Lampiran 3 tidak ditemukan")
    else:
        print("   file perhotelan tidak ada di sampel")

    print()
    print("=" * 78)
    print(f"TOTAL entri: spike lama {total_lama} -> parser baru {total_baru} "
          f"({total_baru - total_lama:+d})")


if __name__ == "__main__":
    main()
