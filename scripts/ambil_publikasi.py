"""Tarik daftar publikasi BPS Kalsel (domain 6300) dari WebAPI, filter tahun rilis.

Jendela tahun dihitung RELATIF terhadap tanggal hari ini - N tahun terakhir,
default 2. Jadi tahun 2027 otomatis mengambil rilis 2026-2027 tanpa mengubah
kode. Angka mati akan diam-diam menolak publikasi baru begitu tahun berganti.

Sesuai Term of Use BPS: ada jeda antar request supaya tidak membebani server.
Semua halaman discan sampai habis - hasil API TIDAK diasumsikan terurut rl_date.

Jalankan:  venv/Scripts/python.exe scripts/ambil_publikasi.py
           venv/Scripts/python.exe scripts/ambil_publikasi.py --tahun-min 2024
Output  :  data/publikasi_2025_2026.json
"""

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import date, datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BPS_API_KEY", "").strip()
DOMAIN = os.getenv("BPS_DOMAIN", "6300").strip()
BASE_URL = "https://webapi.bps.go.id/v1/api"

FILE_HASIL = "data/publikasi_2025_2026.json"

# Berapa tahun terakhir yang diambil, dihitung dari tahun berjalan.
JUMLAH_TAHUN = 2


def tahun_dipakai(tahun_min=None):
    """Jendela tahun rilis yang diambil, relatif terhadap hari ini.

    tahun_min diberikan hanya untuk kasus khusus (lewat --tahun-min); kalau
    kosong, dihitung dari tahun berjalan supaya tidak perlu diubah tiap tahun.
    """
    sekarang = date.today().year  # noqa: DTZ011 - tahun lokal memang yang dimaksud
    if tahun_min is None:
        tahun_min = sekarang - (JUMLAH_TAHUN - 1)
    return set(range(int(tahun_min), sekarang + 1))


JEDA_DETIK = 1.0        # Term of Use: jangan membebani server BPS
MAKS_PERCOBAAN = 3      # retry ringan per halaman
JEDA_RETRY = 3.0
TIMEOUT = 30

# Field yang ingin dipastikan ada di output (nilai asli dari API tetap disimpan utuh).
FIELD_PENTING = [
    "pub_id", "title", "abstract", "rl_date", "pdf",
    "cover", "subject_csa", "issn", "size",
]


def url_halaman(page):
    return (f"{BASE_URL}/list/model/publication/lang/ind/domain/{DOMAIN}"
            f"/page/{page}/key/{API_KEY}/")


def ambil_halaman(page):
    """Ambil satu halaman dengan retry ringan.

    Return (pagination, daftar_publikasi). Lempar Exception kalau semua percobaan gagal.
    """
    galat_terakhir = None

    for percobaan in range(1, MAKS_PERCOBAAN + 1):
        try:
            r = requests.get(url_halaman(page), timeout=TIMEOUT)
            r.raise_for_status()
            body = r.json()

            if body.get("status") != "OK":
                raise ValueError(f"status API = {body.get('status')}, "
                                 f"data-availability = {body.get('data-availability')}")

            data = body.get("data")
            # Bentuk khas WebAPI BPS: data = [ {info pagination}, [ ...publikasi... ] ]
            if isinstance(data, list) and len(data) == 2:
                pagination = data[0] if isinstance(data[0], dict) else {}
                daftar = data[1] if isinstance(data[1], list) else []
            else:
                pagination, daftar = {}, (data if isinstance(data, list) else [])

            return pagination, daftar

        except Exception as e:  # noqa: BLE001 - script sekali pakai, cukup catat pesannya
            galat_terakhir = e
            if percobaan < MAKS_PERCOBAAN:
                print(f"    percobaan {percobaan} gagal ({e}), ulangi dalam {JEDA_RETRY}s")
                time.sleep(JEDA_RETRY)

    raise RuntimeError(galat_terakhir)


def daftar_subjek(p):
    """subject_csa dari API bisa list, null, atau string. Selalu kembalikan list str.

    Satu publikasi bisa punya lebih dari satu subjek, jadi tiap elemen dihitung
    terpisah saat membuat sebaran.
    """
    nilai = p.get("subject_csa")
    if nilai is None or nilai == "":
        return ["(kosong)"]
    if isinstance(nilai, list):
        bersih = [str(s).strip() for s in nilai if str(s).strip()]
        return bersih or ["(kosong)"]
    return [str(nilai).strip()]


def tahun_rilis(rl_date):
    """Ambil tahun dari rl_date. Return int atau None kalau tidak terbaca."""
    if not rl_date:
        return None
    cocok = re.search(r"(19|20)[0-9]{2}", str(rl_date))
    return int(cocok.group(0)) if cocok else None


def main(argv=None):
    arg = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    arg.add_argument("--tahun-min", type=int, default=None,
                     help=("Tahun rilis paling awal yang diambil (default: "
                           f"tahun berjalan - {JUMLAH_TAHUN - 1})"))
    opsi = arg.parse_args(argv)
    TAHUN_DIPAKAI = tahun_dipakai(opsi.tahun_min)

    if not API_KEY:
        print("BPS_API_KEY kosong di .env - isi dulu sebelum menjalankan script ini.")
        sys.exit(1)

    print(f"Menarik publikasi domain {DOMAIN} dari WebAPI BPS")
    print(f"Jendela tahun rilis: {sorted(TAHUN_DIPAKAI)}")

    semua_publikasi = []      # seluruh tahun, untuk statistik pembanding
    halaman_gagal = []
    total_halaman = None
    page = 1

    while True:
        label = f"{page}/{total_halaman}" if total_halaman else f"{page}/?"
        print(f"  halaman {label} ...", end=" ", flush=True)

        try:
            pagination, daftar = ambil_halaman(page)
        except Exception as e:  # noqa: BLE001
            print(f"GAGAL ({e})")
            halaman_gagal.append(page)
            # Tetap lanjut - satu halaman gagal tidak boleh menghentikan proses.
            if total_halaman is None:
                # Halaman pertama gagal -> daftar publikasi tidak diketahui sama
                # sekali. JANGAN menulis berkas hasil: menimpanya dengan daftar
                # kosong akan menghapus metadata 72 publikasi yang sudah ada,
                # dan tahap berikutnya akan menyangka semuanya terhapus.
                print("  Halaman pertama gagal - kemungkinan besar jaringan.")
                print(f"  {FILE_HASIL} TIDAK diubah supaya data lama tetap utuh.")
                sys.exit(1)
            page += 1
            if page > total_halaman:
                break
            time.sleep(JEDA_DETIK)
            continue

        if total_halaman is None:
            total_halaman = pagination.get("pages") or 1
            print(f"OK ({len(daftar)} item, total {pagination.get('total', '?')} "
                  f"publikasi / {total_halaman} halaman)")
        else:
            print(f"OK ({len(daftar)} item)")

        semua_publikasi.extend(daftar)

        page += 1
        if page > total_halaman:
            break
        time.sleep(JEDA_DETIK)   # jeda sesuai Term of Use

    # ---------- Filter tahun rilis ----------
    lolos = []
    tanpa_tanggal = 0
    for p in semua_publikasi:
        th = tahun_rilis(p.get("rl_date"))
        if th is None:
            tanpa_tanggal += 1
            continue
        if th in TAHUN_DIPAKAI:
            lolos.append(p)

    # ---------- Simpan ----------
    keluaran = {
        "diambil_pada": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "domain": DOMAIN,
        "filter_tahun_rilis": sorted(TAHUN_DIPAKAI),
        "total_semua_tahun": len(semua_publikasi),
        "total_lolos_filter": len(lolos),
        "halaman_gagal": halaman_gagal,
        "publikasi": lolos,
    }
    if not lolos and os.path.exists(FILE_HASIL):
        # Nol hasil padahal berkas lama ada = hampir pasti kegagalan penarikan,
        # bukan BPS benar-benar menghapus seluruh publikasinya.
        print(f"  Tidak ada publikasi lolos filter, tapi {FILE_HASIL} sudah ada.")
        print("  Berkas TIDAK ditimpa. Periksa jaringan lalu jalankan ulang.")
        sys.exit(1)

    os.makedirs(os.path.dirname(FILE_HASIL), exist_ok=True)
    sementara = FILE_HASIL + ".tmp"
    with open(sementara, "w", encoding="utf-8") as f:
        json.dump(keluaran, f, ensure_ascii=False, indent=2)
    os.replace(sementara, FILE_HASIL)

    # ---------- Ringkasan ----------
    print()
    print("=" * 70)
    print("RINGKASAN")
    print("=" * 70)
    print(f"Total publikasi semua tahun : {len(semua_publikasi)}")
    print(f"Lolos filter {sorted(TAHUN_DIPAKAI)}     : {len(lolos)}")
    if tanpa_tanggal:
        print(f"rl_date tidak terbaca       : {tanpa_tanggal}")

    print()
    print("Sebaran per tahun rilis (semua tahun):")
    per_tahun = Counter(tahun_rilis(p.get("rl_date")) for p in semua_publikasi)
    for th, n in sorted(per_tahun.items(), key=lambda x: (x[0] is None, x[0])):
        tanda = " <- dipakai" if th in TAHUN_DIPAKAI else ""
        print(f"  {th if th is not None else 'tidak terbaca'} : {n}{tanda}")

    print()
    print("Sebaran per subject_csa (yang lolos filter):")
    per_subjek = Counter(s for p in lolos for s in daftar_subjek(p))
    for subjek, n in per_subjek.most_common():
        print(f"  {n:>4}  {subjek}")
    # Totalnya bisa melebihi jumlah publikasi karena ada yang bersubjek ganda.
    print(f"  (total {sum(per_subjek.values())} penyebutan dari {len(lolos)} publikasi)")

    # Cek kelengkapan field penting - berguna sebelum masuk tahap ekstraksi PDF.
    print()
    print("Kelengkapan field penting (yang lolos filter):")
    for field in FIELD_PENTING:
        ada = sum(1 for p in lolos if p.get(field))
        print(f"  {field:<12} : {ada}/{len(lolos)}")

    if halaman_gagal:
        print()
        print(f"HALAMAN GAGAL ({len(halaman_gagal)}): {halaman_gagal}")
        print("Publikasi di halaman tersebut TIDAK ikut tersimpan - jalankan ulang.")

    print()
    print(f"Hasil -> {FILE_HASIL}")


if __name__ == "__main__":
    main()
