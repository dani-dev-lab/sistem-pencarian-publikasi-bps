"""Jalankan parser produksi terhadap seluruh PDF di data/publikasi_pdf/.

Menghasilkan data/hasil_ekstraksi.json plus ringkasan mutu: publikasi yang
gagal total, entri tanpa nomor halaman, dan publikasi dengan hasil mencurigakan.

Jalankan:  venv/Scripts/python.exe scripts/ekstrak_semua.py
"""

import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone

import pdfplumber

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ekstraksi_pdf import cari_heading, ekstrak_lengkap

DIR_PDF = "data/publikasi_pdf"
FILE_META = "data/publikasi_2025_2026.json"
FILE_HASIL = "data/hasil_ekstraksi.json"

TIPE = ("isi", "tabel", "gambar", "lampiran")

# Simpan berkala. Tanpa ini, proses yang terputus di tengah (laptop hibernate,
# sesi mati) kehilangan seluruh pekerjaan TANPA JEJAK - berkas hasil lama tetap
# utuh di tempatnya sehingga terlihat seolah run-nya berhasil.
SIMPAN_TIAP = 10


def simpan(hasil, total, selesai):
    """Tulis hasil beserta penanda kelengkapannya.

    Penanda `selesai` dan `publikasi_terproses` ditulis DI DALAM berkas, bukan
    hanya di log, supaya pemeriksaan berikutnya tidak perlu mengandalkan cap
    waktu berkas atau menghitung baris log.
    """
    keluaran = {
        "selesai": selesai,
        "publikasi_terproses": len(hasil),
        "total_publikasi": total,
        "diperbarui_pada": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hasil": hasil,
    }
    sementara = FILE_HASIL + ".tmp"
    with open(sementara, "w", encoding="utf-8") as f:
        json.dump(keluaran, f, ensure_ascii=False, indent=2)
    # Ganti secara atomik supaya berkas hasil tidak pernah separuh tertulis.
    os.replace(sementara, FILE_HASIL)


def muat_judul():
    """{pub_id: judul} untuk membuat laporan terbaca."""
    if not os.path.exists(FILE_META):
        return {}
    with open(FILE_META, encoding="utf-8") as f:
        return {p["pub_id"]: p.get("title", "") for p in json.load(f)["publikasi"]}


def main():
    judul_pub = muat_judul()
    berkas = sorted(n for n in os.listdir(DIR_PDF) if n.lower().endswith(".pdf"))
    if not berkas:
        print(f"Tidak ada PDF di {DIR_PDF}/")
        return

    print(f"Memproses {len(berkas)} PDF dari {DIR_PDF}/")
    mulai = time.time()

    hasil = []
    for i, nama in enumerate(berkas, start=1):
        path = os.path.join(DIR_PDF, nama)
        pub_id = nama[:-4]
        judul = judul_pub.get(pub_id, "(tidak ada di metadata)")

        print(f"[{i:>2}/{len(berkas)}] {judul[:50]:<50}", end=" ", flush=True)

        try:
            # Heading dicatat terpisah supaya bisa membedakan "daftarnya memang
            # tidak ada" dari "daftarnya ada tapi gagal dibaca".
            with pdfplumber.open(path) as pdf:
                heading = cari_heading(pdf)
            jejak = []
            entri, n_daftar, n_badan, n_lengkap = ekstrak_lengkap(path, pub_id, jejak)
            galat = None
        except Exception as e:  # noqa: BLE001 - satu PDF rusak tidak boleh menghentikan
            heading, entri, jejak, galat = {}, [], [], str(e)
            n_daftar = n_badan = n_lengkap = 0

        per_tipe = Counter(e["tipe"] for e in entri)
        tanpa_halaman = sum(1 for e in entri if not e["halaman"])

        hasil.append({
            "publikasi_id": pub_id,
            "judul": judul,
            "heading_ditemukan": sorted(heading),
            "jumlah_entri": len(entri),
            "per_tipe": dict(per_tipe),
            "tanpa_halaman": tanpa_halaman,
            "mode_tanpa_label": jejak,
            "dari_daftar": n_daftar,
            "dari_badan": n_badan,
            "halaman_fisik_dilengkapi": n_lengkap,
            "per_sumber": dict(Counter(e["sumber"] for e in entri)),
            "galat": galat,
            "entri": entri,
        })

        if galat:
            print(f"GALAT: {galat[:40]}")
        else:
            rincian = " ".join(f"{t[:3]}={per_tipe.get(t, 0)}" for t in TIPE)
            print(f"{len(entri):>4} entri  ({rincian})  "
                  f"[daftar={n_daftar} badan={n_badan} +fisik={n_lengkap}]")

        if i % SIMPAN_TIAP == 0:
            simpan(hasil, len(berkas), selesai=False)
            print(f"          (disimpan sementara: {i}/{len(berkas)})")

    simpan(hasil, len(berkas), selesai=True)

    # ------------------------------- Ringkasan -------------------------------
    total_entri = sum(h["jumlah_entri"] for h in hasil)
    total_tanpa_hal = sum(h["tanpa_halaman"] for h in hasil)
    agregat = Counter()
    for h in hasil:
        agregat.update(h["per_tipe"])

    print()
    print("=" * 74)
    print("RINGKASAN")
    print("=" * 74)
    print(f"Publikasi diproses : {len(hasil)}")
    print(f"Total entri        : {total_entri}")
    print(f"Waktu              : {time.time() - mulai:.0f} detik")
    print()
    print("Sebaran per tipe:")
    for t in TIPE:
        n = agregat.get(t, 0)
        pct = n / total_entri * 100 if total_entri else 0
        print(f"  {t:<10} {n:>6}  ({pct:>5.1f}%)")

    pct_tanpa = total_tanpa_hal / total_entri * 100 if total_entri else 0
    print()
    print(f"Entri tanpa nomor halaman : {total_tanpa_hal} dari {total_entri} "
          f"({pct_tanpa:.1f}%)")

    kosong = [h for h in hasil if h["jumlah_entri"] == 0]
    print(f"Publikasi 0 entri         : {len(kosong)}")
    print(f"halaman_fisik dilengkapi  : "
          f"{sum(h.get('halaman_fisik_dilengkapi', 0) for h in hasil)}")

    per_sumber = Counter()
    for h in hasil:
        per_sumber.update(h.get("per_sumber", {}))
    print()
    print("Sebaran per sumber:")
    for s_ in ("daftar", "badan", "keduanya"):
        print(f"  {s_:<10} {per_sumber.get(s_, 0):>6}")

    pakai_tanpa_label = [h for h in hasil if h.get("mode_tanpa_label")]
    print()
    print(f"Publikasi memakai mode TANPA LABEL: {len(pakai_tanpa_label)}")
    for h in pakai_tanpa_label:
        print(f"  {h['judul'][:52]:<52} {h['mode_tanpa_label']}")

    # --------------------------- Hasil mencurigakan ---------------------------
    curiga = []
    for h in hasil:
        if h["galat"]:
            curiga.append((h, f"galat: {h['galat'][:50]}"))
            continue
        if h["jumlah_entri"] == 0:
            curiga.append((h, "0 entri sama sekali"))
            continue
        # Heading ketemu tapi tidak menghasilkan entri satu pun.
        buntu = [t for t in h["heading_ditemukan"] if not h["per_tipe"].get(t)]
        if buntu:
            curiga.append((h, f"heading {', '.join(buntu)} ada tapi 0 entri"))
            continue
        # Publikasi statistik yang hanya menghasilkan Daftar Isi.
        if set(h["per_tipe"]) == {"isi"}:
            curiga.append((h, "hanya Daftar Isi, tidak ada tabel/gambar/lampiran"))
            continue
        if h["tanpa_halaman"] > h["jumlah_entri"] * 0.25:
            curiga.append((h, (f"{h['tanpa_halaman']}/{h['jumlah_entri']} "
                               "entri tanpa nomor halaman")))

    print()
    print("=" * 74)
    print(f"PUBLIKASI PERLU DIPERIKSA ({len(curiga)})")
    print("=" * 74)
    if not curiga:
        print("  tidak ada")
    for h, alasan in curiga:
        print(f"  {h['publikasi_id']}  {h['judul'][:42]:<42}")
        print(f"      heading={h['heading_ditemukan']} entri={h['jumlah_entri']} "
              f"-> {alasan}")

    print()
    print(f"Hasil lengkap -> {FILE_HASIL}")


if __name__ == "__main__":
    main()
