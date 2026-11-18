"""Hasil pencarian TANPA centang: database uji (dengan kecamatan) vs salinan produksi, menurut ISI.
21 kueri (12 + 9 berfilter wilayah) lewat pencarian_wilayah.cari. id entri berbeda antardatabase,
jadi dibandingkan (publikasi, tipe, nomor, judul, halaman, skor) + daftar publikasi + provinsi."""
import os, sys
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.path.insert(0, f"{DIR}/tests"); sys.path.insert(0, f"{DIR}/scripts")
sys.stdout.reconfigure(encoding="utf-8")
if os.environ.get("PYTHONHASHSEED") != "0":
    import subprocess; sys.exit(subprocess.run([sys.executable] + sys.argv, env={**os.environ, "PYTHONHASHSEED": "0"}).returncode)
from potret_tampilan import konfigurasi
from ukur_kinerja import KUERI, KUERI_WILAYAH
from app import create_app
from app.services import mesin_pencari as M, pencarian_wilayah as P
def isi(h):
    e = lambda xs: [(x["publikasi_id"], x["tipe"], x["nomor"], x["judul"], x["halaman"], x["skor"]) for x in xs]
    return {"ditemukan": e(h["ditemukan"]), "saran": e(h["saran"]), "provinsi": e(h.get("provinsi", [])),
            "publikasi": [(x["publikasi_id"], x.get("skor")) for x in h["publikasi"]], "filter": h["filter"]["kode"]}
def jalan(db):
    M._korpus = None
    with create_app(konfigurasi(db)).app_context():
        return {(k, w): isi(P.cari(k, w=w)) for k, w in [(k, "") for k in KUERI] + KUERI_WILAYAH}
a, b = jalan("salinan"), jalan("uji")
beda = [q for q in a if a[q] != b[q]]
for q in beda:
    for bag in a[q]:
        if a[q][bag] != b[q][bag]:
            x, y = a[q][bag], b[q][bag]
            print("BEDA", q, bag, "hanya-salinan:", [t for t in x if t not in y][:3], "hanya-uji:", [t for t in y if t not in x][:3])
print(f"identik {len(a) - len(beda)}/{len(a)} kueri")
