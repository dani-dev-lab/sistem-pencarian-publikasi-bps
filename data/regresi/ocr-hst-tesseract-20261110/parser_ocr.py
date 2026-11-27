"""Jalankan parser produksi (app/services/ekstraksi_pdf.py, TIDAK diubah) pada
halaman hasil OCR. Untuk spike revisi 4; hasil ke berkas, BUKAN ke MySQL.

Jalankan dengan venv PROYEK dari folder proyek:
  venv/Scripts/python.exe C:/Users/Dani/alat-ocr/parser_ocr.py <deteksi.json> <mesin> <keluaran.json>

Adaptor:
  - Halaman yang punya lapisan teks tetap halaman pdfplumber asli.
  - Halaman tanpa lapisan teks diganti HalamanOCR: kata dari cache OCR
    (koordinat poin PDF), dengan
      size     = tinggi median baris OCR-nya, dibulatkan 0,5 pt (OCR tidak
                 memberi ukuran huruf; tinggi baris pengganti terdekat)
      fontname = "OCR", non_stroking_color = (0,) - OCR tidak tahu font
                 atau warna, jadi pembeda gaya jalur badan hanya ukuran.
  - Kata watermark dibuang menurut teks (mengandung "bps" / "go.id"),
    karena OCR tidak punya matriks karakter. Ini SATU-SATUNYA aturan teks.
Urutan langkah sama dengan ekstrak_lengkap().
"""
import json
import os
import re
import statistics
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.getcwd())
import pdfplumber  # noqa: E402

from app.services import ekstraksi_pdf as ep  # noqa: E402

RE_WATERMARK = re.compile(r"bps|go\.id|\.go\b", re.IGNORECASE)


class HalamanOCR:
    def __init__(self, data):
        per_baris = defaultdict(list)
        for k in data["kata"]:
            per_baris[tuple(k.get("baris") or (id(k),))].append(k["bottom"] - k["top"])
        tinggi = {b: statistics.median(v) for b, v in per_baris.items()}
        self.kata = []
        for k in data["kata"]:
            if RE_WATERMARK.search(k["text"]):
                continue
            t = tinggi[tuple(k.get("baris") or (id(k),))]
            self.kata.append({**k, "size": round(t * 2) / 2, "fontname": "OCR",
                              "non_stroking_color": (0,)})
        self.width = data["lebar_pt"]
        self.height = data["tinggi_pt"]

    def filter(self, _fungsi):
        return self

    def extract_words(self, extra_attrs=None, **_):
        kunci = {"text", "x0", "x1", "top", "bottom"} | set(extra_attrs or ())
        return [{k: v for k, v in kata.items() if k in kunci}
                for kata in sorted(self.kata, key=lambda k: (round(k["top"]), k["x0"]))]


class PdfCampuran:
    def __init__(self, pdf, ganti):
        self.pages = [ganti.get(i + 1, h) for i, h in enumerate(pdf.pages)]


def main():
    deteksi = json.load(open(sys.argv[1], encoding="utf-8"))
    mesin, keluar = sys.argv[2], sys.argv[3]
    # Opsional: mesin lain untuk rentang halaman tertentu, mis. "tesseract-psm4:10-30"
    # (psm 4 hanya untuk halaman Daftar Tabel). Dicatat di ringkasan.
    timpa = {}
    if len(sys.argv) > 4:
        m2, rentang = sys.argv[4].split(":")
        a, b = map(int, rentang.split("-"))
        timpa = {n: m2 for n in range(a, b + 1)}
    path = deteksi["pdf"]
    domain = os.path.basename(os.path.dirname(path))
    pub_id = os.path.splitext(os.path.basename(path))[0]
    cache = os.path.join("data", "ocr_cache", domain, pub_id)
    ganti, hilang = {}, []
    for n in deteksi["halaman_ocr"]:
        f = os.path.join(cache, f"{n:04d}-{timpa.get(n, mesin)}.json")
        if os.path.exists(f):
            ganti[n] = HalamanOCR(json.load(open(f, encoding="utf-8")))
        else:
            hilang.append(n)
    if hilang:
        raise SystemExit(f"cache OCR belum lengkap: {len(hilang)} halaman, mis. {hilang[:5]}")

    t = time.perf_counter()
    with pdfplumber.open(path) as asli:
        pdf = PdfCampuran(asli, ganti)
        heading = ep.cari_heading(pdf)
        dari_daftar = []
        for tipe, halaman in sorted(heading.items(), key=lambda x: x[1]):
            dari_daftar.extend(ep._baca_daftar(pdf, halaman, tipe, pub_id))
        for e in dari_daftar:
            e.setdefault("halaman_fisik", None)
            e.setdefault("sumber", "daftar")
        baris_halaman = {}
        dari_badan = ep.ekstrak_badan(pdf, pub_id, baris_halaman)
        gabungan = ep._gabung(dari_daftar, dari_badan)
        n_fisik = ep.lengkapi_halaman_fisik(pdf, gabungan)
        n_isi = ep.lengkapi_halaman_isi(gabungan, baris_halaman)
    ringkas = {"pdf": path, "mesin": mesin, "timpa": sys.argv[4] if len(sys.argv) > 4 else None, "halaman_ocr": len(ganti),
               "heading": heading, "dari_daftar": len(dari_daftar), "dari_badan": len(dari_badan),
               "halaman_fisik_dilengkapi": n_fisik, "halaman_fisik_isi": n_isi,
               "entri": len(gabungan), "detik_parser": round(time.perf_counter() - t, 1)}
    json.dump({"ringkasan": ringkas, "entri": gabungan}, open(keluar, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)
    print(json.dumps(ringkas, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
