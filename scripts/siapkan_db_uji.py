"""Buat database uji (salinan produksi) untuk KonfigurasiUji, kalau belum ada.

Database uji = nama database di DATABASE_URL + "_uji" (db_pencarian_bps_uji),
di server MySQL yang sama. Lihat url_database_uji() di app/config.py.

Sifat:
- produksi hanya DIBACA (mysqldump --single-transaction);
- kalau database uji SUDAH ada, tidak diapa-apakan. Skrip ini tidak pernah
  menghapus atau menimpa. Untuk menyegarkan salinan yang usang, hapus dulu
  database ujinya secara manual, lalu jalankan lagi;
- dump dialirkan langsung ke database uji, tanpa berkas sementara. Dump dibuat
  TANPA --databases, jadi tidak memuat "USE" dan tidak mungkin menulis ke
  database produksi;
- sesudahnya jumlah baris dan CHECKSUM TABLE tiap tabel dibandingkan.
- Kata sandi MySQL lewat variabel lingkungan MYSQL_PWD, tidak pernah dicetak.

Jalankan (dari folder proyek):
  venv\\Scripts\\python.exe scripts\\siapkan_db_uji.py
"""

import os
import subprocess
import sys

DIR_PROYEK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR_PROYEK)

from sqlalchemy.engine import make_url  # noqa: E402

from app.config import Config, KonfigurasiUji, periksa_database_uji, program_mysql  # noqa: E402


def cari_program(nama):
    """mysql / mysqldump: MYSQL_BIN di .env, lalu PATH (app.config.program_mysql)."""
    return program_mysql(nama)


def main():
    periksa_database_uji(KonfigurasiUji)
    produksi = make_url(Config.SQLALCHEMY_DATABASE_URI)
    uji = make_url(KonfigurasiUji.SQLALCHEMY_DATABASE_URI)
    if not produksi.drivername.startswith("mysql"):
        raise SystemExit("DATABASE_URL bukan MySQL; skrip ini hanya untuk MySQL.")

    mysql, mysqldump = cari_program("mysql"), cari_program("mysqldump")
    env = {**os.environ}
    if produksi.password:
        env["MYSQL_PWD"] = produksi.password
    dasar = [f"--host={produksi.host or '127.0.0.1'}", f"--port={produksi.port or 3306}",
             f"--user={produksi.username}", "--default-character-set=utf8mb4"]

    def sql(perintah, db=None):
        r = subprocess.run([mysql, *dasar, "-N", "-B", "-e", perintah] + ([db] if db else []),
                           env=env, capture_output=True, text=True, encoding="utf-8")
        if r.returncode:
            raise SystemExit("mysql gagal: " + r.stderr.strip()[:300])
        return r.stdout.strip()

    print(f"produksi : {produksi.database}")
    print(f"uji      : {uji.database}")
    if sql(f"SHOW DATABASES LIKE '{uji.database}'"):
        print("Database uji SUDAH ADA - tidak diubah. Untuk menyegarkannya, hapus dulu "
              "secara manual lalu jalankan skrip ini lagi.")
        return 0

    charset, collation = sql(
        "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA "
        f"WHERE SCHEMA_NAME = '{produksi.database}'").split()
    sql(f"CREATE DATABASE `{uji.database}` CHARACTER SET {charset} COLLATE {collation}")
    print(f"database uji dibuat ({charset} / {collation}); menyalin ...")

    dump = subprocess.Popen(
        [mysqldump, *dasar, "--single-transaction", "--routines", "--triggers", "--events",
         "--hex-blob", "--no-tablespaces", produksi.database],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    muat = subprocess.run([mysql, *dasar, uji.database], env=env, stdin=dump.stdout,
                          capture_output=True)
    dump.stdout.close()
    galat_dump = dump.stderr.read().decode("utf-8", "replace").strip()
    if dump.wait() or muat.returncode:
        raise SystemExit("PENYALINAN GAGAL (database uji sudah dibuat, isinya tidak lengkap; "
                         "hapus manual sebelum mencoba lagi):\n  mysqldump: "
                         + galat_dump[:300] + "\n  mysql: "
                         + muat.stderr.decode("utf-8", "replace").strip()[:300])

    print(f"\n  {'tabel':<22}{'produksi':>10}{'uji':>10}  checksum")
    semua_sama = True
    for t in sql("SHOW TABLES", produksi.database).split():
        a = sql(f"SELECT COUNT(*) FROM `{t}`", produksi.database)
        b = sql(f"SELECT COUNT(*) FROM `{t}`", uji.database)
        ca = sql(f"CHECKSUM TABLE `{t}`", produksi.database).split()[-1]
        cb = sql(f"CHECKSUM TABLE `{t}`", uji.database).split()[-1]
        sama = a == b and ca == cb
        semua_sama &= sama
        print(f"  {t:<22}{a:>10}{b:>10}  {'sama' if sama else 'BEDA'}")
    print("\nSALINAN IDENTIK DENGAN PRODUKSI:", "YA" if semua_sama else
          "TIDAK (bisa karena produksi berubah selama penyalinan, mis. log pencarian baru)")
    return 0 if semua_sama else 1


if __name__ == "__main__":
    sys.exit(main())
