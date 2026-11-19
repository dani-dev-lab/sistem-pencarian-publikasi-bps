"""Dengan centang di PRODUKSI (log mati): 3 kueri, seksi kecamatan + seksi Publikasi tampil, dan
tombol PDF 5 kartu kecamatan pertama per kueri dicek ke halaman PDF sebenarnya (teks halaman memuat
nomor tabel atau awal judul). Hanya membaca."""
import os, re, sys, html, glob
from urllib.parse import urlencode
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.stdout.reconfigure(encoding="utf-8")
import pdfplumber
from app import create_app
from app.config import Config
from app.services.ekstraksi_pdf import _bukan_watermark
app = create_app(type("KonfigurasiProduksiTanpaLog", (Config,), {"CATAT_LOG_PENCARIAN": False}))
c = app.test_client()
for a in [{"q": "jumlah penduduk menurut desa", "kec": "1"}, {"q": "sekolah", "w": "6301", "kec": "1"},
          {"q": "Kecamatan Kintap Dalam Angka 2026", "w": "6301", "kc": "kintap", "kec": "1"}]:
    t = c.get("/hasil?" + urlencode(a)).get_data(as_text=True)
    seksi = re.search(r'<h2 class="seksi seksi-kecamatan">.*?</section>', t, re.S)
    pub = re.search(r'<h2 class="seksi">Publikasi</h2>(.*?)</section>', t, re.S)
    m1 = re.search(r'<h3 class="kartu-judul">(.*?)</h3>', pub.group(1), re.S) if pub else None
    pub1 = m1.group(1) if m1 else "(tidak ada kartu)"
    print(f"{a}: seksi kecamatan {bool(seksi)}, publikasi pertama: {html.unescape(re.sub('<[^>]+>', '', pub1)).strip()[:50]}")
    benar = cek = 0
    for kartu in re.findall(r'<article class="kartu kartu-(?:tabel|gambar|lampiran)">(.*?)</article>', seksi.group(0) if seksi else "", re.S)[:5]:
        m = re.search(r'href="/pdf/([0-9a-f]+)#page=(\d+)"', kartu); n = re.search(r"Nomor ([0-9.]+)", kartu)
        judul = html.unescape(re.sub("<[^>]+>", "", re.search(r'<h3 class="kartu-judul">(.*?)</h3>', kartu, re.S).group(1))).strip()
        if not m: continue
        f = glob.glob(f"data/publikasi_pdf/*/{m.group(1)}.pdf")[0]
        with pdfplumber.open(f) as pdf:
            teks = re.sub(r"\s+", " ", pdf.pages[int(m.group(2)) - 1].filter(_bukan_watermark).extract_text() or "")
        # Publikasi OCR (PDF tanpa lapisan teks): teks halaman dari cache OCR - yang
        # dibaca parser. Versi alat pertama memakai lapisan teks saja dan salah
        # menandai Gambar 4 Mataraman 2025 hal. 41 (gambarnya dicek: benar).
        cache = glob.glob(f"data/ocr_cache/*/{m.group(1)}/{int(m.group(2)):04d}-easyocr.json")
        if not teks.strip() and cache:
            import json
            teks = " ".join(w["text"] for w in json.load(open(cache[0], encoding="utf-8"))["kata"])
        kata = " ".join(judul.split()[:4])
        ok = (n and re.search(r"\b" + re.escape(n.group(1)) + r"\b", teks)) or kata.lower() in teks.lower()
        cek += 1; benar += bool(ok)
        print(f"     hal {m.group(2):>4} nomor {n.group(1) if n else '-':8} {'OK ' if ok else 'CEK'} {judul[:55]}")
    print(f"     tombol PDF: {benar}/{cek} halaman memuat nomor/awal judul")
