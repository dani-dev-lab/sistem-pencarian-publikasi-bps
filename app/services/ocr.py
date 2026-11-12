"""OCR untuk halaman PDF tanpa lapisan teks (EasyOCR, OPSIONAL).

Delapan publikasi kab/kota tidak punya lapisan teks: hurufnya diubah menjadi
kurva vektor atau dirasterkan menjadi gambar (lihat CLAUDE.md, revisi 4). Modul
ini membuat halaman-halaman itu terbaca oleh parser koordinat yang SAMA, tanpa
mengubah parser: kotak kata hasil OCR disajikan dengan antarmuka halaman
pdfplumber (`.filter()` + `.extract_words()`).

Prinsip (rancangan disetujui pemilik project 12 Nov 2026):
- OPSIONAL. EasyOCR/torch/numpy hanya diimpor DI DALAM fungsi OCR, tidak di
  tingkat modul, sehingga server web yang mengimpor pipeline_data tidak
  pernah memuat torch. Kalau EasyOCR tidak terpasang, atau OCR dimatikan
  (perbarui.py --tanpa-ocr), halaman tanpa teks dilewati dan dicatat.
- HANYA halaman tanpa lapisan teks: karakter non-watermark (penyaring matriks
  _bukan_watermark yang sama dengan parser) bukan spasi < MIN_KARAKTER_TEKS,
  dan hanya di publikasi yang >= AMBANG_PUBLIKASI halamannya seperti itu.
- CACHE per halaman di data/ocr_cache/<domain>/<pub_id>/<hal:04d>-easyocr.json
  (di-gitignore), koordinat dalam poin PDF. _meta.json mencatat sidik PDF
  (ukuran, mtime) dan daftar halaman tanpa teks; sidik berubah = cache basi
  dan dibuat ulang. Cache dibaca tanpa EasyOCR.

Keterbatasan: OCR tidak memberi font/ukuran/warna, jadi jalur badan (pembeda
gaya keterangan) tidak menghasilkan entri dari halaman OCR. Entri datang
dari jalur Daftar; halaman_fisik tetap terisi lewat penanda bernomor.
"""

import json
import os
import re
import statistics
import time
from collections import defaultdict
from importlib.util import find_spec

from app.config import BASE_DIR

MESIN = "easyocr"
DPI = 300
SKALA = 72 / DPI
MIN_KARAKTER_TEKS = 20      # karakter non-watermark per halaman; di bawah ini = tanpa teks
# Syarat TINGKAT PUBLIKASI (12 Nov 2026): OCR hanya untuk publikasi yang
# sebagian besar halamannya tanpa teks. PDF bertekst juga punya halaman
# kosong, sampul, dan pembatas bab di bawah MIN_KARAKTER_TEKS (median korpus
# 10,7%); meng-OCR-nya sia-sia (+-25 detik per halaman kosong). Diukur di 306
# PDF: kedelapan target >= 69,6%, publikasi berikutnya 44,4% - ambang di celah.
AMBANG_PUBLIKASI = 0.5
PRASARING_KARAKTER = 300    # pypdfium2: lebih dari ini (watermark ikut) pasti bertekst
DIR_CACHE = os.path.join(BASE_DIR, "data", "ocr_cache")

# OCR tidak punya matriks karakter; watermark yang sempat terbaca dibuang
# menurut teksnya. Di cache HST (320 halaman) tidak ada satu pun.
RE_WATERMARK = re.compile(r"bps|go\.id|\.go\b", re.IGNORECASE)


def tersedia():
    """EasyOCR terpasang? Diperiksa TANPA mengimpornya (find_spec)."""
    return find_spec("easyocr") is not None


def folder_cache(path_pdf):
    domain = os.path.basename(os.path.dirname(os.path.abspath(path_pdf)))
    pub_id = os.path.splitext(os.path.basename(path_pdf))[0]
    return os.path.join(DIR_CACHE, domain, pub_id)


def _sidik(path_pdf):
    st = os.stat(path_pdf)
    return [st.st_size, int(st.st_mtime)]


def _tulis_atomik(path, isi):
    sementara = path + ".tmp"
    with open(sementara, "w", encoding="utf-8") as f:
        json.dump(isi, f, ensure_ascii=False)
    os.replace(sementara, path)


# --------------------------------------------------------------------------
# Deteksi halaman tanpa lapisan teks
# --------------------------------------------------------------------------

def _hitung_tanpa_teks(path_pdf, pdf=None):
    """(nomor halaman fisik tanpa lapisan teks, mulai 1; jumlah halaman)."""
    import pdfplumber
    import pypdfium2 as pdfium

    from app.services.ekstraksi_pdf import _bukan_watermark

    doc = pdfium.PdfDocument(path_pdf)
    try:
        jumlah = len(doc)
        tipis = []
        for i in range(jumlah):
            tp = doc[i].get_textpage()
            if tp.count_chars() <= PRASARING_KARAKTER:
                tipis.append(i)
    finally:
        doc.close()
    if not tipis:
        return [], jumlah
    buka = pdf is None
    pdf = pdf or pdfplumber.open(path_pdf)
    try:
        hasil = []
        for i in tipis:
            n = sum(1 for c in pdf.pages[i].filter(_bukan_watermark).chars if c["text"].strip())
            if n < MIN_KARAKTER_TEKS:
                hasil.append(i + 1)
        return hasil, jumlah
    finally:
        if buka:
            pdf.close()


def halaman_tanpa_teks(path_pdf, pdf=None):
    """Halaman yang perlu OCR: [] kecuali publikasi ini >= AMBANG_PUBLIKASI
    tanpa teks. Return (halaman, jumlah_halaman_tanpa_teks, jumlah_halaman).

    Memakai _meta.json kalau sidik PDF sama (deteksi halaman berkurva vektor
    bisa makan beberapa menit). _meta.json hanya ditulis untuk publikasi yang
    lolos syarat, jadi PDF bertekst tidak meninggalkan folder cache.
    """
    folder = folder_cache(path_pdf)
    meta_path = os.path.join(folder, "_meta.json")
    sidik = _sidik(path_pdf)
    if os.path.exists(meta_path):
        meta = json.load(open(meta_path, encoding="utf-8"))
        if meta.get("sidik") == sidik and "jumlah_halaman" in meta:
            h = meta["halaman_tanpa_teks"]
            return h, len(h), meta["jumlah_halaman"]
    halaman, jumlah = _hitung_tanpa_teks(path_pdf, pdf)
    if not halaman or len(halaman) < AMBANG_PUBLIKASI * jumlah:
        return [], len(halaman), jumlah
    os.makedirs(folder, exist_ok=True)
    # Cache lama untuk PDF yang sudah berganti tidak boleh dipakai lagi.
    if os.path.exists(meta_path) and json.load(open(meta_path, encoding="utf-8")).get("sidik") != sidik:
        for f in os.listdir(folder):
            if f.endswith(f"-{MESIN}.json"):
                os.remove(os.path.join(folder, f))
    _tulis_atomik(meta_path, {"sidik": sidik, "mesin": MESIN, "dpi": DPI,
                              "kriteria": f"karakter non-watermark < {MIN_KARAKTER_TEKS}, "
                                          f"publikasi >= {AMBANG_PUBLIKASI:.0%} halaman",
                              "jumlah_halaman": jumlah, "halaman_tanpa_teks": halaman})
    return halaman, len(halaman), jumlah


# --------------------------------------------------------------------------
# OCR satu halaman (EasyOCR diimpor HANYA di sini)
# --------------------------------------------------------------------------

_pembaca = None


def _ocr_halaman(path_pdf, nomor):
    """Render halaman 300 dpi lalu EasyOCR. Return isi berkas cache."""
    global _pembaca
    import easyocr          # noqa: PLC0415 - sengaja di sini, lihat docstring modul
    import numpy as np      # noqa: PLC0415
    import pypdfium2 as pdfium

    if _pembaca is None:
        _pembaca = easyocr.Reader(["id", "en"], gpu=False, verbose=False)
    doc = pdfium.PdfDocument(path_pdf)
    try:
        hal = doc[nomor - 1]
        img = hal.render(scale=DPI / 72).to_pil().convert("RGB")
        lebar, tinggi = hal.get_width(), hal.get_height()
    finally:
        doc.close()
    mulai = time.perf_counter()
    kata = []
    for poli, teks, conf in _pembaca.readtext(np.array(img)):
        xs = [p[0] for p in poli]
        ys = [p[1] for p in poli]
        kata.append({"text": teks, "x0": min(xs) * SKALA, "x1": max(xs) * SKALA,
                     "top": min(ys) * SKALA, "bottom": max(ys) * SKALA,
                     "conf": round(float(conf) * 100, 1)})
    return {"mesin": MESIN, "versi": easyocr.__version__, "dpi": DPI,
            "lebar_pt": lebar, "tinggi_pt": tinggi,
            "detik_ocr": round(time.perf_counter() - mulai, 2), "kata": kata}


def berkas_cache(path_pdf, nomor):
    return os.path.join(folder_cache(path_pdf), f"{nomor:04d}-{MESIN}.json")


def isi_cache(path_pdf, halaman, log=print):
    """OCR halaman-halaman yang belum punya cache. Return jumlah yang di-OCR.
    Aman dilanjutkan: halaman yang cache-nya sudah ada dilewati."""
    n = 0
    for i, nomor in enumerate(halaman, 1):
        berkas = berkas_cache(path_pdf, nomor)
        if os.path.exists(berkas):
            continue
        isi = _ocr_halaman(path_pdf, nomor)
        _tulis_atomik(berkas, isi)
        n += 1
        log(f"      hal. {nomor} ({i}/{len(halaman)}): {len(isi['kata'])} kata, {isi['detik_ocr']} s")
    return n


# --------------------------------------------------------------------------
# Adaptor: halaman OCR berantarmuka halaman pdfplumber
# --------------------------------------------------------------------------

class HalamanOCR:
    """Kotak kata dari cache OCR sebagai 'halaman' untuk parser.

    size = tinggi kotak (dibulatkan 0,5 pt). Kalau cache punya nomor baris
    (Tesseract: blok/paragraf/baris), dipakai tinggi median sebaris; EasyOCR
    tidak punya, jadi tiap kotak memakai tingginya sendiri - konfigurasi yang
    dinilai pada 30 tabel HST (12 Nov 2026). fontname "OCR" dan warna hitam:
    OCR tidak tahu font maupun warna.
    """

    def __init__(self, data):
        kata = [k for k in data["kata"] if not RE_WATERMARK.search(k["text"])]
        per_baris = defaultdict(list)
        for k in kata:
            if k.get("baris"):
                per_baris[tuple(k["baris"])].append(k["bottom"] - k["top"])
        self.kata = []
        for k in kata:
            tinggi = (statistics.median(per_baris[tuple(k["baris"])]) if k.get("baris")
                      else k["bottom"] - k["top"])
            self.kata.append({**k, "size": round(tinggi * 2) / 2, "fontname": "OCR",
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
    """pdf pdfplumber dengan sebagian halaman diganti HalamanOCR."""

    def __init__(self, pdf, ganti):
        self.pages = [ganti.get(i + 1, h) for i, h in enumerate(pdf.pages)]


def penyiap(path_pdf, aktif=True, catatan=None, log=print):
    """Fungsi untuk ekstrak_lengkap(penyiap_pdf=...).

    aktif=False (--tanpa-ocr): OCR tidak dipakai sama sekali (cache juga
    tidak) - perilaku sebelum OCR ada; halaman tanpa teks hanya dicatat.
    aktif=True: pakai cache; halaman tanpa cache di-OCR kalau EasyOCR
    terpasang, kalau tidak dilewati. Ringkasan ditulis ke `catatan`.
    """
    def siapkan(pdf):
        halaman, n_tanpa_teks, jumlah = halaman_tanpa_teks(path_pdf, pdf)
        # halaman_tanpa_teks di catatan = halaman yang PERLU OCR. Halaman kosong
        # di PDF bertekst (di bawah AMBANG_PUBLIKASI) bukan kekurangan.
        info = {"halaman_tanpa_teks": len(halaman), "dari_cache": 0, "di_ocr": 0,
                "dilewati": 0, "alasan_dilewati": None,
                "rasio_tanpa_teks": round(n_tanpa_teks / max(jumlah, 1), 3)}
        if not halaman:
            if catatan is not None:
                catatan.update(info)
            return pdf
        if not aktif:
            info.update(dilewati=len(halaman), alasan_dilewati="OCR dimatikan (--tanpa-ocr)")
        else:
            ada = [n for n in halaman if os.path.exists(berkas_cache(path_pdf, n))]
            belum = [n for n in halaman if n not in set(ada)]
            info["dari_cache"] = len(ada)
            if belum and tersedia():
                log(f"      OCR {len(belum)} halaman tanpa teks (EasyOCR, +-15 detik/halaman)")
                info["di_ocr"] = isi_cache(path_pdf, belum, log)
            elif belum:
                info.update(dilewati=len(belum), alasan_dilewati="EasyOCR tidak terpasang")
        if catatan is not None:
            catatan.update(info)
        ganti = {}
        for n in halaman:
            berkas = berkas_cache(path_pdf, n)
            if aktif and os.path.exists(berkas):
                ganti[n] = HalamanOCR(json.load(open(berkas, encoding="utf-8")))
        return PdfCampuran(pdf, ganti) if ganti else pdf

    return siapkan
