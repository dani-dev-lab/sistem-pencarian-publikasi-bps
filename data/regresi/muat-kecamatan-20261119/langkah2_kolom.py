"""Langkah 2: tambahkan kolom baru ke PRODUKSI (skema.pastikan_kolom) - disetujui pemilik project."""
import os, sys
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy import text
from app import create_app
from app.models import db, skema
app = create_app()
with app.app_context():
    print("database:", db.engine.url.database)
    skema.pastikan_kolom()
    for t, k in (("publikasi", "kecamatan"), ("log_pencarian", "sertakan_kecamatan")):
        n = db.session.execute(text("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                                    "AND TABLE_NAME=:t AND COLUMN_NAME=:k"), {"t": t, "k": k}).scalar()
        print(f"{t}.{k}: {'ada' if n else 'TIDAK ADA'}")
    print("publikasi.kecamatan terisi:", db.session.execute(text("SELECT COUNT(*) FROM publikasi WHERE kecamatan IS NOT NULL")).scalar())
