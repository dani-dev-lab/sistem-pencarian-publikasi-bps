"""Diagnosis PDF di data/publikasi_pdf/ sebelum masuk tahap ekstraksi.

Script sekali pakai. Menjawab: mana yang tidak bisa dibuka, mana yang tidak punya
layer teks (kandidat hasil scan), dan mana yang ukurannya jauh meleset dari API.

Jalankan:  venv/Scripts/python.exe scripts/cek_pdf.py
"""

import json
import os
import re

import pdfplumber

FILE_SUMBER = "data/publikasi_2025_2026.json"
DIR_PDF = "data/publikasi_pdf"
AMBANG_SELISIH = 0.20   # tandai kalau selisih ukuran > 20%


def ukuran_ke_byte(teks):
    """'15.78 MB' -> 16546529. Return None kalau tidak terbaca."""
    if not teks:
        return None
    cocok = re.match(r"\s*([0-9]+(?:[.][0-9]+)?)\s*(KB|MB|GB)\s*$", str(teks), re.IGNORECASE)
    if not cocok:
        return None
    pengali = {"kb": 1024, "mb": 1024 ** 2, "gb": 1024 ** 3}[cocok.group(2).lower()]
    return int(float(cocok.group(1)) * pengali)


def mb(n):
    return "?" if n is None else f"{n / 1024 / 1024:.2f} MB"


def main():
    with open(FILE_SUMBER, encoding="utf-8") as f:
        daftar = json.load(f)["publikasi"]

    meta = {p["pub_id"]: p for p in daftar}
    berkas = sorted(n for n in os.listdir(DIR_PDF) if n.lower().endswith(".pdf"))

    print(f"{len(berkas)} file PDF di {DIR_PDF}/")
    print()

    gagal_buka = []
    tanpa_teks = []
    selisih_besar = []
    total_halaman = 0

    for i, nama in enumerate(berkas, start=1):
        path = os.path.join(DIR_PDF, nama)
        pub_id = nama[:-4]
        p = meta.get(pub_id, {})
        judul = (p.get("title") or "(tidak ada di JSON)").replace("\n", " ")

        ukuran_nyata = os.path.getsize(path)
        ukuran_api = ukuran_ke_byte(p.get("size"))

        print(f"[{i:>2}/{len(berkas)}] {judul[:48]:<48}", end=" ")

        try:
            with pdfplumber.open(path) as pdf:
                jml_halaman = len(pdf.pages)
                teks_hal1 = pdf.pages[0].extract_text() if jml_halaman else None
        except Exception as e:  # noqa: BLE001 - script diagnosis, cukup catat pesannya
            print(f"GAGAL DIBUKA: {e}")
            gagal_buka.append((nama, str(e)))
            continue

        total_halaman += jml_halaman
        ada_teks = bool(teks_hal1 and teks_hal1.strip())
        if not ada_teks:
            tanpa_teks.append((nama, judul))

        # Bandingkan ukuran file nyata dengan field size dari API.
        tanda_ukuran = ""
        if ukuran_api:
            selisih = abs(ukuran_nyata - ukuran_api) / ukuran_api
            if selisih > AMBANG_SELISIH:
                tanda_ukuran = f"  ukuran beda {selisih * 100:.0f}%"
                selisih_besar.append((nama, ukuran_nyata, ukuran_api, selisih, judul))

        print(f"{jml_halaman:>4} hal  {mb(ukuran_nyata):>9}  "
              f"{'teks OK' if ada_teks else 'TANPA TEKS'}{tanda_ukuran}")

    # ---------- Ringkasan ----------
    print()
    print("=" * 74)
    print("RINGKASAN")
    print("=" * 74)
    print(f"Bisa dibuka       : {len(berkas) - len(gagal_buka)}/{len(berkas)}")
    print(f"Gagal dibuka      : {len(gagal_buka)}")
    print(f"Tanpa teks hal. 1 : {len(tanpa_teks)}  (kandidat PDF hasil scan)")
    print(f"Selisih ukuran    : {len(selisih_besar)} file (> {AMBANG_SELISIH * 100:.0f}%)")
    print(f"Total halaman     : {total_halaman}")

    if gagal_buka:
        print()
        print("File yang gagal dibuka:")
        for nama, pesan in gagal_buka:
            print(f"  {nama}  -  {pesan}")

    if tanpa_teks:
        print()
        print("File tanpa layer teks (perlu OCR atau dikeluarkan dari scope):")
        for nama, judul in tanpa_teks:
            print(f"  {nama}  -  {judul[:60]}")

    if selisih_besar:
        print()
        print("File dengan selisih ukuran mencolok (nyata vs field size API):")
        for nama, nyata, api, selisih, judul in sorted(
                selisih_besar, key=lambda x: -x[3]):
            arah = "lebih besar" if nyata > api else "lebih kecil"
            print(f"  {nama}  {mb(nyata):>9} vs {mb(api):>9}  "
                  f"({selisih * 100:>5.0f}% {arah})  {judul[:38]}")

    # Cek silang isi folder vs daftar di JSON.
    id_berkas = {n[:-4] for n in berkas}
    id_json = set(meta)
    if id_json - id_berkas:
        print()
        print(f"Ada di JSON tapi filenya belum ada: {len(id_json - id_berkas)}")
        for pid in sorted(id_json - id_berkas):
            print(f"  {pid}  -  {(meta[pid].get('title') or '')[:60]}")
    if id_berkas - id_json:
        print()
        print(f"Ada file tapi tidak terdaftar di JSON: {len(id_berkas - id_json)}")
        for pid in sorted(id_berkas - id_json):
            print(f"  {pid}.pdf")


if __name__ == "__main__":
    main()
