"""log_pencarian.sertakan_kecamatan: database uji (berkecamatan) -> 0/1, salinan produksi -> NULL.
Baris uji dihapus lagi; CHECKSUM log_pencarian sebelum = sesudah."""
import os, sys
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.path.insert(0, f"{DIR}/tests"); sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy import text
from potret_tampilan import konfigurasi
from app import create_app
from app.models import db, skema
for nama in ("uji", "salinan"):
    K = type("KonfigurasiLog", (konfigurasi(nama),), {"CATAT_LOG_PENCARIAN": True})
    skema._SIAP = False      # pastikan_kolom sekali per PROSES; skrip ini memakai dua database
    app = create_app(K)
    with app.app_context():
        c = app.test_client(); c.get("/")                    # pastikan_kolom
        cs0 = db.session.execute(text("CHECKSUM TABLE log_pencarian")).one()[1]
        id0 = db.session.execute(text("SELECT COALESCE(MAX(id), 0) FROM log_pencarian")).scalar()
        for u in ["/hasil?q=penduduk&w=6301", "/hasil?q=penduduk&w=6301&kec=1", "/hasil?q=tpk&kc=pelaihari&w=6301"]:
            c.get(u)
        db.session.commit()
        baris = db.session.execute(text("SELECT keyword, wilayah_filter, jumlah_hasil, sertakan_kecamatan FROM log_pencarian "
                                        "WHERE id > :i ORDER BY id"), {"i": id0}).all()
        db.session.execute(text("DELETE FROM log_pencarian WHERE id > :i"), {"i": id0}); db.session.commit()
        cs1 = db.session.execute(text("CHECKSUM TABLE log_pencarian")).one()[1]
        print(db.engine.url.database, [tuple(b) for b in baris], "| CHECKSUM sama sesudah dihapus:", cs0 == cs1)
