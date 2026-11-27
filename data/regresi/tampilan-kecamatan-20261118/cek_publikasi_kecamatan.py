"""Seksi PUBLIKASI dengan publikasi kecamatan (database uji). Contoh pemilik project:
kotak dicentang, Kab. Tanah Laut, kecamatan Kintap, "Kecamatan Kintap Dalam Angka 2026"."""
import os, re, sys, html
from urllib.parse import urlencode
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.path.insert(0, f"{DIR}/tests"); sys.stdout.reconfigure(encoding="utf-8")
from potret_tampilan import konfigurasi
from app import create_app
c = create_app(konfigurasi("uji")).test_client()
def publikasi(a):
    t = c.get("/hasil?" + urlencode(a)).get_data(as_text=True)
    s = re.search(r'<h2 class="seksi">Publikasi</h2>(.*?)</section>', t, re.S)
    kartu = re.findall(r'<article class="kartu kartu-pub">(.*?)</article>', s.group(1), re.S) if s else []
    keluar = []
    for k in kartu:
        judul = html.unescape(re.sub("<[^>]+>", "", re.search(r'<h3 class="kartu-judul">(.*?)</h3>', k, re.S).group(1))).strip()
        kec = re.search(r'label-kecamatan">(.*?)</span>', k)
        keluar.append((judul, kec.group(1) if kec else None))
    jumlah = re.search(r"<strong>(\d+)</strong> publikasi", t)
    return keluar, int(jumlah.group(1)) if jumlah else None
q = "Kecamatan Kintap Dalam Angka 2026"
for a in [{"q": "penduduk", "w": "6301", "kec": "1"}, {"q": "penduduk", "w": "6301"}, {"q": q, "w": "6301", "kec": "1", "kc": "kintap"}, {"q": q, "w": "6301", "kc": "kintap"},
          {"q": q, "w": "6301", "kec": "1"}, {"q": q, "kec": "1"}, {"q": q, "w": "6301"}, {"q": q}]:
    k, n = publikasi(a)
    print(f"{a}: {len(k)} kartu (ringkas {n}), kecamatan {sum(1 for _, x in k if x)}")
    for judul, kec in k[:3]:
        print(f"     {judul[:60]} | {kec}")
