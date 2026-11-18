"""Waktu 12 kueri uji tanpa centang: salinan produksi vs database uji (berkecamatan), bergantian 2x.
Median per kueri dari 20 ulangan, lalu rata-rata median dan kueri terlambat."""
import os, statistics, sys, time
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.path.insert(0, f"{DIR}/tests"); sys.path.insert(0, f"{DIR}/scripts")
sys.stdout.reconfigure(encoding="utf-8")
from potret_tampilan import konfigurasi
from ukur_kinerja import KUERI
from app import create_app
from app.services import mesin_pencari as M
def ukur(db):
    M._korpus = None
    with create_app(konfigurasi(db)).app_context():
        M.cari("pemanasan"); med = []
        for k in KUERI:
            M.cari(k); w = []
            for _ in range(20):
                t = time.perf_counter(); M.cari(k); w.append((time.perf_counter() - t) * 1000)
            med.append(statistics.median(w))
    return statistics.mean(med), max(med)
for putaran in (1, 2):
    for db in ("salinan", "uji"):
        r, m = ukur(db)
        print(f"putaran {putaran} {db:8s} rata-rata median {r:6.1f} ms, terlambat {m:6.1f} ms")
