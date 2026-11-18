"""Potret tampilan pencarian: HTML + JSON yang diterima petugas (18 Nov 2026).

Dipakai untuk jaminan "tanpa centang kecamatan, hasil IDENTIK dengan
sekarang". Merender lewat test_client:
  - beranda (/ dan /?w=6301);
  - /hasil untuk 12 kueri uji + 9 kueri berfilter wilayah (21 kueri, daftar
    yang sama dengan scripts/ukur_kinerja.py);
  - /api/saran untuk 5 awalan.
Angka "N ms" di halaman hasil disamarkan; selebihnya dibandingkan byte demi
byte.

  python tests/potret_tampilan.py simpan <keluar.json> --db salinan|uji
  python tests/potret_tampilan.py banding <a.json> <b.json>

--db salinan = db_pencarian_bps_salinan_uji (salinan produksi tanpa
kecamatan); --db uji = db_pencarian_bps_uji. Produksi TIDAK PERNAH dipakai:
request menjalankan skema.pastikan_kolom(), yang bisa mengubah skema. Log
pencarian mati (KonfigurasiUji).
"""
import json
import os
import re
import sys

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Urutan entri berskor sama dan urutan kata `sorot` bergantung pada urutan
# iterasi set/dict string, yang diacak per proses (hash randomization). Dua
# potret dari kode dan data yang SAMA terbukti berbeda di 4/28 halaman tanpa
# ini. Potret karena itu selalu dibuat dengan PYTHONHASHSEED=0.
if os.environ.get("PYTHONHASHSEED") != "0":
    import subprocess
    sys.exit(subprocess.run([sys.executable] + sys.argv,
                            env={**os.environ, "PYTHONHASHSEED": "0"}).returncode)

os.chdir(DIR)
sys.path.insert(0, DIR)
sys.path.insert(0, os.path.join(DIR, "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

from urllib.parse import urlencode  # noqa: E402

AWALAN_SARAN = ["penduduk", "luas pan", "jumlah sek", "tpk", "ekspor"]
RE_WAKTU = re.compile(r"&middot; \d+ ms")


def konfigurasi(nama):
    from sqlalchemy.engine import make_url
    from app.config import Config, KonfigurasiUji
    if nama == "uji":
        return KonfigurasiUji
    url = make_url(Config.SQLALCHEMY_DATABASE_URI)
    url = url.set(database=f"{url.database}_salinan_uji").render_as_string(hide_password=False)
    return type("KonfigurasiSalinan", (KonfigurasiUji,), {"SQLALCHEMY_DATABASE_URI": url})


def daftar_url():
    from ukur_kinerja import KUERI, KUERI_WILAYAH
    url = ["/", "/?w=6301"]
    url += ["/hasil?" + urlencode({"q": k}) for k in KUERI]
    url += ["/hasil?" + urlencode({"q": k, "w": w}) for k, w in KUERI_WILAYAH]
    url += ["/api/saran?" + urlencode({"q": a}) for a in AWALAN_SARAN]
    return url


def simpan(keluar, db):
    from app import create_app
    app = create_app(konfigurasi(db))
    hasil = {}
    with app.test_client() as c:
        for u in daftar_url():
            r = c.get(u)
            teks = RE_WAKTU.sub("&middot; # ms", r.get_data(as_text=True))
            hasil[u] = {"status": r.status_code, "isi": teks}
    with open(keluar, "w", encoding="utf-8") as f:
        json.dump({"db": db, "potret": hasil}, f, ensure_ascii=False)
    print(f"{len(hasil)} URL ({db}) -> {keluar}")


def banding(a, b):
    pa = json.load(open(a, encoding="utf-8"))["potret"]
    pb = json.load(open(b, encoding="utf-8"))["potret"]
    beda = [u for u in pa if pa[u] != pb.get(u)] + [u for u in pb if u not in pa]
    for u in beda:
        print("BEDA", u)
        if u in pa and u in pb:
            la, lb = pa[u]["isi"].splitlines(), pb[u]["isi"].splitlines()
            for i, (x, y) in enumerate(zip(la, lb)):
                if x != y:
                    print(f"   baris {i}: {x.strip()[:120]!r}\n          -> {y.strip()[:120]!r}")
                    break
            else:
                print(f"   jumlah baris {len(la)} -> {len(lb)}")
    print(f"IDENTIK {len(pa) - len(beda)}/{len(pa)}" if not beda else f"BERBEDA {len(beda)} dari {len(pa)}")
    return not beda


if __name__ == "__main__":
    if sys.argv[1] == "simpan":
        simpan(sys.argv[2], sys.argv[sys.argv.index("--db") + 1])
    else:
        sys.exit(0 if banding(sys.argv[2], sys.argv[3]) else 1)
