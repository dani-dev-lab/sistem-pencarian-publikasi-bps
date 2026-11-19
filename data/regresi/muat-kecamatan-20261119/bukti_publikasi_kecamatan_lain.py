"""Seksi PUBLIKASI di PRODUKSI (log mati, hanya baca) untuk kecamatan dari kabupaten berbeda.
Per kecamatan: (1) kueri judul publikasinya + kecamatan dipilih -> publikasi kecamatan itu paling
atas berlabel "Kec. X"; (2) kueri topik "penduduk" + kecamatan dipilih -> publikasi kecamatan itu
didahulukan; (3) tanpa centang/kecamatan -> tidak ada publikasi kecamatan."""
import os, re, sys, html
from urllib.parse import urlencode
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.stdout.reconfigure(encoding="utf-8")
from app import create_app
from app.config import Config
from app.services import mesin_pencari as M
app = create_app(type("KonfigurasiProduksiTanpaLog", (Config,), {"CATAT_LOG_PENCARIAN": False}))
c = app.test_client()
def kartu(a):
    t = c.get("/hasil?" + urlencode(a)).get_data(as_text=True)
    s = re.search(r'<h2 class="seksi">Publikasi</h2>(.*?)</section>', t, re.S)
    out = []
    for k in re.findall(r'<article class="kartu kartu-pub">(.*?)</article>', s.group(1) if s else "", re.S):
        j = html.unescape(re.sub("<[^>]+>", "", re.search(r'<h3 class="kartu-judul">(.*?)</h3>', k, re.S).group(1))).strip()
        m = re.search(r'label-kecamatan">(.*?)</span>', k)
        out.append((j, m.group(1) if m else None))
    return out
with app.app_context():
    daftar = {w: dict(M.daftar_kecamatan(w)) for w in ("6303", "6309", "6371")}
uji = [("6303", "martaputimur" if "martaputimur" in daftar["6303"] else "martapuratimur"), ("6309", "tanjung"), ("6371", "banjarmasinutara")]
lulus = total = 0
for w, kc in uji:
    nama = daftar[w][kc]
    for tahun in ("2026", "2025"):
        q = f"Kecamatan {nama} Dalam Angka {tahun}"
        k1 = kartu({"q": q, "w": w, "kec": "1", "kc": kc})
        ok1 = bool(k1) and k1[0] == (q, f"Kec. {nama}")
        total += 1; lulus += ok1
        print(f"[{'OK' if ok1 else 'GAGAL'}] {w} kc={kc} '{q}': pertama {k1[0] if k1 else None}")
    k2 = kartu({"q": "penduduk", "w": w, "kec": "1", "kc": kc})
    ok2 = bool(k2) and all(x[1] == f"Kec. {nama}" for x in k2[:sum(1 for y in k2 if y[1] == f'Kec. {nama}')]) and k2[0][1] == f"Kec. {nama}"
    total += 1; lulus += ok2
    print(f"[{'OK' if ok2 else 'GAGAL'}] {w} kc={kc} 'penduduk': {len(k2)} kartu, 3 teratas {[x[1] or x[0][:30] for x in k2[:3]]}")
    k3 = kartu({"q": f"Kecamatan {nama} Dalam Angka 2026", "w": w})
    ok3 = all(x[1] is None for x in k3)
    total += 1; lulus += ok3
    print(f"[{'OK' if ok3 else 'GAGAL'}] {w} tanpa centang: {len(k3)} kartu, kecamatan {sum(1 for x in k3 if x[1])}")
print(f"{lulus}/{total} lulus")
