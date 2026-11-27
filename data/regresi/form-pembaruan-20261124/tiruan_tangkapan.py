"""WebAPI TIRUAN untuk tangkapan layar "Cek dulu" (24 Nov 2026). BUKAN data BPS.

Menyajikan daftar publikasi ke-14 wilayah dari DATABASE UJI (hanya dibaca),
berbentuk respons WebAPI, terurut rl_date terbaru, 10 per halaman. Supaya
hasil cek tidak kosong, diberi simulasi:
  - Kab. Tanah Laut (6301): 3 publikasi rekaan rilis 2024 ("baru", ukuran
    rekaan 12/18/25 MB), dan 2 publikasi yang ada dibuat "direvisi";
  - Provinsi (6300): SEMUA publikasi dibuat "direvisi" (skenario peringatan
    penarikan besar).
Ukuran (`size`) = ukuran PDF lokal kalau ada, selain itu 10 MB.

Jalankan: venv/Scripts/python.exe tiruan_tangkapan.py PORT
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, DIR)

import sqlalchemy as sa  # noqa: E402

from app.config import Config, KonfigurasiUji  # noqa: E402

PORT = int(sys.argv[1])
DATA = {}
mesin = sa.create_engine(KonfigurasiUji.SQLALCHEMY_DATABASE_URI)
with mesin.connect() as k:
    for r in k.execute(sa.text(
            "SELECT id, domain, judul, abstrak, tanggal_rilis, updt_date_api FROM publikasi "
            "ORDER BY domain, tanggal_rilis DESC, id")).mappings():
        path = os.path.join(str(Config.DIR_PUBLIKASI_PDF), r["domain"], f"{r['id']}.pdf")
        mb = os.path.getsize(path) / 1e6 if os.path.exists(path) else 10.0
        DATA.setdefault(r["domain"], []).append({
            "pub_id": r["id"], "title": r["judul"], "abstract": r["abstrak"],
            "rl_date": str(r["tanggal_rilis"]), "size": f"{mb:.2f} MB",
            "updt_date": str(r["updt_date_api"]) if r["updt_date_api"] else None,
            "pdf": f"http://127.0.0.1:{PORT}/pdf/{r['id']}", "cover": None, "subject_csa": []})
# Skenario "penarikan besar": semua publikasi provinsi dibuat direvisi, supaya
# cek semua wilayah melewati ambang peringatan (>= 50 publikasi).
for p in DATA["6300"]:
    p["updt_date"] = "2026-11-21"
tala = DATA["6301"]
for p in tala[:2]:
    p["updt_date"] = "2026-11-20"
for i, (judul, mb) in enumerate((("Kabupaten Tanah Laut Dalam Angka 2024 (REKAAN)", 25),
                                 ("Statistik Daerah Kabupaten Tanah Laut 2024 (REKAAN)", 12),
                                 ("Kecamatan Jorong Dalam Angka 2024", 18))):
    tala.append({"pub_id": f"rekaan{i}tangkapanlayar0000", "title": judul, "abstract": "rekaan",
                 "rl_date": f"2024-0{9 - i}-30", "size": f"{mb} MB", "updt_date": None,
                 "pdf": "", "cover": None, "subject_csa": []})
for d in DATA.values():
    d.sort(key=lambda p: p["rl_date"], reverse=True)


class Tiruan(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        m = re.match(r"/v1/api/list/model/publication/lang/ind/domain/(\d+)/page/(\d+)/key/", self.path)
        if not m:
            self.send_response(404)
            self.end_headers()
            return
        pubs = DATA.get(m.group(1), [])
        hal = int(m.group(2))
        n = max(1, -(-len(pubs) // 10))
        isi = json.dumps({"status": "OK", "data-availability": "available",
                          "data": [{"page": hal, "pages": n, "total": len(pubs)},
                                   pubs[(hal - 1) * 10:hal * 10]]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(isi)))
        self.end_headers()
        self.wfile.write(isi)


print(f"tiruan siap di {PORT}: {sum(len(v) for v in DATA.values())} publikasi", flush=True)
ThreadingHTTPServer(("127.0.0.1", PORT), Tiruan).serve_forever()
