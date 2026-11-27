"""Muat ulang publikasi tertentu ke DATABASE PRODUKSI (varian muat_salinan.py) dengan jalur penulis yang
sama dengan scripts/perbarui.py: sidik_pdf -> ekstrak_berkas -> simpan_entri.

PENGAMAN: menolak jalan kalau DATABASE_URL menunjuk db_pencarian_bps
(produksi). DATABASE_URL salinan diberikan lewat variabel lingkungan;
python-dotenv tidak menimpa variabel yang sudah ada.
Pemakaian: DATABASE_URL=... python muat_salinan.py <daftar_pid.json>
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())
from sqlalchemy.engine import make_url  # noqa: E402

from app import create_app  # noqa: E402
from app.config import KonfigurasiUji  # noqa: E402
from app.models import Publikasi, db  # noqa: E402
from app.services import pipeline_data, sumber_bps, versi_data  # noqa: E402

app = create_app(KonfigurasiUji)
nama_db = make_url(app.config["SQLALCHEMY_DATABASE_URI"]).database
# Varian PRODUKSI (12 Nov 2026, disetujui pemilik project): hanya ke
# db_pencarian_bps dan hanya dengan flag eksplisit. Jalur penulisnya sama
# persis dengan pemuat salinan.
if nama_db != "db_pencarian_bps" or "--produksi-disetujui" not in sys.argv:
    raise SystemExit(f"DITOLAK: butuh db_pencarian_bps + --produksi-disetujui (dapat {nama_db!r})")
print("database:", nama_db)
pid = json.load(open(sys.argv[1]))
with app.app_context():
    versi_data.pastikan_tabel()
    for i, p in enumerate(pid, 1):
        pub = db.session.get(Publikasi, p)
        path = f"data/publikasi_pdf/{pub.domain}/{p}.pdf"
        sidik = sumber_bps.sidik_pdf(path)
        entri, catatan = pipeline_data.ekstrak_berkas(path, p)
        pipeline_data.simpan_entri(p, entri, sidik, catatan)
        print(f"[{i}/{len(pid)}] {p[:8]} {len(entri)} entri", flush=True)
