"""CHECKSUM TABLE + jumlah baris semua tabel satu database (HANYA membaca).
  venv/Scripts/python.exe checksum_db.py produksi|uji > keluar.json"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import sqlalchemy as sa  # noqa: E402

from app.config import Config, KonfigurasiUji  # noqa: E402

url = Config.SQLALCHEMY_DATABASE_URI if sys.argv[1] == "produksi" else KonfigurasiUji.SQLALCHEMY_DATABASE_URI
hasil = {}
with sa.create_engine(url).connect() as k:
    for (t,) in k.execute(sa.text("SHOW TABLES")):
        n = k.execute(sa.text(f"SELECT COUNT(*) FROM `{t}`")).scalar()
        c = k.execute(sa.text(f"CHECKSUM TABLE `{t}`")).all()[0][1]
        hasil[t] = [n, int(c) if c is not None else None]
print(json.dumps({"database": sa.engine.make_url(url).database, "tabel": hasil}, indent=1))
