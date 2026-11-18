"""Kotak info kecamatan di database uji: dirender tanpa centang, tidak dirender dengan centang;
/api/kecamatan/jumlah = jumlah di seksi bercentang untuk kueri yang sama."""
import os, re, sys, time
from urllib.parse import urlencode
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.path.insert(0, f"{DIR}/tests"); sys.stdout.reconfigure(encoding="utf-8")
from potret_tampilan import konfigurasi
from app import create_app
c = create_app(konfigurasi("uji")).test_client()
for q, w in [("jumlah penduduk menurut desa", ""), ("penduduk", "6301"), ("tanah laut", ""), ("penduduk tala", ""), ("tpk", ""), ("penduduk", "6300")]:
    a = {"q": q, **({"w": w} if w else {})}
    t0 = c.get("/hasil?" + urlencode(a)).get_data(as_text=True)
    info = re.search(r'<div class="info-kecamatan" id="info-kecamatan" data-url="([^"]+)"', t0)
    t = time.perf_counter(); j = c.get(info.group(1).replace("&amp;", "&")).get_json(); ms = (time.perf_counter() - t) * 1000
    t1 = c.get("/hasil?" + urlencode({**a, "kec": "1"})).get_data(as_text=True)
    m = re.search(r"<strong>(\d+)</strong> bagian cocok", t1)
    n_seksi = int(m.group(1)) if m else t1.count('<span class="label-kecamatan">')
    print(f"{q!r} w={w or '-'}: info={bool(info)} api={j} ({ms:.0f} ms) | seksi bercentang={n_seksi} | "
          f"info saat dicentang={'id=\"info-kecamatan\"' in t1} | SAMA={j['jumlah'] == n_seksi}")
