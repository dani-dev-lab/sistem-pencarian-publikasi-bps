"""Spike OCR: Tesseract (portabel) vs EasyOCR (CPU) pada halaman terpilih.

Pemakaian (dari venv-ocr, BUKAN venv proyek):
  venv-ocr/Scripts/python.exe spike_ocr.py <keluaran_dir> <pdf>:<hal1,hal2,...> [...]
Halaman = nomor halaman fisik PDF (mulai 1). Hasil per halaman:
  <id>-p<hal>.png          render 300 dpi (bahan baca manual)
  <id>-p<hal>.tess.txt     teks Tesseract (ind+eng, psm 3)
  <id>-p<hal>.easy.txt     teks EasyOCR (id+en), kotak disusun jadi baris
  waktu.json               detik per halaman per mesin + waktu muat model
"""
import json
import os
import sys
import time

import numpy as np
import pypdfium2 as pdfium
import pytesseract

DIR = os.path.dirname(os.path.abspath(__file__))
TESS = os.path.join(DIR, "tesseract", "tesseract.exe")
pytesseract.pytesseract.tesseract_cmd = TESS
os.environ["TESSDATA_PREFIX"] = os.path.join(DIR, "tesseract", "tessdata")
DPI = 300


def render(pdf, nomor):
    halaman = pdf[nomor - 1]
    return halaman.render(scale=DPI / 72).to_pil().convert("RGB")


def baris_easyocr(hasil):
    """Kotak EasyOCR -> baris teks: dikelompokkan menurut pusat vertikal."""
    kotak = []
    for poli, teks, _ in hasil:
        ys = [p[1] for p in poli]; xs = [p[0] for p in poli]
        kotak.append(((min(ys) + max(ys)) / 2, min(xs), max(ys) - min(ys), teks))
    kotak.sort()
    baris, sekarang, y0 = [], [], None
    for y, x, tinggi, teks in kotak:
        if y0 is not None and abs(y - y0) > max(8, tinggi * 0.5):
            baris.append(" ".join(t for _, t in sorted(sekarang))); sekarang = []
        sekarang.append((x, teks)); y0 = y if not sekarang[:-1] else (y0 + y) / 2
    if sekarang:
        baris.append(" ".join(t for _, t in sorted(sekarang)))
    return "\n".join(baris)


def main():
    keluar = sys.argv[1]
    os.makedirs(keluar, exist_ok=True)
    import easyocr
    t = time.perf_counter()
    pembaca = easyocr.Reader(["id", "en"], gpu=False, verbose=False)
    waktu = {"muat_easyocr_detik": round(time.perf_counter() - t, 1), "halaman": []}
    for arg in sys.argv[2:]:
        path, nomor = arg.rsplit(":", 1)
        pid = os.path.splitext(os.path.basename(path))[0][:8]
        pdf = pdfium.PdfDocument(path)
        for n in [int(x) for x in nomor.split(",")]:
            img = render(pdf, n)
            dasar = os.path.join(keluar, f"{pid}-p{n}")
            img.save(dasar + ".png")
            t = time.perf_counter()
            teks_t = pytesseract.image_to_string(img, lang="ind+eng", config="--psm 3")
            dt_t = time.perf_counter() - t
            t = time.perf_counter()
            teks_e = baris_easyocr(pembaca.readtext(np.array(img)))
            dt_e = time.perf_counter() - t
            open(dasar + ".tess.txt", "w", encoding="utf-8").write(teks_t)
            open(dasar + ".easy.txt", "w", encoding="utf-8").write(teks_e)
            waktu["halaman"].append({"pdf": pid, "hal": n, "tesseract_detik": round(dt_t, 2),
                                     "easyocr_detik": round(dt_e, 2), "ukuran_px": img.size})
            print(f"{pid} p{n}: tesseract {dt_t:5.1f} s, easyocr {dt_e:5.1f} s", flush=True)
    json.dump(waktu, open(os.path.join(keluar, "waktu.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
