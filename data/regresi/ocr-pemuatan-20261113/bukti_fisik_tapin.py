"""Bukti per entri untuk halaman_fisik yang berubah di dua PDRB Tapin LU.

  python bukti_fisik_tapin.py potret/produksi-sebelum.json potret/uji-sesudah-ocr.json

Untuk tiap entri bernomor yang `berubah`: cari "Tabel|Table|Lampiran <nomor>"
di SELURUH kata OCR halaman fisik barunya (bukan hanya baris teratas - versi
pertama alat ini hanya melihat 14 kata teratas dan melaporkan 31 "tidak ada"
padahal semuanya ada). Juga dicetak halaman lain yang memuat label sama.
"""
import glob
import json
import os
import re
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir("C:/sistem-pencarian-bps")
m = {}
exec(open(os.path.join(DIR, "banding_kunci.py"), encoding="utf-8").read().split("a = json.load")[0], m)
a = json.load(open(os.path.join(DIR, sys.argv[1]), encoding="utf-8"))
b = json.load(open(os.path.join(DIR, sys.argv[2]), encoding="utf-8"))


def teks_hal(d, hal):
    kata = json.load(open(f"{d}/{hal:04d}-easyocr.json", encoding="utf-8"))["kata"]
    kata.sort(key=lambda k: (round(k["top"] / 6), k["x0"]))
    return " ".join(k["text"] for k in kata)


for pid in ["182e2e58be59ddf2d26a7a44", "25f039221e44a34843043419"]:
    h = m["banding_pub"](a["entri"][pid], b["entri"][pid])
    d = glob.glob(f"data/ocr_cache/*/{pid}")[0]
    ada = total = 0
    print("==", m["TARGET"][pid])
    for lama, baru in h["berubah"]:
        if not lama[1]:
            continue
        total += 1
        hal = baru[4]
        pola = rf"(tabel|table|lampiran|appendi\w*)\W{{0,3}}{re.escape(lama[1])}(?![\d])"
        t = teks_hal(d, hal)
        cocok = re.search(pola, t, re.I)
        ada += bool(cocok)
        lain = [p for p in range(1, 200) if p != hal and os.path.exists(f"{d}/{p:04d}-easyocr.json")
                and re.search(pola, teks_hal(d, p), re.I)]
        print(f"  {lama[0]:<8} {lama[1]:<5} cetak {lama[3]:<4} fisik {str(lama[4]):<4}-> {hal:<4} "
              f"{'ADA: ' + t[max(0, cocok.start() - 5):cocok.end() + 45] if cocok else 'TIDAK ADA'}"
              f" | label juga di hal {lain[:6]}")
    print(f"  keterangan ditemukan di halaman baru: {ada}/{total}")
