"""Bagian 1: kolom publikasi.kecamatan di database uji dan salinan (produksi tidak dipakai)."""
import os, sys
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.path.insert(0, f"{DIR}/tests"); sys.stdout.reconfigure(encoding="utf-8")
os.environ["PYTHONHASHSEED"] = "0"
from potret_tampilan import konfigurasi
from app import create_app
from app.models import db, skema
from sqlalchemy import text
for nama in ("uji", "salinan"):
    app = create_app(konfigurasi(nama))
    with app.app_context():
        v0 = db.session.execute(text("select versi from versi_data")).scalar()
        skema._SIAP = False; skema.pastikan_kolom()
        v1 = db.session.execute(text("select versi from versi_data")).scalar()
        n2 = skema.sinkron_kecamatan()
        r = db.session.execute(text("select count(*), sum(kecamatan is not null), count(distinct concat(domain, kecamatan)), "
                                    "sum(kecamatan is not null and judul not like 'Kecamatan%'), sum(kecamatan is null and judul like 'Kecamatan%') from publikasi")).one()
        print(f"{db.engine.url.database}: publikasi {r[0]}, kecamatan terisi {r[1]}, kecamatan unik {r[2]}, "
              f"salah-tanda {r[3]}/{r[4]}, versi {v0}->{v1}, sinkron kedua menulis {n2}")
