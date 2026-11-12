"""mysqldump db_pencarian_bps ke luar repo, lalu pulihkan ke DB SALINAN
db_uji_batas_heading (bukti bisa dipulihkan + tempat uji pemuatan).
Produksi hanya DIBACA. Kredensial lewat MYSQL_PWD; tidak pernah dicetak."""
import datetime
import hashlib
import os
import subprocess
import sys

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

load_dotenv(".env")
u = make_url(os.environ["DATABASE_URL"])
assert u.database == "db_pencarian_bps", "nama database tak terduga"
BIN = "C:/laragon/bin/mysql/mysql-8.0.30-winx64/bin/"
env = {**os.environ}
if u.password:
    env["MYSQL_PWD"] = u.password
dasar = [f"--host={u.host or '127.0.0.1'}", f"--port={u.port or 3306}", f"--user={u.username}",
         "--default-character-set=utf8mb4"]
DIR = "C:/Users/Dani/cadangan-bps"
UJI = "db_uji_batas_heading"


def sql(q, db=None):
    r = subprocess.run([BIN + "mysql.exe", *dasar, "-N", "-B", "-e", q] + ([db] if db else []),
                       env=env, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise SystemExit("mysql gagal: " + r.stderr[:300])
    return r.stdout.strip()


if sql(f"SHOW DATABASES LIKE '{UJI}'"):
    raise SystemExit(f"{UJI} sudah ada, berhenti")
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
berkas = f"{DIR}/db_pencarian_bps-{stamp}-sebelum-batas-heading.sql"
# TANPA --databases: dump tidak memuat USE, jadi tidak mungkin menimpa DB asli.
r = subprocess.run([BIN + "mysqldump.exe", *dasar, "--single-transaction", "--routines", "--triggers",
                    "--events", "--hex-blob", "--no-tablespaces", f"--result-file={berkas}", u.database],
                   env=env, capture_output=True, text=True)
print("mysqldump exit", r.returncode, r.stderr.strip()[:200])
if r.returncode:
    sys.exit(1)
isi = open(berkas, "rb").read()
print("berkas:", berkas, f"{len(isi) / 1024 / 1024:.1f} MB | SHA-256:", hashlib.sha256(isi).hexdigest())
print("memuat USE/CREATE DATABASE:", b"\nUSE " in isi or b"CREATE DATABASE" in isi)
sql(f"CREATE DATABASE {UJI} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
with open(berkas, "rb") as f:
    r = subprocess.run([BIN + "mysql.exe", *dasar, UJI], env=env, stdin=f, capture_output=True)
print("pemulihan exit", r.returncode, r.stderr.decode("utf-8", "replace").strip()[:200])
tabel = sql("SHOW TABLES", u.database).split()
semua_sama = True
for t in tabel:
    a = sql(f"SELECT COUNT(*) FROM `{t}`", u.database)
    b = sql(f"SELECT COUNT(*) FROM `{t}`", UJI)
    ca = sql(f"CHECKSUM TABLE `{t}`", u.database).split()[-1]
    cb = sql(f"CHECKSUM TABLE `{t}`", UJI).split()[-1]
    semua_sama &= (a == b and ca == cb)
    print(f"  {t:<22}{a:>8}{b:>8}  checksum {'sama' if ca == cb else 'BEDA'}")
print("SALINAN IDENTIK DENGAN PRODUKSI:", semua_sama)
