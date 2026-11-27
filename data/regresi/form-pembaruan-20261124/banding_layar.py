"""Banding piksel dua folder tangkapan layar, per berkas.

SAMA     identik piksel demi piksel
DERAU    beda maksimum <= 4/255 per kanal: penskalaan JPEG sampul oleh browser;
         terbukti muncul juga di antara dua potret dari kode dan data yang SAMA
         (24 Nov 2026: 4/12 berkas, maks 4, semuanya di kotak gambar sampul)
BEDA     selebihnya (ukuran berbeda, atau beda > 4/255)
"""
import os
import sys

from PIL import Image, ImageChops

BATAS_DERAU = 4
a, b = sys.argv[1], sys.argv[2]
hitung = {"SAMA": 0, "DERAU": 0, "BEDA": 0}
for n in sorted(os.listdir(a)):
    x, y = Image.open(f"{a}/{n}").convert("RGB"), Image.open(f"{b}/{n}").convert("RGB")
    if x.size != y.size:
        status, rinci = "BEDA", f"ukuran {x.size} vs {y.size}"
    else:
        d = ImageChops.difference(x, y)
        kotak = d.getbbox()
        maks = max(hi for _, hi in d.getextrema()) if kotak else 0
        status = "SAMA" if not kotak else "DERAU" if maks <= BATAS_DERAU else "BEDA"
        rinci = f"{x.size}" + (f", kotak beda {kotak}, maks {maks}/255" if kotak else "")
    hitung[status] += 1
    print(f"{status:<6}{n}  {rinci}")
print(f"{hitung['SAMA']} sama, {hitung['DERAU']} derau <= {BATAS_DERAU}/255, {hitung['BEDA']} beda")
sys.exit(1 if hitung["BEDA"] else 0)
