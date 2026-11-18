"""/api/saran di database uji: tanpa kec=1 tidak ada saran dari publikasi kecamatan; dengan kec=1 boleh ada."""
import os, sys, json
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.path.insert(0, f"{DIR}/tests"); sys.stdout.reconfigure(encoding="utf-8")
from potret_tampilan import konfigurasi, AWALAN_SARAN
from app import create_app
c = create_app(konfigurasi("uji")).test_client()
for a in AWALAN_SARAN + ["jumlah penduduk menurut desa"]:
    s0 = c.get("/api/saran", query_string={"q": a}).get_json()["saran"]
    s1 = c.get("/api/saran", query_string={"q": a, "kec": "1"}).get_json()["saran"]
    k0 = sum("Kecamatan" in x["publikasi"] for x in s0); k1 = sum("Kecamatan" in x["publikasi"] for x in s1)
    print(f"{a!r:32} tanpa kec: {len(s0)} saran, {k0} kecamatan | kec=1: {len(s1)} saran, {k1} kecamatan")
