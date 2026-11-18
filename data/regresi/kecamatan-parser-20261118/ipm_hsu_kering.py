"""IPM HSU (a21060d6, hanya di produksi): ekstraksi kering parser sekarang vs produksi, per kunci. Produksi hanya dibaca."""
import os, sys, glob
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy import create_engine, text
from app.config import Config
from app.services import pipeline_data, perkiraan_halaman
pid = [r for r in create_engine(Config.SQLALCHEMY_DATABASE_URI).connect().execute(
    text("select id, domain from publikasi where id like 'a21060d6%'"))][0]
with create_engine(Config.SQLALCHEMY_DATABASE_URI).connect() as c:
    lama = [dict(r._mapping) for r in c.execute(text(
        "select tipe, nomor, judul, halaman, halaman_fisik from entri_dokumen where publikasi_id=:p order by id"), {"p": pid[0]})]
entri, _ = pipeline_data.ekstrak_berkas(f"data/publikasi_pdf/{pid[1]}/{pid[0]}.pdf", pid[0], log=lambda *_: None)
prk = perkiraan_halaman.perkirakan(entri)
baru = [{"tipe": e["tipe"], "nomor": e.get("nomor"), "judul": e["judul"], "halaman": e.get("halaman"),
         "halaman_fisik": e.get("halaman_fisik") or prk.get(i)} for i, e in enumerate(entri)]
print("produksi", len(lama), "kering", len(baru), "identik per urutan dan isi:", lama == baru)
