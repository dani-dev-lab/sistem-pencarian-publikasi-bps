r"""Uji pipeline di lingkungan terisolasi: salinan kode, DATABASE UJI, WebAPI tiruan.

Cara menjalankan (dari folder proyek):

    venv\Scripts\python.exe -u tests\uji_pipeline.py > uji_log.txt 2>&1

Semua bagian sekitar 60 menit (25 Nov 2026: 3.080 detik, 165 uji). Sebagian saja (untuk pengembang): tambahkan
--hanya DKRW (huruf bagian; U dan Z selalu jalan).

Kamus: salinan memakai data/kamus_sinonim.json working tree, dan bagian N
menerapkannya ke database uji sebelum potret awal ("Terapkan ke data"), jadi
kamus yang belum diterapkan tidak membuat P2/C2/O1 gagal. --kamus-head
(opsional) memakai kamus versi commit terakhir, misalnya untuk menguji kode
tanpa ikut menguji suntingan kamus yang belum di-commit.

Kode keluar (untuk tim IT):
    0  semua uji lulus (uji yang DILEWATI tidak dihitung gagal)
    1  ada uji yang gagal - baca baris "GAGAL:" di akhir keluaran
    2  lingkungan belum siap; tidak ada yang dijalankan dan tidak ada yang diubah

Syarat lingkungan (diperiksa di awal, kode 2 kalau kurang):
- .env lengkap (DATABASE_URL, SECRET_KEY, ADMIN_PASSWORD_HASH).
- Program mysql dan mysqldump: MYSQL_BIN di .env, atau ada di PATH
  (app.config.program_mysql). Tidak ada path Laragon yang ditulis mati.
- Database uji sudah ada (DATABASE_URL + "_uji", dibuat
  scripts/siapkan_db_uji.py).
- PDF domain uji (data/publikasi_pdf/6305) ada di disk. Folder sementara sistem
  harus satu drive dengan proyek, karena PDF uji berupa hardlink.
- EasyOCR TIDAK wajib. Uji yang benar-benar menjalankan OCR dilewati dengan
  keterangan kalau EasyOCR tidak terpasang.

Sifat (13 Nov 2026):
- HANYA database uji yang ditulis. Semua perbarui.py dijalankan dengan
  --db-uji, aplikasi dengan KonfigurasiUji; pengaman periksa_database_uji tetap
  aktif. Produksi hanya DIBACA: CHECKSUM TABLE di awal dan akhir, harus sama.
- Database uji di-mysqldump di awal, lalu di akhir DIHAPUS DAN DIBUAT ULANG dari
  dump itu, dan dibuktikan sama dengan CHECKSUM TABLE. Hapus/buat ulang hanya
  untuk nama berakhiran "_uji"; selain itu berhenti dengan galat.
- Tidak ada akses ke API BPS dan tidak ada unduhan dari BPS. Metadata, PDF, dan
  sampul disajikan server tiruan di 127.0.0.1, dibangun dari baris database uji.
  Tiga pengaman (19 Nov 2026, sejak ada unduhan sampul): url_cover/url_pdf di
  database uji diarahkan ke server tiruan di awal (dipulihkan bersama database
  uji di akhir); proses di salinan memakai proxy mati untuk semua alamat
  selain 127.0.0.1/localhost, sehingga URL BPS yang lolos GAGAL di mesin ini;
  U4/A5 membuktikan keduanya. Sampul ditulis ke folder salinan (DIR_SAMPUL).
- Salinan kode, PDF (hardlink), dan cache OCR (salinan) di folder sementara;
  folder proyek tidak ditulis. PDF uji = hardlink, jadi JANGAN pernah
  os.utime / menulis ke isinya: ganti berkas hanya lewat os.replace.
"""
import copy, glob, hashlib, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ASLI = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace(os.sep, "/")
sys.path.insert(0, ASLI)

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.config import Config, KonfigurasiUji, program_mysql  # noqa: E402

KODE_LULUS, KODE_GAGAL, KODE_LINGKUNGAN = 0, 1, 2
# --kamus-head: salinan memakai data/kamus_sinonim.json versi commit terakhir
# (lihat siapkan_salinan). Tanpa opsi ini: kamus working tree, seperti dulu.
KAMUS_HEAD = "--kamus-head" in sys.argv
# Q1: commit terakhir SEBELUM formulir pilihan penarikan (abeab3b^).
KODE_SEBELUM_FORMULIR = "4c5707258616fe71da7ca1ef72036c9309e00a38"

SP = os.path.join(tempfile.gettempdir(), "uji_pipeline_bps").replace(os.sep, "/")
UJI = f"{SP}/uji"                 # salinan proyek tempat skrip dijalankan
SUMBER = f"{SP}/uji_sumber_pdf"   # PDF yang disajikan server tiruan
DUMP_UJI = f"{SP}/cadangan_db_uji.sql"
PY = sys.executable
DOMAIN = "6305"                   # Kab. Tapin: 17 PDF, 4 di antaranya hasil OCR
KEY = "KUNCIUJIRAHASIA12345"
PORT = 5981

URL_PROD = make_url(Config.SQLALCHEMY_DATABASE_URI)
URL_UJI = make_url(KonfigurasiUji.SQLALCHEMY_DATABASE_URI)
DB_PROD, DB_UJI = URL_PROD.database, URL_UJI.database


class LingkunganBelumSiap(Exception):
    pass


def nama_uji_sah(nama):
    """Satu-satunya pintu hapus/buat ulang database: hanya nama *_uji."""
    return bool(nama) and nama.endswith("_uji") and nama != DB_PROD


# ---------------------------------------------------------------- MySQL CLI
ENV_MY = {**os.environ}
if URL_PROD.password:
    ENV_MY["MYSQL_PWD"] = URL_PROD.password       # tidak pernah dicetak
DASAR_MY = [f"--host={URL_PROD.host or '127.0.0.1'}", f"--port={URL_PROD.port or 3306}",
            f"--user={URL_PROD.username}", "--default-character-set=utf8mb4"]
MYSQL = MYSQLDUMP = None


def sql(q, db=None):
    r = subprocess.run([MYSQL, *DASAR_MY, "-N", "-B", "-e", q] + ([db] if db else []),
                       env=ENV_MY, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError("mysql: " + r.stderr[:300])
    return r.stdout.strip()


def checksum_db(db):
    """{tabel: (jumlah baris, CHECKSUM TABLE)} - hanya membaca."""
    hasil = {}
    for t in sql("SHOW TABLES", db).split():
        n = sql(f"SELECT COUNT(*) FROM `{t}`", db)
        c = sql(f"CHECKSUM TABLE `{t}`", db).split()[-1]
        hasil[t] = (n, c)
    return hasil


# ---------------------------------------------------------------- hasil uji
hasil_uji = []      # (nama, "lulus" | "gagal" | "lewati")


def cek(nama, ok, bukti=""):
    hasil_uji.append((nama, "lulus" if ok else "gagal"))
    print(f"  [{'LULUS' if ok else 'GAGAL'}] {nama}" + (f"  -- {bukti}" if bukti != "" else ""), flush=True)


def lewati(nama, alasan):
    hasil_uji.append((nama, "lewati"))
    print(f"  [LEWATI] {nama}  -- {alasan}", flush=True)


def tampil(teks, n=12):
    baris = [b for b in teks.splitlines() if b.strip()]
    print("    | " + "\n    | ".join(baris[-n:]), flush=True)


# ---------------------------------------------------------------- lingkungan
def periksa_lingkungan():
    """Semua prasyarat. Tidak mengubah apa pun. Gagal = LingkunganBelumSiap."""
    global MYSQL, MYSQLDUMP
    if not nama_uji_sah(DB_UJI):
        raise LingkunganBelumSiap(f"nama database uji {DB_UJI!r} tidak berakhiran _uji "
                                  f"atau sama dengan produksi {DB_PROD!r}")
    try:
        MYSQL, MYSQLDUMP = program_mysql("mysql"), program_mysql("mysqldump")
    except SystemExit as e:
        raise LingkunganBelumSiap(str(e)) from None
    try:
        sql("SELECT 1")
    except RuntimeError as e:
        raise LingkunganBelumSiap(f"MySQL tidak bisa dihubungi ({e}). Laragon sudah Start All?") from None
    if not sql(f"SHOW DATABASES LIKE '{DB_UJI}'"):
        raise LingkunganBelumSiap(f"database uji {DB_UJI} belum ada. Jalankan dulu: "
                                  r"venv\Scripts\python.exe scripts\siapkan_db_uji.py")
    pdf = glob.glob(f"{ASLI}/data/publikasi_pdf/{DOMAIN}/*.pdf")
    if not pdf:
        raise LingkunganBelumSiap(f"PDF domain {DOMAIN} tidak ada di data/publikasi_pdf/{DOMAIN}")
    n_db = sql(f"SELECT COUNT(*) FROM publikasi WHERE domain='{DOMAIN}'", DB_UJI)
    if int(n_db) != len(pdf):
        raise LingkunganBelumSiap(f"database uji punya {n_db} publikasi domain {DOMAIN}, "
                                  f"di disk {len(pdf)} PDF")
    if os.path.splitdrive(tempfile.gettempdir())[0].lower() != os.path.splitdrive(ASLI)[0].lower():
        raise LingkunganBelumSiap("folder sementara beda drive dengan proyek (hardlink tidak bisa)")
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", PORT)) == 0:
            raise LingkunganBelumSiap(f"port {PORT} untuk server tiruan sudah dipakai")


def cadangkan_db_uji():
    """mysqldump database uji (tanpa --databases: tidak memuat USE)."""
    os.makedirs(SP, exist_ok=True)
    r = subprocess.run([MYSQLDUMP, *DASAR_MY, "--single-transaction", "--routines", "--triggers",
                        "--events", "--hex-blob", "--no-tablespaces", f"--result-file={DUMP_UJI}", DB_UJI],
                       env=ENV_MY, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("mysqldump database uji gagal: " + r.stderr[:300])
    with open(DUMP_UJI, "rb") as f:
        f.seek(-200, os.SEEK_END)
        if b"Dump completed" not in f.read():
            raise RuntimeError("dump database uji tidak lengkap")
    return sql(f"SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM "
               f"information_schema.SCHEMATA WHERE SCHEMA_NAME='{DB_UJI}'").split()


def pulihkan_db_uji(charset, collation):
    """Hapus dan buat ulang database uji dari dump awal. Hanya untuk *_uji."""
    if not nama_uji_sah(DB_UJI):
        raise SystemExit(f"GALAT: menolak menghapus {DB_UJI!r} - bukan database uji")
    with open(DUMP_UJI, "rb") as f:
        f.seek(-200, os.SEEK_END)
        if b"Dump completed" not in f.read():
            raise SystemExit("GALAT: dump awal tidak lengkap - database uji TIDAK dihapus")
    sql(f"DROP DATABASE `{DB_UJI}`")
    sql(f"CREATE DATABASE `{DB_UJI}` CHARACTER SET {charset} COLLATE {collation}")
    with open(DUMP_UJI, "rb") as f:
        r = subprocess.run([MYSQL, *DASAR_MY, DB_UJI], env=ENV_MY, stdin=f, capture_output=True)
    if r.returncode:
        raise RuntimeError("pemulihan database uji gagal: " + r.stderr.decode("utf-8", "replace")[:300])


def siapkan_salinan():
    """Salinan kode + hardlink PDF domain uji + salinan cache OCR-nya."""
    shutil.rmtree(UJI, ignore_errors=True)
    shutil.rmtree(SUMBER, ignore_errors=True)
    os.makedirs(f"{UJI}/data/publikasi_pdf/{DOMAIN}")
    os.makedirs(SUMBER)
    for d in ("app", "scripts"):
        shutil.copytree(f"{ASLI}/{d}", f"{UJI}/{d}", ignore=shutil.ignore_patterns("__pycache__"))
    for f in ("wilayah.json", "kamus_sinonim.json"):
        shutil.copy2(f"{ASLI}/data/{f}", f"{UJI}/data/{f}")
    if KAMUS_HEAD:
        # --kamus-head: kamus versi commit terakhir, bukan working tree.
        # Bagian N menerapkan kamus mana pun yang dipakai ke database uji.
        isi = subprocess.run(["git", "-C", ASLI, "show", "HEAD:data/kamus_sinonim.json"],
                             capture_output=True, check=True).stdout
        open(f"{UJI}/data/kamus_sinonim.json", "wb").write(isi)
    aktifkan(DOMAIN)
    for p in glob.glob(f"{ASLI}/data/publikasi_pdf/{DOMAIN}/*.pdf"):
        n = os.path.basename(p)
        os.link(p, f"{UJI}/data/publikasi_pdf/{DOMAIN}/{n}")
        os.link(p, f"{SUMBER}/{n}")
    if os.path.isdir(f"{ASLI}/data/ocr_cache/{DOMAIN}"):
        shutil.copytree(f"{ASLI}/data/ocr_cache/{DOMAIN}", f"{UJI}/data/ocr_cache/{DOMAIN}")


def aktifkan(*kode, tambahan=()):
    w = json.load(open(f"{ASLI}/data/wilayah.json", encoding="utf-8"))
    w["wilayah"] = [dict(x) for x in w["wilayah"]] + [dict(x) for x in tambahan]
    for x in w["wilayah"]:
        x["aktif"] = x["kode"] in kode
    json.dump(w, open(f"{UJI}/data/wilayah.json", "w", encoding="utf-8"), ensure_ascii=False)


# Lingkungan proses di salinan. DATABASE_URL = URL produksi HANYA sebagai dasar
# url_database_uji(); setiap skrip dijalankan dengan --db-uji (lihat jalan()).
ENV = {**os.environ, "SECRET_KEY": "kunci-uji-acak-" + "x" * 30, "ADMIN_PASSWORD_HASH": "scrypt:dummy",
       "BPS_API_KEY": KEY, "BPS_API_BASE_URL": f"http://127.0.0.1:{PORT}/v1/api",
       "DATABASE_URL": Config.SQLALCHEMY_DATABASE_URI, "MYSQL_BIN": Config.MYSQL_BIN,
       "PYTHONUTF8": "1", "PORT": "5000"}
ENV.pop("BPS_DOMAIN", None)
assert ENV["BPS_API_BASE_URL"].startswith("http://127.0.0.1:"), "uji tidak boleh ke API BPS"
# Jaringan luar diblokir untuk proses di salinan: requests membaca variabel
# proxy ini, jadi alamat selain 127.0.0.1/localhost diarahkan ke port 9 lokal
# yang tidak melayani apa pun (ProxyError), bukan ke BPS.
PROXY_MATI = "http://127.0.0.1:9"
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    ENV[_k] = PROXY_MATI
ENV["NO_PROXY"] = ENV["no_proxy"] = "127.0.0.1,localhost"
ENV["DIR_SAMPUL"] = f"{UJI}/data/sampul"      # bukan data/sampul/ proyek


def jalan(skrip, *arg, timeout=3600, env_tambah=None):
    """Jalankan skrip di salinan. perbarui.py SELALU dengan --db-uji."""
    arg = list(arg)
    if skrip == "perbarui.py" and "--db-uji" not in arg:
        arg.insert(0, "--db-uji")
    t = time.time()
    r = subprocess.run([PY, "-u", f"{UJI}/scripts/{skrip}", *arg], cwd=SP, env={**ENV, **(env_tambah or {})},
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, r.stdout + r.stderr, time.time() - t


def jalan_py(kode, timeout=1800, env_tambahan=None):
    """Potongan Python di salinan. Wajib memakai KonfigurasiUji, tidak boleh create_app()."""
    sah = {"KonfigurasiUji"} | set(re.findall(r"class (\w+)\(KonfigurasiUji\)", kode))
    for arg in re.findall(r"create_app\(([^)]*)\)", kode):
        if arg.strip() not in sah:
            raise AssertionError(f"potongan uji harus memakai create_app(KonfigurasiUji), bukan {arg!r}")
    r = subprocess.run([PY, "-c", f"import sys; sys.path.insert(0, r'{UJI}')\n" + kode], cwd=SP,
                       env={**ENV, **(env_tambahan or {})},
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def ringkasan():
    return json.load(open(f"{UJI}/data/pembaruan_terakhir-uji.json", encoding="utf-8"))


# ---------------------------------------------------------------- potret DB uji
MESIN_UJI = None


def potret(domain=None):
    """{pub_id: {"pub": {...}, "entri": Counter(tuple)}} dari database UJI."""
    global MESIN_UJI
    MESIN_UJI = MESIN_UJI or sa.create_engine(URL_UJI)
    syarat = "WHERE domain=:d" if domain else ""
    hasil = {}
    with MESIN_UJI.connect() as k:
        for r in k.execute(sa.text(
                f"SELECT id, domain, judul, abstrak, teks_ternormalisasi, galat_ekstraksi, halaman_ocr "
                f"FROM publikasi {syarat}"), {"d": domain}).mappings():
            hasil[r["id"]] = {"pub": dict(r), "entri": Counter()}
        for r in k.execute(sa.text(
                f"SELECT e.publikasi_id, e.tipe, e.nomor, e.judul, e.halaman, e.halaman_fisik, "
                f"e.halaman_fisik_perkiraan, e.sumber, "
                f"e.teks_ternormalisasi FROM entri_dokumen e JOIN publikasi p ON p.id=e.publikasi_id "
                f"{syarat.replace('domain', 'p.domain')}"), {"d": domain}):
            hasil[r[0]]["entri"][tuple(r[1:])] += 1
    return hasil


def beda_potret(a, b):
    """Daftar pub_id yang entri ATAU medan publikasinya berbeda (dibandingkan per kunci)."""
    return sorted(p for p in set(a) | set(b) if a.get(p) != b.get(p))


# ---------------------------------------------------------------- WebAPI tiruan
KEADAAN = {"domain": {}, "gagal_domain": {}, "gagal_halaman": {}, "mode_pdf": {}, "berkas_pdf": {},
           "mode_sampul": {}, "isi_sampul": {}}
PERMINTAAN = []


def _buat_sampul_tiruan():
    import io
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (500, 709), (0, 43, 106)).save(b, "JPEG", quality=85)
    return b.getvalue()


SAMPUL_TIRUAN = _buat_sampul_tiruan()     # JPEG 500x709, seperti sampul WebAPI


def _buat_sampul_revisi():
    import io
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (500, 709), (180, 30, 30)).save(b, "JPEG", quality=85)
    return b.getvalue()


SAMPUL_REVISI = _buat_sampul_revisi()     # sampul "edisi revisi": warna lain, byte lain


class Tiruan(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _kirim(self, kode, isi, jenis="application/json"):
        self.send_response(kode)
        self.send_header("Content-Type", jenis)
        self.send_header("Content-Length", str(len(isi)))
        self.end_headers()
        self.wfile.write(isi)

    def do_GET(self):
        PERMINTAAN.append((time.time(), self.path))
        m = re.match(r"/v1/api/list/model/publication/lang/ind/domain/(\d+)/page/(\d+)/key/([^/]+)/", self.path)
        if m:
            d, hal = m.group(1), int(m.group(2))
            mode = KEADAAN["gagal_domain"].get(d) or (KEADAAN["gagal_halaman"].get(d) == hal and "500")
            if mode == "putus":
                self.connection.close()
                return
            if mode:
                self._kirim(500, b"{}")
                return
            pubs = KEADAAN["domain"].get(d, [])
            n = max(1, -(-len(pubs) // 10))
            isi = {"status": "OK", "data-availability": "available",
                   "data": [{"page": hal, "pages": n, "total": len(pubs)}, pubs[(hal - 1) * 10:hal * 10]]}
            self._kirim(200, json.dumps(isi).encode())
            return
        m = re.match(r"/pdf/(\w+)", self.path)
        if m:
            pid = m.group(1)
            mode = KEADAAN["mode_pdf"].get(pid)
            if mode == "500":
                self._kirim(500, b"x")
                return
            if mode == "html":
                self._kirim(200, b"<html>galat</html>" * 200, "text/html")
                return
            if mode == "400":
                self._kirim(400, b"x")
                return
            isi = open(KEADAAN["berkas_pdf"][pid], "rb").read()
            self._kirim(200, isi[:50000] if mode == "potong" else isi, "application/pdf")
            return
        m = re.match(r"/cover\.php\?f=TOKENUJI(\w+)$", self.path)
        if m:
            mode = KEADAAN["mode_sampul"].get(m.group(1))
            if mode == "400":
                self._kirim(400, b"x")
            elif mode == "html":
                self._kirim(200, b"<html>galat</html>" * 200, "text/html")
            else:
                self._kirim(200, KEADAAN["isi_sampul"].get(m.group(1), SAMPUL_TIRUAN), "image/jpeg")
            return
        self._kirim(404, b"{}")


# Sampul tiruan berbentuk seperti WebAPI asli (cover.php?f=<token>), supaya
# penyamaran token di pesan galat ikut teruji.
TOKEN_TIRUAN = "TOKENUJI"


def url_tiruan(jenis, pid):
    if jenis == "cover":
        return f"http://127.0.0.1:{PORT}/cover.php?f={TOKEN_TIRUAN}{pid}"
    return f"http://127.0.0.1:{PORT}/{jenis}/{pid}"


def metadata_dari_db(domain):
    """Daftar publikasi berbentuk respons WebAPI, terurut rl_date terbaru."""
    pubs = []
    with sa.create_engine(URL_UJI).connect() as k:
        for r in k.execute(sa.text(
                "SELECT id, judul, abstrak, tanggal_rilis, updt_date_api, url_cover, issn FROM publikasi "
                "WHERE domain=:d ORDER BY tanggal_rilis DESC, id"), {"d": domain}).mappings():
            pubs.append({"pub_id": r["id"], "title": r["judul"], "abstract": r["abstrak"],
                         "rl_date": str(r["tanggal_rilis"]) if r["tanggal_rilis"] else None,
                         "updt_date": str(r["updt_date_api"]) if r["updt_date_api"] else None,
                         "pdf": url_tiruan("pdf", r["id"]), "cover": url_tiruan("cover", r["id"]),
                         "issn": r["issn"], "subject_csa": []})
    return pubs


def arahkan_url_ke_tiruan():
    """url_cover/url_pdf SEMUA publikasi database uji -> server tiruan. Isi asli
    (alamat webapi.bps.go.id bertoken) kembali saat database uji dipulihkan
    dari dump di akhir (Z1)."""
    sql(f"UPDATE publikasi SET url_cover=CONCAT('http://127.0.0.1:{PORT}/cover.php?f={TOKEN_TIRUAN}', id), "
        f"url_pdf=CONCAT('http://127.0.0.1:{PORT}/pdf/', id)", DB_UJI)


def url_luar_di_db():
    return int(sql("SELECT COUNT(*) FROM publikasi WHERE url_cover NOT LIKE 'http://127.0.0.1:%' "
                   "OR url_pdf NOT LIKE 'http://127.0.0.1:%'", DB_UJI))


KODE_CEK_JARINGAN = """
import requests
try:
    requests.get('https://webapi.bps.go.id/v1/api/domain/type/all/key/x/', timeout=10)
    print('LUAR TERHUBUNG')
except requests.exceptions.ProxyError:
    print('LUAR DIBLOKIR')
except Exception as e:
    print('LUAR LAIN', type(e).__name__)
r = requests.get(URL_TIRUAN, timeout=10)
print('TIRUAN', r.status_code, r.headers.get('Content-Type'))
"""


def siapkan_tiruan():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Tiruan)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    pubs = metadata_dari_db(DOMAIN)
    for p in pubs:
        KEADAAN["berkas_pdf"][p["pub_id"]] = f"{SUMBER}/{p['pub_id']}.pdf"
    KEADAAN["domain"][DOMAIN] = pubs
    return srv, pubs


# ---------------------------------------------------------------- skenario
def bagian_u():
    print("\n=== U. PENGAMAN DATABASE UJI ===", flush=True)
    kode, keluar, err = jalan_py(
        "from app import create_app\n"
        "from app.config import Config, KonfigurasiUji\n"
        "class UjiSalah(KonfigurasiUji):\n"
        "    SQLALCHEMY_DATABASE_URI = Config.SQLALCHEMY_DATABASE_URI\n"
        "try:\n"
        "    create_app(UjiSalah); print('TIDAK-DITOLAK')\n"
        "except SystemExit as e:\n"
        "    print('DITOLAK', 'PRODUKSI' in str(e))\n")
    cek("U1 KonfigurasiUji yang menunjuk nama produksi ditolak (SystemExit)",
        "DITOLAK True" in keluar, (keluar + err).strip()[-80:])

    prod_asli = f"{UJI}/data/pembaruan_terakhir.json"
    kode, keluar, dtk = jalan("perbarui.py", "--lokal")
    baris1 = keluar.splitlines()[0] if keluar else ""
    cek("U2 baris pertama perbarui.py = database uji",
        baris1.startswith(f"Database tujuan: {DB_UJI} ") and "(UJI" in baris1, baris1[:90])
    n_luar = url_luar_di_db()
    kode, keluar, err = jalan_py(f"URL_TIRUAN = {url_tiruan('cover', 'cek')!r}\n" + KODE_CEK_JARINGAN)
    cek("U4 tanpa BPS: url_cover/url_pdf database uji semuanya ke server tiruan; alamat luar "
        "diblokir proxy mati (tidak sampai ke BPS); server tiruan tetap terjangkau",
        n_luar == 0 and "LUAR DIBLOKIR" in keluar and "TIRUAN 200 image/jpeg" in keluar,
        f"URL luar di DB {n_luar}; " + (keluar + err).strip().replace("\n", " | ")[-120:])
    cek("U3 ringkasan ke pembaruan_terakhir-uji.json, berkas produksi tidak dibuat",
        os.path.exists(f"{UJI}/data/pembaruan_terakhir-uji.json") and not os.path.exists(prod_asli)
        and ringkasan()["status"] in ("tidak_ada_baru", "sukses"), f"exit {kode}, {dtk:.0f} d")


def kolom_pub(pid, k):
    return sql(f"SELECT {k} FROM publikasi WHERE id='{pid}'", DB_UJI)


def entri_n(pid):
    return int(sql(f"SELECT COUNT(*) FROM entri_dokumen WHERE publikasi_id='{pid}'", DB_UJI))


def path_uji(pid):
    return f"{UJI}/data/publikasi_pdf/{DOMAIN}/{pid}.pdf"


def tanpa_teks(s):
    """Potret tanpa kolom teks_ternormalisasi (satu-satunya kolom yang
    bergantung pada kamus)."""
    return {p: ({k: v for k, v in x["pub"].items() if k != "teks_ternormalisasi"},
                Counter({e[:-1]: n for e, n in x["entri"].items()}))
            for p, x in s.items()}


# pub_id domain uji yang teks_ternormalisasi-nya diubah bagian N (kamus baru).
TERKENA_KAMUS = []


def bagian_n():
    """Kamus salinan diterapkan ke database uji SEBELUM potret s0 (24 Nov 2026).

    Ekspektasi P2/C2/O1 ("ekstraksi ulang = isi sebelum, per kunci, termasuk
    teks_ternormalisasi") hanya bermakna kalau isi sebelum dinormalkan dengan
    kamus yang SAMA dengan yang dipakai pipeline saat mengekstrak ulang. Kamus
    yang diubah lewat berkas atau /admin/kamus tanpa "Terapkan ke data"
    membuat database uji tertinggal (24 Nov 2026: kelompok p0 -> 47 publikasi,
    3 di antaranya Tapin). Langkah ini = tombol "Terapkan ke data" di database
    uji; database uji dipulihkan dari dump awal di Z1.
    """
    print("\n=== N. KAMUS SALINAN DITERAPKAN KE DATABASE UJI ===", flush=True)
    lama = potret()
    kode, keluar, err = jalan_py(
        "import json\n"
        "from app import create_app\nfrom app.config import KonfigurasiUji\n"
        "from app.services import normalisasi_data\n"
        "with create_app(KonfigurasiUji).app_context():\n"
        "    a = normalisasi_data.jalankan()\n"
        "    b = normalisasi_data.jalankan()\n"
        "print('N1', json.dumps([a['entri_diubah'], a['publikasi_diubah'], b['entri_diubah'], b['publikasi_diubah']]))\n")
    m = re.search(r"^N1 (.*)$", keluar, re.M)
    n = json.loads(m.group(1)) if m else None
    baru = potret()
    berubah = sorted(p for p in baru if baru[p] != lama[p])
    TERKENA_KAMUS[:] = [p for p in berubah if baru[p]["pub"]["domain"] == DOMAIN]
    cek("N1 kamus salinan diterapkan: hanya teks_ternormalisasi yang berubah, penerapan kedua mengubah 0",
        kode == 0 and n is not None and n[2] == 0 and n[3] == 0 and tanpa_teks(baru) == tanpa_teks(lama),
        f"entri diubah {n[0] if n else '?'}, publikasi diubah {n[1] if n else '?'}, "
        f"{len(berubah)} publikasi terkena, domain uji: {[p[:8] for p in TERKENA_KAMUS]}"
        if n else (err or keluar)[-300:])
    return lama


def bagian_p(s0, usang, s_lama=None):
    print(f"\n=== P. EKSTRAKSI PENUH DOMAIN {DOMAIN} (--lokal --paksa) ===", flush=True)
    diproses0 = {p: kolom_pub(p, "updt_date_diproses") for p in usang}
    kode, keluar, dtk = jalan("perbarui.py", "--lokal", "--paksa")
    tampil(keluar, 6)
    r = ringkasan()
    d = r["domain"][0]
    n_dom = len([p for p in s0 if s0[p]["pub"]["domain"] == DOMAIN])
    cek(f"P1 {n_dom} diproses, 0 diunduh, 0 gagal, exit 0",
        kode == 0 and r["diproses"] == n_dom and r["diunduh"] == 0 and not d["gagal"],
        f"exit {kode}, proses {r['diproses']}, unduh {r['diunduh']}, {dtk:.0f} d, tahap {r['durasi_tahap']}")
    s1 = potret()
    beda = beda_potret(s0, s1)
    cek(f"P2 isi database uji identik per kunci dengan sebelum ({len(s1)} publikasi, semua domain)",
        not beda, f"berbeda: {beda[:5]}")
    # P2b: publikasi domain uji yang terkena kamus baru (bagian N). Ekstraksi
    # ulang menghasilkan teks BARU (= s0), bukan teks lama database uji.
    if s_lama is not None:
        cek(f"P2b {len(TERKENA_KAMUS)} publikasi domain uji terkena kamus baru: teks ekstraksi ulang = "
            "teks sesudah kamus diterapkan, bukan teks lama",
            all(s1[p] == s0[p] != s_lama[p] for p in TERKENA_KAMUS),
            [p[:8] for p in TERKENA_KAMUS] or "tidak ada (kamus = isi database uji)")
    cek("P3 --lokal --paksa TIDAK memajukan updt_date_diproses publikasi usang",
        all(kolom_pub(p, "updt_date_diproses") == diproses0[p] for p in usang), diproses0)
    n_null = sql(f"SELECT COUNT(*) FROM entri_dokumen e JOIN publikasi p ON p.id=e.publikasi_id "
                 f"WHERE p.domain='{DOMAIN}' AND e.teks_ternormalisasi IS NULL", DB_UJI)
    cek("P4 tanpa entri dengan teks_ternormalisasi NULL", n_null == "0", n_null)
    return dtk


def bagian_l(usang):
    print("\n=== L. MODE LOKAL (tanpa jaringan) ===", flush=True)
    PERMINTAAN.clear()
    kode, keluar, _ = jalan("perbarui.py", "--lokal")
    tampil(keluar, 6)
    r = ringkasan()
    menunggu = {m["pub_id"] for m in r["domain"][0]["menunggu_unduhan"]}
    cek(f"L1 --lokal: tidak ada kerja, {len(usang)} 'menunggu pembaruan online'",
        kode == 0 and r["status"] == "tidak_ada_baru" and menunggu == set(usang),
        f"exit {kode}, {r['status']}, menunggu {len(menunggu)}")
    cek("L2 --lokal: nol permintaan ke server (tiruan maupun BPS)", not PERMINTAAN, len(PERMINTAAN))


def bagian_c(s0, ocr_pub):
    print("\n=== C. OCR ===", flush=True)
    s1 = potret(DOMAIN)
    cek(f"C1 {len(ocr_pub)} publikasi OCR: entri dari cache identik, halaman_ocr terisi",
        len(ocr_pub) >= 1 and all(s1[p] == s0[p] and s1[p]["pub"]["halaman_ocr"] and s1[p]["entri"] for p in ocr_pub),
        {p[:8]: (s1[p]["pub"]["halaman_ocr"], sum(s1[p]["entri"].values())) for p in ocr_pub})

    # C2a-c: --paksa + --tanpa-ocr ditolak kalau ada publikasi OCR di domain
    # aktif (17 Nov 2026). Gabungan itu dulu menghapus entri hasil OCR.
    cs0, n_minta = checksum_db(DB_UJI), len(PERMINTAAN)
    kode, keluar, dtk = jalan("perbarui.py", "--lokal", "--paksa", "--tanpa-ocr")
    r = ringkasan()
    cek("C2a --lokal --paksa --tanpa-ocr: ditolak, exit 1, pesan akibat + cara benar, semua publikasi OCR disebut",
        kode == 1 and "TIDAK DIJALANKAN: --paksa dan --tanpa-ocr" in keluar
        and "--paksa TANPA --tanpa-ocr" in keluar and "Database tidak diubah" in keluar
        and f"DOMAIN {DOMAIN}" not in keluar
        and r["status"] == "gagal" and r.get("tahap") == "pemeriksaan pilihan"
        and sorted(r.get("publikasi_ocr", [])) == ocr_pub,
        f"exit {kode}, {dtk:.0f} d, {len(r.get('publikasi_ocr', []))}/{len(ocr_pub)} publikasi OCR")
    tampil(keluar, 24)
    cek("C2a database uji tidak berubah (CHECKSUM TABLE)", checksum_db(DB_UJI) == cs0)
    kode, keluar, dtk = jalan("perbarui.py", "--paksa", "--tanpa-ocr")
    cek("C2b online --paksa --tanpa-ocr: ditolak sebelum jaringan (0 permintaan), database uji tidak berubah",
        kode == 1 and "TIDAK DIJALANKAN: --paksa dan --tanpa-ocr" in keluar
        and len(PERMINTAAN) == n_minta and checksum_db(DB_UJI) == cs0,
        f"exit {kode}, {len(PERMINTAAN) - n_minta} permintaan")
    # Domain aktif tanpa publikasi OCR (domain tiruan, kosong): tidak ditolak.
    aktifkan(TIRUAN["kode"], tambahan=[TIRUAN])
    kode, keluar, dtk = jalan("perbarui.py", "--lokal", "--paksa", "--tanpa-ocr")
    aktifkan(DOMAIN)
    cek("C2c domain aktif tanpa publikasi OCR: --paksa --tanpa-ocr tetap jalan, exit 0",
        kode == 0 and "TIDAK DIJALANKAN" not in keluar and ringkasan()["status"] == "tidak_ada_baru"
        and checksum_db(DB_UJI) == cs0, f"exit {kode}, status {ringkasan()['status']!r}")

    # C2: --tanpa-ocr = perilaku sebelum OCR ada. Publikasi OCR dipaksa dibaca
    # ulang lewat "belum pernah diekstrak" (bukan --paksa, yang kini ditolak).
    sql("UPDATE publikasi SET diekstrak_pada=NULL WHERE id IN ("
        + ",".join(f"'{p}'" for p in ocr_pub) + ")", DB_UJI)
    kode, keluar, dtk = jalan("perbarui.py", "--lokal", "--tanpa-ocr")
    r = ringkasan()
    s2 = potret(DOMAIN)
    alasan = {c["pub_id"]: c["alasan"] for c in r["domain"][0]["perlu_diperiksa"]}
    lain = [p for p in s2 if p not in ocr_pub]
    cek("C2 --tanpa-ocr: halaman dilewati, masuk 'perlu diperiksa', halaman_ocr kosong",
        kode == 0 and all(not s2[p]["pub"]["halaman_ocr"] and "--tanpa-ocr" in alasan.get(p, "") for p in ocr_pub),
        f"exit {kode}, {dtk:.0f} d, alasan: {[alasan.get(p, '-')[:40] for p in ocr_pub][:2]}")
    cek("C2 --tanpa-ocr: publikasi bertekst tidak berubah, publikasi OCR kehilangan entri OCR",
        all(s2[p] == s0[p] for p in lain)
        and all(sum(s2[p]["entri"].values()) < sum(s0[p]["entri"].values()) for p in ocr_pub),
        {p[:8]: (sum(s0[p]["entri"].values()), sum(s2[p]["entri"].values())) for p in ocr_pub})
    kode, keluar, dtk = jalan("perbarui.py", "--lokal", "--paksa")
    cek("C2 OCR dinyalakan lagi: kembali identik per kunci (cache dipakai ulang)",
        kode == 0 and not beda_potret(potret(), s0) and ringkasan()["domain"][0].get("gagal") == [],
        f"exit {kode}, {dtk:.0f} d")

    # C3: cache kurang + EasyOCR tidak ada -> halaman dilewati dengan alasan
    pid = min(ocr_pub, key=lambda p: os.path.getsize(path_uji(p)))
    folder = f"{UJI}/data/ocr_cache/{DOMAIN}/{pid}"
    halaman = sorted(f for f in os.listdir(folder) if f.endswith("-easyocr.json"))
    simpan = f"{SP}/cache_disimpan"
    os.makedirs(simpan, exist_ok=True)
    for f in halaman[:3]:
        os.replace(f"{folder}/{f}", f"{simpan}/{f}")
    kode, keluar, err = jalan_py(
        "import json\n"
        "from app import create_app\nfrom app.config import KonfigurasiUji\n"
        "from app.services import ocr, pipeline_data\n"
        "ocr.tersedia = lambda: False\n"
        "app = create_app(KonfigurasiUji)\n"
        "with app.app_context():\n"
        f"    entri, cat = pipeline_data.ekstrak_berkas(r'{path_uji(pid)}', '{pid}', ocr_aktif=True, log=lambda *a: None)\n"
        "print('OCR', json.dumps(cat['ocr']))\n")
    for f in halaman[:3]:
        os.replace(f"{simpan}/{f}", f"{folder}/{f}")
    m = re.search(r"^OCR (.*)$", keluar, re.M)
    info = json.loads(m.group(1)) if m else {}
    cek("C3 cache kurang + EasyOCR tidak ada: 3 halaman dilewati, alasan tercatat, sisanya dari cache",
        info.get("dilewati") == 3 and info.get("di_ocr") == 0 and info.get("alasan_dilewati") == "EasyOCR tidak terpasang"
        and info.get("dari_cache") == len(halaman) - 3, info or err[-200:])

    # C4: PDF berganti -> cache OCR lama dibuang. PDF uji = hardlink: ganti lewat os.replace.
    path = path_uji(pid)
    shutil.copyfile(path, path + ".baru")
    os.replace(path + ".baru", path)
    kode, keluar, err = jalan_py(
        "import os, json\nfrom app.services import ocr\n"
        f"h, n, j = ocr.halaman_tanpa_teks(r'{path}')\n"
        f"f = r'{folder}'\n"
        "meta = json.load(open(f + '/_meta.json', encoding='utf-8'))\n"
        "print('C4', len(h), len([x for x in os.listdir(f) if x.endswith('-easyocr.json')]), "
        "meta['sidik'] == ocr._sidik(r'" + path + "'))\n")
    m = re.search(r"C4 (\d+) (\d+) (\w+)", keluar)
    cek("C4 PDF berganti: cache halaman lama dibuang, _meta.json memakai sidik baru",
        m and int(m.group(1)) > 0 and m.group(2) == "0" and m.group(3) == "True",
        m.group(0) if m else err[-200:])
    os.link(f"{ASLI}/data/publikasi_pdf/{DOMAIN}/{pid}.pdf", path + ".asli")
    os.replace(path + ".asli", path)
    shutil.rmtree(folder)
    shutil.copytree(f"{ASLI}/data/ocr_cache/{DOMAIN}/{pid}", folder)

    # C5: PDF bertekst dengan halaman kosong tidak di-OCR (syarat publikasi 50%)
    bertekst = sorted((p for p in s0 if s0[p]["pub"]["domain"] == DOMAIN and p not in ocr_pub),
                      key=lambda p: os.path.getsize(path_uji(p)))
    kode, keluar, err = jalan_py(
        "import os\nfrom app.services import ocr\n"
        f"for pid in {bertekst!r}:\n"
        f"    p = r'{UJI}/data/publikasi_pdf/{DOMAIN}/' + pid + '.pdf'\n"
        "    h, n, j = ocr.halaman_tanpa_teks(p)\n"
        "    if n:\n"
        "        print('C5', pid, len(h), n, j, os.path.exists(ocr.folder_cache(p)))\n"
        "        break\n")
    m = re.search(r"C5 (\w+) (\d+) (\d+) (\d+) (\w+)", keluar)
    if not m:
        lewati("C5 PDF bertekst berhalaman kosong tidak di-OCR", "tidak ada PDF bertekst berhalaman kosong di domain uji")
    else:
        cek("C5 PDF bertekst berhalaman kosong: tidak di-OCR, tidak meninggalkan folder cache",
            m.group(2) == "0" and int(m.group(3)) > 0 and m.group(5) == "False",
            f"{m.group(1)[:8]}: {m.group(3)}/{m.group(4)} halaman kosong")

    # C6: server web tidak memuat EasyOCR / torch
    kode, keluar, err = jalan_py(
        "import sys\nfrom app import create_app\nfrom app.config import KonfigurasiUji\n"
        "c = create_app(KonfigurasiUji).test_client()\n"
        "kode = [c.get('/').status_code, c.get('/hasil?q=pdrb+tapin').status_code]\n"
        "print('C6', kode, 'easyocr' in sys.modules, 'torch' in sys.modules)\n")
    cek("C6 aplikasi web melayani pencarian tanpa memuat easyocr/torch",
        "C6 [200, 200] False False" in keluar, (keluar + err).strip()[-120:])

    # C7: OCR sungguhan satu halaman tanpa cache (butuh EasyOCR)
    from importlib.util import find_spec
    if find_spec("easyocr") is None:
        lewati("C7 OCR sungguhan 1 halaman", "EasyOCR tidak terpasang (requirements-ocr.txt); uji lain tetap berjalan")
        return
    # Halaman dengan kata terbanyak: halaman 2 kata membuat "100% sama" tak berarti.
    hal7 = max(halaman, key=lambda f: len(json.load(open(f"{folder}/{f}", encoding="utf-8"))["kata"]))
    halaman = [hal7]
    n = int(halaman[0][:4])
    asli = json.load(open(f"{folder}/{halaman[0]}", encoding="utf-8"))
    os.remove(f"{folder}/{halaman[0]}")
    kode, keluar, err = jalan_py(
        "from app.services import ocr\n"
        f"print('C7', ocr.isi_cache(r'{path}', [{n}], log=lambda *a: None))\n", timeout=900)
    baru = json.load(open(f"{folder}/{halaman[0]}", encoding="utf-8")) if os.path.exists(f"{folder}/{halaman[0]}") else {}
    ta = [k["text"] for k in asli["kata"]]
    tb = [k["text"] for k in baru.get("kata", [])]
    sama = sum((Counter(ta) & Counter(tb)).values()) / max(len(ta), 1)
    cek("C7 OCR sungguhan 1 halaman: cache dibuat, teks >= 95% sama dengan cache semula",
        "C7 1" in keluar and sama >= 0.95, f"{len(tb)} kata, sama {sama:.1%}, {baru.get('detik_ocr')} d")
    shutil.copy2(f"{ASLI}/data/ocr_cache/{DOMAIN}/{pid}/{halaman[0]}", f"{folder}/{halaman[0]}")


def bagian_h(s0):
    print("\n=== H. BATAS HEADING DAFTAR ===", flush=True)
    da = [p for p in s0 if s0[p]["pub"]["domain"] == DOMAIN and "Dalam Angka" in s0[p]["pub"]["judul"]]
    kode, keluar, err = jalan_py(
        "import pdfplumber\nfrom app.services import ekstraksi_pdf as E\n"
        f"for pid in {da!r}:\n"
        f"    with pdfplumber.open(r'{UJI}/data/publikasi_pdf/{DOMAIN}/' + pid + '.pdf') as pdf:\n"
        "        print('H1', pid, E.cari_heading(pdf).get('gambar'), E.BATAS_HALAMAN_CARI)\n")
    temuan = re.findall(r"H1 (\w+) (\w+) (\d+)", keluar)
    lewat = [(p, int(g)) for p, g, b in temuan if g != "None" and int(g) >= int(b)]
    n_gambar = {p: sql(f"SELECT COUNT(*) FROM entri_dokumen WHERE publikasi_id='{p}' AND tipe='gambar' "
                       f"AND sumber IN ('daftar','keduanya') AND halaman IS NOT NULL", DB_UJI) for p, _ in lewat}
    cek("H1 Daftar Gambar Dalam Angka sesudah halaman 25 terbaca, entrinya berhalaman cetak",
        lewat and all(int(n) > 0 for n in n_gambar.values()),
        f"{[(p[:8], g) for p, g in lewat]}, gambar daftar {list(n_gambar.values())}" if lewat else (keluar + err)[-200:])

    # H2: blok Daftar sintetis - halaman kosong di sela blok paling banyak 2
    kode, keluar, err = jalan_py(
        "from types import SimpleNamespace\nfrom app.services import ekstraksi_pdf as E\n"
        "E._kata_halaman = lambda hal: hal\n"
        "E._kelompokkan_baris = lambda kata: [[k] for k in kata]\n"
        "E._teks_baris = lambda b: b[0]\n"
        "prosa = ['kalimat prosa biasa', 'tanpa dot leader', 'sama sekali', 'lebih dari tiga baris']\n"
        "def daftar(label, heading=None):\n"
        "    return ([heading] if heading else []) + [f'{label} {i}.1 Judul contoh ............... {i}' for i in range(1, 7)]\n"
        "for k in (0, 1, 2, 3):\n"
        "    hal = [prosa, prosa, daftar('Tabel', 'DAFTAR TABEL')] + [daftar('Tabel') for _ in range(3, 25)]\n"
        "    hal += [[] for _ in range(k)] + [daftar('Gambar', 'DAFTAR GAMBAR'), prosa]\n"
        "    print('H2', k, E.cari_heading(SimpleNamespace(pages=hal)).get('gambar'), E.MAKS_HALAMAN_KOSONG)\n")
    h2 = re.findall(r"H2 (\d) (\w+) (\d+)", keluar)
    maks = int(h2[0][2]) if h2 else -1
    cek("H2 blok Daftar: halaman kosong di sela <= MAKS_HALAMAN_KOSONG tidak memutus, lebih dari itu memutus",
        len(h2) == 4 and all((g != "None") == (int(k) <= maks) for k, g, _ in h2), h2 or err[-200:])


def bagian_f():
    """Perkiraan halaman fisik (16 Nov 2026).

    Dijalankan SEBELUM potret s0 diambil: sesudah F semua perkiraan terisi,
    sehingga P2 (ekstraksi ulang --paksa identik per kunci, termasuk
    halaman_fisik_perkiraan) sekaligus membuktikan pipeline_data.simpan_entri
    dan scripts/isi_perkiraan_halaman.py menghasilkan perkiraan yang sama.
    """
    print("\n=== F. PERKIRAAN HALAMAN FISIK ===", flush=True)
    # F1: aturan murni, kasus sintetis. (cetak, fisik) -> entri.
    kode, keluar, err = jalan_py(
        "from app.services.perkiraan_halaman import perkirakan\n"
        "def e(tipe, cetak, fisik=None, perk=False):\n"
        "    return {'tipe': tipe, 'halaman': cetak, 'halaman_fisik': fisik, 'halaman_fisik_perkiraan': perk}\n"
        "def T(c, f=None): return e('tabel', c, f)\n"
        "def kasus(nama, entri, harap):\n"
        "    h = perkirakan(entri)\n"
        "    dapat = [h.get(i) for i, x in enumerate(entri) if x['halaman_fisik'] is None]\n"
        "    print('F1', nama, 'OK' if dapat == harap else f'SALAH {dapat} != {harap}')\n"
        "kasus('apit-sepakat', [T('10',20), T('12',22), T('15'), T('20',30), T('22',32)], [25])\n"
        "kasus('apit-beda', [T('10',20), T('12',22), T('15'), T('20',32), T('22',34)], [None])\n"
        "kasus('tepi<=10', [T('10',20), T('12',22), T('22'), T('23')], [32, None])\n"
        "kasus('nilai-asli-tetap', [T('10',20), T('12',22), T('15',99), T('16')], [26])\n"
        "kasus('jangkar-menyimpang', [T('10',20), T('12',22), T('14',50), T('15'), T('16',26), T('18',28)], [25])\n"
        "kasus('setipe-dulu', [T('10',20), T('12',22), T('20',30), T('22',32), e('gambar','11',41),\n"
        "      e('gambar','13',43), e('gambar','12'), T('15')], [42, 25])\n"
        "kasus('isi-jangkar', [e('isi','1',27), e('isi','13',39), T('10')], [36])\n"
        "kasus('perkiraan-bukan-jangkar', [e('tabel','10',20,True), e('tabel','12',22,True), T('11')], [None])\n"
        "kasus('romawi-dilewati', [T('10',20), T('12',22), T('xi'), T(None), e('isi','vii')], [None, None, None])\n"
        # Entri isi (16 Nov 2026): HANYA jangkar tabel/gambar/lampiran, jangkar isi diabaikan.
        "kasus('isi-dari-nonisi', [T('10',20), T('12',22), T('20',30), T('22',32), e('isi','15')], [25])\n"
        "kasus('isi-tanpa-nonisi-kosong', [e('isi','1',27), e('isi','13',39), e('isi','10')], [None])\n"
        "kasus('isi-abaikan-jangkar-isi', [T('10',20), T('12',22), T('20',30), T('22',32), e('isi','11',23),\n"
        "      e('isi','13',25), e('isi','15')], [25])\n")
    f1 = re.findall(r"F1 (\S+) (OK|SALAH.*)", keluar)
    cek("F1 aturan perkiraan: 12 kasus sintetis", len(f1) == 12 and all(h == "OK" for _, h in f1),
        [f"{n}: {h}" for n, h in f1 if h != "OK"] or (err[-200:] if len(f1) != 12 else "12/12"))

    # F2: data lama (perkiraan kosong) diisi skrip = keadaan sebelum dikosongkan.
    kode, keluar, _ = jalan("isi_perkiraan_halaman.py", "--db-uji")    # isi dulu kalau belum
    pf0 = potret()
    n_perk = int(sql("SELECT COUNT(*) FROM entri_dokumen WHERE halaman_fisik_perkiraan=1", DB_UJI))
    q_asli = ("SELECT COUNT(*), COALESCE(SUM(halaman_fisik), 0), COALESCE(SUM(id * halaman_fisik), 0) "
              "FROM entri_dokumen WHERE halaman_fisik_perkiraan=0 AND halaman_fisik IS NOT NULL")
    n_asli = sql(q_asli, DB_UJI)
    sql("UPDATE entri_dokumen SET halaman_fisik=NULL, halaman_fisik_perkiraan=0 "
        "WHERE halaman_fisik_perkiraan=1", DB_UJI)
    kode, keluar, dtk = jalan("isi_perkiraan_halaman.py", "--db-uji")
    tampil(keluar, 4)
    diisi = re.search(r"baru diisi\s*:\s*(\d+)", keluar)
    beda = beda_potret(pf0, potret())
    cek(f"F2 perkiraan dikosongkan lalu diisi skrip: identik per kunci dengan sebelumnya ({n_perk} perkiraan)",
        kode == 0 and n_perk > 0 and diisi and int(diisi.group(1)) == n_perk and not beda,
        f"exit {kode}, diisi {diisi and diisi.group(1)}, {dtk:.0f} d, berbeda: {beda[:3]}")
    n_asli2 = sql(q_asli, DB_UJI)
    cek("F2 halaman fisik asli tidak berubah (jumlah baris, jumlah nilai, jumlah id*nilai)",
        n_asli2 == n_asli, f"{n_asli} -> {n_asli2}")
    n_luar = sql("SELECT COUNT(*) FROM entri_dokumen WHERE halaman_fisik_perkiraan=1 "
                 "AND (halaman IS NULL OR halaman NOT REGEXP '^[0-9]+$')", DB_UJI)
    cek("F2 perkiraan hanya di entri berhalaman cetak angka", n_luar == "0", n_luar)

    # F3: idempoten
    kode, keluar, _ = jalan("isi_perkiraan_halaman.py", "--db-uji")
    cek("F3 run kedua: tidak ada yang berubah", kode == 0 and "Tidak ada yang berubah." in keluar
        and not beda_potret(pf0, potret()), f"exit {kode}")

    # F4: database tujuan wajib disebut
    kode, keluar, _ = jalan("isi_perkiraan_halaman.py")
    cek("F4 tanpa --db-uji/--produksi ditolak (exit 2), database tidak tersentuh",
        kode == 2 and "--produksi" in keluar and not beda_potret(pf0, potret()), f"exit {kode}")

    # F5: kunci pembaruan dihormati (PID proses uji ini masih hidup)
    kunci = f"{UJI}/data/pembaruan.lock"
    with open(kunci, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    try:
        kode, keluar, _ = jalan("isi_perkiraan_halaman.py", "--db-uji")
    finally:
        os.remove(kunci)
    cek("F5 pembaruan lain berjalan: TIDAK DIJALANKAN (exit 2)",
        kode == 2 and "TIDAK DIJALANKAN" in keluar and not beda_potret(pf0, potret()), f"exit {kode}")


KODE_BAGIAN_I = r'''
from app.services import ekstraksi_pdf as E
def w(t, x0, x1=None):
    return {"text": t, "x0": x0, "x1": x1 if x1 is not None else x0 + 6 * len(t), "top": 0, "bottom": 10}
def baris(*kata):
    return list(kata)
def cetak(nama, entri, harap):
    dapat = [(e["nomor"], e["judul"], e["halaman"]) for e in entri]
    print("I", nama, "OK" if dapat == harap else f"SALAH {dapat} != {harap}")
KANAN = 520
def hal(t, x1=KANAN):
    return w(t, x1 - 6 * len(t), x1)

# C: kop "Lampiran ... Halaman" bukan entri; label di kop tetap membuka entri pertama (Dalam Angka).
cetak("C-kop-lampiran", E._parse_baris([
    baris(w("Lampiran", 90), hal("Halaman")),
    baris(w("Lampiran", 90), w("1", 150), w("Judul", 170), w("satu", 210), hal("5")),
    baris(w("Lampiran", 90), w("2", 150), w("Judul", 170), w("dua", 210), hal("7"))], "lampiran", "x", 400),
    [("1", "Judul satu", "5"), ("2", "Judul dua", "7")])
cetak("C-kop-berlabel-dalam-angka", E._parse_baris([
    baris(w("Gambar", 90), hal("Halaman")),
    baris(w("Figure", 90), hal("Page")),
    baris(w("13.2", 90), w("Jumlah", 150), w("Penduduk", 200), w("Miskin", 260), hal("457"))], "gambar", "x", 400),
    [("13.2", "Jumlah Penduduk Miskin", "457")])
# A2: kata + dot leader + nomor menempel; BAB 3 dan 3.1 tidak tergabung.
cetak("A2-kata-leader-nomor", E._parse_baris([
    baris(w("BAB", 90), w("3", 115), w("TINJAUAN", 125), w("EKONOMI..........39", 180, KANAN)),
    baris(w("3.1", 90), w("Tinjauan", 125), w("PDRB", 180), w(".........42", 220, KANAN))], "isi", "x", 400),
    [(None, "BAB 3 TINJAUAN EKONOMI", "39"), (None, "3.1 Tinjauan PDRB", "42")])
# A1: folio romawi kecil sebaris dibuang; "Triwulan IV" (romawi besar) aman.
cetak("A1-folio-sebaris", E._parse_baris([
    baris(w("2.6", 90), w("Ekspor", 125), w("Impor", 170), w("......", 210), hal("35"), w("vii", 560, 575))], "isi", "x", 400),
    [(None, "2.6 Ekspor Impor", "35")])
cetak("A1-romawi-besar-aman", E._parse_baris([
    baris(w("Tabel", 90), w("1", 130), w("PDRB", 150), w("Triwulan", 190), hal("12", 470), w("IV", 500, 515))],
    "tabel", "x", 400),
    [("1", "PDRB Triwulan 12 IV", None)])
# A': kata terjauh x1=488, kolom nomor x1=387 -> batas turun, entri tertutup.
halaman_ap = [baris(w("v", 482, 488))] + [
    baris(w(j, 90), w("……………", 200, 370), w(n, 375, 387)) for j, n in
    (("Pendahuluan", "1"), ("Metodologi", "11"), ("Hasil", "19"), ("Penutup", "25"))]
bk = E._batas_kanan(halaman_ap, "isi")
print("I A-batas", "OK" if 380 < bk < 387 else f"SALAH batas {bk}")
cetak("A-kolom-sejajar", E._parse_baris(halaman_ap[1:], "isi", "x", bk),
      [(None, "Pendahuluan", "1"), (None, "Metodologi", "11"), (None, "Hasil", "19"), (None, "Penutup", "25")])
# B: nomor di baris pertama, lanjutan menempel ke entri SEBELUMNYA.
cetak("B-lanjutan", E._parse_baris([
    baris(w("3.6", 90), w("Perubahan", 124), w("Inventori/Change", 190), w("in", 300), hal("69")),
    baris(w("Inventory", 124)),
    baris(w("3.7", 90), w("Perkembangan", 124), w("Ekspor", 210), hal("70"))], "isi", "x", 400),
    [(None, "3.6 Perubahan Inventori/Change in Inventory", "69"), (None, "3.7 Perkembangan Ekspor", "70")])
# Kolom judul (17 Nov 2026): Daftar tanpa label, nomor halaman di BARIS SENDIRI
# (Tabalong Dalam Angka 2025). Kolom judul tidak boleh ditebak dari x0 leader.
halaman_tl = [
    baris(w("Tabel", 42), w("Halaman", 330, 377)),
    baris(w("Jumlah", 77), w("Sekolah", 120), w("Dasar", 170)), baris(w("4.1.1", 43, 62)),
    baris(w("di", 77), w("Kabupaten", 90)), baris(w("..................", 310, 360), w("93", 366, 377)),
    baris(w("Jumlah", 77), w("Guru", 120)), baris(w("4.1.2", 43, 62)),
    baris(w("..................", 310, 360), w("96", 366, 377)),
    baris(w("Jumlah", 77), w("Murid", 120)), baris(w("4.1.3", 43, 62)),
    baris(w("..................", 310, 360), w("99", 366, 377))]
bk = E._batas_kanan(halaman_tl, "tabel")
cetak("kolom-judul-nomor-baris-sendiri", E._parse_baris(halaman_tl, "tabel", "x", bk),
      [("4.1.1", "Jumlah Sekolah Dasar di Kabupaten", "93"), ("4.1.2", "Jumlah Guru", "96"),
       ("4.1.3", "Jumlah Murid", "99")])
# B: layout biasa (nomor di baris TERAKHIR) tidak boleh tersentuh.
cetak("B-layout-biasa-aman", E._parse_baris([
    baris(w("BAB", 90), w("I", 115), w("PENDAHULUAN", 124), hal("1")),
    baris(w("Penduduk", 124), w("Usia", 180), w("Kerja", 215), w("dan", 250)),
    baris(w("Angkatan", 124), w("Kerja", 180), hal("5"))], "isi", "x", 400),
    [(None, "BAB I PENDAHULUAN", "1"), (None, "Penduduk Usia Kerja dan Angkatan Kerja", "5")])

# Kecamatan Dalam Angka (18 Nov 2026): baris dirapikan seperti di _baca_daftar.
def rapi(halaman):
    return [E._rapikan_nomor_halaman(b) for b in halaman]
def baca(halaman):
    h = rapi(halaman)
    return E._parse_baris(h, "tabel", "x", E._batas_kanan(h, "tabel"))
# Pola 2: nomor halaman ditimpa leader (x1 leader 368 > x0 nomor 367), Banjar 2026.
cetak("K2-halaman-ditimpa-leader", baca([
    baris(w("4.1.1", 74, 92), w("Jumlah", 99), w("Sekolah", 140), w("........", 190, 368), w("3..3", 367, 376)),
    baris(w("4.1.2", 74, 92), w("Jumlah", 99), w("Guru", 140), w("........", 190, 369), w("3.4", 367, 376)),
    baris(w("4.1.3", 74, 92), w("Jumlah", 99), w("Murid", 140), w("........", 190, 368), w(".3..5.", 367, 377))]),
    [("4.1.1", "Jumlah Sekolah", "33"), ("4.1.2", "Jumlah Guru", "34"), ("4.1.3", "Jumlah Murid", "35")])
# Pola 2: "3.4" dengan celah normal (tidak ditimpa) TIDAK diubah.
b_aman = baris(w("Tabel", 90), w("Judul", 140), w("........", 190, 364), w("3.4", 366, 376))
print("I K2-tanpa-tumpang-aman", "OK" if E._rapikan_nomor_halaman(b_aman) is b_aman else "SALAH diubah")
# Pola 3: digit di dalam kata leader + "." sendirian (Balangan 2025) -> mode nomor-sebaris aktif.
cetak("K3-halaman-dalam-leader", baca([
    baris(w("4.4.1", 57, 75), w("Banyaknya", 91), w("Bencana", 150), w("..........4..2..", 200, 377)),
    baris(w("4.4.2", 57, 75), w("Korban", 91), w("Jiwa", 150), w("..........4..3..", 200, 378), w(".", 378, 381)),
    baris(w("4.4.3", 57, 75), w("Mitigasi", 91), w("Bencana", 150), w("..........4...4..", 200, 379))]),
    [("4.4.1", "Banyaknya Bencana", "42"), ("4.4.2", "Korban Jiwa", "43"), ("4.4.3", "Mitigasi Bencana", "44")])
# Pola 1 (nomor terpotong "2.1." + "1", Tanah Laut 2025) DIBATALKAN 18 Nov 2026:
# penomoran Daftar != badan di sumbernya membuat 27 tombol PDF meleset. Tidak diuji.
'''


def bagian_i():
    """Parser Daftar: pola C, A2, A1, A', B (16 Nov 2026) dan pola kecamatan
    2-3 (18 Nov 2026; pola 1 dibatalkan), baris sintetis."""
    print("\n=== I. PARSER DAFTAR (pola C, A2, A1, A', B, kecamatan K2-K3) ===", flush=True)
    kode, keluar, err = jalan_py(KODE_BAGIAN_I)
    hasil = re.findall(r"^I (\S+) (OK|SALAH.*)$", keluar, re.M)
    n = 13
    cek(f"I1 {len(hasil)} kasus sintetis parser Daftar", len(hasil) == n and all(h == "OK" for _, h in hasil),
        [f"{n}: {h}" for n, h in hasil if h != "OK"] or (err[-300:] if len(hasil) != n else f"{n}/{n}"))


def bagian_s():
    """Deteksi wilayah dari kueri (filter wilayah, 10 Nov 2026; singkatan dikonfirmasi 16 Nov 2026).

    Memakai data/wilayah.json ASLI proyek. Salinan uji hanya mengaktifkan
    domain uji, padahal deteksi hanya mengenali wilayah aktif. Kasus wajib
    dari data/regresi/filter-wilayah-20261110.md (Syarat 4), ditambah SETIAP
    singkatan yang tercantum di wilayah.json, sehingga singkatan baru otomatis
    ikut diuji.
    """
    print("\n=== S. DETEKSI WILAYAH DARI KUERI ===", flush=True)
    kode, keluar, err = jalan_py(
        "import json\n"
        "from app.services import wilayah, preprocessing as P\n"
        f"PATH = r'{ASLI}/data/wilayah.json'\n"
        "def kode(q): return [t['kode'] for t in wilayah.deteksi(P.tokenkan(q), PATH)]\n"
        "kasus = [('penduduk banjar', ['6303']), ('penduduk banjarmasin', ['6371']),\n"
        "         ('penduduk banjarbaru', ['6372']), ('penduduk banjar baru', ['6372']),\n"
        "         ('penduduk kotabaru', ['6302']), ('penduduk kota baru', ['6302']),\n"
        "         ('penduduk miskin', []), ('jumlah hotel kabupaten kota 2024', []),\n"
        "         ('penduduk tanah laut dan kotabaru', ['6301', '6302']),\n"
        "         ('penduduk kalimantan selatan', []), ('pdrb kabupaten tapin', ['6305'])]\n"
        "w = json.load(open(PATH, encoding='utf-8'))['wilayah']\n"
        "for x in w:\n"
        "    for s in x.get('singkatan') or []:\n"
        "        kasus.append((f'penduduk miskin {s}', [x['kode']]))\n"
        "status = sorted({str(x.get('singkatan_status')) for x in w if x['kode'] != '6300'})\n"
        "print('S status', status)\n"
        "for q, harap in kasus:\n"
        "    d = kode(q)\n"
        "    print('S', q.replace(' ', '_'), 'OK' if d == harap else f'SALAH {d} != {harap}')\n")
    hasil = re.findall(r"^S (\S+) (OK|SALAH.*)$", keluar, re.M)
    n_singkatan = len(re.findall(r"^S penduduk_miskin_", keluar, re.M))   # "penduduk miskin" tanpa _ tidak ikut
    cek(f"S1 deteksi wilayah: {len(hasil)} kasus ({n_singkatan} singkatan dari wilayah.json)",
        len(hasil) >= 19 and n_singkatan == 8 and all(h == "OK" for _, h in hasil),
        [f"{n}: {h}" for n, h in hasil if h != "OK"] or (err[-300:] if not hasil else f"{len(hasil)} OK"))
    status = re.search(r"^S status (.*)$", keluar, re.M)
    cek("S2 singkatan_status 13 kab/kota = dikonfirmasi (tim IT BPS Kalsel, 16 Nov 2026)",
        status and status.group(1) == "['dikonfirmasi']", status.group(1) if status else err[-200:])


def bagian_o(pubs, per_id, usang, s0):
    print("\n=== O. ONLINE (server tiruan): publikasi usang diunduh ulang ===", flush=True)
    for p in usang:
        per_id[p]["updt_date"] = "2026-12-31"
    PERMINTAAN.clear()
    kode, keluar, dtk = jalan("perbarui.py")
    tampil(keluar, 10)
    r = ringkasan()
    cek(f"O1 tepat {len(usang)} diunduh + diproses, status sukses, exit 0",
        kode == 0 and r["status"] == "sukses" and r["diunduh"] == len(usang) and r["diproses"] == len(usang),
        f"exit {kode}, {r['status']}, unduh {r['diunduh']}, proses {r['diproses']}, {dtk:.0f} d")
    n_beda = sql(f"SELECT COUNT(*) FROM publikasi WHERE domain='{DOMAIN}' AND updt_date_api IS NOT NULL "
                 f"AND (updt_date_diproses IS NULL OR updt_date_diproses<>updt_date_api)", DB_UJI)
    cek("O1 updt_date_diproses kini cocok dengan updt_date_api", n_beda == "0", n_beda)
    cek("O1 durasi 4 tahap tercatat", set(r["durasi_tahap"]) == {"ambil_metadata", "unduh", "ekstraksi", "muat"}
        and r["durasi_tahap"]["ekstraksi"] > 0, r["durasi_tahap"])
    jeda = [b[0] - a[0] for a, b in zip(PERMINTAAN, PERMINTAAN[1:])]
    cek("O1 jeda antar permintaan >= ~1 detik", jeda and min(jeda) >= 0.95,
        f"minimum {min(jeda):.2f} d dari {len(PERMINTAAN)} permintaan" if jeda else "tidak ada permintaan")
    cek("O1 isi identik per kunci (PDF tiruan = PDF lama)", not beda_potret(s0, potret()))
    PERMINTAAN.clear()
    kode, keluar, _ = jalan("perbarui.py")
    r = ringkasan()
    cek("O2 run kedua: tidak ada yang dikerjakan, tidak ada unduhan",
        kode == 0 and r["status"] == "tidak_ada_baru" and r["diproses"] == 0
        and not any("/pdf/" in p for _, p in PERMINTAAN), f"{r['status']}, proses {r['diproses']}")


def bagian_b(pubs, per_id, kecil):
    print("\n=== B. PUBLIKASI BARU & updt_date BERUBAH ===", flush=True)
    id_baru = "aaaabbbbccccddddeeee0001"
    baru = copy.deepcopy(per_id[kecil[0]])
    baru.update(pub_id=id_baru, title="Publikasi Tiruan Baru", pdf=f"http://127.0.0.1:{PORT}/pdf/{id_baru}",
                updt_date=None)
    KEADAAN["berkas_pdf"][id_baru] = f"{SUMBER}/{kecil[0]}.pdf"
    KEADAAN["domain"][DOMAIN] = pubs + [baru]
    per_id[kecil[1]]["updt_date"] = "2026-12-30"
    kode, keluar, _ = jalan("perbarui.py")
    r = ringkasan()
    cek("B1 publikasi baru: masuk, entri terisi, teks ternormalisasi terisi",
        r["publikasi_baru"] and r["publikasi_baru"][0]["pub_id"] == id_baru
        and entri_n(id_baru) == entri_n(kecil[0]) > 0 and kolom_pub(id_baru, "teks_ternormalisasi") != "NULL",
        f"exit {kode}, entri {entri_n(id_baru)}/{entri_n(kecil[0])}")
    cek("B1 tanpa entri NULL normalisasi",
        sql("SELECT COUNT(*) FROM entri_dokumen WHERE teks_ternormalisasi IS NULL", DB_UJI) == "0")
    cek("B2 updt_date berubah: diunduh ulang + diproses",
        kolom_pub(kecil[1], "updt_date_diproses") == "2026-12-30" and r["diunduh"] == 2,
        f"diunduh {r['diunduh']}, diproses {kolom_pub(kecil[1], 'updt_date_diproses')}")
    per_id[kecil[1]]["updt_date"] = None
    kode, keluar, _ = jalan("perbarui.py")
    r = ringkasan()
    cek("B3 updt_date kosong dari API: bukan perubahan, nilai lama dipertahankan",
        r["diproses"] == 0 and kolom_pub(kecil[1], "updt_date_api") == "2026-12-30",
        f"proses {r['diproses']}, api {kolom_pub(kecil[1], 'updt_date_api')}")
    per_id[kecil[1]]["updt_date"] = "2026-12-30"
    return baru


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def bagian_g(per_id, x):
    print("\n=== G. UNDUHAN GAGAL (kelas bug 'publikasi tertinggal') ===", flush=True)
    n0, proses0, h0 = entri_n(x), kolom_pub(x, "updt_date_diproses"), md5(path_uji(x))
    per_id[x]["updt_date"] = "2026-12-29"
    for mode in ("500", "html", "potong"):
        KEADAAN["mode_pdf"][x] = mode
        kode, keluar, dtk = jalan("perbarui.py")
        r = ringkasan()
        d = r["domain"][0]
        cek(f"G1 unduh '{mode}': exit 3, sebagian, data+PDF lama utuh, api tersimpan, diproses tak maju",
            kode == 3 and r["status"] == "sebagian" and len(d["gagal"]) == 1 and entri_n(x) == n0
            and md5(path_uji(x)) == h0 and kolom_pub(x, "updt_date_api") == "2026-12-29"
            and kolom_pub(x, "updt_date_diproses") == proses0 and not os.path.exists(path_uji(x) + ".part"),
            f"exit {kode}, {r['status']}, {dtk:.0f} d, pesan: {d['gagal'][0]['pesan'][:60] if d['gagal'] else ''}")
    del KEADAAN["mode_pdf"][x]
    kode, keluar, _ = jalan("perbarui.py")
    r = ringkasan()
    cek("G2 run berikutnya memprosesnya sendiri setelah pulih",
        kode == 0 and r["diunduh"] == 1 and kolom_pub(x, "updt_date_diproses") == "2026-12-29"
        and r["status"] == "sukses", f"exit {kode}, {r['status']}, diunduh {r['diunduh']}")


def bagian_e(pubs, per_id, kecil, baru):
    print("\n=== E. PDF RUSAK, PDF 0 ENTRI, PDF HILANG/DIGANTI ===", flush=True)
    y = kecil[3]
    n0 = entri_n(y)
    rusak = f"{SP}/rusak.pdf"
    open(rusak, "wb").write(b"%PDF-1.4\n" + b"sampah bukan pdf\n" * 200 + b"%%EOF\n")
    KEADAAN["berkas_pdf"][y] = rusak
    per_id[y]["updt_date"] = "2026-12-28"
    kode, keluar, _ = jalan("perbarui.py")
    galat = kolom_pub(y, "galat_ekstraksi")
    cek("E1 PDF tak terbaca: entri lama utuh, galat tercatat, exit 3",
        kode == 3 and entri_n(y) == n0 and galat not in ("NULL", ""), f"exit {kode}, entri {entri_n(y)}/{n0}, galat: {galat[:50]}")
    KEADAAN["berkas_pdf"][y] = f"{SUMBER}/{y}.pdf"
    kode, keluar, _ = jalan("perbarui.py")
    cek("E2 pulih: galat terhapus, dicoba lagi otomatis",
        kode == 0 and kolom_pub(y, "galat_ekstraksi") == "NULL" and entri_n(y) == n0,
        f"exit {kode}, galat {kolom_pub(y, 'galat_ekstraksi')}")

    # PDF sah tanpa teks: 0 entri itu sah dan tidak boleh diekstrak ulang tiap run
    id_kosong = "aaaabbbbccccddddeeee0002"
    kosong = f"{SP}/kosong.pdf"
    open(kosong, "wb").write(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n"
        + b"%" + b"x" * 1200 + b"\n%%EOF\n")
    b2 = copy.deepcopy(per_id[kecil[0]])
    b2.update(pub_id=id_kosong, title="Publikasi Tiruan Kosong", pdf=f"http://127.0.0.1:{PORT}/pdf/{id_kosong}",
              updt_date=None)
    KEADAAN["berkas_pdf"][id_kosong] = kosong
    KEADAAN["domain"][DOMAIN] = pubs + [baru, b2]
    kode, keluar, _ = jalan("perbarui.py")
    r = ringkasan()
    cek("E3 PDF sah 0 entri: tercatat diekstrak",
        entri_n(id_kosong) == 0 and kolom_pub(id_kosong, "diekstrak_pada") != "NULL",
        f"exit {kode}, perlu diperiksa: {[c['alasan'][:40] for c in r['domain'][0]['perlu_diperiksa'] if c['pub_id'] == id_kosong]}")
    kode, keluar, _ = jalan("perbarui.py")
    cek("E4 run berikutnya TIDAK mengekstrak ulang publikasi 0 entri", ringkasan()["diproses"] == 0,
        f"proses {ringkasan()['diproses']}")

    z = kecil[4]
    os.remove(path_uji(z))          # hanya menghapus hardlink salinan
    kode, keluar, _ = jalan("perbarui.py")
    r = ringkasan()
    cek("E5 PDF hilang di disk: diunduh ulang + diekstrak", kode == 0 and r["diunduh"] == 1 and os.path.exists(path_uji(z)),
        f"exit {kode}, diunduh {r['diunduh']}")
    shutil.copy(f"{SUMBER}/{z}.pdf", path_uji(z) + ".salin")
    os.replace(path_uji(z) + ".salin", path_uji(z))
    kode, keluar, _ = jalan("perbarui.py")
    r = ringkasan()
    cek("E6 PDF diganti di disk: diekstrak tanpa unduh", r["diproses"] == 1 and r["diunduh"] == 0,
        f"proses {r['diproses']}, unduh {r['diunduh']}")

    w = kecil[5]
    per_id[w]["updt_date"] = "2026-12-27"
    sql(f"UPDATE publikasi SET updt_date_api='2026-12-27' WHERE id='{w}'", DB_UJI)   # metadata sudah ditarik
    d0 = kolom_pub(w, "updt_date_diproses")
    kode, keluar, _ = jalan("perbarui.py", "--lokal")
    r = ringkasan()
    cek("E7 --lokal: updt_date_diproses tak maju, tercatat menunggu",
        kolom_pub(w, "updt_date_diproses") == d0 and any(m["pub_id"] == w for m in r["domain"][0]["menunggu_unduhan"]),
        f"diproses {kolom_pub(w, 'updt_date_diproses')}")
    kode, keluar, _ = jalan("perbarui.py")          # selesaikan supaya bagian berikut mulai bersih


def popen_perbarui():
    """perbarui.py di latar, SELALU --db-uji."""
    return subprocess.Popen([PY, "-u", f"{UJI}/scripts/perbarui.py", "--db-uji"], cwd=SP, env=ENV,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def bagian_t(per_id, x, kecil):
    print("\n=== T. TRANSAKSI DAN KUNCI ===", flush=True)
    kode, keluar, err = jalan_py(
        "from app import create_app\nfrom app.config import KonfigurasiUji\n"
        "from app.models import db, EntriDokumen\nfrom app.services import pipeline_data as P\n"
        "app = create_app(KonfigurasiUji)\n"
        "with app.app_context():\n"
        f"    n0 = EntriDokumen.query.filter_by(publikasi_id='{x}').count()\n"
        "    try:\n"
        f"        P.simpan_entri('{x}', [{{'tipe':'tabel','judul':'ok'}},{{'tipe':'TIPE-TIDAK-SAH','judul':'gagal'}}], (1,1), {{}})\n"
        "        print('TIDAK-GAGAL')\n"
        "    except Exception:\n"
        "        print('GAGAL-SEPERTI-DIHARAPKAN')\n"
        f"    print('jumlah', n0, EntriDokumen.query.filter_by(publikasi_id='{x}').count())\n")
    m = re.search(r"jumlah (\d+) (\d+)", keluar)
    cek("T1 gagal di tengah transaksi: entri lama utuh",
        "GAGAL-SEPERTI-DIHARAPKAN" in keluar and m and m.group(1) == m.group(2) and int(m.group(1)) > 0,
        keluar.strip().replace("\n", " | ")[-120:] + err[-150:])

    proses0 = kolom_pub(x, "updt_date_diproses")
    per_id[x]["updt_date"] = "2026-12-26"
    PERMINTAAN.clear()
    p = popen_perbarui()
    t0 = time.time()
    while time.time() - t0 < 120 and not any("/pdf/" in q for _, q in PERMINTAAN):
        time.sleep(0.05)
    subprocess.run(["taskkill", "/F", "/PID", str(p.pid)], capture_output=True)
    p.wait()
    kunci = f"{UJI}/data/pembaruan.lock"
    cek("T2 proses dibunuh: kunci basi tertinggal", os.path.exists(kunci), f"setelah {time.time() - t0:.1f} d")
    cek("T2 proses dibunuh: entri & diproses belum berubah",
        kolom_pub(x, "updt_date_diproses") == proses0 and entri_n(x) > 0, kolom_pub(x, "updt_date_diproses"))
    kode, keluar, _ = jalan("perbarui.py")
    cek("T3 run berikutnya menimpa kunci basi dan menyelesaikan",
        kode == 0 and kolom_pub(x, "updt_date_diproses") == "2026-12-26" and not os.path.exists(kunci),
        f"exit {kode}, {ringkasan()['status']}")

    # Kunci hidup: run pertama diberi kerja (unduh + ekstrak) supaya pasti masih berjalan.
    per_id[kecil[0]]["updt_date"] = "2026-12-25"
    p = popen_perbarui()
    t0 = time.time()
    while time.time() - t0 < 60 and not os.path.exists(kunci):
        time.sleep(0.05)
    kode, keluar, _ = jalan("perbarui.py")
    cek("T4 pembaruan kedua ditolak exit 2, yang pertama tetap hidup", kode == 2 and p.poll() is None,
        f"exit {kode}: {keluar.strip().splitlines()[-1][:70] if keluar.strip() else ''}")
    p.wait()
    cek("T4 pertama selesai normal", p.returncode == 0, p.returncode)


TIRUAN = {"kode": "6399", "nama": "Kab. Tiruan Uji", "aktif": False, "singkatan": [],
          "singkatan_status": "tiruan"}


def bagian_d(per_id, kecil):
    print("\n=== D. MULTI-DOMAIN (domain tiruan 6399) ===", flush=True)
    semula = list(KEADAAN["domain"][DOMAIN])

    # D0: keadaan pemasangan baru - SEMUA wilayah aktif tanpa data dan tanpa
    # laporan --hanya-periksa. Harus berhenti di awal dengan satu pesan, bukan
    # melewati wilayah satu per satu.
    tiruan2 = dict(TIRUAN, kode="6398", nama="Kab. Tiruan Uji Dua")
    aktifkan("6398", TIRUAN["kode"], tambahan=[tiruan2, TIRUAN])
    lap_periksa = f"{UJI}/data/pemeriksaan_domain.json"
    if os.path.exists(lap_periksa):
        os.remove(lap_periksa)
    cs0, n_minta = checksum_db(DB_UJI), len(PERMINTAAN)
    kode, keluar, dtk = jalan("perbarui.py")
    r = ringkasan()
    cek("D0 semua wilayah aktif belum diperiksa: berhenti di awal, exit 1, pesan --hanya-periksa",
        kode == 1 and "TIDAK ADA YANG DIKERJAKAN" in keluar and "perbarui.py --hanya-periksa" in keluar
        and "DOMAIN 6398" not in keluar and r["status"] == "gagal" and "--hanya-periksa" in r.get("pesan", ""),
        f"exit {kode}, {dtk:.0f} d, tahap {r.get('tahap')!r}")
    tampil(keluar, 14)
    cek("D0 tanpa permintaan ke WebAPI, database uji tidak berubah (CHECKSUM TABLE)",
        len(PERMINTAAN) == n_minta and checksum_db(DB_UJI) == cs0, f"{len(PERMINTAAN) - n_minta} permintaan")

    aktifkan(DOMAIN, TIRUAN["kode"], tambahan=[TIRUAN])
    b63 = copy.deepcopy(per_id[kecil[0]])
    id63 = "aaaabbbbccccddddeeee6399"
    b63.update(pub_id=id63, title="Kabupaten Tiruan Dalam Angka Tiruan",
               pdf=f"http://127.0.0.1:{PORT}/pdf/{id63}", updt_date=None)
    KEADAAN["berkas_pdf"][id63] = f"{SUMBER}/{kecil[0]}.pdf"
    KEADAAN["domain"]["6399"] = [b63]

    def run(*arg):
        kode, keluar, _ = jalan("perbarui.py", *arg)
        r = ringkasan()
        return kode, r, {d["kode"]: d for d in r.get("domain", [])}

    kode, r, ds = run()
    cek("D1 domain baru tanpa --hanya-periksa: DILEWATI, domain lama tetap jalan, exit 3",
        ds["6399"]["status"] == "gagal" and "hanya-periksa" in ds["6399"]["pesan"]
        and ds[DOMAIN]["status"] in ("tidak_ada_baru", "sukses") and kode == 3,
        f"exit {kode}, 6399: {str(ds['6399']['pesan'])[:50]}")
    n = sql("SELECT COUNT(*) FROM publikasi WHERE domain='6399'", DB_UJI)
    cek("D1 tak ada baris 6399 masuk", n == "0", n)

    sebelum = sql("SELECT COUNT(*), MAX(updated_at) FROM publikasi", DB_UJI)
    pdf_sebelum = len(glob.glob(f"{UJI}/data/publikasi_pdf/*/*.pdf"))
    kode, keluar, dtk = jalan("perbarui.py", "--hanya-periksa")
    lap = json.load(open(f"{UJI}/data/pemeriksaan_domain.json", encoding="utf-8"))
    n_wil = len(json.load(open(f"{UJI}/data/wilayah.json", encoding="utf-8"))["wilayah"])
    cek(f"D2 --hanya-periksa bersih: {n_wil} wilayah, 0 tabrakan, exit 0",
        kode == 0 and len(lap["domain_berhasil"]) == n_wil and not lap["tabrakan"],
        f"exit {kode}, {len(lap['domain_berhasil'])} domain, {dtk:.0f} d")
    cek("D2 --hanya-periksa tidak menulis DB / PDF",
        sql("SELECT COUNT(*), MAX(updated_at) FROM publikasi", DB_UJI) == sebelum
        and len(glob.glob(f"{UJI}/data/publikasi_pdf/*/*.pdf")) == pdf_sebelum)

    kode, r, ds = run()
    p63 = f"{UJI}/data/publikasi_pdf/6399/{id63}.pdf"
    cek("D3 setelah lolos: 6399 dimuat ke subfolder + wilayah benar",
        ds["6399"]["status"] == "sukses" and os.path.exists(p63) and kolom_pub(id63, "wilayah") == TIRUAN["nama"]
        and kolom_pub(id63, "domain") == "6399", f"{ds['6399']['status']}, {kolom_pub(id63, 'wilayah')}")

    x = kecil[2]
    KEADAAN["gagal_domain"]["6399"] = "putus"
    per_id[x]["updt_date"] = "2026-12-24"
    kode, r, ds = run()
    cek("D4 domain putus jaringan: domain lain tetap diproses, exit 3",
        kode == 3 and r["status"] == "sebagian" and ds["6399"]["status"] == "gagal" and ds["6399"]["jaringan"]
        and ds[DOMAIN]["status"] == "sukses" and kolom_pub(x, "updt_date_diproses") == "2026-12-24",
        f"exit {kode}, {r['status']}, {DOMAIN} {ds[DOMAIN]['status']}")
    cek("D4 data domain yang gagal tidak disentuh", entri_n(id63) > 0 and kolom_pub(id63, "domain") == "6399")
    del KEADAAN["gagal_domain"]["6399"]

    # Halaman ke-2 gagal: domain gagal tanpa upsert sebagian (judul halaman 1 tetap)
    KEADAAN["gagal_halaman"][DOMAIN] = 2
    pid0 = semula[0]["pub_id"]
    judul0 = kolom_pub(pid0, "judul")
    semula[0]["title"] = "JUDUL SEHARUSNYA TIDAK MASUK"
    kode, r, ds = run()
    cek("D5 halaman ke-2 gagal: domain gagal, metadata tak tersentuh",
        ds[DOMAIN]["status"] == "gagal" and kolom_pub(pid0, "judul") == judul0,
        f"{ds[DOMAIN]['status']}: {str(ds[DOMAIN]['pesan'])[:60]}")
    del KEADAAN["gagal_halaman"][DOMAIN]
    semula[0]["title"] = judul0

    KEADAAN["domain"]["6399"] = []
    kode, r, ds = run()
    cek("D6 0 publikasi padahal DB berisi: ditolak, data utuh",
        ds["6399"]["status"] == "gagal" and kolom_pub(id63, "domain") == "6399", str(ds["6399"]["pesan"])[:70])

    t = semula[1]["pub_id"]
    judul_t, ent_t = kolom_pub(t, "judul"), entri_n(t)
    kol = copy.deepcopy(semula[1])
    kol["title"] = "JUDUL DOMAIN LAIN"
    KEADAAN["domain"]["6399"] = [b63, kol]
    kode, keluar, _ = jalan("perbarui.py", "--hanya-periksa")
    lap = json.load(open(f"{UJI}/data/pemeriksaan_domain.json", encoding="utf-8"))
    cek("D7 --hanya-periksa: 1 pub_id di dua domain = TEPAT 1 tabrakan, exit 1",
        kode == 1 and [x["pub_id"] for x in lap["tabrakan"]] == [t], f"exit {kode}, {len(lap['tabrakan'])} tabrakan")
    KEADAAN["domain"][DOMAIN] = [p for p in semula if p["pub_id"] != t]
    kode, keluar, _ = jalan("perbarui.py", "--hanya-periksa")
    lap = json.load(open(f"{UJI}/data/pemeriksaan_domain.json", encoding="utf-8"))
    cek("D7b tabrakan API-vs-DB terdeteksi, tepat 1",
        kode == 1 and [x["pub_id"] for x in lap["tabrakan"]] == [t]
        and lap["tabrakan"][0].get("domain_tersimpan") == DOMAIN, f"exit {kode}, {len(lap['tabrakan'])} tabrakan")
    KEADAAN["domain"][DOMAIN] = semula
    jalan("perbarui.py", "--hanya-periksa")
    kode, r, ds = run()
    cek("D8 pengaman: baris domain lain TIDAK ditimpa, dilaporkan, exit 3",
        kode == 3 and ds["6399"]["status"] == "sebagian" and ds["6399"]["tabrakan"][0]["pub_id"] == t
        and kolom_pub(t, "judul") == judul_t and kolom_pub(t, "domain") == DOMAIN and entri_n(t) == ent_t,
        f"exit {kode}, {ds['6399']['status']}")

    KEADAAN["domain"]["6399"] = [kol]
    kode, r, ds = run()
    cek("D9 publikasi hilang dari daftar API: dilaporkan, tidak dihapus",
        ds["6399"]["tidak_di_daftar"] and ds["6399"]["tidak_di_daftar"][0]["pub_id"] == id63 and entri_n(id63) > 0,
        len(ds["6399"]["tidak_di_daftar"]))
    KEADAAN["domain"]["6399"] = [b63]
    aktifkan(DOMAIN)


def bagian_k():
    print("\n=== K. API KEY TIDAK BOCOR ===", flush=True)
    import requests
    try:
        requests.get(f"http://127.0.0.1:9/v1/key/{KEY}/", timeout=2)
        cek("K0 alat uji sah: pesan galat mentah memang memuat key", False, "tidak ada galat")
    except Exception as e:  # noqa: BLE001
        cek("K0 alat uji sah: pesan galat mentah memang memuat key", KEY in str(e))
    bocor = []
    putus = {"BPS_API_BASE_URL": "http://127.0.0.1:9/v1/api"}       # port tertutup, bukan BPS
    for skenario, arg in (("jaringan putus", ()), ("periksa putus", ("--hanya-periksa",))):
        kode, keluar, _ = jalan("perbarui.py", *arg, timeout=900, env_tambah=putus)
        for nama_b, berkas in (("keluaran", None), ("ringkasan", "pembaruan_terakhir-uji.json"),
                               ("pemeriksaan", "pemeriksaan_domain.json")):
            isi = keluar if berkas is None else (open(f"{UJI}/data/{berkas}", encoding="utf-8").read()
                                                  if os.path.exists(f"{UJI}/data/{berkas}") else "")
            if KEY in isi:
                bocor.append((skenario, nama_b))
        cek(f"K1 {skenario}: gagal dengan pesan, key tersamar", kode == 1 and "***" in keluar and "127.0.0.1" in keluar,
            f"exit {kode}")
    cek("K1 key tidak ada di keluaran/ringkasan/laporan", not bocor, bocor)


def bagian_r(contoh_id):
    print("\n=== R. ROUTE PDF & HALAMAN ADMIN (test_client, KonfigurasiUji) ===", flush=True)
    kode_r = rf"""
import json, os, re
from app import create_app
from app.config import KonfigurasiUji
from app.models import Publikasi
app = create_app(KonfigurasiUji); c = app.test_client()
U = r'{UJI}/data/publikasi_pdf'
with app.app_context():
    semua = [(p.id, p.domain, p.url_pdf) for p in Publikasi.query.filter(Publikasi.domain.in_(['{DOMAIN}', '6399'])).all()]
buruk = []
n = 0
for pid, dom, _ in semua:
    path = f'{{U}}/{{dom}}/{{pid}}.pdf'
    if not os.path.exists(path): continue
    n += 1
    r = c.get('/pdf/' + pid); isi = r.get_data(); r.close()
    if (r.status_code != 200 or r.headers.get('Location') or r.mimetype != 'application/pdf' or isi[:4] != b'%PDF'
            or len(isi) != os.path.getsize(path) or 'attachment' in r.headers.get('Content-Disposition', '')):
        buruk.append((pid, r.status_code))
print('PDF_LOKAL', n, 'buruk', buruk)
h = c.get('/hasil?q=pdrb&w={DOMAIN}').get_data(as_text=True)
# Kartu "Juga ada di publikasi provinsi" menautkan PDF domain 6300, yang tidak
# ada di salinan uji: route itu benar mengalihkan ke url_pdf. Dinilai terpisah.
lokal = set(p for p, _, _ in semua)
tautan = re.findall(r'href="(/pdf/(\w+)[^"]*)"', h)
ok = lain = lain_ok = 0
for t, pid in tautan:
    r = c.get(t.split('#')[0])
    if pid in lokal:
        ok += r.status_code == 200 and not r.headers.get('Location') and r.get_data()[:4] == b'%PDF'
    else:
        lain += 1; lain_ok += r.status_code == 302
    r.close()
print('TOMBOL', len(tautan) - lain, 'ok', ok, 'LAIN', lain, 'alih', lain_ok)
url = dict((p, u) for p, _, u in semua)['{contoh_id}']
path = f'{{U}}/{DOMAIN}/{contoh_id}.pdf'
os.replace(path, path + '.x'); r = c.get('/pdf/{contoh_id}'); print('HILANG', r.status_code, r.headers.get('Location') == url); os.replace(path + '.x', path)
print('TAK_ADA', c.get('/pdf/..%2f..%2fapp').status_code, c.get('/pdf/tidakada').status_code)
with c.session_transaction() as s: s['admin_masuk'] = True; s['admin_aktif'] = int(__import__('time').time())
F = r'{UJI}/data/pembaruan_terakhir-uji.json'
contoh = {{
 'sebagian': {{'status':'sebagian','selesai_pada':'2026-11-05T01:00:00+00:00','jaringan':False,'jumlah_publikasi':80,'publikasi_baru':[{{'pub_id':'x','judul':'Judul Baru <b>','entri':5,'wilayah':'Kab. Tapin'}}],'entri_sebelum':10,'entri_sesudah':15,'durasi_detik':60,'durasi_tahap':{{'ambil_metadata':1.5,'unduh':2.5,'ekstraksi':3.5,'muat':0.5}},
   'domain':[{{'kode':'6305','wilayah':'Kab. Tapin','status':'sebagian','pesan':None,'jumlah_publikasi':17,'diunduh':1,'diproses':0,'gagal':[{{'judul':'Judul Gagal','tahap':'unduh','pesan':'HTTP 500'}}],'tabrakan':[{{'pub_id':'id1','domain_lain':'6399','judul_api':'Judul Tabrakan'}}],'tidak_di_daftar':[{{'pub_id':'y','judul':'z'}}],'menunggu_unduhan':[{{'pub_id':'m'}}],'perlu_diperiksa':[]}},
             {{'kode':'6301','wilayah':'Kab. Tanah Laut','status':'gagal','pesan':'halaman 1: putus','jumlah_publikasi':0,'diunduh':0,'diproses':0,'gagal':[],'tabrakan':[],'tidak_di_daftar':[],'menunggu_unduhan':[],'perlu_diperiksa':[]}}]}},
 'sukses': {{'status':'sukses','selesai_pada':'2026-11-05T01:00:00+00:00','jaringan':False,'jumlah_publikasi':80,'publikasi_baru':[],'entri_sebelum':10,'entri_sesudah':15,'durasi_detik':60,'durasi_tahap':{{'ambil_metadata':1,'unduh':2,'ekstraksi':3,'muat':4}},'domain':[]}},
 'tidak_ada_baru': {{'status':'tidak_ada_baru','selesai_pada':'2026-11-05T01:00:00+00:00','jaringan':False,'jumlah_publikasi':80,'durasi_detik':60,'publikasi_baru':[],'domain':[{{'kode':'6305','wilayah':'Kab. Tapin','status':'tidak_ada_baru','pesan':None,'jumlah_publikasi':17,'diunduh':0,'diproses':0,'gagal':[],'tabrakan':[],'tidak_di_daftar':[],'menunggu_unduhan':[],'perlu_diperiksa':[]}}],'durasi_tahap':{{'ambil_metadata':1,'unduh':0,'ekstraksi':0,'muat':0}}}},
 'gagal_jaringan': {{'status':'gagal','selesai_pada':'2026-11-05T01:00:00+00:00','jaringan':True,'durasi_detik':5,'domain':[]}},
 'gagal_lain': {{'status':'gagal','selesai_pada':'2026-11-05T01:00:00+00:00','jaringan':False,'tahap':'konfigurasi','durasi_detik':5}},
 'gagal_periksa': {{'status':'gagal','selesai_pada':'2026-11-05T01:00:00+00:00','jaringan':False,'tahap':'pemeriksaan wilayah','pesan':'Tim IT perlu menjalankan sekali: perbarui.py --hanya-periksa','durasi_detik':0}},
 'lama_sukses': {{'status':'sukses','selesai_pada':'2026-09-15T01:00:00+00:00','jumlah_publikasi':74,'publikasi_baru':[{{'pub_id':'x','judul':'Format Lama','entri':3}}],'entri_sebelum':1,'entri_sesudah':4,'diekstrak_ulang':0,'durasi_detik':179}},
 'lama_tidak_ada': {{'jumlah_publikasi':79,'durasi_detik':175,'status':'tidak_ada_baru','selesai_pada':'2026-11-05T01:53:19+00:00'}},
}}
harap = {{'sebagian':['selesai sebagian','Kab. Tanah Laut','Sebagian gagal','Judul Gagal','Judul Tabrakan','halaman 1: putus','menunggu pembaruan online','tidak lagi ada','ambil daftar 1.5','&lt;b&gt;'],'sukses':['Pembaruan selesai','simpan 4'],'tidak_ada_baru':['Tidak ada publikasi baru','Tidak ada yang baru'],'gagal_jaringan':['DNS jaringan','Pemecahan masalah'],'gagal_lain':['di tahap konfigurasi'],'gagal_periksa':['di tahap pemeriksaan wilayah','perbarui.py --hanya-periksa'],'lama_sukses':['Format Lama','179 detik'],'lama_tidak_ada':['Tidak ada publikasi baru','175 detik']}}
# Teks lama tentang jenis Wi-Fi tidak boleh tampil lagi (penyebabnya DNS).
def lama(h): return ['ADA: ' + x for x in ('BPS - Pegawai', 'BPS - Tamu') if x in h]
for nama, isi in contoh.items():
    json.dump(isi, open(F, 'w', encoding='utf-8'))
    r = c.get('/admin/perbarui'); h = r.get_data(as_text=True)
    print('ADMIN', nama, r.status_code, 'kurang', [x for x in harap[nama] if x not in h] + lama(h))
os.remove(F)
r = c.get('/admin/perbarui'); h = r.get_data(as_text=True)
print('ADMIN tanpa_berkas', r.status_code, 'kurang', [x for x in ['webapi.bps.go.id'] if x not in h] + lama(h))
"""
    kode, keluar, err = jalan_py(kode_r, timeout=900)
    print("    | " + keluar.strip().replace("\n", "\n    | "), err[-800:], flush=True)
    m = re.search(r"PDF_LOKAL (\d+) buruk (.*)", keluar)
    cek("R1 /pdf/<id> menyajikan berkas lokal untuk semua publikasi domain uji",
        m and int(m.group(1)) > 0 and m.group(2) == "[]", m.group(0)[:100] if m else err[-200:])
    m = re.search(r"TOMBOL (\d+) ok (\d+) LAIN (\d+) alih (\d+)", keluar)
    cek("R2 tombol Buka PDF di /hasil -> berkas lokal tanpa redirect; PDF di luar salinan -> alih ke url_pdf",
        m and int(m.group(1)) > 0 and m.group(1) == m.group(2) and m.group(3) == m.group(4), m.group(0) if m else "")
    cek("R3 berkas hilang -> cadangan redirect ke url_pdf", "HILANG 302 True" in keluar)
    cek("R4 id tak dikenal / path aneh -> 404", "TAK_ADA 404 404" in keluar)
    admin = re.findall(r"ADMIN (\w+) (\d+) kurang (.*)", keluar)
    cek("R5 /admin/perbarui (ringkasan -uji) merender semua status + format lama",
        len(admin) == 9 and all(a[1] == "200" and a[2] == "[]" for a in admin), admin)


def siapkan_bat():
    """perbarui-data.bat sungguhan di salinan: python/activate palsu mengarah ke venv asli."""
    os.makedirs(f"{UJI}/venv/Scripts", exist_ok=True)
    open(f"{UJI}/venv/Scripts/python.exe", "wb").close()
    with open(f"{UJI}/venv/Scripts/activate.bat", "w", newline="") as f:
        jalur = os.path.dirname(PY).replace("/", chr(92))
        f.write('@set "PATH=' + jalur + ';%PATH%"' + chr(13) + chr(10))
    shutil.copy2(f"{ASLI}/perbarui-data.bat", f"{UJI}/perbarui-data.bat")
    open(f"{UJI}/.env", "w").write("# kosong: nilai uji datang dari variabel lingkungan\n")


def bat(*arg):
    """perbarui-data.bat di salinan, SELALU --db-uji."""
    r = subprocess.run(["cmd", "/c", os.path.normpath(f"{UJI}/perbarui-data.bat"), "--db-uji", *arg], cwd=UJI,
                       env=ENV, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=600)
    return r.stdout + r.stderr


def bagian_w(per_id, v):
    print("\n=== W. TOMBOL WEB + .BAT SUNGGUHAN (keduanya --db-uji) ===", flush=True)
    per_id[v]["updt_date"] = "2026-12-23"
    KEADAAN["mode_pdf"][v] = "500"
    kode_web = rf"""
import time
from app import create_app
from app.config import KonfigurasiUji
app = create_app(KonfigurasiUji); c = app.test_client()
with c.session_transaction() as s: s['admin_masuk'] = True; s['admin_aktif'] = int(__import__('time').time())
r = c.post('/admin/perbarui/mulai'); print('MULAI', r.status_code)
r = c.post('/admin/perbarui/mulai'); h = c.get('/admin/perbarui').get_data(as_text=True); print('KEDUA_NONAKTIF', 'sedang berjalan' in h)
t = time.time()
while time.time() - t < 600:
    h = c.get('/admin/perbarui').get_data(as_text=True)
    if 'Pembaruan sedang berjalan' not in h: break
    time.sleep(1)
print('SEBAGIAN_TAMPIL', 'selesai sebagian' in h, 'JUDUL_GAGAL', {per_id[v]['title'][:30]!r} in h, 'UJI', '{DB_UJI}' in h)
"""
    kode, keluar, err = jalan_py(kode_web, timeout=700)
    print("    | " + keluar.strip().replace("\n", "\n    | "), err[-500:], flush=True)
    cek("W1 tombol web (KonfigurasiUji): berjalan ke DB uji, POST kedua ditolak, ringkasan 'sebagian' + judul gagal",
        "MULAI 302" in keluar and "KEDUA_NONAKTIF True" in keluar
        and "SEBAGIAN_TAMPIL True JUDUL_GAGAL True UJI True" in keluar)
    del KEADAAN["mode_pdf"][v]

    siapkan_bat()
    isi_bat = open(f"{ASLI}/perbarui-data.bat", "rb").read()
    cek("W2 .bat tetap ASCII + CRLF", all(x < 128 for x in isi_bat) and b"\n" not in isi_bat.replace(b"\r\n", b""))

    def baris(k, kata):
        return [b.strip() for b in k.splitlines() if kata in b][:2]

    per_id[v]["updt_date"] = "2026-12-22"
    KEADAAN["mode_pdf"][v] = "500"
    k = bat()
    cek("W3 .bat exit 3 -> SELESAI SEBAGIAN", "PEMBARUAN SELESAI SEBAGIAN" in k and "PEMBARUAN GAGAL" not in k,
        baris(k, "PEMBARUAN"))
    del KEADAAN["mode_pdf"][v]
    k = bat()
    cek("W4 .bat exit 0 -> PEMBARUAN SELESAI., cek MySQL ke database uji",
        "PEMBARUAN SELESAI." in k and "SEBAGIAN" not in k and f"database: {DB_UJI}" in k,
        baris(k, "PEMBARUAN") + baris(k, "database:"))
    KEADAAN["gagal_domain"][DOMAIN] = "putus"
    k = bat()
    cek("W5 .bat exit 1 -> PEMBARUAN GAGAL + pesan jaringan", "PEMBARUAN GAGAL" in k and "tidak bisa dihubungi" in k,
        baris(k, "PEMBARUAN"))
    del KEADAAN["gagal_domain"][DOMAIN]
    per_id[v]["updt_date"] = "2026-12-21"            # run pertama diberi kerja supaya pasti masih berjalan
    p = popen_perbarui()
    t0 = time.time()
    while time.time() - t0 < 60 and not os.path.exists(f"{UJI}/data/pembaruan.lock"):
        time.sleep(0.05)
    k = bat()
    cek("W6 .bat saat terkunci -> TIDAK DIJALANKAN", "TIDAK DIJALANKAN" in k, baris(k, "DIJALANKAN"))
    p.wait()


KODE_BAGIAN_V = r'''
import json, os, re, statistics, sys, time
from urllib.parse import urlencode
sys.path.insert(0, os.path.join(sys.path[0], "scripts"))
assert os.environ.get("PYTHONHASHSEED") == "0"
from app import create_app
from app.config import KonfigurasiUji
from ukur_kinerja import KUERI, KUERI_WILAYAH
from app.services import mesin_pencari as M
class KonfigurasiTanpaKec(KonfigurasiUji):
    SQLALCHEMY_DATABASE_URI = URL_TANPA_KEC
RE_WIDGET = [re.compile(r'\n\n  <select name="kc"[\s\S]*?</select>'),
             re.compile(r'\n\n  <label class="centang-kecamatan">[\s\S]*?js/kecamatan\.js" defer></script>'),
             re.compile(r'\n\n<div class="info-kecamatan"[\s\S]*?</div>')]
RE_WAKTU = re.compile(r"&middot; \d+ ms")
URL = ["/", "/?w=6301"] + ["/hasil?" + urlencode({"q": k}) for k in KUERI] + \
      ["/hasil?" + urlencode({"q": k, "w": w}) for k, w in KUERI_WILAYAH]
SARAN = ["penduduk", "luas pan", "jumlah sek", "tpk", "ekspor", "jumlah penduduk menurut desa"]
def app_untuk(tanpa):
    return create_app(KonfigurasiTanpaKec) if tanpa else create_app(KonfigurasiUji)
def potret(tanpa, buang):
    c = app_untuk(tanpa).test_client(); out = {}
    for u in URL:
        t = RE_WAKTU.sub("# ms", c.get(u).get_data(as_text=True))
        if buang:
            for rx in RE_WIDGET: t = rx.sub("", t)
        out[u] = t
    return out
uji, tanpa = potret(False, True), potret(True, False)
beda = [u for u in URL if uji[u] != tanpa[u]]
print("V1", len(URL), json.dumps(beda))
c = create_app(KonfigurasiUji).test_client()
kec = [s["publikasi"] for a in SARAN for s in c.get("/api/saran", query_string={"q": a}).get_json()["saran"]
       if s["publikasi"].startswith("Kecamatan")]
kec1 = sum(s["publikasi"].startswith("Kecamatan") for a in SARAN
           for s in c.get("/api/saran", query_string={"q": a, "kec": "1"}).get_json()["saran"])
print("V2", len(kec), kec1)
def waktu(tanpa):
    M._korpus = None
    with app_untuk(tanpa).app_context():
        M.cari("pemanasan"); med = []
        for q in KUERI:
            M.cari(q); w = []
            for _ in range(10):
                t = time.perf_counter(); M.cari(q); w.append(time.perf_counter() - t)
            med.append(statistics.median(w))
        return statistics.mean(med) * 1000
w = [(waktu(True), waktu(False)) for _ in range(3)]
print("V3", json.dumps(w))
cek = []
for a in [{"q": "jumlah penduduk menurut desa"}, {"q": "penduduk", "w": "6305"}, {"q": "tpk"}]:
    j = c.get("/api/kecamatan/jumlah", query_string=a).get_json()["jumlah"]
    t = c.get("/hasil?" + urlencode({**a, "kec": "1"})).get_data(as_text=True)
    m = re.search(r"<strong>(\d+)</strong> bagian cocok", t)
    cek.append([a["q"], j, int(m.group(1)) if m else None, 'class="seksi seksi-kecamatan"' in t])
print("V4", json.dumps(cek))
# V5: seksi PUBLIKASI ikut membaca publikasi kecamatan kalau dicentang / kecamatan dipilih,
# dan publikasi kecamatan yang dipilih paling atas (temuan pemilik project 19 Nov 2026:
# "Kecamatan Kintap Dalam Angka 2026" tidak muncul). Domain uji 6305: Kecamatan Binuang.
def kartu_publikasi(a):
    t = c.get("/hasil?" + urlencode(a)).get_data(as_text=True)
    s = re.search(r'<h2 class="seksi">Publikasi</h2>(.*?)</section>', t, re.S)
    out = []
    # Kartu PUBLIKASI = tepat dua bentuk kelas: tanpa sampul, atau dengan sampul
    # ("ada-sampul", 19 Nov 2026). Kartu tabel/gambar/lampiran/bab tidak cocok.
    for k in re.findall(r'<article class="kartu kartu-pub(?: ada-sampul)?">(.*?)</article>', s.group(1) if s else "", re.S):
        j = re.sub("<[^>]+>", "", re.search(r'<h3 class="kartu-judul">(.*?)</h3>', k, re.S).group(1)).strip()
        m = re.search(r'label-kecamatan">(.*?)</span>', k)
        out.append([j, m.group(1) if m else None])
    return out
q5 = "Kecamatan Binuang Dalam Angka 2025"
print("V5", json.dumps({"dipilih": kartu_publikasi({"q": q5, "w": "6305", "kec": "1", "kc": "binuang"})[:2],
                        "tanpa_centang": kartu_publikasi({"q": q5, "w": "6305"})}))
'''


def bagian_v():
    """Tampilan kecamatan (18 Nov 2026): TANPA centang hasil identik.

    Pembanding yang bisa dibuat ulang kapan saja: salinan sementara database
    uji yang publikasi kecamatannya dihapus (<uji>_tanpakec_uji, dari dump
    awal). Halaman database uji, sesudah widget kecamatan (dropdown, kotak
    centang, kotak info) dibuang, harus byte-identik dengan halaman salinan
    itu, dan waktunya setara.

    /api/saran TIDAK dibandingkan byte demi byte: urutan seri edisi berjudul
    sama panjang ditentukan filesort MySQL dan berubah menurut rencana
    kueri (dicatat, menunggu keputusan pemilik project). Yang diuji: tanpa
    kec=1 tidak ada saran dari publikasi kecamatan.
    """
    print("\n=== V. TAMPILAN KECAMATAN: TANPA CENTANG IDENTIK ===", flush=True)
    kode, keluar, err = jalan_py(
        "from app import create_app\nfrom app.config import KonfigurasiUji\nfrom app.models import skema, Publikasi\n"
        "with create_app(KonfigurasiUji).app_context():\n"
        "    skema.pastikan_kolom()\n"
        "    print('V0', Publikasi.query.filter(Publikasi.kecamatan.isnot(None)).count())\n")
    m = re.search(r"^V0 (\d+)$", keluar, re.M)
    if not m:
        cek("V0 kolom publikasi.kecamatan terisi", False, err[-300:])
        return
    if int(m.group(1)) == 0:
        lewati("V tampilan kecamatan", "database uji tidak berisi publikasi Kecamatan Dalam Angka")
        return
    tanpa = f"{DB_UJI[:-len('_uji')]}_tanpakec_uji"
    if not nama_uji_sah(tanpa):
        raise SystemExit(f"GALAT: nama salinan sementara tidak sah: {tanpa}")
    sql(f"DROP DATABASE IF EXISTS `{tanpa}`")
    sql(f"CREATE DATABASE `{tanpa}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    try:
        with open(DUMP_UJI, "rb") as f:
            r = subprocess.run([MYSQL, *DASAR_MY, tanpa], env=ENV_MY, stdin=f, capture_output=True)
        if r.returncode:
            raise RuntimeError("memuat salinan tanpa kecamatan gagal: " + r.stderr.decode("utf-8", "replace")[:300])
        # Dump dibuat sebelum V0; kolom kecamatan diisi ulang dari judul (sama dengan sinkron_kecamatan).
        url_tanpa = URL_UJI.set(database=tanpa).render_as_string(hide_password=False)
        kode, keluar, err = jalan_py(
            "from app import create_app\nfrom app.config import KonfigurasiUji\nfrom app.models import skema\n"
            f"class KonfigurasiTanpaKec(KonfigurasiUji):\n    SQLALCHEMY_DATABASE_URI = {url_tanpa!r}\n"
            "with create_app(KonfigurasiTanpaKec).app_context():\n    skema.pastikan_kolom()\n")
        for q in ("DELETE e FROM entri_dokumen e JOIN publikasi p ON p.id = e.publikasi_id WHERE p.kecamatan IS NOT NULL",
                  "DELETE pk FROM publikasi_kategori pk JOIN publikasi p ON p.id = pk.publikasi_id WHERE p.kecamatan IS NOT NULL",
                  "DELETE FROM publikasi WHERE kecamatan IS NOT NULL"):
            sql(q, tanpa)
        n_sisa = sql("SELECT COUNT(*) FROM publikasi", tanpa)

        kode, keluar, err = jalan_py(f"URL_TANPA_KEC = {url_tanpa!r}\n" + KODE_BAGIAN_V,
                                     env_tambahan={"PYTHONHASHSEED": "0"})
        def baris(kunci):
            m = re.search(rf"^{kunci} (.*)$", keluar, re.M)
            return m.group(1) if m else None
        v1 = baris("V1")
        if v1 is None:
            cek("V1 potongan uji berjalan", False, err[-400:])
            return
        n_url, beda = v1.split(" ", 1)
        beda = json.loads(beda)
        cek(f"V1 tanpa centang: {n_url} halaman (beranda + 21 kueri) identik dengan salinan tanpa kecamatan "
            f"({n_sisa} publikasi), widget kecamatan dibuang", not beda, beda[:5] or f"{n_url}/{n_url}")
        n_kec, n_kec1 = map(int, baris("V2").split())
        cek("V2 /api/saran tanpa kec=1: 0 saran dari publikasi kecamatan (kec=1 boleh ada)", n_kec == 0,
            f"tanpa kec {n_kec}, kec=1 {n_kec1}")
        # 3 putaran bergantian; yang dibandingkan putaran TERCEPAT tiap database.
        # Gangguan dari proses lain di laptop hanya bisa memperlambat, dan sekali
        # terjadi di satu putaran (19 Nov 2026: 111 vs 84 ms di salinan TANPA
        # kecamatan) sehingga perbandingan per putaran gagal tanpa sebab kode.
        w = json.loads(baris("V3"))
        t_min, u_min = min(t for t, _ in w), min(u for _, u in w)
        cek("V3 waktu 12 kueri tanpa centang setara (putaran tercepat, selisih <= 10%)",
            abs(u_min - t_min) / t_min <= 0.10,
            f"tercepat: tanpa {t_min:.0f} ms / uji {u_min:.0f} ms; per putaran: "
            + "; ".join(f"{t:.0f}/{u:.0f}" for t, u in w))
        v4 = json.loads(baris("V4"))
        cek("V4 kotak info = jumlah di seksi bercentang; seksi tampil dengan kec=1",
            all(j == n and s for _, j, n, s in v4), v4)
        v5 = json.loads(baris("V5"))
        pertama = v5["dipilih"][0] if v5["dipilih"] else [None, None]
        cek("V5 seksi Publikasi: kecamatan dipilih -> publikasi kecamatan itu paling atas berlabel Kec.; "
            "tanpa centang -> tidak ada publikasi kecamatan",
            pertama == ["Kecamatan Binuang Dalam Angka 2025", "Kec. Binuang"]
            and all(k is None for _, k in v5["tanpa_centang"]), v5)
    finally:
        sql(f"DROP DATABASE IF EXISTS `{tanpa}`")


KODE_A4 = """
import json, re
from app import create_app
from app.config import KonfigurasiUji
app = create_app(KonfigurasiUji)
with app.test_client() as c:
    h = c.get('/hasil?q=tapin&w=6305').get_data(as_text=True)
    kartu = re.findall(r'<article class="kartu kartu-pub(?: ada-sampul)?">[\\s\\S]*?</article>', h)
    hasil = {}
    for k in kartu:
        pid = re.search(r'/pdf/(\\w+)', k).group(1)
        img = re.search(r'<img class="sampul" src="([^"]+)"\\s+width="(\\d+)" height="(\\d+)" alt="([^"]*)" loading="lazy"', k)
        rec = {'img': bool(img), 'kelas': 'ada-sampul' in k.split('>', 1)[0], 'div': k.count('kartu-badan')}
        if img:
            g = c.get(img.group(1).replace('&amp;', '&'))
            rec.update(ukuran=[int(img.group(2)), int(img.group(3))], alt=img.group(4)[:60], status=g.status_code,
                       jenis=g.mimetype, byte=len(g.data), luar='://' in img.group(1))
        hasil[pid] = rec
    e = c.get('/hasil?q=penduduk&w=6305').get_data(as_text=True)
    entri = re.findall(r'<article class="kartu kartu-(?:tabel|gambar|lampiran|isi)[^>]*>[\\s\\S]*?</article>', e)
    print('A4', json.dumps({'kartu': hasil, 'entri': len(entri), 'entri_sampul': sum('sampul' in k for k in entri),
                            'tanpa': c.get('/sampul/' + TANPA).status_code, 'jahat': c.get('/sampul/..%2Fx').status_code}))
"""


def bagian_a(kecil, per_id):
    """Sampul publikasi (19 Nov 2026): unduhan di perbarui.py, cadangan PDF,
    gagal, --lokal, dan tampilan kartu. Folder sampul salinan dikosongkan dulu,
    jadi tidak bergantung pada bagian lain."""
    print("\n=== A. SAMPUL PUBLIKASI ===", flush=True)
    from PIL import Image
    dir_s = ENV["DIR_SAMPUL"]
    shutil.rmtree(dir_s, ignore_errors=True)
    aktifkan(DOMAIN)
    KEADAAN["domain"].pop("6399", None)
    dom = sorted(x["pub_id"] for x in KEADAAN["domain"][DOMAIN])
    # publikasi kecil bertekst: unduh ulang + ekstraksi y di A2 cepat
    x_cad, y_gagal, z_lokal = kecil[4], kecil[3], kecil[5]

    def resmi(p):
        return f"{dir_s}/{p}.jpg"

    def cadangan(p):
        return f"{dir_s}/{p}.cadangan.jpg"

    # A1: x -> 400 (cadangan PDF); y -> 400 dan PDF-nya hilang + tak bisa diunduh (gagal)
    KEADAAN["mode_sampul"].update({x_cad: "400", y_gagal: "400"})
    pdf_y = path_uji(y_gagal)
    os.remove(pdf_y)                      # hardlink di salinan saja; berkas aslinya tidak disentuh
    KEADAAN["mode_pdf"][y_gagal] = "400"
    PERMINTAAN.clear()
    kode, keluar, dtk = jalan("perbarui.py")
    r = ringkasan()
    minta = [(t, q) for t, q in PERMINTAAN if q.startswith("/cover.php")]
    identik = all(os.path.exists(resmi(p)) and open(resmi(p), "rb").read() == SAMPUL_TIRUAN
                  for p in dom if p not in (x_cad, y_gagal))
    cek(f"A1 sampul ada: {len(dom) - 2} sampul resmi dari server tiruan, byte identik",
        identik and r["sampul"]["resmi"] == len(dom) - 2, f"exit {kode}, {dtk:.0f} d, {r['sampul']}")
    uk_cad = None
    if os.path.exists(cadangan(x_cad)):
        with Image.open(cadangan(x_cad)) as im:
            uk_cad = im.size
    cek("A1 cadangan PDF: unduhan 400 -> <id>.cadangan.jpg lebar 500 dari halaman 1, tanpa <id>.jpg",
        r["sampul"]["cadangan"] == 1 and uk_cad and uk_cad[0] == 500 and not os.path.exists(resmi(x_cad)), uk_cad)
    gagal_domain = [g["pub_id"] for d in r["domain"] for g in d["gagal"]]
    cek("A1 sampul gagal (unduhan 400, PDF tidak ada): tanpa berkas, dicatat; status domain hanya "
        "dipengaruhi unduhan PDF, bukan sampul",
        r["sampul"]["gagal"] == 1 and not os.path.exists(resmi(y_gagal)) and not os.path.exists(cadangan(y_gagal))
        and gagal_domain == [y_gagal], f"status {r['status']}, gagal {gagal_domain}")
    jeda = [b[0] - a[0] for a, b in zip(minta, minta[1:])]
    cek("A1 satu permintaan sampul per publikasi (400 tidak diulang), jeda >= ~1 detik",
        len(minta) == len(dom) and jeda and min(jeda) >= 0.95,
        f"{len(minta)} permintaan, jeda minimum {min(jeda):.2f} d" if jeda else "tidak ada permintaan")
    cek("A1 token sampul tidak tercetak di keluaran (pesan galat memuat f=***)",
        TOKEN_TIRUAN not in keluar and "f=***" in keluar)
    tampil("\n".join(b for b in keluar.splitlines() if "ampul" in b), 8)

    # A2: run berikutnya, server pulih -> hanya x dan y diminta; resmi menggantikan cadangan
    KEADAAN["mode_sampul"].clear()
    KEADAAN["mode_pdf"].pop(y_gagal, None)
    PERMINTAAN.clear()
    kode, keluar, _ = jalan("perbarui.py")
    r = ringkasan()
    minta = sorted(q for _, q in PERMINTAAN if q.startswith("/cover.php"))
    cek("A2 run berikutnya: hanya 2 yang belum punya sampul resmi diminta; cadangan diganti resmi",
        minta == sorted(url_tiruan("cover", p).split(str(PORT), 1)[1] for p in (x_cad, y_gagal))
        and os.path.exists(resmi(x_cad))
        and not os.path.exists(cadangan(x_cad)) and os.path.exists(resmi(y_gagal)) and os.path.exists(pdf_y),
        f"exit {kode}, permintaan {len(minta)}, {r['sampul']}")

    # A3: --lokal: tanpa permintaan; publikasi tanpa berkas mendapat cadangan PDF
    os.remove(resmi(z_lokal))
    PERMINTAAN.clear()
    kode, keluar, _ = jalan("perbarui.py", "--lokal")
    r = ringkasan()
    cek("A3 --lokal: 0 permintaan, publikasi tanpa berkas mendapat cadangan PDF",
        not PERMINTAAN and os.path.exists(cadangan(z_lokal)) and r["sampul"]["cadangan"] == 1,
        f"{len(PERMINTAAN)} permintaan, {r['sampul']}")

    # A4: tampilan. z: berkasnya dihapus -> kartu tanpa gambar, markup kartu lama.
    os.remove(cadangan(z_lokal))
    kode, keluar, err = jalan_py(f"TANPA = {z_lokal!r}\n" + KODE_A4)
    m = re.search(r"^A4 (.*)$", keluar, re.M)
    if not m:
        cek("A4 potongan tampilan berjalan", False, err[-300:])
        return
    a4 = json.loads(m.group(1))
    k = a4["kartu"]
    dengan = [p for p in k if p != z_lokal]
    cek(f"A4 sampul ada: {len(dengan)} kartu publikasi bergambar lewat route lokal, width/height 500x709, "
        "alt 'Sampul <judul>', lazy; gambar = berkas",
        dengan and all(k[p]["img"] and k[p]["kelas"] and k[p]["div"] == 1 and k[p]["ukuran"] == [500, 709]
                       and k[p]["alt"].startswith("Sampul ") and k[p]["status"] == 200
                       and k[p]["jenis"] == "image/jpeg" and k[p]["byte"] == len(SAMPUL_TIRUAN)
                       and not k[p]["luar"] for p in dengan),
        f"{len(dengan)} kartu")
    cek("A4 sampul tidak ada: kartu tanpa <img>, tanpa kelas/pembungkus sampul (markup lama); /sampul -> 404",
        z_lokal in k and k[z_lokal] == {"img": False, "kelas": False, "div": 0} and a4["tanpa"] == 404,
        k.get(z_lokal))
    cek("A4 kartu tabel/gambar/lampiran/bab tidak pernah bersampul; id tidak sah -> 404",
        a4["entri"] > 0 and a4["entri_sampul"] == 0 and a4["jahat"] == 404,
        f"{a4['entri']} kartu entri, id jahat {a4['jahat']}")
    cek("A5 sepanjang uji tidak ada URL luar di database uji (url_cover/url_pdf)", url_luar_di_db() == 0)

    # A6/A7 (24 Nov 2026): sampul ikut revisi. r_pid sudah punya sampul resmi
    # (A2). updt_date di API berubah -> PDF diunduh ulang -> sampulnya juga.
    r_pid = x_cad

    def part():
        return glob.glob(f"{dir_s}/*.part")

    tanpa = {p for p in dom if not os.path.exists(resmi(p))}     # z_lokal (A4), diminta seperti biasa
    mtime_lain = {p: os.stat(resmi(p)).st_mtime_ns for p in dom if p != r_pid and os.path.exists(resmi(p))}
    per_id[r_pid]["updt_date"] = "2026-12-18"
    KEADAAN["isi_sampul"][r_pid] = SAMPUL_REVISI
    PERMINTAAN.clear()
    kode, keluar, _ = jalan("perbarui.py")
    r = ringkasan()
    minta = {q for _, q in PERMINTAAN if q.startswith("/cover.php")}
    harap = {url_tiruan("cover", p).split(str(PORT), 1)[1] for p in tanpa | {r_pid}}
    cek("A6 revisi berhasil: PDF diunduh ulang, sampul resmi DITIMPA sampul baru (byte identik), tanpa sisa .part",
        open(resmi(r_pid), "rb").read() == SAMPUL_REVISI and r["sampul"]["diperbarui"] == 1
        and kolom_pub(r_pid, "updt_date_diproses") == "2026-12-18" and not part(),
        f"exit {kode}, {r['sampul']}")
    cek("A6 publikasi yang tidak direvisi tidak diunduh ulang sampulnya (berkasnya tidak tersentuh)",
        minta == harap and all(os.stat(resmi(p)).st_mtime_ns == m for p, m in mtime_lain.items()),
        f"{len(minta)} permintaan sampul, harap {len(harap)}")
    tampil("\n".join(b for b in keluar.splitlines() if "ampul" in b), 4)

    hasil_a7 = []
    for i, mode in enumerate(("400", "html")):
        per_id[r_pid]["updt_date"] = f"2026-12-1{6 - i}"
        KEADAAN["mode_sampul"][r_pid] = mode
        kode, keluar, _ = jalan("perbarui.py")
        r = ringkasan()
        hasil_a7.append((mode, open(resmi(r_pid), "rb").read() == SAMPUL_REVISI,
                         r["sampul"]["lama_dipertahankan"], not part(),
                         kolom_pub(r_pid, "updt_date_diproses") == per_id[r_pid]["updt_date"],
                         r["domain"][0]["status"]))
    cek("A7 revisi, unduhan sampul gagal (HTTP 400 / bukan gambar): sampul lama tetap dipakai (byte sama), "
        "dicatat lama_dipertahankan, PDF tetap diproses, status domain tidak gagal",
        all(ok and n == 1 and bersih and diproses and st == "sukses" for _, ok, n, bersih, diproses, st in hasil_a7),
        hasil_a7)
    KEADAAN["mode_sampul"].clear()
    KEADAAN["isi_sampul"].clear()


# ---------------------------------------------------------------- Q. pilihan penarikan
def siapkan_provinsi():
    """Wilayah kedua untuk bagian Q: provinsi 6300 dari database uji. PDF =
    hardlink (tidak diunduh, sidik sama), daftar tiruan dibangun dari baris DB."""
    for d in (f"{UJI}/data/publikasi_pdf/6300", f"{SUMBER}/6300"):
        os.makedirs(d, exist_ok=True)
    for p in glob.glob(f"{ASLI}/data/publikasi_pdf/6300/*.pdf"):
        n = os.path.basename(p)
        for tujuan in (f"{UJI}/data/publikasi_pdf/6300/{n}", f"{SUMBER}/6300/{n}"):
            if not os.path.exists(tujuan):
                os.link(p, tujuan)
    pubs = metadata_dari_db("6300")
    for p in pubs:
        KEADAAN["berkas_pdf"][p["pub_id"]] = f"{SUMBER}/6300/{p['pub_id']}.pdf"
    KEADAAN["domain"]["6300"] = pubs
    return {p["pub_id"]: p for p in pubs}


def jalan_catat(*arg, skrip=None):
    """perbarui.py (--db-uji) + permintaan ke tiruan selama run itu."""
    PERMINTAAN.clear()
    if skrip:
        r = subprocess.run([PY, "-u", skrip, "--db-uji", *arg], cwd=SP, env=ENV, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=3600)
        kode, keluar = r.returncode, r.stdout + r.stderr
    else:
        kode, keluar, _ = jalan("perbarui.py", *arg)
    return kode, keluar, list(PERMINTAAN)


def pdf_diminta(minta):
    return [q.split("/pdf/", 1)[1] for _, q in minta if q.startswith("/pdf/")]


def sampul_diminta(minta):
    return sorted(q.split(TOKEN_TIRUAN, 1)[1] for _, q in minta if q.startswith("/cover.php"))


def daftar_diminta(minta):
    return sorted({m.group(1) for _, q in minta for m in [re.search(r"/domain/(\d+)/page/", q)] if m})


def jeda_min(minta):
    t = [x for x, _ in minta]
    return min((b - a for a, b in zip(t, t[1:])), default=None)


def baku(keluar):
    """Keluaran untuk dibandingkan antar-versi: angka -> #, baris sampul,
    log, dan waktu dibuang."""
    buang = ("ampul", "Log run ini", "Selesai ", "Database tujuan")
    return [re.sub(r"\d+", "#", b) for b in keluar.splitlines() if b.strip() and not any(x in b for x in buang)]


KODE_Q_WEB = r'''
import json, re, time
from werkzeug.datastructures import MultiDict
from app import create_app
from app.config import KonfigurasiUji
from app.services import pembaruan, pilihan_pembaruan as P
app = create_app(KonfigurasiUji); c = app.test_client()
with c.session_transaction() as s: s['admin_masuk'] = True; s['admin_aktif'] = int(__import__('time').time())
hasil = {}
b = P.bawaan()
hasil['bawaan_tanpa_argumen'] = b.argumen() == [] and P.dari_formulir(MultiDict()) == b
hasil['perintah_bawaan'] = pembaruan.perintah(True, b.argumen())[2:]
salah = {
 'tanpa_wilayah': {'formulir': '1', 'jenis': ['kabkota'], 'dari': '2025', 'sampai': '2026'},
 'kabkota_tanpa_jenis': {'formulir': '1', 'wilayah': ['6305'], 'dari': '2025', 'sampai': '2026'},
 'wilayah_asing': {'formulir': '1', 'wilayah': ['6305', '9999'], 'jenis': ['kabkota'], 'dari': '2025', 'sampai': '2026'},
 'wilayah_tidak_aktif': {'formulir': '1', 'wilayah': ['6301'], 'jenis': ['kabkota'], 'dari': '2025', 'sampai': '2026'},
 'jenis_asing': {'formulir': '1', 'wilayah': ['6305'], 'jenis': ['semua'], 'dari': '2025', 'sampai': '2026'},
 'dari_lebih_besar': {'formulir': '1', 'wilayah': ['6305'], 'jenis': ['kabkota'], 'dari': '2026', 'sampai': '2025'},
 'tahun_belum_tiba': {'formulir': '1', 'wilayah': ['6305'], 'jenis': ['kabkota'], 'dari': '2025', 'sampai': str(P.tahun_ini() + 1)},
 'tahun_terlalu_awal': {'formulir': '1', 'wilayah': ['6305'], 'jenis': ['kabkota'], 'dari': str(P.tahun_min_pilihan() - 1), 'sampai': '2026'},
 'tahun_bukan_angka': {'formulir': '1', 'wilayah': ['6305'], 'jenis': ['kabkota'], 'dari': '2025;DROP', 'sampai': '2026'},
}
for nama, data in salah.items():
    r = c.post('/admin/perbarui/mulai', data=MultiDict([(k, x) for k, v in data.items() for x in (v if isinstance(v, list) else [v])]))
    h = r.get_data(as_text=True)
    g = re.search(r'<ul class="daftar-galat">(.*?)</ul>', h, re.S)
    hasil['tolak_' + nama] = [r.status_code, re.findall(r'<li>(.*?)</li>', g.group(1)) if g else None]
k = pembaruan.keadaan()
hasil['tidak_ada_proses'] = (not k['berjalan']) and k['mulai'] is None and not k['baris']
hasil['opsi_tahun'] = re.findall(r'<option value="(\d+)"', c.get('/admin/perbarui').get_data(as_text=True))
# satu kiriman SAH: cek dulu, Kab. Tapin, hanya Kecamatan Dalam Angka
r = c.post('/admin/perbarui/mulai', data=MultiDict([('formulir', '1'), ('wilayah', '6305'), ('jenis', 'kecamatan'),
                                                    ('dari', '2025'), ('sampai', '2026'), ('aksi', 'cek')]))
hasil['cek_status'] = r.status_code
t = time.time()
while pembaruan.keadaan()['berjalan'] and time.time() - t < 600:
    time.sleep(0.5)
k = pembaruan.keadaan()
h = c.get('/admin/perbarui').get_data(as_text=True)
hasil['cek_kode'] = k['kode_keluar']
hasil['cek_baris_pilihan'] = [b for b in k['baris'] if b.startswith('Pilihan:')]
hasil['cek_tampil'] = 'id="hasil-cek"' in h and 'Kab. Tapin' in h and 'Kecamatan Dalam Angka' in h
hasil['formulir_terisi'] = sorted(re.findall(r'name="(?:wilayah|jenis)"\s+value="(\w+)"\s*(?:data-kabkota="1")?\s*checked', h))
print('QWEB ' + json.dumps(hasil))
'''


def bagian_q(per_id):
    """Pilihan penarikan (24 Nov 2026): wilayah/jenis/tahun, validasi, --cek-dulu,
    tanpa pilihan = sama seperti kode sebelumnya. Wilayah aktif: 6305 (kab/kota
    + 24 Kecamatan Dalam Angka) dan 6300 (provinsi). Tidak ada akses ke BPS."""
    print("\n=== Q. PILIHAN PENARIKAN (wilayah / jenis / tahun / cek dulu) ===", flush=True)
    aktifkan(DOMAIN, "6300")
    KEADAAN["domain"].pop("6399", None)
    for k in ("gagal_domain", "gagal_halaman", "mode_pdf", "mode_sampul", "isi_sampul"):
        KEADAAN[k].clear()          # sisa gangguan bagian lain; Q0 membuktikan keadaan bersih
    prov = siapkan_provinsi()
    info = {}
    # Domain dari database, bukan ditebak: bagian lain (B, E) menambah publikasi
    # uji ke domain ini yang tidak ada di per_id. Publikasi tanpa PDF lokal
    # (dihapus bagian lain) tidak dipakai sebagai sampel.
    for baris in sql(f"SELECT id, domain, kecamatan IS NOT NULL, COALESCE(halaman_ocr,0), YEAR(tanggal_rilis) "
                     f"FROM publikasi WHERE domain IN ('{DOMAIN}','6300')", DB_UJI).splitlines():
        pid, dom, kec, ocr, th = baris.split("\t")
        pdf = f"{UJI}/data/publikasi_pdf/{dom}/{pid}.pdf"
        if not os.path.exists(pdf) or (dom == DOMAIN and pid not in per_id) or (dom == "6300" and pid not in prov):
            continue
        info[pid] = {"kec": kec == "1", "ocr": int(ocr), "tahun": int(th), "dom": dom,
                     "mb": os.path.getsize(pdf)}

    def kecil(syarat, n=1, kecuali=()):
        return sorted((p for p, v in info.items() if not v["ocr"] and p not in kecuali and syarat(v)),
                      key=lambda p: info[p]["mb"])[:n]

    K, X = kecil(lambda v: v["dom"] == DOMAIN and not v["kec"], 2)
    C, = kecil(lambda v: v["dom"] == DOMAIN and v["kec"])
    P26, = kecil(lambda v: v["dom"] == "6300" and v["tahun"] == 2026)
    P25, = kecil(lambda v: v["dom"] == "6300" and v["tahun"] == 2025)

    # Q0: penyelaras (sisa bagian lain + sampul 120 publikasi), lalu run tanpa kerja
    kode, keluar, _ = jalan_catat()
    kode, keluar, minta = jalan_catat()
    r = ringkasan()
    cek("Q0 tanpa pilihan, tanpa perubahan: 2 wilayah dibaca, 0 PDF, 0 sampul, status tidak_ada_baru; "
        "ringkasan mencatat pilihan bawaan",
        kode == 0 and daftar_diminta(minta) == ["6300", DOMAIN] and not pdf_diminta(minta)
        and not sampul_diminta(minta) and r["status"] == "tidak_ada_baru"
        and r.get("pilihan", {}).get("bawaan") is True and r["pilihan"]["wilayah"] == ["6300", DOMAIN],
        f"exit {kode}, {r['status']}, pilihan {r.get('pilihan')}")

    # Q1: tanpa pilihan = KODE SEBELUM FITUR FORMULIR, pada keadaan yang sama.
    # Commit tetap, bukan HEAD: sejak fitur di-commit (abeab3b), HEAD sudah
    # memuat --cek-dulu, dan Q1 jadi membandingkan kode baru dengan dirinya
    # sendiri (24 Nov 2026; penjaga lama_asli menangkapnya).
    lama = f"{SP}/uji_lama"
    sambungan = f"{lama}/data"
    try:
        os.makedirs(lama, exist_ok=True)
        berkas = subprocess.run(["git", "-C", ASLI, "ls-tree", "-r", "--name-only", KODE_SEBELUM_FORMULIR,
                                 "app", "scripts"], capture_output=True, text=True, check=True).stdout.split()
        for f in berkas:
            os.makedirs(os.path.dirname(f"{lama}/{f}"), exist_ok=True)
            open(f"{lama}/{f}", "wb").write(subprocess.run(
                ["git", "-C", ASLI, "show", f"{KODE_SEBELUM_FORMULIR}:{f}"], capture_output=True, check=True).stdout)
        subprocess.run(["cmd", "/c", "mklink", "/J", os.path.normpath(sambungan), os.path.normpath(f"{UJI}/data")],
                       capture_output=True, check=True)
        skrip_lama = f"{lama}/scripts/perbarui.py"
        lama_asli = "--cek-dulu" not in open(skrip_lama, encoding="utf-8").read()

        N = "qqqqrrrrsssstttt6300baru"
        nb = copy.deepcopy(KEADAAN["domain"]["6300"][0])
        nb.update(pub_id=N, title="Publikasi Baru Uji Pilihan 2026", abstract="abstrak uji pilihan",
                  rl_date="2026-11-15", updt_date="2026-11-15", pdf=url_tiruan("pdf", N), cover=url_tiruan("cover", N))
        KEADAAN["berkas_pdf"][N] = f"{SUMBER}/{X}.pdf"
        KEADAAN["domain"]["6300"].insert(0, nb)
        x_api, x_proses = kolom_pub(X, "updt_date_api"), kolom_pub(X, "updt_date_diproses")
        per_id[X]["updt_date"] = "2026-12-15"

        kode_l, keluar_l, minta_l = jalan_catat(skrip=skrip_lama)
        r_l, s_l = ringkasan(), potret()
        # kembalikan keadaan: N belum ada, X belum diproses (sidik dibiarkan = berkas di disk)
        for q in (f"DELETE FROM entri_dokumen WHERE publikasi_id='{N}'",
                  f"DELETE FROM publikasi_kategori WHERE publikasi_id='{N}'",
                  f"DELETE FROM publikasi WHERE id='{N}'",
                  f"UPDATE publikasi SET updt_date_api='{x_api}', updt_date_diproses='{x_proses}' WHERE id='{X}'"):
            sql(q, DB_UJI)
        for f in (f"{UJI}/data/publikasi_pdf/6300/{N}.pdf", f"{ENV['DIR_SAMPUL']}/{N}.jpg",
                  f"{ENV['DIR_SAMPUL']}/{N}.cadangan.jpg"):
            if os.path.exists(f):
                os.remove(f)
        kode_b, keluar_b, minta_b = jalan_catat()
        r_b, s_b = ringkasan(), potret()
    finally:
        if os.path.isdir(sambungan):
            os.rmdir(sambungan)          # hanya sambungannya; isi data/ salinan tidak disentuh
        shutil.rmtree(lama, ignore_errors=True)

    def inti(r):
        return {"status": r["status"], "diproses": r["diproses"], "diunduh": r["diunduh"],
                "baru": sorted(p["pub_id"] for p in r["publikasi_baru"]),
                "domain": [(d["kode"], d["status"], d["diunduh"], d["diproses"], len(d["gagal"]),
                            len(d["tidak_di_daftar"]), len(d["menunggu_unduhan"])) for d in r["domain"]]}

    bukan_sampul = lambda m: [q for _, q in m if not q.startswith("/cover.php")]  # noqa: E731
    cek(f"Q1 kode lama benar-benar versi {KODE_SEBELUM_FORMULIR[:7]} (tanpa --cek-dulu) dan bekerja: "
        "1 baru + 1 direvisi",
        lama_asli and kode_l == 0 and inti(r_l)["diproses"] == 2 and inti(r_l)["baru"] == [N],
        f"exit {kode_l}, {inti(r_l)}")
    cek("Q1 tanpa pilihan = kode sebelumnya: permintaan daftar+PDF sama PERSIS (urutan), database sama per kunci, "
        "ringkasan inti sama",
        bukan_sampul(minta_l) == bukan_sampul(minta_b) and not beda_potret(s_l, s_b) and inti(r_l) == inti(r_b),
        f"permintaan {len(bukan_sampul(minta_l))}/{len(bukan_sampul(minta_b))}, beda DB {beda_potret(s_l, s_b)[:3]}")
    beda_baris = [b for b in difflib_unified(baku(keluar_l), baku(keluar_b))]
    cek("Q1 keluaran layar sama (angka/waktu dan baris sampul diabaikan)", not beda_baris, beda_baris[:6])
    cek("Q1 satu-satunya beda yang DISENGAJA: sampul publikasi direvisi ikut diunduh ulang (keputusan 24 Nov)",
        set(sampul_diminta(minta_b)) == set(sampul_diminta(minta_l)) | {X} and X not in sampul_diminta(minta_l)
        and set(r_b) - set(r_l) == {"pilihan"},
        f"lama {sampul_diminta(minta_l)}, baru {sampul_diminta(minta_b)}, kunci baru {sorted(set(r_b) - set(r_l))}")

    # Q2: kombinasi wilayah / jenis / tahun
    BARU = "2026-12-29"
    for p in (K, C):
        per_id[p]["updt_date"] = BARU
    for p in (P26, P25):
        prov[p]["updt_date"] = BARU
    api0 = {p: kolom_pub(p, "updt_date_api") for p in (K, C, P26, P25)}

    def diproses(p):
        return kolom_pub(p, "updt_date_diproses") == BARU

    def tak_tersentuh(*ps):
        return all(kolom_pub(p, "updt_date_api") == api0[p] and not diproses(p) for p in ps)

    jeda = []
    kode, keluar, minta = jalan_catat("--wilayah", DOMAIN, "--jenis", "kecamatan")
    r = ringkasan()
    jeda.append(jeda_min(minta))
    cek("Q2a --wilayah 6305 --jenis kecamatan: hanya Kecamatan Dalam Angka yang direvisi diproses; publikasi "
        "kab/kota dan provinsi tidak disentuh (metadata pun tidak); daftar 6300 tidak diminta",
        kode == 0 and diproses(C) and tak_tersentuh(K, P26, P25) and pdf_diminta(minta) == [C]
        and daftar_diminta(minta) == [DOMAIN] and [d["kode"] for d in r["domain"]] == [DOMAIN],
        f"exit {kode}, pdf {pdf_diminta(minta)}, daftar {daftar_diminta(minta)}")
    cek("Q2a publikasi di luar pilihan jenis tidak dilaporkan 'tidak lagi di daftar'; ringkasan mencatat pilihan",
        r["domain"][0]["tidak_di_daftar"] == [] and r["pilihan"]["jenis"] == ["kecamatan"]
        and r["pilihan"]["wilayah"] == [DOMAIN] and r["pilihan"]["bawaan"] is False and "Pilihan: " in keluar,
        r.get("pilihan"))
    kode, keluar, minta = jalan_catat("--wilayah", DOMAIN, "--jenis", "kabkota")
    r = ringkasan()
    jeda.append(jeda_min(minta))
    cek("Q2b --jenis kabkota: hanya publikasi kab/kota yang direvisi; tidak_di_daftar kosong",
        kode == 0 and diproses(K) and pdf_diminta(minta) == [K] and tak_tersentuh(P26, P25)
        and r["domain"][0]["tidak_di_daftar"] == [], f"exit {kode}, pdf {pdf_diminta(minta)}")
    kode, keluar, minta = jalan_catat("--wilayah", "6300", "--tahun-min", "2025", "--tahun-maks", "2025")
    r = ringkasan()
    jeda.append(jeda_min(minta))
    cek("Q2c --wilayah 6300 --tahun-min 2025 --tahun-maks 2025: hanya rilis 2025 diproses, rilis 2026 tidak "
        "disentuh; tidak_di_daftar kosong",
        kode == 0 and diproses(P25) and tak_tersentuh(P26) and pdf_diminta(minta) == [P25]
        and daftar_diminta(minta) == ["6300"] and r["domain"][0]["tidak_di_daftar"] == [],
        f"exit {kode}, pdf {pdf_diminta(minta)}, tidak_di_daftar {len(r['domain'][0]['tidak_di_daftar'])}")
    s0 = potret("6300")
    kode, keluar, minta = jalan_catat("--wilayah", "6300", "--tahun-min", "2024", "--tahun-maks", "2024")
    r = ringkasan()
    cek("Q2d tahun tanpa publikasi (2024): 0 lolos BUKAN kegagalan selama database juga tidak punya publikasi "
        "2024; data provinsi tidak berubah",
        kode == 0 and r["status"] == "tidak_ada_baru" and not pdf_diminta(minta) and potret("6300") == s0
        and tak_tersentuh(P26), f"exit {kode}, {r['status']}, {r['domain'][0].get('pesan')}")
    kode, keluar, minta = jalan_catat()
    jeda.append(jeda_min(minta))
    cek("Q2e lalu tanpa pilihan: sisa revisi (provinsi 2026) diproses", kode == 0 and diproses(P26)
        and pdf_diminta(minta) == [P26], f"exit {kode}, pdf {pdf_diminta(minta)}")
    cek("Q2 jeda antar-permintaan ke WebAPI/PDF/sampul >= ~1 detik di semua run berpilihan",
        all(j is not None and j >= 0.95 for j in jeda), [round(j, 2) for j in jeda if j is not None])

    n_kec = sum(1 for v in info.values() if v["dom"] == DOMAIN and v["kec"])
    ekstrak0 = {p: kolom_pub(p, "diekstrak_pada") for p in (K, P26)}
    kode, keluar, minta = jalan_catat("--lokal", "--paksa", "--wilayah", DOMAIN, "--jenis", "kecamatan")
    r = ringkasan()
    cek(f"Q2f --lokal --paksa --wilayah 6305 --jenis kecamatan: tepat {n_kec} publikasi kecamatan dibaca ulang, "
        "kab/kota dan provinsi tidak; 0 permintaan jaringan",
        kode == 0 and r["diproses"] == n_kec and not minta
        and all(kolom_pub(p, "diekstrak_pada") == v for p, v in ekstrak0.items()),
        f"exit {kode}, diproses {r['diproses']}, permintaan {len(minta)}")

    # Q3: pilihan ditolak di baris perintah: exit 1, tanpa jaringan, database dan ringkasan tidak berubah
    cs0 = checksum_db(DB_UJI)
    rk0 = open(f"{UJI}/data/pembaruan_terakhir-uji.json", "rb").read()
    tolak = []
    for arg in (["--wilayah", "9999"], ["--wilayah", "6301"], ["--jenis", "semua"], ["--tahun-min", "2019"],
                ["--tahun-maks", str(time.localtime().tm_year + 1)], ["--tahun-min", "2026", "--tahun-maks", "2025"],
                ["--tahun-maks", "abc"], ["--hanya-periksa", "--wilayah", DOMAIN], ["--cek-dulu", "--paksa"],
                ["--cek-dulu", "--lokal"], ["--kecamatan", "--jenis", "kecamatan"]):
        kode, keluar, minta = jalan_catat(*arg)
        tolak.append((" ".join(arg), kode, "DITOLAK" in keluar, len(minta)))
    cek("Q3 pilihan tidak sah di perbarui.py: semua exit 1 + DITOLAK, 0 permintaan, database dan ringkasan "
        "tidak berubah",
        all(k == 1 and d and m == 0 for _, k, d, m in tolak) and checksum_db(DB_UJI) == cs0
        and open(f"{UJI}/data/pembaruan_terakhir-uji.json", "rb").read() == rk0,
        [t for t in tolak if not (t[1] == 1 and t[2] and t[3] == 0)] or f"{len(tolak)} ditolak")

    # Q4: formulir web (test_client, KonfigurasiUji): validasi server + satu cek sungguhan
    PERMINTAAN.clear()
    kode, keluar, err = jalan_py(KODE_Q_WEB, timeout=900)
    m = re.search(r"^QWEB (.*)$", keluar, re.M)
    if not m:
        cek("Q4 potongan formulir web berjalan", False, err[-400:])
    else:
        w = json.loads(m.group(1))
        tolak_web = {k[6:]: v for k, v in w.items() if k.startswith("tolak_")}
        cek(f"Q4 formulir: {len(tolak_web)} kiriman tidak sah ditolak server (HTTP 400 + pesan), tidak ada proses dimulai",
            all(v[0] == 400 and v[1] for v in tolak_web.values()) and w["tidak_ada_proses"],
            {k: v for k, v in tolak_web.items() if not (v[0] == 400 and v[1])} or len(tolak_web))
        cek("Q4 bawaan formulir = tanpa argumen (perintah sama dengan tombol lama); POST tanpa formulir = bawaan",
            w["bawaan_tanpa_argumen"] and len(w["perintah_bawaan"]) == 2
            and w["perintah_bawaan"][0].endswith("perbarui.py") and w["perintah_bawaan"][1] == "--db-uji",
            w["perintah_bawaan"])
        th = list(range(2020, time.localtime().tm_year + 1))
        cek("Q4 pilihan tahun = tahun_min_pilihan .. tahun berjalan (tahun yang belum tiba tidak ada)",
            w["opsi_tahun"] == [str(x) for x in th] * 2, w["opsi_tahun"][:3] + ["..."] + w["opsi_tahun"][-2:])
        cek("Q4 'Cek dulu' dari formulir: jalur perbarui.py yang sama, pilihan sampai ke proses, hasil tampil, "
            "formulir terisi pilihan yang sama",
            w["cek_status"] == 302 and w["cek_kode"] == 0 and w["cek_tampil"]
            and w["cek_baris_pilihan"] == ["Pilihan: wilayah: Kab. Tapin; jenis (kab/kota): Kecamatan Dalam Angka; "
                                           "tahun rilis 2025-2026"]
            and w["formulir_terisi"] == [DOMAIN, "kecamatan"], {k: w[k] for k in ("cek_kode", "cek_baris_pilihan",
                                                                                    "formulir_terisi")})
        cek("Q4 cek dari formulir: hanya daftar 6305 diminta, 0 PDF/sampul; database dan ringkasan pembaruan "
            "tidak berubah",
            daftar_diminta(PERMINTAAN) == [DOMAIN] and not pdf_diminta(PERMINTAAN) and not sampul_diminta(PERMINTAAN)
            and checksum_db(DB_UJI) == cs0 and open(f"{UJI}/data/pembaruan_terakhir-uji.json", "rb").read() == rk0)

    # Q5: --cek-dulu menghitung dengan benar, tanpa mengunduh dan tanpa menulis
    N2 = "qqqqrrrrsssstttt6305baru"
    nb = copy.deepcopy(per_id[K])
    nb.update(pub_id=N2, title="Publikasi Kabupaten Baru Uji Cek", rl_date="2026-11-20", updt_date="2026-11-20",
              size="3.5 MB", pdf=url_tiruan("pdf", N2), cover=url_tiruan("cover", N2))
    KEADAAN["domain"][DOMAIN].insert(0, nb)
    KEADAAN["berkas_pdf"][N2] = f"{SUMBER}/{K}.pdf"
    per_id[C]["updt_date"] = "2026-12-30"                 # kecamatan direvisi
    hilang = path_uji(X)
    os.replace(hilang, hilang + ".x")                     # PDF lokal hilang: baca ulang + unduh
    try:
        kode, keluar, minta = jalan_catat("--wilayah", DOMAIN, "--cek-dulu")
        c1 = json.load(open(f"{UJI}/data/cek_pembaruan-uji.json", encoding="utf-8"))
        kode2, keluar2, minta2 = jalan_catat("--wilayah", DOMAIN, "--jenis", "kabkota", "--cek-dulu")
        c2 = json.load(open(f"{UJI}/data/cek_pembaruan-uji.json", encoding="utf-8"))
    finally:
        os.replace(hilang + ".x", hilang)
    d1 = c1["domain"][0]
    n_dom = len(KEADAAN["domain"][DOMAIN])
    cek("Q5 --cek-dulu: baru 1, direvisi 1, baca ulang 1, sisanya tidak berubah; unduh 3 PDF",
        kode == 0 and (d1["baru"], d1["direvisi"], d1["baca_ulang"], d1["tetap"], d1["unduh"]) == (1, 1, 1, n_dom - 3, 3)
        and d1["di_daftar"] == n_dom and c1["perkiraan"]["publikasi_diproses"] == 3,
        f"exit {kode}, {({k: d1[k] for k in ('di_daftar', 'baru', 'direvisi', 'baca_ulang', 'tetap', 'unduh', 'mb_unduh')})}")
    cek("Q5 --cek-dulu --jenis kabkota: kecamatan yang direvisi tidak dihitung",
        kode2 == 0 and (c2["domain"][0]["baru"], c2["domain"][0]["direvisi"]) == (1, 0)
        and c2["pilihan"]["jenis"] == ["kabkota"], c2["domain"][0].get("direvisi"))
    cek("Q5 --cek-dulu tidak mengunduh (0 PDF, 0 sampul, berkas baru tidak ada), database dan ringkasan pembaruan "
        "tidak berubah",
        not pdf_diminta(minta + minta2) and not sampul_diminta(minta + minta2)
        and not os.path.exists(path_uji(N2)) and checksum_db(DB_UJI) == cs0
        and open(f"{UJI}/data/pembaruan_terakhir-uji.json", "rb").read() == rk0
        and "Tidak ada PDF yang diunduh" in keluar, f"{len(minta) + len(minta2)} permintaan")
    kode_p, keluar_p, err_p = jalan_py(
        "import sys; sys.path.insert(0, sys.path[0] + '/scripts')\n"
        "import perbarui\nfrom app.services import pilihan_pembaruan as P\n"
        "perbarui.PILIHAN = P.periksa(dari=2020)\n"
        "t = dict(baru=60, direvisi=0, baca_ulang=0, unduh=60, mb_unduh=2000.0, mb_baca=2000.0)\n"
        "b = perbarui.perkiraan_cek(t, 10)\n"
        "perbarui.PILIHAN = P.bawaan()\n"
        "k = perbarui.perkiraan_cek(dict(baru=2, direvisi=1, baca_ulang=0, unduh=3, mb_unduh=20.0, mb_baca=20.0), 10)\n"
        "print('PK', b['besar'], len(b['peringatan']), len(b['catatan']), k['besar'], len(k['catatan']))\n")
    # 25 Nov 2026: ambang dari wilayah.json (> 30 menit / > 1 GB); jumlah
    # publikasi tidak lagi jadi alasan, jadi 60 publikasi 2000 MB = 2 alasan.
    cek("Q5 peringatan penarikan besar (> 30 menit / > 1 GB, dari wilayah.json) + catatan PDF lama (< 2025); "
        "kecil tanpa peringatan",
        "PK True 2 2 False 1" in keluar_p, (keluar_p + err_p)[-200:])
    KEADAAN["domain"][DOMAIN].remove(nb)
    per_id[C]["updt_date"] = BARU

    # Q6: kunci satu pembaruan juga untuk pilihan dan cek
    open(f"{UJI}/data/pembaruan.lock", "w").write(str(os.getpid()))      # PID hidup = proses uji ini
    try:
        hasil = [jalan_catat(*a) for a in (["--wilayah", DOMAIN, "--cek-dulu"], ["--wilayah", DOMAIN, "--jenis", "kabkota"])]
    finally:
        os.remove(f"{UJI}/data/pembaruan.lock")
    cek("Q6 saat terkunci: cek dan pembaruan berpilihan berhenti (exit 2), 0 permintaan",
        all(k == 2 and "SUDAH BERJALAN" in o and not m for k, o, m in hasil), [h[0] for h in hasil])

    # Q7: perbarui-data.bat sungguhan dengan pilihan (koma lewat %* utuh)
    siapkan_bat()
    # Dua kode = semua wilayah aktif salinan; kalau koma terpotong di %*, kodenya
    # tidak dikenal dan DITOLAK.
    k = bat("--wilayah", f"{DOMAIN},6300", "--jenis", "kecamatan", "--cek-dulu")
    cek("Q7 .bat --wilayah 6305,6300 --jenis kecamatan --cek-dulu: pilihan sampai utuh, penutup 'CEK SELESAI'",
        "Pilihan: wilayah: semua wilayah aktif; jenis (kab/kota): Kecamatan Dalam Angka" in k
        and "HASIL CEK" in k and "CEK SELESAI" in k
        and "PEMBARUAN SELESAI" not in k, [b.strip() for b in k.splitlines() if "Pilihan" in b or "SELESAI" in b][:3])
    k = bat("--wilayah", "9999")
    cek("Q7 .bat pilihan tidak sah: DITOLAK -> PEMBARUAN GAGAL (bukan 'pembaruan lain sedang berjalan')",
        "DITOLAK" in k and "PEMBARUAN GAGAL" in k and "TIDAK DIJALANKAN" not in k)

    # selesai: kembali ke satu wilayah uji
    for p in (K, C):
        per_id[p]["updt_date"] = BARU
    KEADAAN["domain"].pop("6300", None)
    aktifkan(DOMAIN)


def difflib_unified(a, b):
    import difflib
    return [x for x in difflib.unified_diff(a, b, lineterm="", n=0) if x[:1] in "+-" and x[:3] not in ("+++", "---")]


KODE_J = r'''
import copy, json, os, re, sys
from datetime import datetime, timedelta, timezone
from werkzeug.datastructures import MultiDict
from app import create_app
from app.config import Config, KonfigurasiUji
from app.services import pembaruan, ringkasan_pembaruan as R, pilihan_pembaruan as P
hasil = {}
F_RINGKASAN = r'{UJI}/data/pembaruan_terakhir-uji.json'
RINGKASAN_ASLI = open(F_RINGKASAN, 'rb').read() if os.path.exists(F_RINGKASAN) else None

# J1: satuan
hasil['ukuran'] = [R.format_ukuran(x) for x in (None, 0, 0.04, 0.05, 211.53, 1023.94, 1024, 1250, 412345)]
hasil['durasi'] = [R.format_durasi(x) for x in (0, 44.6, 59.4, 59.6, 89, 1790, 3569, 3600, 9000)]
hasil['durasi_kira'] = R.format_durasi(514, kira=True)

# J2: status dari aturan murni (ambang dari wilayah.json salinan)
A = R.ambang()
hasil['ambang'] = A
def cek(wil, baru=1, direvisi=0, baca=0, tetap=10, mb=10.0, detik=300, gagal=()):
    dom = [dict(kode=str(6300 + i), wilayah=w, status='berhasil', baru=baru, direvisi=direvisi,
                baca_ulang=baca, tetap=tetap, unduh=baru + direvisi, mb_unduh=mb / max(len(wil), 1))
           for i, w in enumerate(wil, 1)]
    dom += [dict(kode='6399', wilayah=g, status='gagal', pesan='putus', baru=0, direvisi=0, baca_ulang=0)
            for g in gagal]
    n = len(wil)
    return {'status': 'berhasil', 'domain': dom, 'pilihan': P.bawaan().ke_dict(), 'durasi_detik': 3,
            'total': dict(baru=baru * n, direvisi=direvisi * n, baca_ulang=baca * n, tetap=tetap * n,
                          unduh=(baru + direvisi) * n, mb_unduh=mb, mb_baca=mb, di_daftar=0, tabrakan=0),
            'perkiraan': {'publikasi_diproses': (baru + direvisi + baca) * n,
                          'detik': dict(total=detik, daftar=1, unduh=1, baca_pdf=1, sampul=1, unduh_lambat=1),
                          'catatan': [], 'laju_unduh_mb_per_detik': 5.0}}
def st(c, sisa):
    k = R.ringkas_cek(c, sisa, A, 'C:')
    return [k['status'], k['boleh_mulai']]
GB = R.MB_PER_GB
hasil['status'] = {
 'terbaru': st(cek(['Kab. Tapin'], baru=0, mb=0, detik=20), 1.0),          # 0 diproses: abu-abu walau disk kecil
 'siap': st(cek(['Kab. Tapin']), 10 ** 6),
 'besar_menit_pas': st(cek(['Kab. Tapin'], detik=30 * 60), 10 ** 6),        # TEPAT 30 menit: belum besar
 'besar_menit_lebih': st(cek(['Kab. Tapin'], detik=30 * 60 + 1), 10 ** 6),
 'besar_gb_pas': st(cek(['Kab. Tapin'], mb=1.0 * GB), 10 ** 6),
 'besar_gb_lebih': st(cek(['Kab. Tapin'], mb=1.0 * GB + 0.1), 10 ** 6),
 'disk_pas': st(cek(['Kab. Tapin'], mb=100.0), 120.0),                      # 100 + 20% = 120: cukup
 'disk_kurang': st(cek(['Kab. Tapin'], mb=100.0), 119.9),
 'disk_dulu_dari_besar': st(cek(['Kab. Tapin'], mb=5000.0, detik=9000), 100.0),
 'disk_tak_diketahui': st(cek(['Kab. Tapin'], mb=5000.0, detik=9000), None),
}
kal = lambda c, s=10 ** 6: R.ringkas_cek(c, s, A)['kalimat']
hasil['kalimat'] = {
 'satu': kal(cek(['Kota Banjarmasin'], tetap=620)),
 'tiga': kal(cek(['Kab. Tapin', 'Kab. Banjar', 'Kota Banjarbaru'], tetap=1)),
 'lima': kal(cek(['A1', 'A2', 'A3', 'A4', 'A5'], tetap=1)),
 'revisi': kal(cek(['Kab. Tapin'], baru=0, direvisi=2, tetap=3)),
 'gagal': kal(cek(['Kab. Tapin'], tetap=3, gagal=['Kab. Balangan'])),
 'disk': kal(cek(['Kab. Tapin'], mb=100.0), 50.0),
 'terbaru': kal(cek(['Kab. Tapin'], baru=0, mb=0, tetap=40)),
}
# ambang benar-benar dibaca dari wilayah.json, tidak dari kode
F = str(Config.FILE_WILAYAH)
asli = open(F, 'rb').read()
w = json.loads(asli)
w['ambang_penarikan']['besar_menit'] = 4
open(F, 'w', encoding='utf-8').write(json.dumps(w))
hasil['ambang_diubah'] = R.ringkas_cek(cek(['Kab. Tapin'], detik=300), 10 ** 6, R.ambang())['status']
del w['ambang_penarikan']
open(F, 'w', encoding='utf-8').write(json.dumps(w))
try:
    R.ambang(); hasil['ambang_hilang'] = 'TIDAK DITOLAK'
except SystemExit as e:
    hasil['ambang_hilang'] = str(e)
open(F, 'wb').write(asli)

# J3-J5: halaman /admin/perbarui dengan keadaan cek buatan (tanpa proses)
selesai = datetime.now(timezone.utc)
keadaan = {'berjalan': False, 'selesai': selesai, 'jenis': 'cek', 'mulai': selesai - timedelta(minutes=1),
           'baris': ['x'], 'kode_keluar': 0, 'pilihan': None}
pembaruan.keadaan = lambda: keadaan
SISA = {'mb': 10 ** 6}
R.sisa_ruang_mb = lambda path=None: SISA['mb']
dimulai = []
pembaruan.mulai = lambda uji=False, pilihan=None, cek=False: dimulai.append((cek, pilihan.argumen())) or True
app = create_app(KonfigurasiUji); c = app.test_client()
with c.session_transaction() as s: s['admin_masuk'] = True; s['admin_aktif'] = int(__import__('time').time())
def halaman(data, sisa):
    SISA['mb'] = sisa
    data = copy.deepcopy(data); data['selesai_pada'] = selesai
    pembaruan.hasil_cek = lambda uji=False: data
    h = c.get('/admin/perbarui').get_data(as_text=True)
    i = h.find('id="ringkasan-cek"')
    bag = h[i:] if i >= 0 else ''
    m = re.search(r'data-status="(\w+)"', bag)
    tombol = re.search(r'<button type="submit" name="aksi" value="mulai"[^>]*>', h).group(0)
    det = re.search(r'<details class="lipat rincian-wilayah">\s*<summary>Lihat rincian per wilayah</summary>(.*?)</details>', bag, re.S)
    return {'status': m.group(1) if m else None,
            'judul': re.search(r'class="status-ringkasan"[^>]*><span[^>]*></span>([^<]*)', bag).group(1) if m else None,
            'kotak': len(re.findall(r'<div class="kotak-angka">', bag[:bag.find('</dl>')])),
            'nilai': re.findall(r'<span class="nilai-angka">([^<]*)', bag[:bag.find('</dl>')]),
            'tabel_dilipat': bool(det and 'tabel-cek' in det.group(1)),
            'mulai_nonaktif': ' disabled' in tombol,
            'alasan': 'id="alasan-mulai"' in h and 'aria-describedby="alasan-mulai"' in tombol}
data_siap = cek(['Kab. Tapin'], mb=211.5, detik=514)
hasil['halaman'] = {
 'siap': halaman(data_siap, 10 ** 6),
 'besar': halaman(cek(['Kab. Tapin'], mb=3500.0, detik=7300), 10 ** 6),
 'disk': halaman(data_siap, 100.0),
 'terbaru': halaman(cek(['Kab. Tapin'], baru=0, mb=0, detik=20), 100.0),
}
# J4: POST Mulai pembaruan, pilihan sama dengan cek yang kekurangan ruang disk
SISA['mb'] = 100.0
d = copy.deepcopy(data_siap); d['selesai_pada'] = selesai
pembaruan.hasil_cek = lambda uji=False: d
def kirim(aksi='mulai', dari=None):
    b = P.bawaan()
    data = [('formulir', '1'), ('dari', str(dari or b.dari)), ('sampai', str(b.sampai)), ('aksi', aksi)]
    data += [('wilayah', x) for x in b.wilayah] + [('jenis', j) for j in b.jenis]
    r = c.post('/admin/perbarui/mulai', data=MultiDict(data))
    return [r.status_code, 'Mulai pembaruan dinonaktifkan' in r.get_data(as_text=True), len(dimulai)]
hasil['post'] = {'sama_disk_kurang': kirim(), 'cek_tetap_boleh': kirim('cek')}
SISA['mb'] = 10 ** 6
hasil['post']['sama_disk_cukup'] = kirim()
SISA['mb'] = 100.0
hasil['post']['pilihan_lain'] = kirim(dari=P.bawaan().dari - 1)      # tahun lain = bukan pilihan cek itu
hasil['dimulai'] = dimulai

# J5: ringkasan SESUDAH pembaruan, gaya yang sama
F = F_RINGKASAN
keadaan.update(jenis='pembaruan', selesai=None)
pembaruan.hasil_cek = lambda uji=False: None
dasar = {'selesai_pada': '2026-11-25T01:00:00+00:00', 'jaringan': False, 'jumlah_publikasi': 80,
         'entri_sebelum': 10, 'entri_sesudah': 15, 'durasi_detik': 765, 'diproses': 2, 'diunduh': 2,
         'unduhan': {'berkas': 2, 'mb': 1300.0},
         'publikasi_baru': [{'pub_id': 'x', 'judul': 'Judul Publikasi Baru Uji', 'entri': 5, 'wilayah': 'Kab. Tapin'}],
         'domain': [{'kode': '6305', 'wilayah': 'Kab. Tapin', 'status': 'sukses', 'pesan': None, 'jumlah_publikasi': 17,
                     'diunduh': 2, 'diproses': 2, 'gagal': [], 'tabrakan': [], 'tidak_di_daftar': [],
                     'menunggu_unduhan': [], 'perlu_diperiksa': []}]}
sesudah = {}
for nama, ubah in (('sukses', {'status': 'sukses'}), ('tidak_ada_baru', {'status': 'tidak_ada_baru', 'publikasi_baru': []}),
                   ('sebagian', {'status': 'sebagian'}), ('gagal', {'status': 'gagal', 'jaringan': True})):
    isi = copy.deepcopy(dasar); isi.update(ubah)
    if nama == 'sebagian':
        isi['domain'][0]['gagal'] = [{'judul': 'Judul Gagal Uji', 'tahap': 'unduh', 'pesan': 'HTTP 500'}]
    json.dump(isi, open(F, 'w', encoding='utf-8'))
    h = c.get('/admin/perbarui').get_data(as_text=True)
    i = h.find('id="ringkasan-pembaruan"'); bag = h[i:]
    m = re.search(r'data-status="(\w+)"', bag)
    sesudah[nama] = {'status': m.group(1) if i >= 0 and m else None,
                     'kelas': re.findall(r'panel-ringkasan (warna-\w+)" id="ringkasan-pembaruan"', h),
                     'label': re.findall(r'<dt>([^<]*)</dt>', bag[:bag.find('</dl>')]),
                     'nilai': re.findall(r'<span class="nilai-angka">([^<]*)', bag[:bag.find('</dl>')]),
                     'judul_baru': 'Judul Publikasi Baru Uji' in h, 'gagal_tampil': 'Judul Gagal Uji' in h,
                     'dilipat': 'Lihat rincian per wilayah' in h}
if RINGKASAN_ASLI is None:
    os.remove(F)
else:
    open(F, 'wb').write(RINGKASAN_ASLI)
hasil['sesudah'] = sesudah
print('JHASIL ' + json.dumps(hasil, ensure_ascii=False))
'''

KODE_J_WEB = r'''
import json, re, time
from werkzeug.datastructures import MultiDict
from app import create_app
from app.config import KonfigurasiUji
from app.services import pembaruan, pilihan_pembaruan as P
app = create_app(KonfigurasiUji); c = app.test_client()
with c.session_transaction() as s: s['admin_masuk'] = True; s['admin_aktif'] = int(__import__('time').time())
b = P.bawaan()
data = [('formulir', '1'), ('dari', str(b.dari)), ('sampai', str(b.sampai)), ('aksi', 'cek'), ('wilayah', '{DOMAIN}')]
data += [('jenis', j) for j in b.jenis]
c.post('/admin/perbarui/mulai', data=MultiDict(data))
t = time.time()
while pembaruan.keadaan()['berjalan'] and time.time() - t < 600:
    time.sleep(0.5)
h = c.get('/admin/perbarui').get_data(as_text=True)
i = h.find('id="ringkasan-cek"'); bag = h[i:] if i >= 0 else ''
m = re.search(r'data-status="(\w+)"', bag)
k = re.search(r'<p class="kalimat-ringkasan">(.*?)</p>', bag, re.S)
print('JWEB ' + json.dumps({'kode': pembaruan.keadaan()['kode_keluar'], 'status': m.group(1) if m else None,
      'kalimat': re.sub(r'\s+', ' ', k.group(1)) if k else None,
      'nilai': re.findall(r'<span class="nilai-angka">([^<]*)', bag[:bag.find('</dl>')]),
      'rincian': 'Lihat rincian per wilayah' in bag}, ensure_ascii=False))
'''


def bagian_j(per_id):
    """Ringkasan hasil "Cek dulu" dan pembaruan untuk pembaca non-IT (25 Nov 2026):
    satuan, empat status, kalimat, tombol Mulai nonaktif saat disk kurang (juga
    ditolak di server), rincian dilipat, ringkasan sesudah pembaruan."""
    print("\n=== J. RINGKASAN CEK DULU / PEMBARUAN (kartu status) ===", flush=True)
    kode, keluar, err = jalan_py(KODE_J.replace("{UJI}", UJI), timeout=600)
    m = re.search(r"^JHASIL (.*)$", keluar, re.M)
    if not m:
        cek("J0 potongan uji berjalan", False, (err or keluar)[-600:])
        return
    h = json.loads(m.group(1))
    print("    | " + json.dumps(h, ensure_ascii=False)[:3000], flush=True)
    cek("J1 satuan ukuran: MB/GB satu desimal, koma Indonesia, 1 GB = 1024 MB",
        h["ukuran"] == ["tidak diketahui", "0 MB", "< 0,1 MB", "0,1 MB", "211,5 MB", "1.023,9 MB",
                        "1,0 GB", "1,2 GB", "402,7 GB"], h["ukuran"])
    cek("J1 satuan waktu: detik/menit/jam, perkiraan bertanda ±",
        h["durasi"] == ["0 detik", "45 detik", "59 detik", "1 menit", "1 menit", "30 menit", "59 menit",
                        "1,0 jam", "2,5 jam"] and h["durasi_kira"] == "±9 menit", [h["durasi"], h["durasi_kira"]])
    s = h["status"]
    cek("J2 empat status + batas: abu-abu (0 diproses), hijau, kuning (> 30 menit / > 1 GB, batasnya belum), "
        "merah (unduhan + 20% > sisa, mengalahkan kuning; Mulai tidak boleh); sisa disk tak diketahui bukan merah",
        h["ambang"] == {"besar_menit": 30, "besar_gb": 1, "cadangan_disk_persen": 20}
        and s == {"terbaru": ["terbaru", True], "siap": ["siap", True],
                  "besar_menit_pas": ["siap", True], "besar_menit_lebih": ["besar", True],
                  "besar_gb_pas": ["siap", True], "besar_gb_lebih": ["besar", True],
                  "disk_pas": ["siap", True], "disk_kurang": ["disk", False],
                  "disk_dulu_dari_besar": ["disk", False], "disk_tak_diketahui": ["besar", True]}, s)
    k = h["kalimat"]
    cek("J2 kalimat ringkasan: wilayah disebut kalau <= 3, selain itu 'dari 5 wilayah'; revisi, gagal, disk, terbaru",
        k["satu"] == "Ada 1 publikasi baru dari Kota Banjarmasin. 620 publikasi lain tidak berubah. "
                     "Klik Mulai pembaruan untuk menariknya."
        and k["tiga"].startswith("Ada 3 publikasi baru dari Kab. Tapin, Kab. Banjar, dan Kota Banjarbaru.")
        and k["lima"].startswith("Ada 5 publikasi baru dari 5 wilayah.")
        and k["revisi"].startswith("Ada 2 publikasi yang direvisi BPS dari Kab. Tapin.")
        and "Cek gagal untuk Kab. Balangan" in k["gagal"]
        and "sisa ruang hanya 50,0 MB" in k["disk"] and "120,0 MB" in k["disk"]
        and k["terbaru"].startswith("Tidak ada publikasi baru atau yang direvisi BPS. 40 publikasi"), k)
    cek("J2 ambang dibaca dari wilayah.json (besar_menit 4 -> 5 menit jadi kuning); kunci hilang ditolak dengan pesan",
        h["ambang_diubah"] == "besar" and "ambang_penarikan belum diisi" in h["ambang_hilang"],
        [h["ambang_diubah"], h["ambang_hilang"][:90]])
    hal = h["halaman"]
    cek("J3 halaman: kartu di atas hasil cek dengan status + 4 angka, tabel rincian dilipat di <details>",
        all(hal[x]["status"] == x and hal[x]["kotak"] == 4 and hal[x]["tabel_dilipat"] for x in hal)
        and hal["siap"]["judul"] == "Siap ditarik" and hal["terbaru"]["judul"] == "Semua sudah terbaru"
        and hal["disk"]["judul"] == "Ruang disk tidak cukup"
        and hal["besar"]["judul"].startswith("Penarikan besar")
        and hal["siap"]["nilai"][1:3] == ["211,5 MB", "±9 menit"] and hal["besar"]["nilai"][1] == "3,4 GB",
        {x: (v["status"], v["kotak"], v["tabel_dilipat"], v["nilai"]) for x, v in hal.items()})
    cek("J3 tombol Mulai pembaruan nonaktif + penjelasan HANYA saat ruang disk kurang",
        [hal[x]["mulai_nonaktif"] for x in ("siap", "besar", "disk", "terbaru")] == [False, False, True, False]
        and [hal[x]["alasan"] for x in ("siap", "besar", "disk", "terbaru")] == [False, False, True, False],
        {x: (v["mulai_nonaktif"], v["alasan"]) for x, v in hal.items()})
    p = h["post"]
    cek("J4 server menolak Mulai pembaruan (HTTP 409, 0 proses) untuk pilihan yang sama dengan cek yang kekurangan "
        "disk; Cek dulu, disk cukup, atau pilihan lain tetap dimulai",
        p["sama_disk_kurang"] == [409, True, 0] and p["cek_tetap_boleh"] == [302, False, 1]
        and p["sama_disk_cukup"] == [302, False, 2] and p["pilihan_lain"] == [302, False, 3]
        and [x[0] for x in h["dimulai"]] == [True, False, False], [p, h["dimulai"]])
    sd = h["sesudah"]
    label = ["Publikasi baru", "Gagal", "Terunduh", "Durasi"]
    cek("J5 ringkasan SESUDAH pembaruan bergaya sama: status berwarna (hijau/abu-abu/kuning/merah), "
        "4 angka (baru, gagal, terunduh, durasi), judul publikasi baru tetap tampil, rincian dilipat",
        [sd[x]["kelas"] for x in ("sukses", "tidak_ada_baru", "sebagian", "gagal")]
        == [["warna-hijau"], ["warna-abu"], ["warna-kuning"], ["warna-merah"]]
        and all(v["label"] == label and v["dilipat"] for v in sd.values())
        and sd["sukses"]["nilai"] == ["1 ", "0 ", "1,3 GB", "13 menit"] and sd["sukses"]["judul_baru"]
        and sd["sebagian"]["nilai"][1] == "1 " and sd["sebagian"]["gagal_tampil"],
        {x: (v["kelas"], v["nilai"], v["judul_baru"]) for x, v in sd.items()})

    # J6: ujung ke ujung, "Cek dulu" sungguhan lewat test_client + WebAPI tiruan
    aktifkan(DOMAIN)
    KEADAAN["domain"].pop("6399", None)
    for x in ("gagal_domain", "gagal_halaman", "mode_pdf", "mode_sampul", "isi_sampul"):
        KEADAAN[x].clear()
    kode, _, _ = jalan_catat()                                  # selaraskan database uji dengan tiruan
    web = []
    for tambah in (False, True):
        nb = None
        if tambah:
            contoh = next(p for p in KEADAAN["domain"][DOMAIN] if p["pub_id"] in per_id)
            nb = copy.deepcopy(contoh)
            nb.update(pub_id="jjjjkkkkllllmmmm6305baru", title="Publikasi Baru Uji Ringkasan",
                      rl_date="2026-11-24", updt_date="2026-11-24", size="12.5 MB",
                      pdf=url_tiruan("pdf", "jjjjkkkkllllmmmm6305baru"))
            KEADAAN["domain"][DOMAIN].insert(0, nb)
        try:
            kode_w, keluar_w, err_w = jalan_py(KODE_J_WEB.replace("{DOMAIN}", DOMAIN), timeout=900)
        finally:
            if nb:
                KEADAAN["domain"][DOMAIN].remove(nb)
        m = re.search(r"^JWEB (.*)$", keluar_w, re.M)
        web.append(json.loads(m.group(1)) if m else {"galat": (err_w or keluar_w)[-300:]})
    cek("J6 Cek dulu sungguhan (WebAPI tiruan): tanpa perubahan = abu-abu 'Semua sudah terbaru'; 1 publikasi baru "
        "= hijau, kalimat menyebut Kab. Tapin, ukuran 12,5 MB, sisa disk terbaca",
        kode == 0 and web[0].get("kode") == 0 and web[0].get("status") == "terbaru"
        and web[1].get("status") == "siap" and (web[1].get("kalimat") or "").startswith("Ada 1 publikasi baru dari Kab. Tapin.")
        and web[1]["nilai"][1] == "12,5 MB" and web[1]["nilai"][3] not in ("tidak diketahui", "")
        and web[0]["rincian"] and web[1]["rincian"], web)


KODE_X = r'''
import json, re, sys, time
from werkzeug.security import generate_password_hash
from app import create_app
from app.config import Config, KonfigurasiUji, menit_sesi_admin
from app.routes import admin as A
hasil = {}
app = create_app(KonfigurasiUji)
app.config['ADMIN_PASSWORD_HASH'] = generate_password_hash('sandi-uji-x-123')
c = app.test_client()
JAM = {'t': time.time()}
A._sekarang = lambda: JAM['t']
from urllib.parse import unquote
# Revisi 25 Nov 2026: halaman admin terpisah. Menu admin HANYA di /admin/*;
# halaman pencarian hanya punya tombol "Halaman Admin".
MENU = [('/admin/kamus', 'Kamus Sinonim'), ('/admin/log', 'Log Pencarian'),
        ('/admin/perbarui', 'Perbarui Data'), ('/admin/sandi', 'Ganti Sandi')]
def kop(h):
    hd = re.search(r'<header class="kop[^"]*">.*?</header>', h, re.S)
    hd = hd.group(0) if hd else ''
    nav = re.search(r'<nav class="menu-utama".*?</nav>', hd, re.S)
    nav = nav.group(0) if nav else ''
    t = re.search(r'(<a class="tombol-admin"[^>]*>)(.*?)</a>', hd, re.S)
    # Label yang dibaca pembaca layar: tanpa tag dan tanpa ikon (🔒, ✓ hanya hiasan).
    label = ' '.join(re.sub(r'<span class="tanda-masuk"[^>]*>.*?</span>|<[^>]+>|&#\d+;', ' ',
                            t.group(2)).split()).replace(' )', ')') if t else None
    return {'jenis': 'admin' if 'kop-admin' in hd[:60] else 'pencarian',
            'menu': re.findall(r'<li><a href="([^"]+)"[^>]*>([^<]+)</a></li>', nav),
            'aktif': re.findall(r'<a href="([^"]+)" aria-current="page"', nav),
            'tombol_admin': [re.search(r'href="([^"]+)"', t.group(1)).group(1), label,
                             'target=' in t.group(1)] if t else None,
            'kembali': re.findall(r'<a class="tombol-kembali" href="([^"]+)"', hd),
            'keluar': 'action="/admin/logout"' in hd,
            'admin': ('Masuk sebagai admin' in nav and 'action="/admin/logout"' in nav)
                     or bool(label and '(masuk)' in label)}
def masuk(alamat='127.0.0.1', sandi='sandi-uji-x-123', nxt=''):
    return c.post('/admin/login', data={'sandi': sandi, 'next': nxt}, environ_base={'REMOTE_ADDR': alamat})
def keluar():
    with c.session_transaction() as s: s.clear()

# X1: menu di semua halaman, menu aktif, penanda admin hanya saat login
tanpa = {u: (c.get(u).status_code, kop(c.get(u).get_data(as_text=True)))
         for u in ('/', '/hasil?q=penduduk', '/hasil?q=zzqqxx', '/admin/login')}
masuk()
dengan = {}
for u in ('/', '/hasil?q=penduduk', '/admin/', '/admin/kamus', '/admin/log', '/admin/log/periksa?q=p0',
          '/admin/perbarui', '/admin/sandi'):
    r = c.get(u); dengan[u] = (r.status_code, kop(r.get_data(as_text=True)))
hasil['x1'] = {'tanpa': tanpa, 'dengan': dengan, 'menu_harap': MENU}
keluar()

# X7: tombol "Halaman Admin" di halaman pencarian -> login -> kembali ke /admin/
k0 = kop(c.get('/').get_data(as_text=True))['tombol_admin']
r1 = c.get(k0[0])
lok = r1.headers.get('Location', '')
r2 = masuk(nxt=unquote(re.search(r'next=([^&]+)', lok).group(1)) if 'next=' in lok else '')
r3 = c.get(r2.headers.get('Location', '/x'))
k1 = kop(c.get('/hasil?q=penduduk').get_data(as_text=True))['tombol_admin']
r4 = c.get(k1[0])
hasil['x7'] = {'tombol_awal': k0, 'klik': [r1.status_code, lok], 'login': [r2.status_code, r2.headers.get('Location')],
               'admin': [r3.status_code, kop(r3.get_data(as_text=True))['jenis']], 'tombol_masuk': k1,
               'klik_masuk': [r4.status_code, r4.headers.get('Location')]}
keluar()

# X2: tanpa login, menu admin -> login -> kembali ke tujuan (termasuk query)
x2 = {}
for u in ('/admin/kamus', '/admin/log?semua=1', '/admin/perbarui', '/admin/sandi', '/admin/log/periksa?q=p0+penduduk'):
    keluar()
    r = c.get(u)
    lok = r.headers.get('Location', '')
    nxt = re.search(r'next=([^&]+)', lok)
    from urllib.parse import unquote
    nxt = unquote(nxt.group(1)) if nxt else None
    r2 = masuk(nxt=nxt)
    r3 = c.get(r2.headers.get('Location', '/x'))
    x2[u] = [r.status_code, nxt, r2.status_code, r2.headers.get('Location'), r3.status_code]
# kiriman POST saat belum login: tujuan = halaman asal (Referer)
keluar()
r = c.post('/admin/kamus/tambah-varian', data={'kanonik': 'x', 'varian': 'y'},
           headers={'Referer': 'http://localhost/admin/kamus?q=pdrb'})
x2['post'] = [r.status_code, r.headers.get('Location')]
# tujuan berbahaya diganti beranda admin
bahaya = {}
for n in ('//situs-lain.example', 'http://situs-lain.example/', '/\\situs-lain', 'javascript:alert(1)', '/admin/logout'):
    keluar()
    bahaya[n] = masuk(nxt=n).headers.get('Location')
x2['bahaya'] = bahaya
hasil['x2'] = x2
keluar()

# X3: sesi kedaluwarsa (bawaan 120 menit), waktu diperbarui tiap permintaan
x3 = {'menit': app.config['SESI_ADMIN_MENIT']}
masuk()
with c.session_transaction() as s: s['admin_aktif'] = JAM['t'] - 119 * 60
r = c.get('/admin/kamus')
with c.session_transaction() as s: x3['diperbarui'] = s.get('admin_aktif') == int(JAM['t'])
x3['119_menit'] = r.status_code
with c.session_transaction() as s: s['admin_aktif'] = JAM['t'] - 121 * 60
r = c.get('/admin/kamus')
x3['121_menit'] = [r.status_code, r.headers.get('Location')]
h = c.get(r.headers['Location']).get_data(as_text=True)
x3['pesan'] = 'Sesi admin berakhir karena tidak aktif lebih dari 120 menit' in h
x3['kop_sesudah'] = kop(c.get('/hasil?q=penduduk').get_data(as_text=True))['admin']
# kedaluwarsa juga dari halaman pencarian: penanda admin hilang
masuk()
with c.session_transaction() as s: s['admin_aktif'] = JAM['t'] - 121 * 60
x3['pencarian_kedaluwarsa'] = [kop(c.get('/').get_data(as_text=True))['admin'], c.get('/admin/').status_code]
# session tanpa waktu aktif (versi lama) dianggap kedaluwarsa
keluar()
with c.session_transaction() as s: s['admin_masuk'] = True
x3['tanpa_waktu'] = c.get('/admin/').status_code
hasil['x3'] = x3
keluar()

# X5: penguncian sesudah 5 sandi salah dari satu alamat
x5 = {}
x5['salah'] = [(masuk('10.9.9.1', 'salah').status_code) for _ in range(4)]
r = masuk('10.9.9.1', 'salah')
x5['ke5'] = [r.status_code, 'dikunci 5 menit' in r.get_data(as_text=True)]
r = masuk('10.9.9.1')
x5['benar_saat_kunci'] = [r.status_code, 'coba lagi dalam 5 menit' in r.get_data(as_text=True)]
with c.session_transaction() as s: x5['tidak_masuk'] = not s.get('admin_masuk')
r = c.get('/admin/login', environ_base={'REMOTE_ADDR': '10.9.9.1'})
x5['get_saat_kunci'] = [r.status_code, ' disabled' in r.get_data(as_text=True)]
x5['alamat_lain'] = masuk('10.9.9.2').status_code
keluar()
JAM['t'] += 4 * 60
x5['4_menit'] = masuk('10.9.9.1').status_code
JAM['t'] += 61
x5['5_menit_lebih'] = masuk('10.9.9.1').status_code
keluar()
# sukses mengosongkan hitungan: 4 salah, benar, 4 salah lagi = belum terkunci
for _ in range(4): masuk('10.9.9.3', 'salah')
masuk('10.9.9.3'); keluar()
x5['reset'] = [masuk('10.9.9.3', 'salah').status_code for _ in range(4)]
hasil['x5'] = x5
print('XHASIL ' + json.dumps(hasil, ensure_ascii=False))
'''

KODE_X_ENV = r'''
import json
from app.config import Config, menit_sesi_admin
from app import create_app
from app.config import KonfigurasiUji
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    app = create_app(KonfigurasiUji)
print('XENV ' + json.dumps({'menit': app.config['SESI_ADMIN_MENIT'], 'peringatan': 'SESI_ADMIN_MENIT di .env tidak sah' in buf.getvalue()}))
'''


KODE_X_PROXY = r'''
import json, io, contextlib
from werkzeug.security import generate_password_hash
from app import create_app
from app.config import KonfigurasiUji
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    app = create_app(KonfigurasiUji)
app.config['ADMIN_PASSWORD_HASH'] = generate_password_hash('sandi-uji-proxy-1')
c = app.test_client()
def coba(xff, sandi):
    # Semua permintaan datang dari SATU koneksi (alamat proxy 10.7.7.7); yang
    # berbeda hanya X-Forwarded-For, alamat pengguna menurut proxy.
    r = c.post('/admin/login', data={'sandi': sandi}, environ_base={'REMOTE_ADDR': '10.7.7.7'},
               headers={'X-Forwarded-For': xff})
    with c.session_transaction() as s: s.clear()
    return r.status_code
salah = [coba('203.0.113.1', 'salah') for _ in range(5)]
print('XPROXY ' + json.dumps({'jumlah': app.config['JUMLAH_PROXY'],
      'peringatan': 'JUMLAH_PROXY di .env tidak sah' in buf.getvalue(),
      'salah_a': salah, 'benar_b': coba('203.0.113.2', 'sandi-uji-proxy-1'),
      'benar_a': coba('203.0.113.1', 'sandi-uji-proxy-1')}))
'''


def bagian_x():
    """Tampilan 25 Nov 2026: menu di semua halaman, login + kembali ke tujuan,
    sesi admin kedaluwarsa (SESI_ADMIN_MENIT), penguncian sesudah 5 sandi salah."""
    print("\n=== X. MENU, LOGIN, SESI ADMIN, PENGUNCIAN ===", flush=True)
    kode, keluar, err = jalan_py(KODE_X, timeout=600)
    m = re.search(r"^XHASIL (.*)$", keluar, re.M)
    if not m:
        cek("X0 potongan uji berjalan", False, (err or keluar)[-800:])
        return
    h = json.loads(m.group(1))
    print("    | " + json.dumps(h, ensure_ascii=False)[:2500], flush=True)
    menu = [list(x) for x in h["x1"]["menu_harap"]]
    t, d = h["x1"]["tanpa"], h["x1"]["dengan"]
    cari = ("/", "/hasil?q=penduduk", "/hasil?q=zzqqxx")
    adm = [u for u in d if u.startswith("/admin")]
    cek("X1 halaman pencarian: kop tanpa menu admin dan tanpa Keluar, satu tombol 'Halaman Admin' ke /admin/ "
        "(tab yang sama); saat login berlabel 'Halaman Admin (masuk)'",
        all(t[u][0] == 200 and t[u][1]["jenis"] == "pencarian" and t[u][1]["menu"] == [] and not t[u][1]["keluar"]
            and t[u][1]["kembali"] == [] and t[u][1]["tombol_admin"] == ["/admin/", "Halaman Admin", False] for u in cari)
        and all(d[u][0] == 200 and d[u][1]["jenis"] == "pencarian" and d[u][1]["menu"] == [] and not d[u][1]["keluar"]
                and d[u][1]["tombol_admin"] == ["/admin/", "Halaman Admin (masuk)", False] for u in cari if u in d),
        {u: (v[1]["jenis"], v[1]["menu"], v[1]["tombol_admin"], v[1]["keluar"]) for u, v in {**t, **d}.items()
         if not u.startswith("/admin")})
    cek("X1 halaman admin: menu 4 butir (Kamus, Log, Perbarui, Ganti Sandi) + 'Kembali ke Pencarian' + Keluar + "
        "penanda admin; login (belum masuk): hanya 'Kembali ke Pencarian'",
        all(d[u][0] == 200 and d[u][1]["jenis"] == "admin" and d[u][1]["menu"] == menu and d[u][1]["kembali"] == ["/"]
            and d[u][1]["keluar"] and d[u][1]["admin"] and d[u][1]["tombol_admin"] is None for u in adm)
        and t["/admin/login"][1]["jenis"] == "admin" and t["/admin/login"][1]["menu"] == []
        and t["/admin/login"][1]["kembali"] == ["/"] and not t["/admin/login"][1]["keluar"],
        {u: (v[1]["jenis"], len(v[1]["menu"]), v[1]["kembali"], v[1]["keluar"]) for u, v in {**t, **d}.items()
         if u.startswith("/admin")})
    harap_aktif = {"/admin/": [], "/admin/kamus": ["/admin/kamus"],
                   "/admin/log": ["/admin/log"], "/admin/log/periksa?q=p0": ["/admin/log"],
                   "/admin/perbarui": ["/admin/perbarui"], "/admin/sandi": ["/admin/sandi"]}
    cek("X1 menu admin aktif ditandai aria-current (tepat satu, sesuai halaman; beranda admin tanpa tanda)",
        all(d[u][1]["aktif"] == a for u, a in harap_aktif.items()), {u: d[u][1]["aktif"] for u in adm})
    x7 = h["x7"]
    cek("X7 tombol 'Halaman Admin': belum login -> login (next=/admin/) -> masuk -> kembali ke /admin/ (200); "
        "sudah login -> label '(masuk)' dan langsung masuk (200)",
        x7["tombol_awal"] == ["/admin/", "Halaman Admin", False]
        and x7["klik"] == [302, "/admin/login?next=/admin/"] and x7["login"] == [302, "/admin/"]
        and x7["admin"] == [200, "admin"] and x7["tombol_masuk"] == ["/admin/", "Halaman Admin (masuk)", False]
        and x7["klik_masuk"] == [200, None], x7)
    x2 = h["x2"]
    cek("X2 tanpa login: menu admin -> login (next = tujuan + query) -> kembali ke tujuan, HTTP 200",
        all(v[0] == 302 and v[1] == u and v[2] == 302 and v[3] == u and v[4] == 200
            for u, v in x2.items() if u.startswith("/admin")), {u: v for u, v in x2.items() if u.startswith("/")})
    cek("X2 kiriman POST tanpa login -> login dengan next = halaman asal; next berbahaya -> beranda admin",
        x2["post"][0] == 302 and x2["post"][1].endswith("next=/admin/kamus?q%3Dpdrb")
        and all(v == "/admin/" for v in x2["bahaya"].values()), [x2["post"], x2["bahaya"]])
    x3 = h["x3"]
    cek("X3 sesi bawaan 120 menit: 119 menit tidak aktif masih masuk (waktu diperbarui), 121 menit keluar + pesan; "
        "penanda admin hilang juga di halaman pencarian; session tanpa waktu aktif = keluar",
        x3["menit"] == 120 and x3["119_menit"] == 200 and x3["diperbarui"]
        and x3["121_menit"][0] == 302 and x3["121_menit"][1] == "/admin/login?next=/admin/kamus"
        and x3["pesan"] and x3["kop_sesudah"] is False and x3["pencarian_kedaluwarsa"] == [False, 302]
        and x3["tanpa_waktu"] == 302, x3)
    env = {}
    for nilai in ("5", " 30 ", "1440", "abc", "0", "-3", "1,5", "99999", ""):
        kode_e, keluar_e, err_e = jalan_py(KODE_X_ENV, env_tambahan={"SESI_ADMIN_MENIT": nilai})
        m = re.search(r"^XENV (.*)$", keluar_e, re.M)
        env[nilai] = json.loads(m.group(1)) if m else (err_e or keluar_e)[-200:]
    harap = {"5": [5, False], " 30 ": [30, False], "1440": [1440, False], "abc": [120, True], "0": [120, True],
             "-3": [120, True], "1,5": [120, True], "99999": [120, True], "": [120, False]}
    cek("X4 SESI_ADMIN_MENIT dari lingkungan/.env: angka 1-1440 dipakai; tidak sah = bawaan 120 + peringatan "
        "(aplikasi tetap jalan); kosong = 120",
        all(isinstance(env[k], dict) and [env[k]["menit"], env[k]["peringatan"]] == v for k, v in harap.items()),
        env)
    kode5, keluar5, err5 = jalan_py(KODE_X.replace("hasil['x1']", "hasil['_']").split("# X1:")[0] + r'''
masuk()
with c.session_transaction() as s: s['admin_aktif'] = JAM['t'] - 4 * 60
a = c.get('/admin/').status_code
with c.session_transaction() as s: s['admin_aktif'] = JAM['t'] - 6 * 60
b = c.get('/admin/').status_code
print('XLIMA', app.config['SESI_ADMIN_MENIT'], a, b)
''', env_tambahan={"SESI_ADMIN_MENIT": "5"})
    cek("X4 SESI_ADMIN_MENIT=5 berlaku: 4 menit tidak aktif masih masuk, 6 menit keluar",
        "XLIMA 5 200 302" in keluar5, (keluar5 + err5)[-300:])
    x5 = h["x5"]
    cek("X5 penguncian: 4 salah = 200, ke-5 = 429 dikunci 5 menit; sandi benar saat terkunci ditolak (tidak masuk), "
        "formulir nonaktif; alamat lain tidak terkunci; 4 menit masih terkunci, > 5 menit boleh; sukses "
        "mengosongkan hitungan",
        x5["salah"] == [200] * 4 and x5["ke5"] == [429, True] and x5["benar_saat_kunci"] == [429, True]
        and x5["tidak_masuk"] and x5["get_saat_kunci"] == [429, True] and x5["alamat_lain"] == 302
        and x5["4_menit"] == 429 and x5["5_menit_lebih"] == 302 and x5["reset"] == [200] * 4, x5)

    # X6: JUMLAH_PROXY (25 Nov 2026). Lima sandi salah dengan X-Forwarded-For A,
    # lalu sandi benar dengan X-Forwarded-For B dan A, dari koneksi yang sama.
    px = {}
    for nilai in ("", "0", "1", " 1 ", "abc", "-1", "1,5", "99"):
        kode_p, keluar_p, err_p = jalan_py(KODE_X_PROXY, env_tambahan={"JUMLAH_PROXY": nilai})
        m = re.search(r"^XPROXY (.*)$", keluar_p, re.M)
        px[nilai] = json.loads(m.group(1)) if m else (err_p or keluar_p)[-300:]
    print("    | " + json.dumps(px, ensure_ascii=False), flush=True)

    def pola(v, jumlah, peringatan, benar_b):
        return (isinstance(v, dict) and v["jumlah"] == jumlah and v["peringatan"] == peringatan
                and v["salah_a"] == [200, 200, 200, 200, 429] and v["benar_b"] == benar_b and v["benar_a"] == 429)
    cek("X6 JUMLAH_PROXY kosong/0 = perilaku sekarang: X-Forwarded-For diabaikan, satu koneksi = satu alamat "
        "(B ikut terkunci oleh salah A)",
        pola(px[""], 0, False, 429) and pola(px["0"], 0, False, 429), {k: px[k] for k in ("", "0")})
    cek("X6 JUMLAH_PROXY=1: alamat dari X-Forwarded-For, A dan B dikunci terpisah (A terkunci, B tetap bisa masuk)",
        pola(px["1"], 1, False, 302) and pola(px[" 1 "], 1, False, 302), {k: px[k] for k in ("1", " 1 ")})
    cek("X6 JUMLAH_PROXY tidak sah (abc, -1, 1,5, 99) = 0 + PERINGATAN, berperilaku seperti 0",
        all(pola(px[k], 0, True, 429) for k in ("abc", "-1", "1,5", "99")),
        {k: px[k] for k in ("abc", "-1", "1,5", "99")})


SEMUA_BAGIAN = "VFPLCHISOBGETDKRWQAJX"   # V dan F dijalankan sebelum potret s0 (lihat main)


def main():
    print(f"Database uji: {DB_UJI} | produksi (hanya dibaca): {DB_PROD} | domain uji: {DOMAIN}", flush=True)
    siapkan_salinan()
    arahkan_url_ke_tiruan()
    srv, pubs = siapkan_tiruan()
    try:
        bagian_u()
        if "V" in BAGIAN:
            bagian_v()          # sebelum bagian lain mengubah isi database uji
        if "F" in BAGIAN:
            bagian_f()
        s_lama = bagian_n()     # ekspektasi s0 = database uji dengan kamus salinan
        s0 = potret()
        dom = [p for p in s0 if s0[p]["pub"]["domain"] == DOMAIN]
        ocr_pub = sorted(p for p in dom if s0[p]["pub"]["halaman_ocr"])
        # Dua publikasi kecil bertekst dibuat "usang": API punya versi lebih baru.
        usang = sorted((p for p in dom if p not in ocr_pub), key=lambda p: os.path.getsize(path_uji(p)))[:2]
        for p in usang:
            sql(f"UPDATE publikasi SET updt_date_api='2026-12-31' WHERE id='{p}'", DB_UJI)
        s0 = potret()
        per_id = {p["pub_id"]: p for p in pubs}
        # publikasi kecil bertekst (bukan OCR, bukan usang) untuk skenario cepat
        kecil = sorted((p for p in dom if p not in ocr_pub and p not in usang),
                       key=lambda p: os.path.getsize(path_uji(p)))[:6]
        baru = None
        if BAGIAN != SEMUA_BAGIAN:
            print(f"\n(--hanya {BAGIAN}: bagian lain dilewati)", flush=True)
        for b in BAGIAN:
            if b == "P": bagian_p(s0, usang, s_lama)
            if b == "L": bagian_l(usang)
            if b == "C": bagian_c(s0, ocr_pub)
            if b == "H": bagian_h(s0)
            if b == "I": bagian_i()
            if b == "S": bagian_s()
            if b == "O": bagian_o(pubs, per_id, usang, s0)
            if b == "B": baru = bagian_b(pubs, per_id, kecil)
            if b == "G": bagian_g(per_id, kecil[2])
            if b == "E": bagian_e(pubs, per_id, kecil, baru or copy.deepcopy(per_id[kecil[0]]))
            if b == "T": bagian_t(per_id, kecil[2], kecil)
            if b == "D": bagian_d(per_id, kecil)
            if b == "K": bagian_k()
            if b == "R": bagian_r(kecil[0])
            if b == "W": bagian_w(per_id, kecil[2])
            if b == "Q": bagian_q(per_id)
            if b == "A": bagian_a(kecil, per_id)
            if b == "J": bagian_j(per_id)
            if b == "X": bagian_x()
    finally:
        srv.shutdown()


def jalankan():
    try:
        periksa_lingkungan()
    except LingkunganBelumSiap as e:
        print(f"LINGKUNGAN BELUM SIAP - tidak ada yang dijalankan:\n  {e}", flush=True)
        return KODE_LINGKUNGAN

    t0 = time.time()
    prod_awal = checksum_db(DB_PROD)
    uji_awal = checksum_db(DB_UJI)
    charset = cadangkan_db_uji()
    print(f"Cadangan database uji: {os.path.getsize(DUMP_UJI) / 1e6:.1f} MB, "
          f"{len(uji_awal)} tabel; produksi {len(prod_awal)} tabel", flush=True)
    galat_tak_terduga = None
    try:
        main()
    except Exception as e:  # noqa: BLE001 - tetap pulihkan database uji
        galat_tak_terduga = e
        import traceback
        traceback.print_exc()
    finally:
        print("\n=== Z. PEMULIHAN DAN BUKTI ===", flush=True)
        os.chdir(ASLI)
        try:
            pulihkan_db_uji(*charset)
            uji_akhir = checksum_db(DB_UJI)
            cek("Z1 database uji dipulihkan, CHECKSUM TABLE sama dengan awal", uji_akhir == uji_awal,
                [t for t in uji_awal if uji_awal[t] != uji_akhir.get(t)])
        except Exception as e:  # noqa: BLE001
            cek("Z1 database uji dipulihkan", False, str(e)[:200])
        prod_akhir = checksum_db(DB_PROD)
        cek("Z2 produksi tidak berubah (CHECKSUM TABLE awal = akhir)", prod_akhir == prod_awal,
            [t for t in prod_awal if prod_awal[t] != prod_akhir.get(t)])
        for d in (UJI, SUMBER):
            shutil.rmtree(d, ignore_errors=True)
        cek("Z3 folder sementara dibersihkan", not os.path.exists(UJI) and not os.path.exists(SUMBER))
        if os.path.exists(DUMP_UJI):
            os.remove(DUMP_UJI)
        try:
            os.rmdir(SP)
        except OSError:
            pass
    if galat_tak_terduga is not None:
        cek("galat tak terduga di tengah uji", False, repr(galat_tak_terduga)[:200])

    gagal = [n for n, s in hasil_uji if s == "gagal"]
    dilewati = [n for n, s in hasil_uji if s == "lewati"]
    print(f"\n=== TOTAL: {len(hasil_uji) - len(gagal) - len(dilewati)} lulus, {len(gagal)} gagal, "
          f"{len(dilewati)} dilewati ({time.time() - t0:.0f} detik) ===")
    for n in gagal:
        print("  GAGAL:", n)
    for n in dilewati:
        print("  DILEWATI:", n)
    return KODE_GAGAL if gagal else KODE_LULUS


if __name__ == "__main__":
    # --hanya DKRW: jalankan sebagian bagian saja (urutan tetap SEMUA_BAGIAN).
    # U dan Z selalu jalan. Untuk tim IT: jalankan tanpa argumen.
    BAGIAN = SEMUA_BAGIAN
    if "--hanya" in sys.argv:
        pilih = sys.argv[sys.argv.index("--hanya") + 1].upper()
        BAGIAN = "".join(b for b in SEMUA_BAGIAN if b in pilih)
    sys.exit(jalankan())
