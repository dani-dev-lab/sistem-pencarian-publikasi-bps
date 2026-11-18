"""Memori korpus pencarian dan waktu muat ulangnya (metode korpus-memori-20261110.md).
  python ukur_memori_korpus.py [--db-uji] [--ulang 5]
Hanya membaca database. tracemalloc: memori yang DITAHAN satu objek Korpus + puncak saat membangun."""
import argparse, gc, os, statistics, sys, time, tracemalloc
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.stdout.reconfigure(encoding="utf-8")
from app import create_app
from app.config import KonfigurasiUji
from app.services import mesin_pencari, versi_data

a = argparse.ArgumentParser(); a.add_argument("--db-uji", action="store_true"); a.add_argument("--ulang", type=int, default=5)
o = a.parse_args()
app = create_app(KonfigurasiUji) if o.db_uji else create_app()
with app.app_context():
    from app.models import db
    kamus = mesin_pencari.kamus_default(); versi = versi_data.baca()
    mesin_pencari._bangun_korpus(versi, kamus)          # pemanasan (stemmer, koneksi)
    waktu = []
    for _ in range(o.ulang):
        gc.collect(); t = time.perf_counter(); k = mesin_pencari._bangun_korpus(versi, kamus); waktu.append(time.perf_counter() - t); del k
    gc.collect(); tracemalloc.start()
    k = mesin_pencari._bangun_korpus(versi, kamus)
    gc.collect(); ditahan, puncak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    per_dom = {d: len(v) for d, v in k.entri_per_domain.items()}
    print(f"database {db.engine.url.database}: {len(k.publikasi)} publikasi, {len(k.entri)} entri")
    print(f"muat ulang korpus: median {statistics.median(waktu)*1000:.0f} ms, maks {max(waktu)*1000:.0f} ms ({o.ulang}x)")
    print(f"memori ditahan {ditahan/2**20:.1f} MB, puncak saat membangun {puncak/2**20:.1f} MB")
    print("entri per domain:", dict(sorted(per_dom.items())))
