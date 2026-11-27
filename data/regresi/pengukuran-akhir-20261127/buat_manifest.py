"""Manifest berkas data untuk paket serah terima v1.0.0 (27 Nov 2026).

HANYA MEMBACA berkas. Menulis satu TSV: tiap berkas di data/publikasi_pdf,
data/sampul, dan data/ocr_cache dengan jalur relatif terhadap data/ (garis
miring "/"), ukuran, waktu ubah dalam DETIK BULAT, dan sha256.

Ukuran + detik waktu ubah = sidik yang dipakai aplikasi
(sumber_bps.sidik_pdf, ocr._sidik), jadi kolom itu bisa dibandingkan
langsung di server baru. sha256 untuk memastikan isi berkas utuh sesudah
disalin.

    venv\\Scripts\\python.exe data\\regresi\\pengukuran-akhir-20261127\\buat_manifest.py KELUAR.tsv
"""
import hashlib
import os
import sys

DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA = os.path.join(DIR, "data")
FOLDER = ("publikasi_pdf", "sampul", "ocr_cache")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for potong in iter(lambda: f.read(1 << 20), b""):
            h.update(potong)
    return h.hexdigest()


def main(keluar):
    baris, ringkas = [], {}
    for folder in FOLDER:
        n = b = 0
        for akar, sub, berkas in os.walk(os.path.join(DATA, folder)):
            sub.sort()
            for nama in sorted(berkas):
                if nama == ".gitkeep":
                    continue
                p = os.path.join(akar, nama)
                st = os.stat(p)
                rel = os.path.relpath(p, DATA).replace(os.sep, "/")
                baris.append(f"{folder}\t{rel}\t{st.st_size}\t{int(st.st_mtime)}\t{sha256(p)}")
                n += 1
                b += st.st_size
        ringkas[folder] = (n, b)
    with open(keluar, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Manifest berkas data, Sistem Pencarian Publikasi BPS Kalsel v1.0.0, 27 Nov 2026\n")
        f.write("# Jalur relatif terhadap folder data/. Sidik aplikasi = (ukuran, mtime_detik).\n")
        for folder, (n, b) in ringkas.items():
            f.write(f"# {folder}: {n} berkas, {b} bait\n")
        f.write("folder\tjalur\tukuran\tmtime_detik\tsha256\n")
        f.write("\n".join(baris) + "\n")
    for folder, (n, b) in ringkas.items():
        print(f"{folder}: {n} berkas, {b / 2**20:.1f} MiB")
    print(f"-> {keluar} ({len(baris)} baris)")


if __name__ == "__main__":
    main(sys.argv[1])
