"""Diagnosa selisih waktu tanpa centang: ukuran korpus + waktu dengan GC normal vs GC mati."""
import gc, os, statistics, sys, time
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.path.insert(0, f"{DIR}/tests"); sys.path.insert(0, f"{DIR}/scripts")
sys.stdout.reconfigure(encoding="utf-8")
from potret_tampilan import konfigurasi
from ukur_kinerja import KUERI
from app import create_app
from app.services import mesin_pencari as M
def ukur(db, mode):
    M._korpus = None
    with create_app(konfigurasi(db)).app_context():
        k = M.korpus(); M.cari("pemanasan")
        if mode == "freeze": gc.collect(); gc.freeze()
        if mode == "mati": gc.disable()
        med = []
        for q in KUERI:
            M.cari(q); w = []
            for _ in range(15):
                t = time.perf_counter(); M.cari(q); w.append((time.perf_counter() - t) * 1000)
            med.append(statistics.median(w))
        gc.enable(); gc.unfreeze()
        return len(k.entri), len(k.entri_kec), statistics.mean(med)
for mode in ("normal", "mati", "freeze"):
    for db in ("salinan", "uji"):
        n, nk, r = ukur(db, mode)
        print(f"{mode:7s} {db:8s} entri {n} + kec {nk}: rata-rata median {r:6.1f} ms")
