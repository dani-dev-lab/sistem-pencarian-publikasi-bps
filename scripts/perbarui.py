"""Perbarui data dari WebAPI BPS sampai siap dicari - satu perintah.

Menjalankan empat tahap berurutan:
  1. ambil metadata publikasi   (scripts/ambil_publikasi.py)
  2. unduh PDF yang belum ada   (scripts/unduh_pdf.py)
  3. ekstrak struktur dokumen   (scripts/ekstrak_semua.py, inkremental)
  4. muat ke database           (scripts/muat_ke_database.py, + normalisasi)

Kalau satu tahap gagal, proses BERHENTI di situ. Melanjutkan dengan data
setengah jadi jauh lebih berbahaya daripada berhenti dengan pesan jelas -
misalnya memuat metadata baru tanpa PDF-nya akan membuat entri hilang dari
pencarian tanpa ada yang menyadari.

Jalankan:  venv/Scripts/python.exe scripts/perbarui.py
           venv/Scripts/python.exe scripts/perbarui.py --paksa
"""

import argparse
import json
import os
import subprocess
import sys
import time

DIR_PROYEK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR_PROYEK)

FILE_META = "data/publikasi_2025_2026.json"
FILE_EKSTRAKSI = "data/hasil_ekstraksi.json"
DIR_PDF = "data/publikasi_pdf"

PESAN_JARINGAN = """
  WebAPI BPS tidak bisa dihubungi.

  Penyebab paling umum: laptop tidak tersambung ke jaringan "BPS - Pegawai".
  Jaringan "BPS - Tamu" MEMBLOKIR akses ke webapi.bps.go.id.

  Periksa koneksi lalu jalankan ulang perintah ini.
"""

# Penanda kegagalan jaringan pada keluaran tahap pengambilan data.
JEJAK_JARINGAN = (
    "connection", "timed out", "timeout", "getaddrinfo", "name resolution",
    "max retries", "connectionerror", "unreachable", "refused",
)


def baca_json(path, bawaan=None):
    if not os.path.exists(path):
        return bawaan
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return bawaan


def daftar_pub(meta):
    return (meta or {}).get("publikasi", [])


def entri_per_pub(hasil):
    """{pub_id: jumlah_entri} dari berkas hasil ekstraksi, format apa pun."""
    if not hasil:
        return {}
    daftar = hasil if isinstance(hasil, list) else hasil.get("hasil", [])
    return {h["publikasi_id"]: h["jumlah_entri"] for h in daftar}


def jalankan(nama_tahap, perintah):
    """Jalankan satu tahap. Return (sukses, keluaran)."""
    print()
    print("=" * 74)
    print(f"TAHAP: {nama_tahap}")
    print("=" * 74)

    proses = subprocess.run(
        [sys.executable, *perintah],
        cwd=DIR_PROYEK, text=True, capture_output=True, check=False,
    )
    keluaran = (proses.stdout or "") + (proses.stderr or "")

    # Baris pdfminer tentang FontBBox membanjiri layar tanpa memberi informasi.
    for baris in keluaran.splitlines():
        if "FontBBox" in baris or "CropBox" in baris or "MediaBox" in baris:
            continue
        print(baris)

    return proses.returncode == 0, keluaran


def gagal(nama_tahap, keluaran):
    print()
    print("=" * 74)
    print(f"GAGAL di tahap: {nama_tahap}")
    print("=" * 74)

    if any(j in keluaran.lower() for j in JEJAK_JARINGAN):
        print(PESAN_JARINGAN)
    else:
        print("  Proses dihentikan supaya database tidak terisi data setengah jadi.")
        print("  Perbaiki penyebabnya di atas, lalu jalankan ulang perintah ini.")
    sys.exit(1)


def main():
    arg = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    arg.add_argument("--paksa", action="store_true",
                     help="Ekstrak ulang SEMUA publikasi, bukan hanya yang baru. "
                          "Pakai setiap kali parser diperbarui.")
    arg.add_argument("--tahun-min", type=int, default=None,
                     help="Tahun rilis paling awal (default: 2 tahun terakhir).")
    opsi = arg.parse_args()

    mulai = time.time()
    os.chdir(DIR_PROYEK)

    # Keadaan awal, untuk membandingkan di akhir.
    meta_lama = baca_json(FILE_META)
    id_lama = {p["pub_id"] for p in daftar_pub(meta_lama)}
    entri_lama = entri_per_pub(baca_json(FILE_EKSTRAKSI))
    pdf_lama = len([n for n in os.listdir(DIR_PDF)
                    if n.lower().endswith(".pdf")]) if os.path.isdir(DIR_PDF) else 0

    # ---------------------------- 1. metadata ----------------------------
    perintah = ["scripts/ambil_publikasi.py"]
    if opsi.tahun_min is not None:
        perintah += ["--tahun-min", str(opsi.tahun_min)]
    ok, keluaran = jalankan("1/4 Ambil metadata publikasi", perintah)
    if not ok:
        gagal("1/4 Ambil metadata publikasi", keluaran)

    meta_baru = baca_json(FILE_META)
    id_baru = {p["pub_id"] for p in daftar_pub(meta_baru)}
    publikasi_baru = id_baru - id_lama

    # Halaman yang gagal ditarik berarti daftar publikasinya belum utuh.
    # Melanjutkan bisa membuat publikasi yang ada terlihat seperti terhapus.
    if (meta_baru or {}).get("halaman_gagal"):
        print()
        print(f"  {len(meta_baru['halaman_gagal'])} halaman WebAPI gagal ditarik.")
        gagal("1/4 Ambil metadata publikasi", "connection")

    # Tidak ada yang baru DAN tidak dipaksa -> tidak ada yang perlu dikerjakan.
    if not publikasi_baru and not opsi.paksa:
        print()
        print("=" * 74)
        print("TIDAK ADA PUBLIKASI BARU")
        print("=" * 74)
        print(f"  {len(id_baru)} publikasi di daftar, semuanya sudah diproses.")
        print(f"  Selesai dalam {time.time() - mulai:.0f} detik.")
        print()
        print("  Pakai --paksa kalau ingin mengekstrak ulang setelah parser diubah.")
        return

    if publikasi_baru:
        print()
        print(f"  {len(publikasi_baru)} publikasi baru terdeteksi.")

    # ---------------------------- 2. unduh PDF ----------------------------
    ok, keluaran = jalankan("2/4 Unduh PDF baru", ["scripts/unduh_pdf.py"])
    if not ok:
        gagal("2/4 Unduh PDF baru", keluaran)

    # --------------------------- 3. ekstraksi ---------------------------
    perintah = ["scripts/ekstrak_semua.py"]
    if opsi.paksa:
        perintah.append("--paksa")
    ok, keluaran = jalankan("3/4 Ekstrak struktur dokumen", perintah)
    if not ok:
        gagal("3/4 Ekstrak struktur dokumen", keluaran)

    # --------------------------- 4. muat ke DB ---------------------------
    ok, keluaran = jalankan("4/4 Muat ke database", ["scripts/muat_ke_database.py"])
    if not ok:
        gagal("4/4 Muat ke database", keluaran)

    # ----------------------------- ringkasan -----------------------------
    entri_baru = entri_per_pub(baca_json(FILE_EKSTRAKSI))
    pdf_baru = len([n for n in os.listdir(DIR_PDF) if n.lower().endswith(".pdf")])

    tambah = sum(entri_baru.values()) - sum(entri_lama.values())
    berubah = [pid for pid, n in entri_baru.items()
               if entri_lama.get(pid) is not None and entri_lama[pid] != n]

    print()
    print("=" * 74)
    print("RINGKASAN PEMBARUAN")
    print("=" * 74)
    print(f"  Publikasi di daftar : {len(id_lama)} -> {len(id_baru)} "
          f"({len(publikasi_baru)} baru)")
    print(f"  Berkas PDF          : {pdf_lama} -> {pdf_baru}")
    print(f"  Entri dokumen       : {sum(entri_lama.values())} -> "
          f"{sum(entri_baru.values())} ({tambah:+d})")
    print(f"  Publikasi diekstrak ulang: {len(berubah)}")
    print(f"  Waktu               : {time.time() - mulai:.0f} detik")

    if publikasi_baru:
        print()
        print("  Publikasi baru:")
        judul = {p["pub_id"]: p.get("title", "") for p in daftar_pub(meta_baru)}
        for pid in sorted(publikasi_baru):
            print(f"    {entri_baru.get(pid, 0):>4} entri  {judul.get(pid, pid)[:56]}")


if __name__ == "__main__":
    main()
