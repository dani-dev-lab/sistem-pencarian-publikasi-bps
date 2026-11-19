"""Bandingkan dua potret (tests/potret_tampilan.py) per KARTU: setiap perbedaan harus berada di
kartu publikasi yang dibersihkan (id di berkas daftar), atau berupa urutan/jumlah yang ikut berubah
karena skor publikasi itu. Kartu entri (tabel/gambar/...) harus identik.
  python banding_halaman.py <sebelum.json> <sesudah.json> <daftar_id.txt> [--buang-tombol]"""
import json, re, sys, html
sys.stdout.reconfigure(encoding="utf-8")
a = json.load(open(sys.argv[1], encoding="utf-8"))["potret"]; b = json.load(open(sys.argv[2], encoding="utf-8"))["potret"]
ids = set(re.findall(r"[0-9a-f]{24}", open(sys.argv[3], encoding="utf-8").read()))
RE_TOMBOL = re.compile(r'\n?<button type="button" class="ke-atas"[\s\S]*?</button>|\n?<script src="[^"]*ke-atas\.js" defer></script>')
def bersih(t):
    return RE_TOMBOL.sub("", t) if "--buang-tombol" in sys.argv else t
def kartu(t, jenis):
    out = []
    for k in re.findall(rf'<article class="kartu kartu-{jenis}">(.*?)</article>', t, re.S):
        m = re.search(r"/pdf/([0-9a-f]{24})", k)
        out.append((m.group(1) if m else None, k))
    return out
total = beda = 0; masalah = []
for u in a:
    x, y = bersih(a[u]["isi"]), bersih(b[u]["isi"])
    total += 1
    if x == y:
        continue
    beda += 1
    if u.startswith("/api/saran"):
        masalah.append(f"{u}: saran berubah"); continue
    ex = [k for k in kartu(x, "(?:tabel|gambar|lampiran|isi)")]; ey = [k for k in kartu(y, "(?:tabel|gambar|lampiran|isi)")]
    if ex != ey:
        masalah.append(f"{u}: kartu entri berubah")
    px, py = kartu(x, "pub"), kartu(y, "pub")
    lain_x = [k for k in px if k[0] not in ids]; lain_y = [k for k in py if k[0] not in ids]
    if lain_x != lain_y:
        masalah.append(f"{u}: kartu publikasi LAIN berubah/bergeser")
    sentuh = sorted({k[0][:8] for k in px + py if k[0] in ids and (k not in px or k not in py)})
    sisa_x = re.sub(r'<article class="kartu kartu-pub">.*?</article>|<strong>\d+</strong> publikasi', "", x, flags=re.S)
    sisa_y = re.sub(r'<article class="kartu kartu-pub">.*?</article>|<strong>\d+</strong> publikasi', "", y, flags=re.S)
    if sisa_x != sisa_y:
        masalah.append(f"{u}: bagian lain halaman berubah")
    print(f"BEDA {u}: kartu publikasi yang dibersihkan berubah {sentuh}")
print(f"{total} URL, {beda} berbeda; masalah {len(masalah)}")
for m in masalah:
    print("  MASALAH", m)
