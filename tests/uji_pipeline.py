r"""Uji pipeline baru di lingkungan terisolasi: salinan kode, DB uji, WebAPI tiruan.

Cara menjalankan (dari folder proyek, sekitar 35 menit):

    venv\Scripts\python.exe -u tests\uji_pipeline.py > uji_log.txt 2>&1

Hasil akhirnya baris "=== TOTAL: N lulus, M gagal ===" di log. Script ini bukan
suite pytest, dan kode keluarnya tetap 0 meskipun ada yang gagal.

Syarat:
- HANYA untuk keadaan SEBELUM migrasi multi-domain: PDF masih di
  data/publikasi_pdf/ tanpa subfolder, dan data/publikasi_2025_2026.json serta
  data/hasil_ekstraksi.json masih ada. Sejak migrasi 6 November 2026 keadaan itu
  hanya ada di tag Git arsip-sebelum-rombakan (git worktree add ../arsip
  arsip-sebelum-rombakan). Hasil terakhirnya ada di
  data/regresi/laporan-uji-20261105.md.
- Cadangan mysqldump (tanpa --databases) di ~/cadangan-bps/. Yang dipakai adalah
  cadangan terlama.
- MySQL Laragon di path BIN di bawah, dan .env berisi DATABASE_URL. Folder
  sementara sistem harus satu drive dengan proyek, karena PDF uji berupa hardlink.

DB asli, PDF asli, dan server BPS tidak disentuh; keadaan aslinya dibandingkan di
awal dan akhir. Folder kerja dan database uji dihapus di akhir. PDF uji = hardlink,
jadi JANGAN pernah os.utime / menulis ke isinya: ganti berkas hanya lewat os.replace.
"""
import copy, glob, hashlib, json, os, re, shutil, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Folder kerja di LUAR repo: di dalamnya dibuat salinan kode dan hardlink 79 PDF.
SP = os.path.join(tempfile.gettempdir(), "uji_pipeline_bps").replace(os.sep, "/")
os.makedirs(SP, exist_ok=True)
ASLI = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace(os.sep, "/")
UJI = os.path.join(SP, "uji")
SUMBER = os.path.join(SP, "uji_sumber_pdf")
PY = f"{ASLI}/venv/Scripts/python.exe"
BIN = "C:/laragon/bin/mysql/mysql-8.0.30-winx64/bin/"
DB_UJI = "db_uji_pipeline_bps"
KEY = "KUNCIUJIRAHASIA12345"
DUMP = sorted(glob.glob(os.path.expanduser("~/cadangan-bps/db_pencarian_bps-*.sql")))[0]
BASELINE = f"{ASLI}/data/regresi/potret-79-sebelum-rombakan.json"
PORT = 5981

from dotenv import dotenv_values
from sqlalchemy.engine import make_url
url_asli = make_url(dotenv_values(f"{ASLI}/.env")["DATABASE_URL"])
assert url_asli.database == "db_pencarian_bps"
url_uji = url_asli.set(database=DB_UJI)
assert url_uji.database != "db_pencarian_bps"
env_my = {**os.environ}
if url_asli.password: env_my["MYSQL_PWD"] = url_asli.password
dasar = [f"--host={url_asli.host}", f"--port={url_asli.port or 3306}", f"--user={url_asli.username}", "--default-character-set=utf8mb4"]
def sql(q):
    r = subprocess.run([BIN+"mysql.exe", *dasar, "-N", "-B", "-e", q], env=env_my, capture_output=True, text=True, encoding="utf-8")
    if r.returncode: raise SystemExit("mysql: " + r.stderr[:300])
    return r.stdout.strip()

def keadaan_asli():
    """Sidik DB + PDF asli: harus sama persis di awal dan akhir uji."""
    db = url_asli.database
    baris = sql(f"SELECT (SELECT COUNT(*) FROM {db}.publikasi), (SELECT COUNT(*) FROM {db}.entri_dokumen), "
                f"(SELECT MAX(updated_at) FROM {db}.publikasi), (SELECT MAX(id) FROM {db}.entri_dokumen), "
                f"(SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='{db}' AND TABLE_NAME='publikasi')")
    pdf = sorted((os.path.basename(x), os.path.getsize(x), int(os.path.getmtime(x))) for x in glob.glob(f"{ASLI}/data/publikasi_pdf/*.pdf"))
    return baris, hashlib.md5(repr(pdf).encode()).hexdigest(), len(pdf)

hasil_uji = []
def cek(nama, ok, bukti=""):
    hasil_uji.append((nama, bool(ok)))
    print(f"  [{'LULUS' if ok else 'GAGAL'}] {nama}" + (f"  -- {bukti}" if bukti != "" else ""), flush=True)

# ---------------------------- lingkungan ----------------------------
def siapkan():
    if sql(f"SHOW DATABASES LIKE '{DB_UJI}'"):
        sql(f"DROP DATABASE {DB_UJI}")
    sql(f"CREATE DATABASE {DB_UJI} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    with open(DUMP, "rb") as f:
        subprocess.run([BIN+"mysql.exe", *dasar, DB_UJI], env=env_my, stdin=f, check=True)
    shutil.rmtree(UJI, ignore_errors=True); shutil.rmtree(SUMBER, ignore_errors=True)
    os.makedirs(f"{UJI}/data/publikasi_pdf"); os.makedirs(SUMBER)
    for d in ("app", "scripts"):
        shutil.copytree(f"{ASLI}/{d}", f"{UJI}/{d}", ignore=shutil.ignore_patterns("__pycache__", "publikasi_pdf"))
    for f in ("wilayah.json", "kamus_sinonim.json", "publikasi_2025_2026.json", "hasil_ekstraksi.json"):
        shutil.copy2(f"{ASLI}/data/{f}", f"{UJI}/data/{f}")
    for p in glob.glob(f"{ASLI}/data/publikasi_pdf/*.pdf"):
        n = os.path.basename(p)
        os.link(p, f"{UJI}/data/publikasi_pdf/{n}"); os.link(p, f"{SUMBER}/{n}")
    assert len(os.listdir(f"{UJI}/data/publikasi_pdf")) == 79, "harus dijalankan sebelum PDF asli dipindah"

ENV = {**os.environ, "SECRET_KEY": "kunci-uji-acak-" + "x"*30, "ADMIN_PASSWORD_HASH": "scrypt:dummy", "BPS_API_KEY": KEY,
       "BPS_API_BASE_URL": f"http://127.0.0.1:{PORT}/v1/api", "DATABASE_URL": url_uji.render_as_string(hide_password=False),
       "PYTHONUTF8": "1", "PORT": "5000"}
ENV.pop("BPS_DOMAIN", None)

def jalan(skrip, *arg, timeout=1800):
    t = time.time()
    r = subprocess.run([PY, "-u", f"{UJI}/scripts/{skrip}", *arg], cwd=SP, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, r.stdout + r.stderr, time.time() - t
def ringkasan(): return json.load(open(f"{UJI}/data/pembaruan_terakhir.json", encoding="utf-8"))
def aktifkan(*kode):
    w = json.load(open(f"{ASLI}/data/wilayah.json", encoding="utf-8"))
    for x in w["wilayah"]: x["aktif"] = x["kode"] in kode
    json.dump(w, open(f"{UJI}/data/wilayah.json", "w", encoding="utf-8"), ensure_ascii=False)

# ---------------------------- WebAPI tiruan ----------------------------
KEADAAN = {"domain": {}, "gagal_domain": {}, "gagal_halaman": {}, "mode_pdf": {}, "berkas_pdf": {}}
PERMINTAAN = []
class Tiruan(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _kirim(self, kode, isi, jenis="application/json"):
        self.send_response(kode); self.send_header("Content-Type", jenis); self.send_header("Content-Length", str(len(isi))); self.end_headers(); self.wfile.write(isi)
    def do_GET(self):
        PERMINTAAN.append((time.time(), self.path))
        m = re.match(r"/v1/api/list/model/publication/lang/ind/domain/(\d+)/page/(\d+)/key/([^/]+)/", self.path)
        if m:
            d, hal = m.group(1), int(m.group(2))
            mode = KEADAAN["gagal_domain"].get(d) or (KEADAAN["gagal_halaman"].get(d) == hal and "500")
            if mode == "putus": self.connection.close(); return
            if mode: self._kirim(500, b"{}"); return
            pubs = KEADAAN["domain"].get(d, [])
            n = max(1, -(-len(pubs)//10))
            self._kirim(200, json.dumps({"status": "OK", "data-availability": "available", "data": [{"page": hal, "pages": n, "total": len(pubs)}, pubs[(hal-1)*10:hal*10]]}).encode()); return
        m = re.match(r"/pdf/(\w+)", self.path)
        if m:
            pid = m.group(1); mode = KEADAAN["mode_pdf"].get(pid)
            if mode == "500": self._kirim(500, b"x"); return
            if mode == "html": self._kirim(200, b"<html>galat</html>"*200, "text/html"); return
            if mode == "potong":
                self._kirim(200, open(KEADAAN["berkas_pdf"][pid], "rb").read()[:50000], "application/pdf"); return
            self._kirim(200, open(KEADAAN["berkas_pdf"][pid], "rb").read(), "application/pdf"); return
        self._kirim(404, b"{}")

def siapkan_tiruan():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Tiruan)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    pubs = json.load(open(f"{ASLI}/data/publikasi_2025_2026.json", encoding="utf-8"))["publikasi"]
    for p in pubs:
        p["pdf"] = f"http://127.0.0.1:{PORT}/pdf/{p['pub_id']}"
        KEADAAN["berkas_pdf"][p["pub_id"]] = f"{SUMBER}/{p['pub_id']}.pdf"
    KEADAAN["domain"]["6300"] = pubs
    return pubs

def tampil(teks, n=12):
    baris = [b for b in teks.splitlines() if b.strip()]
    print("    | " + "\n    | ".join(baris[-n:]), flush=True)

def main():
    siapkan()
    sys.path.insert(0, UJI)
    for k, v in ENV.items(): os.environ[k] = v
    os.chdir(UJI)

    print("\n=== M. MIGRASI ===", flush=True)
    # M1: PDF hilang -> dibatalkan tanpa isian separuh
    p_hilang = sorted(glob.glob(f"{UJI}/data/publikasi_pdf/*.pdf"))[0]
    os.replace(p_hilang, p_hilang + ".sembunyi")
    kode, keluar, _ = jalan("migrasi_multidomain.py")
    n_null = sql(f"SELECT COUNT(*) FROM {DB_UJI}.publikasi WHERE domain IS NULL")
    cek("M1 PDF hilang: migrasi berhenti, tak ada baris terisi separuh", kode != 0 and n_null == "79", f"exit {kode}, domain kosong {n_null}/79")
    os.replace(p_hilang + ".sembunyi", p_hilang)
    # M2: migrasi normal
    kode, keluar, _ = jalan("migrasi_multidomain.py"); tampil(keluar, 14)
    cek("M2 migrasi berhasil", kode == 0, f"exit {kode}")
    cek("M2 seluruh baris domain 6300", sql(f"SELECT COUNT(*) FROM {DB_UJI}.publikasi WHERE domain='6300' AND wilayah='Provinsi Kalimantan Selatan'") == "79")
    n_usang = sql(f"SELECT COUNT(*) FROM {DB_UJI}.publikasi WHERE updt_date_api IS NOT NULL AND updt_date_diproses IS NULL")
    cek("M2 tepat 7 PDF usang dikosongkan", n_usang == "7", n_usang)
    n_tanpa = sql(f"SELECT COUNT(*) FROM {DB_UJI}.publikasi WHERE updt_date_api IS NULL")
    n_sama = sql(f"SELECT COUNT(*) FROM {DB_UJI}.publikasi WHERE updt_date_api=updt_date_diproses")
    cek("M2 18 tanpa updt_date, 54 sudah cocok", (n_tanpa, n_sama) == ("18", "54"), f"tanpa {n_tanpa}, cocok {n_sama}")
    cek("M2 sidik & diekstrak_pada & catatan terisi", sql(f"SELECT COUNT(*) FROM {DB_UJI}.publikasi WHERE sidik_ukuran IS NOT NULL AND diekstrak_pada IS NOT NULL AND JSON_LENGTH(catatan_ekstraksi)>0") == "79")
    cek("M2 PDF pindah ke 6300/, folder induk bersih", len(glob.glob(f"{UJI}/data/publikasi_pdf/6300/*.pdf")) == 79 and not glob.glob(f"{UJI}/data/publikasi_pdf/*.pdf"))
    kolom = sql(f"SELECT IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='{DB_UJI}' AND TABLE_NAME='publikasi' AND COLUMN_NAME='domain'")
    cek("M2 domain NOT NULL + berindeks", kolom == "NO" and sql(f"SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA='{DB_UJI}' AND INDEX_NAME='ix_publikasi_domain'") == "1")
    # M3: ulang = tanpa perubahan
    sidik1 = sql(f"SELECT SUM(sidik_mtime), COUNT(updt_date_diproses) FROM {DB_UJI}.publikasi")
    kode, keluar, _ = jalan("migrasi_multidomain.py")
    cek("M3 dijalankan ulang: aman dan tak berubah", kode == 0 and sql(f"SELECT SUM(sidik_mtime), COUNT(updt_date_diproses) FROM {DB_UJI}.publikasi") == sidik1, f"exit {kode}")
    # M4 potret
    kode, keluar, _ = jalan("potret_db.py", "ekspor", f"{SP}/uji_potret_m.json")
    kode, keluar, _ = jalan("potret_db.py", "banding", BASELINE, f"{SP}/uji_potret_m.json")
    cek("M4 potret sesudah migrasi IDENTIK baseline", kode == 0 and "IDENTIK" in keluar, keluar.strip().splitlines()[-1][:80])

    print("\n=== P. EKSTRAKSI PENUH 79 PDF LEWAT JALUR BARU (--lokal --paksa) ===", flush=True)
    kode, keluar, dtk = jalan("perbarui.py", "--lokal", "--paksa", timeout=3600); tampil(keluar, 8)
    r = ringkasan()
    cek("P1 79 diproses, 0 gagal, exit 0", kode == 0 and r["diproses"] == 79 and r["diunduh"] == 0 and not r["domain"][0]["gagal"], f"exit {kode}, proses {r['diproses']}, unduh {r['diunduh']}, {dtk:.0f} d, tahap {r['durasi_tahap']}")
    kode, keluar, _ = jalan("potret_db.py", "ekspor", f"{SP}/uji_potret_p.json")
    kode, keluar, _ = jalan("potret_db.py", "banding", BASELINE, f"{SP}/uji_potret_p.json")
    cek("P2 potret sesudah ekstraksi penuh IDENTIK baseline", kode == 0 and "IDENTIK" in keluar, keluar.strip().splitlines()[-1][:90])
    cek("P3 --lokal --paksa TIDAK memajukan 7 PDF usang", sql(f"SELECT COUNT(*) FROM {DB_UJI}.publikasi WHERE updt_date_api IS NOT NULL AND updt_date_diproses IS NULL") == "7")
    cek("P4 tanpa entri NULL normalisasi", sql(f"SELECT COUNT(*) FROM {DB_UJI}.entri_dokumen WHERE teks_ternormalisasi IS NULL") == "0")

    pubs = siapkan_tiruan()
    per_id = {p["pub_id"]: p for p in pubs}
    usang_id = sql(f"SELECT id FROM {DB_UJI}.publikasi WHERE updt_date_api IS NOT NULL AND updt_date_diproses IS NULL").split()
    # publikasi kecil (bukan usang, punya entri) untuk skenario cepat
    uk = sorted((os.path.getsize(f"{SUMBER}/{i}.pdf"), i) for i in per_id if i not in usang_id)
    kecil = [i for _, i in uk][:6]
    def entri_n(i): return int(sql(f"SELECT COUNT(*) FROM {DB_UJI}.entri_dokumen WHERE publikasi_id='{i}'"))
    def kolom_pub(i, k): return sql(f"SELECT {k} FROM {DB_UJI}.publikasi WHERE id='{i}'")

    print("\n=== L. MODE LOKAL (tanpa jaringan) ===", flush=True)
    PERMINTAAN.clear()
    kode, keluar, _ = jalan("perbarui.py", "--lokal"); tampil(keluar, 10)
    r = ringkasan()
    cek("L1 --lokal: tak ada kerja, 7 'menunggu pembaruan online'", kode == 0 and r["status"] == "tidak_ada_baru" and len(r["domain"][0]["menunggu_unduhan"]) == 7, f"exit {kode}, {r['status']}, menunggu {len(r['domain'][0]['menunggu_unduhan'])}")
    cek("L1 --lokal: nol permintaan ke API", not PERMINTAAN, len(PERMINTAAN))

    print("\n=== O. ONLINE PERTAMA: 7 PDF usang diunduh ulang ===", flush=True)
    PERMINTAAN.clear()
    kode, keluar, dtk = jalan("perbarui.py"); tampil(keluar, 22)
    r = ringkasan()
    cek("O1 tepat 7 diunduh + diproses, status sukses, exit 0", kode == 0 and r["status"] == "sukses" and r["diunduh"] == 7 and r["diproses"] == 7, f"exit {kode}, {r['status']}, unduh {r['diunduh']}, proses {r['diproses']}, {dtk:.0f} d")
    cek("O1 updt_date_diproses kini cocok semua", sql(f"SELECT COUNT(*) FROM {DB_UJI}.publikasi WHERE updt_date_api IS NOT NULL AND (updt_date_diproses IS NULL OR updt_date_diproses<>updt_date_api)") == "0")
    cek("O1 durasi 4 tahap tercatat", set(r["durasi_tahap"]) == {"ambil_metadata", "unduh", "ekstraksi", "muat"} and r["durasi_tahap"]["ekstraksi"] > 0, r["durasi_tahap"])
    jeda = [b[0]-a[0] for a, b in zip(PERMINTAAN, PERMINTAAN[1:])]
    cek("O1 jeda antar request >= ~1 detik", min(jeda) >= 0.95, f"minimum {min(jeda):.2f} d dari {len(PERMINTAAN)} permintaan")
    kode, keluar, _ = jalan("potret_db.py", "ekspor", f"{SP}/uji_potret_o.json")
    kode, keluar, _ = jalan("potret_db.py", "banding", BASELINE, f"{SP}/uji_potret_o.json")
    cek("O1 isi sama persis (PDF tiruan = PDF lama)", kode == 0 and "IDENTIK" in keluar, keluar.strip().splitlines()[-1][:80])
    PERMINTAAN.clear()
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan()
    cek("O2 run kedua: tidak ada yang dikerjakan", kode == 0 and r["status"] == "tidak_ada_baru" and r["diproses"] == 0 and not any("/pdf/" in p for _, p in PERMINTAAN), f"{r['status']}, proses {r['diproses']}")

    print("\n=== B. PUBLIKASI BARU & updt_date BERUBAH ===", flush=True)
    id_baru = "aaaabbbbccccddddeeee0001"
    baru = copy.deepcopy(per_id[kecil[0]]); baru.update(pub_id=id_baru, title="Publikasi Tiruan Baru", pdf=f"http://127.0.0.1:{PORT}/pdf/{id_baru}", updt_date=None)
    KEADAAN["berkas_pdf"][id_baru] = f"{SUMBER}/{kecil[0]}.pdf"
    KEADAAN["domain"]["6300"] = pubs + [baru]
    per_id[kecil[1]]["updt_date"] = "2026-11-04"
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan()
    cek("B1 publikasi baru: masuk, entri terisi, teks ternormalisasi terisi", r["publikasi_baru"] and r["publikasi_baru"][0]["pub_id"] == id_baru and entri_n(id_baru) == entri_n(kecil[0]) and kolom_pub(id_baru, "teks_ternormalisasi") != "NULL", f"entri {entri_n(id_baru)}")
    cek("B1 tanpa entri NULL normalisasi", sql(f"SELECT COUNT(*) FROM {DB_UJI}.entri_dokumen WHERE teks_ternormalisasi IS NULL") == "0")
    cek("B2 updt_date berubah: diunduh ulang + diproses", kolom_pub(kecil[1], "updt_date_diproses") == "2026-11-04" and r["diunduh"] == 2, f"diunduh {r['diunduh']}, diproses {kolom_pub(kecil[1], 'updt_date_diproses')}")
    # API mengirim kosong: bukan perubahan, nilai lama dipertahankan
    per_id[kecil[1]]["updt_date"] = None
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan()
    cek("B3 updt_date kosong dari API: bukan perubahan, nilai dipertahankan", r["diproses"] == 0 and kolom_pub(kecil[1], "updt_date_api") == "2026-11-04", f"proses {r['diproses']}, api {kolom_pub(kecil[1], 'updt_date_api')}")
    per_id[kecil[1]]["updt_date"] = "2026-11-04"

    print("\n=== G. UNDUHAN GAGAL (kelas bug 4 publikasi tertinggal) ===", flush=True)
    x = kecil[2]; n0 = entri_n(x); sidik0 = kolom_pub(x, "sidik_mtime"); proses0 = kolom_pub(x, "updt_date_diproses")
    per_id[x]["updt_date"] = "2026-11-05"
    path_x = f"{UJI}/data/publikasi_pdf/6300/{x}.pdf"; md5 = lambda p: hashlib.md5(open(p, "rb").read()).hexdigest(); h0 = md5(path_x)
    for mode in ("500", "html", "potong"):
        KEADAAN["mode_pdf"][x] = mode
        kode, keluar, _ = jalan("perbarui.py"); r = ringkasan(); d = r["domain"][0]
        cek(f"G1 unduh '{mode}': exit 3, sebagian, data+PDF lama utuh, api tersimpan, diproses tak maju",
            kode == 3 and r["status"] == "sebagian" and len(d["gagal"]) == 1 and entri_n(x) == n0 and md5(path_x) == h0 and kolom_pub(x, "updt_date_api") == "2026-11-05" and kolom_pub(x, "updt_date_diproses") == proses0 and not os.path.exists(path_x + ".part"),
            f"exit {kode}, {r['status']}, pesan: {d['gagal'][0]['pesan'][:60] if d['gagal'] else ''}")
    del KEADAAN["mode_pdf"][x]
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan()
    cek("G2 run berikutnya memprosesnya sendiri setelah pulih", kode == 0 and r["diunduh"] == 1 and kolom_pub(x, "updt_date_diproses") == "2026-11-05" and r["status"] == "sukses", f"exit {kode}, {r['status']}, diunduh {r['diunduh']}")

    print("\n=== E. PDF RUSAK DAN PDF 0 ENTRI ===", flush=True)
    y = kecil[3]; n0 = entri_n(y)
    rusak = f"{SP}/rusak.pdf"; open(rusak, "wb").write(b"%PDF-1.4\n" + b"sampah bukan pdf\n"*200 + b"%%EOF\n")
    KEADAAN["berkas_pdf"][y] = rusak; per_id[y]["updt_date"] = "2026-11-05"
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan()
    galat = kolom_pub(y, "galat_ekstraksi")
    cek("E1 PDF tak terbaca: entri lama utuh, galat tercatat, publikasi lain jalan, exit 3", kode == 3 and entri_n(y) == n0 and galat not in ("NULL", "") , f"exit {kode}, entri {entri_n(y)}/{n0}, galat: {galat[:50]}")
    KEADAAN["berkas_pdf"][y] = f"{SUMBER}/{y}.pdf"
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan()
    cek("E2 pulih: galat terhapus, dicoba lagi otomatis", kode == 0 and kolom_pub(y, "galat_ekstraksi") == "NULL" and entri_n(y) == n0, f"exit {kode}, galat {kolom_pub(y,'galat_ekstraksi')}")
    # PDF sah tanpa teks: 0 entri sah, tidak boleh diekstrak ulang tiap run
    id_kosong = "aaaabbbbccccddddeeee0002"
    kosong = f"{SP}/kosong.pdf"
    isi = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
           b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n" + b"%" + b"x"*1200 + b"\n%%EOF\n")
    open(kosong, "wb").write(isi)
    b2 = copy.deepcopy(per_id[kecil[0]]); b2.update(pub_id=id_kosong, title="Publikasi Tiruan Kosong", pdf=f"http://127.0.0.1:{PORT}/pdf/{id_kosong}", updt_date=None)
    KEADAAN["berkas_pdf"][id_kosong] = kosong
    KEADAAN["domain"]["6300"] = pubs + [baru, b2]
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan()
    cek("E3 PDF sah 0 entri: tercatat diekstrak", entri_n(id_kosong) == 0 and kolom_pub(id_kosong, "diekstrak_pada") != "NULL", f"exit {kode}, entri {entri_n(id_kosong)}, diekstrak {kolom_pub(id_kosong,'diekstrak_pada')}; perlu diperiksa: {[c['alasan'] for c in r['domain'][0]['perlu_diperiksa']]}")
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan()
    cek("E4 run berikutnya TIDAK mengekstrak ulang publikasi 0 entri", r["diproses"] == 0, f"proses {r['diproses']}")
    # PDF hilang di disk & PDF diganti di disk
    z = kecil[4]; pz = f"{UJI}/data/publikasi_pdf/6300/{z}.pdf"
    os.remove(pz)
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan()
    cek("E5 PDF hilang: diunduh ulang + diekstrak", kode == 0 and r["diunduh"] == 1 and os.path.exists(pz), f"exit {kode}, diunduh {r['diunduh']}")
    shutil.copy(f"{SUMBER}/{z}.pdf", pz + ".tmpcopy"); os.replace(pz + ".tmpcopy", pz)
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan()
    cek("E6 PDF diganti di disk: diekstrak tanpa unduh", r["diproses"] == 1 and r["diunduh"] == 0, f"proses {r['diproses']}, unduh {r['diunduh']}")
    # --lokal --paksa tidak boleh menandai sudah mengikuti versi baru
    w = kecil[5]; per_id[w]["updt_date"] = "2026-11-05"
    jalan_api = jalan("perbarui.py", "--lokal"); # metadata tak ditarik di mode lokal, jadi api masih lama
    sql(f"UPDATE {DB_UJI}.publikasi SET updt_date_api='2026-11-05' WHERE id='{w}'")
    d0 = kolom_pub(w, "updt_date_diproses")
    subset = sql(f"SELECT COUNT(*) FROM {DB_UJI}.publikasi")
    kode, keluar, _ = jalan("perbarui.py", "--lokal"); r = ringkasan()
    cek("E7 --lokal: updt_date_diproses tak maju, tercatat menunggu", kolom_pub(w, "updt_date_diproses") == d0 and any(m["pub_id"] == w for m in r["domain"][0]["menunggu_unduhan"]), f"diproses {kolom_pub(w,'updt_date_diproses')}")

    print("\n=== T. TRANSAKSI ===", flush=True)
    kode_tx = f"""
import sys; sys.path.insert(0, r'{UJI}')
from app import create_app
from app.models import db, EntriDokumen
from app.services import pipeline_data as P
app = create_app()
with app.app_context():
    n0 = EntriDokumen.query.filter_by(publikasi_id='{x}').count()
    try:
        P.simpan_entri('{x}', [{{'tipe':'tabel','judul':'ok'}},{{'tipe':'TIPE-TIDAK-SAH','judul':'gagal'}}], (1,1), {{}})
        print('TIDAK-GAGAL')
    except Exception as e:
        print('GAGAL-SEPERTI-DIHARAPKAN')
    print('jumlah', n0, EntriDokumen.query.filter_by(publikasi_id='{x}').count())
"""
    r_tx = subprocess.run([PY, "-c", kode_tx], cwd=SP, env=ENV, capture_output=True, text=True, encoding="utf-8")
    baris = r_tx.stdout.split()
    cek("T1 gagal di tengah transaksi: entri lama utuh", "GAGAL-SEPERTI-DIHARAPKAN" in baris and baris[-1] == baris[-2], r_tx.stdout.strip().replace("\n"," | ")+r_tx.stderr[-200:])
    # dibunuh di tengah proses
    per_id[kecil[2]]["updt_date"] = "2026-11-06"
    PERMINTAAN.clear()
    p = subprocess.Popen([PY, "-u", f"{UJI}/scripts/perbarui.py"], cwd=SP, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time()-t0 < 120 and not any("/pdf/" in q for _, q in PERMINTAAN): time.sleep(0.05)
    subprocess.run(["taskkill", "/F", "/PID", str(p.pid)], capture_output=True); p.wait()
    cek("T2 proses dibunuh: kunci basi tertinggal", os.path.exists(f"{UJI}/data/pembaruan.lock"), f"setelah {time.time()-t0:.1f} d")
    cek("T2 proses dibunuh: entri & diproses belum berubah", kolom_pub(kecil[2], "updt_date_diproses") == "2026-11-05" and entri_n(kecil[2]) > 0, kolom_pub(kecil[2], "updt_date_diproses"))
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan()
    cek("T3 run berikutnya menimpa kunci basi dan menyelesaikan", kode == 0 and kolom_pub(kecil[2], "updt_date_diproses") == "2026-11-06" and not os.path.exists(f"{UJI}/data/pembaruan.lock"), f"exit {kode}, {r['status']}")
    # kunci hidup
    p = subprocess.Popen([PY, "-u", f"{UJI}/scripts/perbarui.py"], cwd=SP, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time()-t0 < 60 and not os.path.exists(f"{UJI}/data/pembaruan.lock"): time.sleep(0.05)
    kode, keluar, _ = jalan("perbarui.py")
    cek("T4 pembaruan kedua ditolak exit 2, yang pertama tetap hidup", kode == 2 and p.poll() is None, f"exit {kode}: {keluar.strip()[:70]}")
    p.wait()
    cek("T4 pertama selesai normal", p.returncode == 0, p.returncode)

    print("\n=== D. MULTI-DOMAIN ===", flush=True)
    aktifkan("6300", "6301")
    b63 = copy.deepcopy(per_id[kecil[0]]); id63 = "aaaabbbbccccddddeeee6301"
    b63.update(pub_id=id63, title="Kabupaten Tanah Laut Dalam Angka Tiruan", pdf=f"http://127.0.0.1:{PORT}/pdf/{id63}", updt_date=None)
    KEADAAN["berkas_pdf"][id63] = f"{SUMBER}/{kecil[0]}.pdf"
    KEADAAN["domain"]["6301"] = [b63]
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan(); ds = {d["kode"]: d for d in r["domain"]}
    cek("D1 domain baru tanpa --hanya-periksa: DILEWATI, 6300 tetap jalan", ds["6301"]["status"] == "gagal" and "hanya-periksa" in ds["6301"]["pesan"] and ds["6300"]["status"] in ("tidak_ada_baru", "sukses") and kode == 3, f"exit {kode}, 6301: {ds['6301']['pesan'][:50]}")
    n_63 = sql(f"SELECT COUNT(*) FROM {DB_UJI}.publikasi WHERE domain='6301'")
    cek("D1 tak ada baris 6301 masuk", n_63 == "0", n_63)
    # --hanya-periksa dengan seluruh wilayah; domain yang tak ada datanya kosong
    baris_sebelum = sql(f"SELECT COUNT(*), MAX(updated_at) FROM {DB_UJI}.publikasi")
    pdf_sebelum = len(glob.glob(f"{UJI}/data/publikasi_pdf/*/*.pdf"))
    kode, keluar, dtk = jalan("perbarui.py", "--hanya-periksa"); tampil(keluar, 8)
    lap = json.load(open(f"{UJI}/data/pemeriksaan_domain.json", encoding="utf-8"))
    cek("D2 --hanya-periksa bersih: 14 domain, 0 tabrakan, exit 0", kode == 0 and len(lap["domain_berhasil"]) == 14 and not lap["tabrakan"], f"exit {kode}, {len(lap['domain_berhasil'])} domain, {lap['pub_id_diperiksa']} pub_id, {dtk:.0f} d")
    cek("D2 --hanya-periksa tidak menulis DB / PDF", sql(f"SELECT COUNT(*), MAX(updated_at) FROM {DB_UJI}.publikasi") == baris_sebelum and len(glob.glob(f"{UJI}/data/publikasi_pdf/*/*.pdf")) == pdf_sebelum)
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan(); ds = {d["kode"]: d for d in r["domain"]}
    p63 = f"{UJI}/data/publikasi_pdf/6301/{id63}.pdf"
    cek("D3 setelah lolos: 6301 dimuat ke subfolder + wilayah benar", ds["6301"]["status"] == "sukses" and os.path.exists(p63) and kolom_pub(id63, "wilayah") == "Kab. Tanah Laut" and kolom_pub(id63, "domain") == "6301", f"{ds['6301']['status']}, {kolom_pub(id63,'wilayah')}")
    # satu domain putus jaringan
    KEADAAN["gagal_domain"]["6301"] = "putus"; per_id[kecil[2]]["updt_date"] = "2026-11-07"
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan(); ds = {d["kode"]: d for d in r["domain"]}
    cek("D4 domain putus jaringan: domain lain tetap diproses, exit 3", kode == 3 and r["status"] == "sebagian" and ds["6301"]["status"] == "gagal" and ds["6301"]["jaringan"] and ds["6300"]["status"] == "sukses" and kolom_pub(kecil[2], "updt_date_diproses") == "2026-11-07", f"exit {kode}, {r['status']}, 6300 {ds['6300']['status']}")
    cek("D4 data domain yang gagal tidak disentuh", entri_n(id63) > 0 and kolom_pub(id63, "domain") == "6301")
    del KEADAAN["gagal_domain"]["6301"]
    # halaman tengah gagal -> domain gagal tanpa upsert sebagian
    KEADAAN["gagal_halaman"]["6300"] = 3; judul0 = kolom_pub(pubs[0]["pub_id"], "judul")
    pubs[0]["title"] = "JUDUL SEHARUSNYA TIDAK MASUK"
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan(); ds = {d["kode"]: d for d in r["domain"]}
    cek("D5 halaman ke-3 gagal: domain gagal, metadata tak tersentuh", ds["6300"]["status"] == "gagal" and kolom_pub(pubs[0]["pub_id"], "judul") == judul0, f"{ds['6300']['status']}: {str(ds['6300']['pesan'])[:60]}")
    del KEADAAN["gagal_halaman"]["6300"]; pubs[0]["title"] = judul0
    # API mengembalikan kosong padahal DB berisi
    simpan = KEADAAN["domain"]["6301"]; KEADAAN["domain"]["6301"] = []
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan(); ds = {d["kode"]: d for d in r["domain"]}
    cek("D6 0 publikasi padahal DB berisi: ditolak, data utuh", ds["6301"]["status"] == "gagal" and kolom_pub(id63, "domain") == "6301", str(ds["6301"]["pesan"])[:70])
    KEADAAN["domain"]["6301"] = simpan
    # tabrakan
    t = pubs[1]["pub_id"]; judul_t = kolom_pub(t, "judul"); ent_t = entri_n(t)
    kol = copy.deepcopy(per_id[t]); kol["title"] = "JUDUL DOMAIN LAIN"
    KEADAAN["domain"]["6301"] = [b63, kol]
    kode, keluar, _ = jalan("perbarui.py", "--hanya-periksa"); lap = json.load(open(f"{UJI}/data/pemeriksaan_domain.json", encoding="utf-8"))
    cek("D7 --hanya-periksa: 1 pub_id = TEPAT 1 tabrakan, exit 1", kode == 1 and [x["pub_id"] for x in lap["tabrakan"]] == [t], f"exit {kode}, {len(lap['tabrakan'])} tabrakan")
    # Hanya satu domain yang menyebutnya di API, tapi di DB milik domain lain
    KEADAAN["domain"]["6300"] = [p for p in pubs if p["pub_id"] != t]
    kode, keluar, _ = jalan("perbarui.py", "--hanya-periksa"); lap = json.load(open(f"{UJI}/data/pemeriksaan_domain.json", encoding="utf-8"))
    cek("D7b tabrakan API-vs-DB terdeteksi, tepat 1", kode == 1 and [x["pub_id"] for x in lap["tabrakan"]] == [t] and lap["tabrakan"][0].get("domain_tersimpan") == "6300", f"exit {kode}, {len(lap['tabrakan'])} tabrakan")
    KEADAAN["domain"]["6300"] = pubs + [baru, b2]
    kode, keluar, _ = jalan("perbarui.py", "--hanya-periksa"); lap = json.load(open(f"{UJI}/data/pemeriksaan_domain.json", encoding="utf-8"))
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan(); ds = {d["kode"]: d for d in r["domain"]}
    cek("D8 pengaman: baris domain lain TIDAK ditimpa, dilaporkan, exit 3", kode == 3 and ds["6301"]["status"] == "sebagian" and ds["6301"]["tabrakan"][0]["pub_id"] == t and kolom_pub(t, "judul") == judul_t and kolom_pub(t, "domain") == "6300" and entri_n(t) == ent_t, f"exit {kode}, {ds['6301']['status']}, judul tetap")
    # hilang dari daftar
    KEADAAN["domain"]["6301"] = [kol]
    kode, keluar, _ = jalan("perbarui.py"); r = ringkasan(); ds = {d["kode"]: d for d in r["domain"]}
    cek("D9 publikasi hilang dari daftar API: dilaporkan, tidak dihapus", ds["6301"]["tidak_di_daftar"] and ds["6301"]["tidak_di_daftar"][0]["pub_id"] == id63 and entri_n(id63) > 0, len(ds["6301"]["tidak_di_daftar"]))
    KEADAAN["domain"]["6301"] = [b63]
    aktifkan("6300")

    print("\n=== K. API KEY TIDAK BOCOR ===", flush=True)
    import requests
    try:
        requests.get(f"http://127.0.0.1:9/v1/key/{KEY}/", timeout=2)
    except Exception as e:
        cek("K0 alat uji sah: pesan galat mentah memang memuat key", KEY in str(e))
    bocor = []
    for skenario, env_tambah, arg in (("jaringan putus", {"BPS_API_BASE_URL": "http://127.0.0.1:9/v1/api"}, ()), ("periksa putus", {"BPS_API_BASE_URL": "http://127.0.0.1:9/v1/api"}, ("--hanya-periksa",))):
        e2 = {**ENV, **env_tambah}
        r2 = subprocess.run([PY, "-u", f"{UJI}/scripts/perbarui.py", *arg], cwd=SP, env=e2, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        keluar2 = r2.stdout + r2.stderr
        ada_url = "127.0.0.1" in keluar2
        for nama_b, isi in (("keluaran", keluar2), ("ringkasan", open(f"{UJI}/data/pembaruan_terakhir.json", encoding="utf-8").read()), ("pemeriksaan", open(f"{UJI}/data/pemeriksaan_domain.json", encoding="utf-8").read())):
            if KEY in isi: bocor.append((skenario, nama_b))
        cek(f"K1 {skenario}: gagal dengan pesan, key tersamar", r2.returncode == 1 and "***" in keluar2 and ada_url, f"exit {r2.returncode}")
    cek("K1 key tidak ada di keluaran/ringkasan/laporan", not bocor, bocor)
    r = ringkasan()
    # kembalikan ringkasan jaringan untuk uji halaman admin
    print("\n=== R. ROUTE PDF & HALAMAN ADMIN (test_client) ===", flush=True)
    kode_r = rf"""
import json, os, re, sys
sys.path.insert(0, r'{UJI}')
from app import create_app
from app.models import Publikasi, db
app = create_app(); c = app.test_client()
with app.app_context():
    semua = [(p.id, p.domain) for p in Publikasi.query.all()]
buruk = []
for pid, dom in semua:
    if pid.startswith('aaaabbbb') and not os.path.exists(rf'{UJI}/data/publikasi_pdf/{{dom}}/{{pid}}.pdf'): continue
    r = c.get('/pdf/'+pid)
    isi = r.get_data(); r.close()
    if r.status_code != 200 or r.headers.get('Location') or r.mimetype != 'application/pdf' or isi[:4] != b'%PDF' or len(isi) != os.path.getsize(rf'{UJI}/data/publikasi_pdf/{{dom}}/{{pid}}.pdf') or 'attachment' in r.headers.get('Content-Disposition',''):
        buruk.append((pid, r.status_code))
print('PDF_LOKAL', len(semua), 'buruk', buruk)
r = c.get('/hasil?q=statistik+ekspor'); h = r.get_data(as_text=True)
tautan = re.findall(r'href="(/pdf/[^"]+)"', h)
ok = 0
for t in tautan:
    r = c.get(t.split('#')[0]); ok += r.status_code == 200 and not r.headers.get('Location') and r.get_data()[:4] == b'%PDF'; r.close()
print('TOMBOL', len(tautan), 'ok', ok, 'contoh', tautan[:2])
# berkas hilang -> cadangan redirect ke BPS (bukan 500)
with app.app_context():
    p = Publikasi.query.filter(Publikasi.id=='{usang_id[0]}').first(); dom=p.domain; url=p.url_pdf
path = rf'{UJI}/data/publikasi_pdf/{{dom}}/{usang_id[0]}.pdf'
os.replace(path, path+'.x'); r = c.get('/pdf/{usang_id[0]}'); print('HILANG', r.status_code, r.headers.get('Location') == url); os.replace(path+'.x', path)
print('TAK_ADA', c.get('/pdf/..%2f..%2fapp').status_code, c.get('/pdf/tidakada').status_code)
with c.session_transaction() as s: s['admin_masuk'] = True
F = rf'{UJI}/data/pembaruan_terakhir.json'
contoh = {{
 'sebagian': {{'status':'sebagian','selesai_pada':'2026-11-05T01:00:00+00:00','jaringan':False,'jumlah_publikasi':80,'publikasi_baru':[{{'pub_id':'x','judul':'Judul Baru <b>','entri':5,'wilayah':'Kab. Tapin'}}],'entri_sebelum':10,'entri_sesudah':15,'durasi_detik':60,'durasi_tahap':{{'ambil_metadata':1.5,'unduh':2.5,'ekstraksi':3.5,'muat':0.5}},
   'domain':[{{'kode':'6300','wilayah':'Provinsi Kalimantan Selatan','status':'sebagian','pesan':None,'jumlah_publikasi':79,'diunduh':1,'diproses':0,'gagal':[{{'judul':'Judul Gagal','tahap':'unduh','pesan':'HTTP 500'}}],'tabrakan':[{{'pub_id':'id1','domain_lain':'6301','judul_api':'Judul Tabrakan'}}],'tidak_di_daftar':[{{'pub_id':'y','judul':'z'}}],'menunggu_unduhan':[{{'pub_id':'m'}}],'perlu_diperiksa':[]}},
             {{'kode':'6301','wilayah':'Kab. Tanah Laut','status':'gagal','pesan':'halaman 1: putus','jumlah_publikasi':0,'diunduh':0,'diproses':0,'gagal':[],'tabrakan':[],'tidak_di_daftar':[],'menunggu_unduhan':[],'perlu_diperiksa':[]}}]}},
 'sukses': {{'status':'sukses','selesai_pada':'2026-11-05T01:00:00+00:00','jaringan':False,'jumlah_publikasi':80,'publikasi_baru':[],'entri_sebelum':10,'entri_sesudah':15,'durasi_detik':60,'durasi_tahap':{{'ambil_metadata':1,'unduh':2,'ekstraksi':3,'muat':4}},'domain':[]}},
 'tidak_ada_baru': {{'status':'tidak_ada_baru','selesai_pada':'2026-11-05T01:00:00+00:00','jaringan':False,'jumlah_publikasi':80,'durasi_detik':60,'publikasi_baru':[],'domain':[{{'kode':'6300','wilayah':'Provinsi Kalimantan Selatan','status':'tidak_ada_baru','pesan':None,'jumlah_publikasi':79,'diunduh':0,'diproses':0,'gagal':[],'tabrakan':[],'tidak_di_daftar':[],'menunggu_unduhan':[],'perlu_diperiksa':[]}}],'durasi_tahap':{{'ambil_metadata':1,'unduh':0,'ekstraksi':0,'muat':0}}}},
 'gagal_jaringan': {{'status':'gagal','selesai_pada':'2026-11-05T01:00:00+00:00','jaringan':True,'durasi_detik':5,'domain':[]}},
 'gagal_lain': {{'status':'gagal','selesai_pada':'2026-11-05T01:00:00+00:00','jaringan':False,'tahap':'konfigurasi','durasi_detik':5}},
 'lama_sukses': {{'status':'sukses','selesai_pada':'2026-09-15T01:00:00+00:00','jumlah_publikasi':74,'publikasi_baru':[{{'pub_id':'x','judul':'Format Lama','entri':3}}],'entri_sebelum':1,'entri_sesudah':4,'diekstrak_ulang':0,'durasi_detik':179}},
 'lama_tidak_ada': {{'jumlah_publikasi':79,'durasi_detik':175,'status':'tidak_ada_baru','selesai_pada':'2026-11-05T01:53:19+00:00'}},
}}
harap = {{'sebagian':['selesai sebagian','Kab. Tanah Laut','Sebagian gagal','Judul Gagal','Judul Tabrakan','halaman 1: putus','menunggu pembaruan online','tidak lagi ada','ambil daftar 1.5','&lt;b&gt;'],'sukses':['Pembaruan selesai','simpan 4'],'tidak_ada_baru':['Tidak ada publikasi baru','Tidak ada yang baru'],'gagal_jaringan':['BPS - Pegawai'],'gagal_lain':['di tahap konfigurasi'],'lama_sukses':['Format Lama','179 detik'],'lama_tidak_ada':['Tidak ada publikasi baru','175 detik']}}
for nama, isi in contoh.items():
    json.dump(isi, open(F,'w',encoding='utf-8'))
    r = c.get('/admin/perbarui'); h = r.get_data(as_text=True)
    kurang = [x for x in harap[nama] if x not in h]
    print('ADMIN', nama, r.status_code, 'kurang', kurang)
os.remove(F)
r = c.get('/admin/perbarui'); print('ADMIN tanpa_berkas', r.status_code, 'kurang', [])
"""
    r_r = subprocess.run([PY, "-c", kode_r], cwd=SP, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    print(r_r.stdout, r_r.stderr[-1500:], flush=True)
    keluar_r = r_r.stdout
    m = re.search(r"PDF_LOKAL (\d+) buruk (.*)", keluar_r)
    cek("R1 /pdf/<id> menyajikan berkas lokal untuk semua publikasi", m and m.group(2) == "[]", m.group(0)[:100] if m else r_r.stderr[-200:])
    m = re.search(r"TOMBOL (\d+) ok (\d+)", keluar_r)
    cek("R2 tombol Buka PDF di /hasil -> berkas lokal, tanpa redirect", m and int(m.group(1)) > 0 and m.group(1) == m.group(2), m.group(0) if m else "")
    cek("R3 berkas hilang -> cadangan redirect ke url_pdf", "HILANG 302 True" in keluar_r)
    cek("R4 id tak dikenal -> 404", "TAK_ADA 404 404" in keluar_r)
    admin = re.findall(r"ADMIN (\w+) (\d+) kurang (.*)", keluar_r)
    cek("R5 /admin/perbarui merender semua status + format lama", len(admin) == 8 and all(a[1] == "200" and a[2] == "[]" for a in admin), admin)

    print("\n=== W. TOMBOL WEB + .BAT SUNGGUHAN ===", flush=True)
    # Satu publikasi unduhannya gagal -> status sebagian (exit 3)
    v = kecil[2]; per_id[v]["updt_date"] = "2026-11-08"; KEADAAN["mode_pdf"][v] = "500"
    kode_web = rf"""
import sys, time
sys.path.insert(0, r'{UJI}')
from app import create_app
app = create_app(); c = app.test_client()
with c.session_transaction() as s: s['admin_masuk'] = True
r = c.post('/admin/perbarui/mulai'); print('MULAI', r.status_code)
r = c.post('/admin/perbarui/mulai'); h = c.get('/admin/perbarui').get_data(as_text=True); print('KEDUA_NONAKTIF', 'sedang berjalan' in h)
t = time.time()
while time.time()-t < 300:
    h = c.get('/admin/perbarui').get_data(as_text=True)
    if 'Pembaruan sedang berjalan' not in h: break
    time.sleep(1)
print('SEBAGIAN_TAMPIL', 'selesai sebagian' in h, 'JUDUL_GAGAL', {per_id[v]['title'][:30]!r} in h, 'LOG', 'halaman 1/' in h)
"""
    r_w = subprocess.run([PY, "-c", kode_web], cwd=SP, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=400)
    print("    | " + r_w.stdout.strip().replace("\n", "\n    | "), r_w.stderr[-500:], flush=True)
    cek("W1 tombol web: berjalan, POST kedua ditolak, ringkasan 'sebagian' + judul gagal + log tampil", "MULAI 302" in r_w.stdout and "KEDUA_NONAKTIF True" in r_w.stdout and "SEBAGIAN_TAMPIL True JUDUL_GAGAL True LOG True" in r_w.stdout)
    del KEADAAN["mode_pdf"][v]

    # .bat: python/activate palsu mengarah ke venv asli, TANPA junction ke venv
    os.makedirs(f"{UJI}/venv/Scripts", exist_ok=True)
    open(f"{UJI}/venv/Scripts/python.exe", "wb").close()
    with open(f"{UJI}/venv/Scripts/activate.bat", "w", newline="") as f:
        jalur = ASLI.replace("/", chr(92)) + chr(92) + "venv" + chr(92) + "Scripts"
        f.write('@set "PATH=' + jalur + ';%PATH%"' + chr(13) + chr(10))
    shutil.copy2(f"{ASLI}/perbarui-data.bat", f"{UJI}/perbarui-data.bat")
    open(f"{UJI}/.env", "w").write("# kosong: nilai uji datang dari variabel lingkungan\n")
    isi_bat = open(f"{ASLI}/perbarui-data.bat", "rb").read()
    cek("W2 .bat tetap ASCII + CRLF", all(x < 128 for x in isi_bat) and b"\n" not in isi_bat.replace(b"\r\n", b""))
    def bat():
        r = subprocess.run(["cmd", "/c", os.path.normpath(f"{UJI}/perbarui-data.bat")], cwd=UJI, env=ENV, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=400)
        return r.stdout + r.stderr
    per_id[v]["updt_date"] = "2026-11-09"; KEADAAN["mode_pdf"][v] = "500"
    k = bat(); cek("W3 .bat exit 3 -> SELESAI SEBAGIAN", "PEMBARUAN SELESAI SEBAGIAN" in k and "PEMBARUAN GAGAL" not in k, [b.strip() for b in k.splitlines() if "PEMBARUAN" in b][:2])
    del KEADAAN["mode_pdf"][v]
    k = bat(); cek("W4 .bat exit 0 -> PEMBARUAN SELESAI.", "PEMBARUAN SELESAI." in k and "SEBAGIAN" not in k, [b.strip() for b in k.splitlines() if "PEMBARUAN" in b][:2])
    KEADAAN["gagal_domain"]["6300"] = "putus"
    k = bat(); cek("W5 .bat exit 1 -> PEMBARUAN GAGAL + pesan jaringan", "PEMBARUAN GAGAL" in k and "tidak bisa dihubungi" in k, [b.strip() for b in k.splitlines() if "PEMBARUAN" in b][:2])
    del KEADAAN["gagal_domain"]["6300"]
    p = subprocess.Popen([PY, "-u", f"{UJI}/scripts/perbarui.py"], cwd=SP, env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time()-t0 < 60 and not os.path.exists(f"{UJI}/data/pembaruan.lock"): time.sleep(0.05)
    k = bat(); cek("W6 .bat saat terkunci -> TIDAK DIJALANKAN", "TIDAK DIJALANKAN" in k, [b.strip() for b in k.splitlines() if "DIJALANKAN" in b][:1])
    p.wait()

    # ------------------------------- penutup -------------------------------
    gagal = [n for n, ok in hasil_uji if not ok]
    print(f"\n=== TOTAL: {len(hasil_uji)-len(gagal)} lulus, {len(gagal)} gagal ===")
    for n in gagal: print("  GAGAL:", n)

if __name__ == "__main__":
    awal_asli = keadaan_asli()
    print("Keadaan asli di awal:", awal_asli, flush=True)
    try:
        main()
    finally:
        os.chdir(SP)
        akhir_asli = keadaan_asli()
        print("Keadaan asli di akhir:", akhir_asli, "| SAMA:", akhir_asli == awal_asli)
        # Hapus hardlink saja; isi berkas asli tetap karena masih ada nama lain.
        for d in (UJI, SUMBER):
            shutil.rmtree(d, ignore_errors=True)
            print("folder dihapus:", os.path.basename(d), not os.path.exists(d))
        for f in ("rusak.pdf", "kosong.pdf", "uji_potret_m.json", "uji_potret_o.json", "uji_potret_p.json"):
            if os.path.exists(f"{SP}/{f}"): os.remove(f"{SP}/{f}")
        print("Sesudah pembersihan, keadaan asli:", keadaan_asli()[1:] == awal_asli[1:], flush=True)
        os.chdir(ASLI)
        try:
            os.rmdir(SP)
        except OSError:
            pass
        try:
            if sql(f"SHOW DATABASES LIKE '{DB_UJI}'"): sql(f"DROP DATABASE {DB_UJI}")
            print("DB uji dihapus:", not sql(f"SHOW DATABASES LIKE '{DB_UJI}'"))
        except SystemExit as e:
            print(e)
