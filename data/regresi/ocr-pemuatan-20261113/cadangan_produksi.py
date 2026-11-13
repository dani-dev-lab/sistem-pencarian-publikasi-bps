"""mysqldump db_pencarian_bps ke luar repo, lalu buktikan bisa dipulihkan di DB uji terpisah.
Kredensial lewat MYSQL_PWD; tidak pernah dicetak."""
import os, subprocess, sys, datetime, hashlib
from dotenv import load_dotenv
from sqlalchemy.engine import make_url
load_dotenv(".env")
u = make_url(os.environ["DATABASE_URL"])
assert u.database == "db_pencarian_bps", "nama database tak terduga"
BIN = "C:/laragon/bin/mysql/mysql-8.0.30-winx64/bin/"
env = {**os.environ}
if u.password: env["MYSQL_PWD"] = u.password
dasar = [f"--host={u.host or '127.0.0.1'}", f"--port={u.port or 3306}", f"--user={u.username}", "--default-character-set=utf8mb4"]
DIR = "C:/Users/Dani/cadangan-bps"
os.makedirs(DIR, exist_ok=True)
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
berkas = f"{DIR}/db_pencarian_bps-{stamp}-sebelum-muat-ocr.sql"
# TANPA --databases: dump tidak memuat USE, jadi tidak mungkin menimpa DB asli saat diuji.
r = subprocess.run([BIN+"mysqldump.exe", *dasar, "--single-transaction", "--routines", "--triggers", "--events", "--hex-blob", "--no-tablespaces", f"--result-file={berkas}", u.database], env=env, capture_output=True, text=True)
print("mysqldump exit", r.returncode, r.stderr.strip()[:300])
if r.returncode: sys.exit(1)
isi = open(berkas, "rb").read()
print("berkas:", berkas, f"{len(isi)/1024/1024:.1f} MB")
print("SHA-256:", hashlib.sha256(isi).hexdigest())
print("ekor:", isi[-60:].decode("utf-8","replace").strip())
print("memuat USE/CREATE DATABASE:", b"\nUSE " in isi or b"CREATE DATABASE" in isi)

UJI = "db_uji_cadangan_bps"
def sql(q, db=None):
    a = [BIN+"mysql.exe", *dasar, "-N", "-B", "-e", q] + ([db] if db else [])
    r = subprocess.run(a, env=env, capture_output=True, text=True, encoding="utf-8")
    if r.returncode: raise SystemExit("mysql gagal: " + r.stderr[:300])
    return r.stdout.strip()
if sql(f"SHOW DATABASES LIKE '{UJI}'"): raise SystemExit(f"{UJI} sudah ada, berhenti")
sql(f"CREATE DATABASE {UJI} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
try:
    with open(berkas, "rb") as f:
        r = subprocess.run([BIN+"mysql.exe", *dasar, UJI], env=env, stdin=f, capture_output=True)
    print("pemulihan exit", r.returncode, r.stderr.decode("utf-8","replace").strip()[:300])
    tabel = sql("SHOW TABLES", u.database).split()
    print(f"{'tabel':<22}{'baris asli':>11}{'baris pulih':>12}  checksum sama")
    semua = True
    for t in tabel:
        n1 = sql(f"SELECT COUNT(*) FROM `{t}`", u.database); n2 = sql(f"SELECT COUNT(*) FROM `{t}`", UJI)
        c1 = sql(f"CHECKSUM TABLE `{t}`", u.database).split()[-1]; c2 = sql(f"CHECKSUM TABLE `{t}`", UJI).split()[-1]
        ok = n1 == n2 and c1 == c2; semua &= ok
        print(f"{t:<22}{n1:>11}{n2:>12}  {ok}")
    print("CADANGAN TERBUKTI PULIH:", semua)
finally:
    sql(f"DROP DATABASE {UJI}")
    print("DB uji dihapus:", not sql(f"SHOW DATABASES LIKE '{UJI}'"))
