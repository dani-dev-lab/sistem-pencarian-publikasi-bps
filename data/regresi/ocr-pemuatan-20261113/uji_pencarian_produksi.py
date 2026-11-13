"""Uji pencarian sesudah pemuatan OCR: kartu muncul + tombol PDF ke halaman yang benar.
Konfigurasi produksi, log pencarian DIMATIKAN (kueri uji tidak masuk log_pencarian)."""
import html, re, sys
sys.path.insert(0, "C:/sistem-pencarian-bps")
import sqlalchemy as sa
from app import create_app
from app.config import Config
class ProduksiTanpaLog(Config):
    CATAT_LOG_PENCARIAN = False
app = create_app(ProduksiTanpaLog)
c = app.test_client()
mesin = sa.create_engine(Config.SQLALCHEMY_DATABASE_URI)
with mesin.connect() as k:
    log_awal = k.execute(sa.text("SELECT COUNT(*), MAX(id) FROM log_pencarian")).one()
KASUS = [  # kueri, pub_id, potongan judul entri, halaman_fisik yang diharapkan
    ("jumlah pasar hulu sungai tengah", "aafda0cff288ddb041cfa024", "Jumlah Pasar Menurut Kecamatan", 287),
    ("perbandingan konsumsi rumah tangga terhadap pmtb tapin", "f338cd99104699dbbd49256a", "Perbandingan Pengeluaran Konsumsi", 79),
    ("menara telekomunikasi hst", "aafda0cff288ddb041cfa024", "Menara Telekomunikasi", 264),
]
lulus = True
for q, pid, judul, fisik in KASUS:
    raw = c.get("/hasil", query_string={"q": q}).get_data(as_text=True)
    # tautan PDF entri dari publikasi itu, beserta teks sebelum tautan
    temu = [(m.start(), m.group(1)) for m in re.finditer(rf'href="[^"]*/pdf/{pid}[^"#]*#page=(\d+)"', raw)]
    teks_kartu = []
    for pos, hal in temu:
        awal = raw.rfind("<article", 0, pos); awal = awal if awal >= 0 else max(0, pos - 3000)
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", raw[awal:pos])))
        teks_kartu.append((int(hal), t))
    cocok = [(h, t) for h, t in teks_kartu if judul.lower() in t.lower()]
    ok = any(h == fisik for h, _ in cocok)
    lulus &= ok
    print(f"[{'LULUS' if ok else 'GAGAL'}] {q!r}: kartu '{judul}' {len(cocok)}x, #page={[h for h, _ in cocok]} (diharapkan {fisik})")
    for h, t in cocok[:1]:
        print("      ", t[-230:])
with mesin.connect() as k:
    log_akhir = k.execute(sa.text("SELECT COUNT(*), MAX(id) FROM log_pencarian")).one()
print("log_pencarian tidak berubah:", tuple(log_awal) == tuple(log_akhir), tuple(log_akhir))
print("SEMUA LULUS:", lulus)
