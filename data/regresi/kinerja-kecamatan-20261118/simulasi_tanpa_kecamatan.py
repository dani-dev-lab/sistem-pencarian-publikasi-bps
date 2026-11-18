"""Simulasi (database UJI, hanya baca): korpus TANPA baris Kecamatan Dalam Angka
(pola kecualikan_judul) -> waktu 12 kueri uji harus kembali ke angka produksi, dan
hasilnya identik dengan produksi. Kode aplikasi tidak diubah; _ambil_korpus/_ambil_publikasi
dibungkus di proses ini saja."""
import os, re, statistics, sys, time
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, f"{DIR}/scripts")
from app import create_app
from app.config import KonfigurasiUji
from app.services import mesin_pencari as M
from app.services.wilayah import pola_judul_dikecualikan
from ukur_kinerja import KUERI
pola = [p[0] for p in pola_judul_dikecualikan()]
kec = lambda judul: any(p.search(judul or "") for p in pola)
asli_e, asli_p = M._ambil_korpus, M._ambil_publikasi
def ringkas(h):
    # id entri produksi != id database uji, jadi dibandingkan menurut isi.
    return [(x["publikasi_id"], x["tipe"], x["nomor"], x["judul"], x["halaman"], x["skor"])
            for x in h["ditemukan"] + h["saran"]], len(h["publikasi"])
def jalan(cfg, saring):
    M._ambil_korpus = (lambda: [b for b in asli_e() if not kec(b[8])]) if saring else asli_e
    M._ambil_publikasi = (lambda: [b for b in asli_p() if not kec(b[1])]) if saring else asli_p
    M._korpus = None
    app = create_app(cfg) if cfg else create_app()
    out = {}
    with app.app_context():
        M.cari("pemanasan")
        for k in KUERI:
            M.cari(k); w = []
            for _ in range(20):
                t = time.perf_counter(); h = M.cari(k); w.append((time.perf_counter() - t) * 1000)
            out[k] = (statistics.median(w), ringkas(h))
    return out
prod = jalan(None, False); uji = jalan(KonfigurasiUji, True)
print(f"{'kueri':38}{'prod':>7}{'uji-tanpa-kec':>15}  hasil identik")
for k in KUERI:
    print(f"{k[:37]:38}{prod[k][0]:>7.0f}{uji[k][0]:>15.0f}  {prod[k][1] == uji[k][1]}")
for k in KUERI:
    if prod[k][1] != uji[k][1]:
        a, b = prod[k][1][0], uji[k][1][0]
        print("BEDA", k, "hanya-prod:", [x[:4] for x in a if x not in b][:3], "hanya-uji:", [x[:4] for x in b if x not in a][:3])
print(f"rata-rata median: prod {statistics.mean(v[0] for v in prod.values()):.0f} ms, "
      f"uji tanpa kecamatan {statistics.mean(v[0] for v in uji.values()):.0f} ms")
