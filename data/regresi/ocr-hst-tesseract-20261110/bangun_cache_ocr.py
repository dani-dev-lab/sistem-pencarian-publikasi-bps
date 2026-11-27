"""Bangun cache OCR per halaman untuk halaman TANPA lapisan teks.

Jalankan dengan venv OCR (C:/Users/Dani/alat-ocr/venv-ocr), bukan venv proyek:
  venv-ocr/Scripts/python.exe bangun_cache_ocr.py <deteksi.json> <dir_proyek> <mesin> <bagian> <jumlah_bagian>

deteksi.json : keluaran langkah deteksi (daftar halaman_ocr, nomor fisik mulai 1)
mesin        : tesseract (hari ini) | easyocr (besok) - struktur berkas sama
bagian/jumlah: untuk menjalankan beberapa proses paralel (halaman i % jumlah == bagian)

Berkas: <dir_proyek>/data/ocr_cache/<domain>/<pub_id>/<hal:04d>-<mesin>.json
  {"mesin", "versi", "dpi", "lebar_pt", "tinggi_pt", "detik_ocr",
   "kata": [{"text", "x0", "x1", "top", "bottom", "conf"}]}
Koordinat dalam POIN PDF (piksel * 72 / dpi), sama dengan koordinat
pdfplumber, supaya parser koordinat yang ada bisa memakainya langsung.
Halaman yang cache-nya sudah ada dilewati (aman diulang).
"""
import json
import os
import sys
import time

import pypdfium2 as pdfium

DIR = os.path.dirname(os.path.abspath(__file__))
DPI = 300
SKALA = 72 / DPI


def ocr_tesseract(img, psm=3):
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = os.path.join(DIR, "tesseract", "tesseract.exe")
    os.environ["TESSDATA_PREFIX"] = os.path.join(DIR, "tesseract", "tessdata")
    d = pytesseract.image_to_data(img, lang="ind+eng", config=f"--psm {psm}",
                                  output_type=pytesseract.Output.DICT)
    kata = []
    for i, t in enumerate(d["text"]):
        if not t.strip():
            continue
        x, y, w, h = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
        kata.append({"text": t, "x0": x * SKALA, "x1": (x + w) * SKALA,
                     "top": y * SKALA, "bottom": (y + h) * SKALA,
                     "conf": float(d["conf"][i]),
                     # baris menurut Tesseract: (blok, paragraf, baris)
                     "baris": [d["block_num"][i], d["par_num"][i], d["line_num"][i]]})
    return kata, str(pytesseract.get_tesseract_version())


_pembaca = None


def ocr_easyocr(img):
    import numpy as np
    import easyocr
    global _pembaca
    if _pembaca is None:
        _pembaca = easyocr.Reader(["id", "en"], gpu=False, verbose=False)
    kata = []
    for poli, t, conf in _pembaca.readtext(np.array(img)):
        xs = [p[0] for p in poli]; ys = [p[1] for p in poli]
        kata.append({"text": t, "x0": min(xs) * SKALA, "x1": max(xs) * SKALA,
                     "top": min(ys) * SKALA, "bottom": max(ys) * SKALA,
                     "conf": round(float(conf) * 100, 1)})
    return kata, easyocr.__version__


def main():
    deteksi = json.load(open(sys.argv[1], encoding="utf-8"))
    proyek, mesin = sys.argv[2], sys.argv[3]
    bagian, jumlah = int(sys.argv[4]), int(sys.argv[5])
    path_pdf = os.path.join(proyek, deteksi["pdf"])
    domain = os.path.basename(os.path.dirname(path_pdf))
    pub_id = os.path.splitext(os.path.basename(path_pdf))[0]
    keluar = os.path.join(proyek, "data", "ocr_cache", domain, pub_id)
    os.makedirs(keluar, exist_ok=True)
    # "tesseract" = psm 3 (bawaan); "tesseract-psm6"/"tesseract-psm4" = mode lain,
    # disimpan dengan nama berkas berbeda supaya bisa dibandingkan.
    if mesin.startswith("tesseract-psm"):
        psm = int(mesin.split("psm")[1])
        fungsi = lambda img: ocr_tesseract(img, psm)
    else:
        fungsi = {"tesseract": ocr_tesseract, "easyocr": ocr_easyocr}[mesin]
    pdf = pdfium.PdfDocument(path_pdf)
    for n in deteksi["halaman_ocr"]:
        if n % jumlah != bagian:
            continue
        berkas = os.path.join(keluar, f"{n:04d}-{mesin}.json")
        if os.path.exists(berkas):
            continue
        hal = pdf[n - 1]
        img = hal.render(scale=DPI / 72).to_pil().convert("RGB")
        t = time.perf_counter()
        kata, versi = fungsi(img)
        dt = time.perf_counter() - t
        sementara = berkas + ".tmp"
        json.dump({"mesin": mesin, "versi": versi, "dpi": DPI,
                   "lebar_pt": hal.get_width(), "tinggi_pt": hal.get_height(),
                   "detik_ocr": round(dt, 2), "kata": kata},
                  open(sementara, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(sementara, berkas)
        print(f"p{n} {len(kata)} kata {dt:.1f} s", flush=True)


if __name__ == "__main__":
    main()
