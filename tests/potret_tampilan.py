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
  python tests/potret_tampilan.py banding <a.json> <b.json> [--buang-widget] [--buang-tombol-atas] [--buang-sampul]

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
    """"uji" = database uji; "salinan" = <produksi>_salinan_uji; nama lain =
    nama database lengkap (misalnya salinan sementara tanpa kecamatan).
    Selalu turunan KonfigurasiUji: log mati, dan periksa_database_uji menolak
    nama database produksi."""
    from sqlalchemy.engine import make_url
    from app.config import Config, KonfigurasiUji
    if nama == "uji":
        return KonfigurasiUji
    url = make_url(Config.SQLALCHEMY_DATABASE_URI)
    db = f"{url.database}_salinan_uji" if nama == "salinan" else nama
    url = url.set(database=db).render_as_string(hide_password=False)
    return type("KonfigurasiSalinan", (KonfigurasiUji,), {"SQLALCHEMY_DATABASE_URI": url})


# Widget kecamatan yang SENGAJA ditambahkan di halaman tanpa centang (dropdown
# kc, kotak centang + skripnya, kotak info). Dibuang dari potret database
# berkecamatan sebelum dibandingkan dengan potret database tanpa kecamatan:
# selebihnya harus byte-identik.
RE_WIDGET_KECAMATAN = [
    re.compile(r'\n\n  <select name="kc"[\s\S]*?</select>'),
    re.compile(r'\n\n  <label class="centang-kecamatan">[\s\S]*?js/kecamatan\.js" defer></script>'),
    re.compile(r'\n\n<div class="info-kecamatan"[\s\S]*?</div>'),
]


def buang_widget_kecamatan(teks):
    for rx in RE_WIDGET_KECAMATAN:
        teks = rx.sub("", teks)
    return teks


# Tombol "Kembali ke atas" (19 Nov 2026), ditambahkan di base.html, jadi ada di
# SETIAP halaman HTML. --buang-tombol-atas membuang blok PERSIS itu (tombol +
# skripnya + satu baris kosong) dari potret b, dan menolak halaman HTML yang
# tidak memuatnya tepat satu kali; selebihnya harus byte-identik dengan a.
RE_TOMBOL_ATAS = re.compile(
    r'^  <button type="button" class="ke-atas" aria-label="Kembali ke atas" title="Kembali ke atas" hidden>\n'
    r'    <svg viewBox="0 0 24 24"[^\n]*</svg>\n'
    r'  </button>\n'
    r'  <script src="/static/js/ke-atas\.js" defer></script>\n\n', re.M)


def buang_tombol_atas(u, teks, salah):
    if u.startswith("/api/"):
        return teks
    teks, n = RE_TOMBOL_ATAS.subn("", teks)
    if n != 1:
        salah.append(f"{u}: tombol ke atas {n}x")
    return teks


# Sampul publikasi (19 Nov 2026): kartu PUBLIKASI yang berkas sampulnya ada
# mendapat kelas ada-sampul, <img class="sampul"> dan pembungkus kartu-badan.
# --buang-sampul mengembalikan kartu itu PERSIS ke bentuk lama (isi kartu
# tidak diindentasi ulang), lalu memastikan tidak ada sisa sampul.
RE_SAMPUL = re.compile(
    r'<article class="kartu kartu-pub ada-sampul">\n'
    r'  <img class="sampul" src="/sampul/\w+\?v=\d+"\n'
    r'       width="\d+" height="\d+" alt="[^"]*" loading="lazy" decoding="async">\n'
    r'  <div class="kartu-badan">'
    r'((?:(?!</article>)[\s\S])*?)\n  </div>\n</article>')


def buang_sampul(u, teks, salah, hitung):
    teks, n = RE_SAMPUL.subn(r'<article class="kartu kartu-pub">\1\n</article>', teks)
    hitung[0] += n
    if "ada-sampul" in teks or 'class="sampul"' in teks or "kartu-badan" in teks:
        salah.append(f"{u}: sisa markup sampul")
    return teks


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


def banding(a, b, buang_widget=False, buang_tombol=False, buang_sampul_=False):
    pa = json.load(open(a, encoding="utf-8"))["potret"]
    pb = json.load(open(b, encoding="utf-8"))["potret"]
    salah = []
    if buang_sampul_:
        hitung = [0]
        pb = {u: {**v, "isi": buang_sampul(u, v["isi"], salah, hitung)} for u, v in pb.items()}
        print(f"SAMPUL dibuang dari {hitung[0]} kartu publikasi")
    if buang_tombol:
        pb = {u: {**v, "isi": buang_tombol_atas(u, v["isi"], salah)} for u, v in pb.items()}
        for x in salah:
            print("TOMBOL", x)
    if buang_widget:        # b = database berkecamatan, a = tanpa kecamatan
        pb = {u: {**v, "isi": buang_widget_kecamatan(v["isi"])} for u, v in pb.items()}
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
    return not beda and not salah


if __name__ == "__main__":
    if sys.argv[1] == "simpan":
        simpan(sys.argv[2], sys.argv[sys.argv.index("--db") + 1])
    else:
        sys.exit(0 if banding(sys.argv[2], sys.argv[3], "--buang-widget" in sys.argv,
                                "--buang-tombol-atas" in sys.argv, "--buang-sampul" in sys.argv) else 1)
