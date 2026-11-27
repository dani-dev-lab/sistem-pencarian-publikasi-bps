"""Waktu 12 kueri uji TANPA centang, bergantian: produksi (berkecamatan) vs salinan produksi
sebelum pemuatan (db_pencarian_bps_salinan_uji, tanpa kecamatan). 3 putaran, 15 ulangan per kueri;
dibandingkan putaran tercepat (gangguan proses lain hanya memperlambat). Hanya membaca."""
import os, statistics, sys, time
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.path.insert(0, f"{DIR}/scripts"); sys.path.insert(0, f"{DIR}/tests")
sys.stdout.reconfigure(encoding="utf-8")
from ukur_kinerja import KUERI
from potret_tampilan import konfigurasi
from app import create_app
from app.config import Config
from app.services import mesin_pencari as M
def ukur(cfg):
    M._korpus = None
    with create_app(cfg).app_context():
        M.cari("pemanasan"); med = []
        for q in KUERI:
            M.cari(q); w = []
            for _ in range(15):
                t = time.perf_counter(); M.cari(q); w.append(time.perf_counter() - t)
            med.append(statistics.median(w))
        return statistics.mean(med) * 1000, max(med) * 1000
prod = type("KonfigurasiProduksiTanpaLog", (Config,), {"CATAT_LOG_PENCARIAN": False})
hasil = {"produksi": [], "salinan": []}
for r in range(3):
    for nama, cfg in (("salinan", konfigurasi("salinan")), ("produksi", prod)):
        rata, telat = ukur(cfg); hasil[nama].append((rata, telat))
        print(f"putaran {r+1} {nama:9s} rata-rata median {rata:6.1f} ms, terlambat {telat:6.1f} ms", flush=True)
p, s = min(x[0] for x in hasil["produksi"]), min(x[0] for x in hasil["salinan"])
print(f"TERCEPAT: produksi {p:.1f} ms, salinan sebelum muat {s:.1f} ms, selisih {(p - s) / s * 100:+.1f}%")
