r"""Uji pipeline di lingkungan terisolasi: salinan kode, DATABASE UJI, WebAPI tiruan.

Cara menjalankan (dari folder proyek):

    venv\Scripts\python.exe -u tests\uji_pipeline.py > uji_log.txt 2>&1

Semua bagian sekitar 37 menit. Sebagian saja (untuk pengembang): tambahkan
--hanya DKRW (huruf bagian; U dan Z selalu jalan).

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
- Tidak ada akses ke API BPS dan tidak ada unduhan dari BPS. Metadata dan PDF
  disajikan server tiruan di 127.0.0.1, dibangun dari baris database uji.
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


def jalan(skrip, *arg, timeout=3600, env_tambah=None):
    """Jalankan skrip di salinan. perbarui.py SELALU dengan --db-uji."""
    arg = list(arg)
    if skrip == "perbarui.py" and "--db-uji" not in arg:
        arg.insert(0, "--db-uji")
    t = time.time()
    r = subprocess.run([PY, "-u", f"{UJI}/scripts/{skrip}", *arg], cwd=SP, env={**ENV, **(env_tambah or {})},
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, r.stdout + r.stderr, time.time() - t


def jalan_py(kode, timeout=1800):
    """Potongan Python di salinan. Wajib memakai KonfigurasiUji, tidak boleh create_app()."""
    sah = {"KonfigurasiUji"} | set(re.findall(r"class (\w+)\(KonfigurasiUji\)", kode))
    for arg in re.findall(r"create_app\(([^)]*)\)", kode):
        if arg.strip() not in sah:
            raise AssertionError(f"potongan uji harus memakai create_app(KonfigurasiUji), bukan {arg!r}")
    r = subprocess.run([PY, "-c", f"import sys; sys.path.insert(0, r'{UJI}')\n" + kode], cwd=SP, env=ENV,
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
KEADAAN = {"domain": {}, "gagal_domain": {}, "gagal_halaman": {}, "mode_pdf": {}, "berkas_pdf": {}}
PERMINTAAN = []


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
            isi = open(KEADAAN["berkas_pdf"][pid], "rb").read()
            self._kirim(200, isi[:50000] if mode == "potong" else isi, "application/pdf")
            return
        self._kirim(404, b"{}")


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
                         "pdf": f"http://127.0.0.1:{PORT}/pdf/{r['id']}", "cover": r["url_cover"],
                         "issn": r["issn"], "subject_csa": []})
    return pubs


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
    cek("U3 ringkasan ke pembaruan_terakhir-uji.json, berkas produksi tidak dibuat",
        os.path.exists(f"{UJI}/data/pembaruan_terakhir-uji.json") and not os.path.exists(prod_asli)
        and ringkasan()["status"] in ("tidak_ada_baru", "sukses"), f"exit {kode}, {dtk:.0f} d")


def kolom_pub(pid, k):
    return sql(f"SELECT {k} FROM publikasi WHERE id='{pid}'", DB_UJI)


def entri_n(pid):
    return int(sql(f"SELECT COUNT(*) FROM entri_dokumen WHERE publikasi_id='{pid}'", DB_UJI))


def path_uji(pid):
    return f"{UJI}/data/publikasi_pdf/{DOMAIN}/{pid}.pdf"


def bagian_p(s0, usang):
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
    return E._gabung_nomor_terbelah([E._rapikan_nomor_halaman(b) for b in halaman])
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
# Pola 1: nomor terpotong "2.1." + "1" (celah 3 pt), >= 3 baris di halaman (Tanah Laut 2025).
cetak("K1-nomor-terbelah", baca([
    baris(w("2.1.", 57, 70), w("1", 73, 77), w("Jumlah", 91), w("RT", 130), w("......", 300, 364), w("19", 366, 376)),
    baris(w("2.1.", 57, 70), w("2", 73, 77), w("Nama", 91), w("Camat", 130), w("......", 300, 364), w("20", 366, 376)),
    baris(w("2.1.", 57, 70), w("3", 73, 77), w("Nama", 91), w("Kepala", 130), w("Desa", 175), w("......", 300, 364), w("21", 366, 376))]),
    [("2.1.1", "Jumlah RT", "19"), ("2.1.2", "Nama Camat", "20"), ("2.1.3", "Nama Kepala Desa", "21")])
# Pola 1: SATU baris "1." + "10" + judul di halaman tidak memicu penggabungan.
h_satu = [baris(w("1.", 57, 63), w("10", 66, 78), w("Desa", 91), w("Terluas", 120), w("......", 300, 364), w("5", 370, 376)),
          baris(w("2.", 57, 63), w("Luas", 91), w("Wilayah", 120), w("......", 300, 364), w("6", 370, 376))]
print("I K1-satu-baris-aman", "OK" if rapi(h_satu) == h_satu and rapi(h_satu)[0][1]["text"] == "10" else "SALAH digabung")
'''


def bagian_i():
    """Parser Daftar: pola C, A2, A1, A', B (16 Nov 2026) dan pola kecamatan
    1-3 (18 Nov 2026), baris sintetis."""
    print("\n=== I. PARSER DAFTAR (pola C, A2, A1, A', B, kecamatan K1-K3) ===", flush=True)
    kode, keluar, err = jalan_py(KODE_BAGIAN_I)
    hasil = re.findall(r"^I (\S+) (OK|SALAH.*)$", keluar, re.M)
    n = 15
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
with c.session_transaction() as s: s['admin_masuk'] = True
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


def bagian_w(per_id, v):
    print("\n=== W. TOMBOL WEB + .BAT SUNGGUHAN (keduanya --db-uji) ===", flush=True)
    per_id[v]["updt_date"] = "2026-12-23"
    KEADAAN["mode_pdf"][v] = "500"
    kode_web = rf"""
import time
from app import create_app
from app.config import KonfigurasiUji
app = create_app(KonfigurasiUji); c = app.test_client()
with c.session_transaction() as s: s['admin_masuk'] = True
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

    # .bat sungguhan: python/activate palsu mengarah ke venv asli
    os.makedirs(f"{UJI}/venv/Scripts", exist_ok=True)
    open(f"{UJI}/venv/Scripts/python.exe", "wb").close()
    with open(f"{UJI}/venv/Scripts/activate.bat", "w", newline="") as f:
        jalur = os.path.dirname(PY).replace("/", chr(92))
        f.write('@set "PATH=' + jalur + ';%PATH%"' + chr(13) + chr(10))
    shutil.copy2(f"{ASLI}/perbarui-data.bat", f"{UJI}/perbarui-data.bat")
    open(f"{UJI}/.env", "w").write("# kosong: nilai uji datang dari variabel lingkungan\n")
    isi_bat = open(f"{ASLI}/perbarui-data.bat", "rb").read()
    cek("W2 .bat tetap ASCII + CRLF", all(x < 128 for x in isi_bat) and b"\n" not in isi_bat.replace(b"\r\n", b""))

    def bat():
        r = subprocess.run(["cmd", "/c", os.path.normpath(f"{UJI}/perbarui-data.bat"), "--db-uji"], cwd=UJI, env=ENV,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600)
        return r.stdout + r.stderr

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


SEMUA_BAGIAN = "FPLCHISOBGETDKRW"   # F dijalankan sebelum potret s0 (lihat bagian_f)


def main():
    print(f"Database uji: {DB_UJI} | produksi (hanya dibaca): {DB_PROD} | domain uji: {DOMAIN}", flush=True)
    siapkan_salinan()
    srv, pubs = siapkan_tiruan()
    try:
        bagian_u()
        if "F" in BAGIAN:
            bagian_f()
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
            if b == "P": bagian_p(s0, usang)
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
