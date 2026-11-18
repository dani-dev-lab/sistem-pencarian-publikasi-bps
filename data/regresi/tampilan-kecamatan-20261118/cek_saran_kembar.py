"""/api/saran di database uji, dengan dan tanpa kec=1: jumlah saran, judul kembar, waktu."""
import os, sys, time
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.path.insert(0, f"{DIR}/tests"); sys.stdout.reconfigure(encoding="utf-8")
from potret_tampilan import konfigurasi
from app import create_app
c = create_app(konfigurasi("uji")).test_client()
for a in ["penduduk", "luas pan", "jumlah sek", "tpk", "ekspor", "jumlah penduduk menurut desa", "sekolah", "kepala desa"]:
    for kec in ("", "1"):
        t = time.perf_counter(); s = c.get("/api/saran", query_string={"q": a, **({"kec": kec} if kec else {})}).get_json()["saran"]
        ms = (time.perf_counter() - t) * 1000
        kembar = len(s) - len({x["judul"].strip().lower() for x in s})
        print(f"{a!r:32} kec={kec or '-'}: {len(s)} saran, kembar {kembar}, kecamatan {sum('Kecamatan' in x['publikasi'] for x in s)}, {ms:.0f} ms")
