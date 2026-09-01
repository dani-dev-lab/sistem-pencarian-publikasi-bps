"""Unduh PDF publikasi dari data/publikasi_2025_2026.json ke data/publikasi_pdf/.

Bisa dilanjutkan (resumable): file yang sudah ada dan ukurannya wajar dilewati,
jadi script aman dijalankan ulang kalau proses terputus di tengah.

Catatan lingkungan: hanya jalan di jaringan "BPS - Pegawai".
Jaringan "BPS - Tamu" memblokir akses ke webapi.bps.go.id.

Keutuhan file dicek berjenjang: ukuran > 1 KB, lalu penanda %PDF di awal dan
%%EOF di akhir (murah, cukup baca beberapa byte). Tambahkan --teliti kalau mau
sekalian membuka tiap file dengan pdfplumber - jauh lebih lambat.

Jalankan:  venv/Scripts/python.exe scripts/unduh_pdf.py
           venv/Scripts/python.exe scripts/unduh_pdf.py --teliti
"""

import json
import os
import re
import sys
import time

import requests

FILE_SUMBER = "data/publikasi_2025_2026.json"
DIR_PDF = "data/publikasi_pdf"

JEDA_DETIK = 1.0        # Term of Use: jangan membebani server BPS
MAKS_PERCOBAAN = 3
JEDA_RETRY = 5.0
TIMEOUT = (15, 120)     # (connect, read) - file bisa sampai 25 MB
UKURAN_CHUNK = 64 * 1024
MINIMAL_WAJAR = 1024    # di bawah ini pasti bukan PDF publikasi utuh
EKOR_DIBACA = 2048      # cukup untuk menemukan %%EOF di ujung file


def ukuran_ke_byte(teks):
    """'15.78 MB' -> 16546529. Return None kalau tidak terbaca."""
    if not teks:
        return None
    cocok = re.match(r"\s*([0-9]+(?:[.][0-9]+)?)\s*(KB|MB|GB)\s*$", str(teks), re.IGNORECASE)
    if not cocok:
        return None
    angka = float(cocok.group(1))
    pengali = {"kb": 1024, "mb": 1024 ** 2, "gb": 1024 ** 3}[cocok.group(2).lower()]
    return int(angka * pengali)


def format_byte(n):
    if n is None:
        return "?"
    for satuan in ("B", "KB", "MB", "GB"):
        if n < 1024 or satuan == "GB":
            return f"{n:.1f} {satuan}" if satuan != "B" else f"{n} B"
        n /= 1024


def berkas_pdf_valid(path):
    """Cek murah: ukuran wajar, diawali %PDF, dan diakhiri %%EOF.

    %%EOF adalah penanda akhir dokumen PDF. Unduhan yang terputus tetap diawali
    %PDF tapi kehilangan penanda ini - itulah yang membedakan file utuh dari
    file terpotong, tanpa perlu parsing sama sekali.
    """
    try:
        ukuran = os.path.getsize(path)
        if ukuran < MINIMAL_WAJAR:                  # langkah 1
            return False
        with open(path, "rb") as f:                 # langkah 2
            if f.read(4) != b"%PDF":
                return False
            f.seek(max(0, ukuran - EKOR_DIBACA))
            return b"%%EOF" in f.read()
    except OSError:
        return False


def bisa_dibuka_pdfplumber(path):
    """Cek mahal (hanya dengan --teliti): benar-benar buka dan hitung halaman."""
    try:
        import pdfplumber  # diimpor di sini supaya penjalanan rutin tetap ringan

        with pdfplumber.open(path) as pdf:
            return len(pdf.pages) > 0
    except Exception:  # noqa: BLE001 - PDF rusak bisa melempar macam-macam
        return False


def sudah_lengkap(path, teliti=False):
    """Cek berjenjang apakah file lama layak dilewati (bukan sisa unduhan terputus).

    Field `size` dari API sengaja TIDAK dipakai sebagai penentu keutuhan: nilainya
    tidak akurat per file (terbukti meleset sampai 167%), sehingga file utuh bisa
    salah dianggap terpotong dan diunduh ulang terus-menerus.
    """
    if not os.path.exists(path):
        return False
    if not berkas_pdf_valid(path):      # langkah 1 + 2, murah
        return False
    if teliti:                          # langkah 3, mahal - hanya kalau diminta
        return bisa_dibuka_pdfplumber(path)
    return True


def unduh_satu(url, path_tujuan):
    """Unduh streaming ke file .part lalu rename. Return (berhasil, pesan, ukuran)."""
    path_sementara = path_tujuan + ".part"
    galat_terakhir = None

    for percobaan in range(1, MAKS_PERCOBAAN + 1):
        try:
            with requests.get(url, stream=True, timeout=TIMEOUT) as r:
                r.raise_for_status()
                with open(path_sementara, "wb") as f:
                    for chunk in r.iter_content(chunk_size=UKURAN_CHUNK):
                        if chunk:
                            f.write(chunk)

            # Verifikasi sebelum diakui: server bisa mengembalikan halaman HTML error
            # dengan status 200.
            if not berkas_pdf_valid(path_sementara):
                ukuran = os.path.getsize(path_sementara) if os.path.exists(path_sementara) else 0
                os.remove(path_sementara)
                raise ValueError(f"bukan PDF (ukuran {format_byte(ukuran)})")

            os.replace(path_sementara, path_tujuan)
            return True, "OK", os.path.getsize(path_tujuan)

        except Exception as e:  # noqa: BLE001 - script sekali pakai, cukup catat pesannya
            galat_terakhir = e
            if os.path.exists(path_sementara):
                try:
                    os.remove(path_sementara)
                except OSError:
                    pass
            if percobaan < MAKS_PERCOBAAN:
                print(f"        percobaan {percobaan} gagal ({e}), ulangi dalam {JEDA_RETRY}s")
                time.sleep(JEDA_RETRY)

    return False, str(galat_terakhir), 0


def total_ukuran_folder(folder):
    total = 0
    for nama in os.listdir(folder):
        p = os.path.join(folder, nama)
        if os.path.isfile(p):
            total += os.path.getsize(p)
    return total


def main():
    teliti = "--teliti" in sys.argv
    if not os.path.exists(FILE_SUMBER):
        print(f"{FILE_SUMBER} tidak ada - jalankan scripts/ambil_publikasi.py dulu.")
        sys.exit(1)

    with open(FILE_SUMBER, encoding="utf-8") as f:
        sumber = json.load(f)

    daftar = sumber.get("publikasi", [])
    if not daftar:
        print("Tidak ada publikasi di file sumber.")
        sys.exit(1)

    os.makedirs(DIR_PDF, exist_ok=True)

    print(f"Sumber   : {FILE_SUMBER} ({len(daftar)} publikasi)")
    print(f"Tujuan   : {DIR_PDF}/")
    print('Jaringan : butuh "BPS - Pegawai" (jaringan tamu diblokir)')
    print(f"Cek utuh : {'teliti (buka via pdfplumber)' if teliti else 'cepat (%PDF + %%EOF)'}")
    print()

    berhasil, dilewati, gagal = [], [], []

    for i, p in enumerate(daftar, start=1):
        pub_id = p.get("pub_id")
        judul = (p.get("title") or "(tanpa judul)").replace("\n", " ")
        url = p.get("pdf")
        perkiraan = ukuran_ke_byte(p.get("size"))

        # pub_id dipakai sebagai nama file: stabil, dan judul mengandung karakter
        # yang bermasalah untuk nama file.
        path = os.path.join(DIR_PDF, f"{pub_id}.pdf")

        print(f"[{i:>2}/{len(daftar)}] {judul[:52]:<52} {format_byte(perkiraan):>9}", end="  ")

        if not pub_id or not url:
            print("GAGAL (pub_id/url kosong)")
            gagal.append((pub_id or "(tanpa pub_id)", "pub_id atau url kosong"))
            continue

        if sudah_lengkap(path, teliti=teliti):
            print(f"dilewati (sudah ada, {format_byte(os.path.getsize(path))})")
            dilewati.append(pub_id)
            continue

        ok, pesan, ukuran = unduh_satu(url, path)
        if ok:
            print(f"OK ({format_byte(ukuran)})")
            berhasil.append(pub_id)
        else:
            print(f"GAGAL ({pesan})")
            gagal.append((pub_id, pesan))

        time.sleep(JEDA_DETIK)   # jeda sesuai Term of Use

    # ---------- Ringkasan ----------
    print()
    print("=" * 70)
    print("RINGKASAN")
    print("=" * 70)
    print(f"Berhasil diunduh : {len(berhasil)}")
    print(f"Dilewati         : {len(dilewati)} (sudah ada dan utuh)")
    print(f"Gagal            : {len(gagal)}")

    if gagal:
        print()
        print("Daftar yang gagal:")
        for pub_id, pesan in gagal:
            print(f"  {pub_id}  -  {pesan}")
        print("Jalankan ulang script ini untuk mencoba lagi; yang sudah ada akan dilewati.")

    jumlah_file = len([n for n in os.listdir(DIR_PDF) if n.lower().endswith(".pdf")])
    print()
    print(f"Isi {DIR_PDF}/ : {jumlah_file} file PDF, "
          f"total {format_byte(total_ukuran_folder(DIR_PDF))}")


if __name__ == "__main__":
    main()
