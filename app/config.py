"""Baca .env dan sediakan konfigurasi aplikasi (termasuk koneksi database)."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Nilai yang dulu dipakai sebagai fallback pengembangan. Sekarang ditolak:
# kalau masih ini, siapa pun yang membaca kode sumber bisa memalsukan session.
SECRET_KEY_LAMA = "kunci-pengembangan-lokal"


class Config:
    # `or ""`, bukan nilai default os.getenv: variabel yang ADA tapi KOSONG
    # di .env tetap mengembalikan "" - dan itu memang mau ditangkap sebagai
    # "belum diisi" oleh periksa_konfigurasi().
    SECRET_KEY = os.getenv("SECRET_KEY") or ""

    # Hash kata sandi halaman admin (dibuat dengan scripts/buat_hash_sandi.py).
    # Satu sandi bersama, bukan akun per orang.
    ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH") or ""

    # Port bawaan server. Opsional; --port di baris perintah menimpanya.
    # Disimpan sebagai teks dan divalidasi di periksa_konfigurasi() supaya
    # salah ketik ("80800", "lima ribu") ditolak dengan pesan, bukan traceback.
    PORT = (os.getenv("PORT") or "5000").strip()

    # WebAPI BPS
    BPS_API_KEY = os.getenv("BPS_API_KEY", "")
    BPS_API_BASE_URL = os.getenv("BPS_API_BASE_URL", "https://webapi.bps.go.id/v1/api")

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'pencarian_bps.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Berkas .env yang ditulis ulang saat sandi admin diganti lewat browser.
    FILE_ENV = BASE_DIR / ".env"

    # Path data
    DIR_PUBLIKASI_PDF = BASE_DIR / "data" / "publikasi_pdf"
    DIR_SAMPEL_PDF = BASE_DIR / "data" / "sampel_pdf"
    FILE_KAMUS_SINONIM = BASE_DIR / "data" / "kamus_sinonim.json"
    FILE_WILAYAH = BASE_DIR / "data" / "wilayah.json"

    # Rekam tiap pencarian di /hasil ke log_pencarian. Sengaja TIDAK dibaca
    # dari .env: log ini bahan perbaikan kamus sinonim, dan satu baris salah di
    # .env server akan mematikannya tanpa ada yang sadar. Yang mematikannya
    # hanya KonfigurasiUji di bawah, supaya pemeriksaan route /hasil tidak
    # mengisi log dengan kueri buatan.
    CATAT_LOG_PENCARIAN = True


def url_database_uji(url_produksi):
    """URL database uji: server yang sama, nama database + '_uji'.

    db_pencarian_bps -> db_pencarian_bps_uji. Diturunkan dari DATABASE_URL,
    bukan ditulis terpisah di .env, supaya tidak ada isian kedua yang bisa
    keliru diisi nama database produksi.
    """
    u = make_url(url_produksi)
    if u.drivername.startswith("sqlite"):
        p = Path(u.database)
        u = u.set(database=str(p.with_name(f"{p.stem}_uji{p.suffix}")))
    else:
        u = u.set(database=f"{u.database}_uji")
    # str(URL) menyamarkan sandi menjadi "***" di SQLAlchemy 2.x.
    return u.render_as_string(hide_password=False)


class KonfigurasiUji(Config):
    """Konfigurasi untuk pengujian: database UJI terpisah, log tidak ditulis.

    Database-nya salinan produksi (db_pencarian_bps_uji), dibuat dengan
    scripts/siapkan_db_uji.py. Uji yang lewat create_app(KonfigurasiUji)
    karena itu tidak bisa mengubah data atau skema produksi - termasuk
    ALTER TABLE dari skema.pastikan_kolom() di awal request.

    Salinan tidak ikut diperbarui sendiri: isinya keadaan produksi saat
    salinan dibuat.

    Pakai: create_app(KonfigurasiUji).
    """
    KONFIGURASI_UJI = True
    SQLALCHEMY_DATABASE_URI = url_database_uji(Config.SQLALCHEMY_DATABASE_URI)
    CATAT_LOG_PENCARIAN = False


def periksa_database_uji(config_class):
    """Tolak berjalan kalau konfigurasi uji menunjuk ke database produksi.

    Produksi = database di DATABASE_URL (Config). Dibandingkan menurut NAMA
    database, jadi juga menangkap subclass yang menimpa
    SQLALCHEMY_DATABASE_URI dengan URL lain yang ujungnya sama. Dipanggil
    dari periksa_konfigurasi() dan dari scripts/siapkan_db_uji.py.
    """
    if not getattr(config_class, "KONFIGURASI_UJI", False):
        return
    nama_uji = make_url(config_class.SQLALCHEMY_DATABASE_URI).database
    nama_produksi = make_url(Config.SQLALCHEMY_DATABASE_URI).database
    if not nama_uji or nama_uji == nama_produksi:
        garis = "=" * 72
        raise SystemExit(
            f"\n{garis}\nKONFIGURASI UJI MENUNJUK KE DATABASE PRODUKSI - tidak dijalankan\n"
            f"{garis}\n\n"
            f"  {config_class.__name__} memakai database {nama_uji!r}, sama dengan\n"
            f"  database produksi di DATABASE_URL. Uji harus memakai salinan\n"
            f"  (lihat url_database_uji() di app/config.py dan\n"
            f"  scripts/siapkan_db_uji.py).\n{garis}"
        )


PESAN_SECRET_KEY = """\
SECRET_KEY di .env kosong atau masih memakai nilai bawaan pengembangan.

  SECRET_KEY mengamankan session login admin. Nilainya harus acak dan
  rahasia. Buat nilai baru dengan perintah:

      venv\\Scripts\\python.exe -c "import secrets; print(secrets.token_hex(32))"

  lalu salin hasilnya ke berkas .env pada baris:

      SECRET_KEY=<hasil perintah di atas>
"""

PESAN_ADMIN_HASH = """\
ADMIN_PASSWORD_HASH di .env kosong.

  Halaman /admin/ dilindungi kata sandi dan aplikasi TIDAK akan berjalan
  tanpa sandi itu ditetapkan. Buat hash-nya dengan perintah:

      venv\\Scripts\\python.exe scripts\\buat_hash_sandi.py

  lalu salin baris yang dicetak ke berkas .env.
"""


def periksa_konfigurasi(config_class=Config):
    """Tolak berjalan kalau .env belum lengkap. Dipanggil dari create_app().

    Dibuat gagal KERAS dengan pesan yang menjelaskan cara memperbaikinya,
    bukan diam-diam memakai nilai bawaan - nilai bawaan yang tersimpan di
    kode sumber sama saja dengan tidak ada pengamanan.
    """
    periksa_database_uji(config_class)
    masalah = []
    if not config_class.SECRET_KEY or config_class.SECRET_KEY == SECRET_KEY_LAMA:
        masalah.append(PESAN_SECRET_KEY)
    if not config_class.ADMIN_PASSWORD_HASH:
        masalah.append(PESAN_ADMIN_HASH)
    if not (config_class.PORT.isdigit() and 1 <= int(config_class.PORT) <= 65535):
        masalah.append(
            f"PORT di .env tidak valid: {config_class.PORT!r}.\n\n"
            "  Isi dengan angka 1-65535 (misalnya PORT=8080), atau kosongkan\n"
            "  supaya memakai 5000.\n")
    if masalah:
        garis = "=" * 72
        raise SystemExit(
            f"\n{garis}\nKONFIGURASI BELUM LENGKAP - aplikasi tidak dijalankan\n"
            f"{garis}\n\n" + "\n".join(masalah)
            + f"\nContoh isian lengkap ada di .env.example.\n{garis}"
        )


# Berlaku untuk halaman /admin/sandi maupun scripts/buat_hash_sandi.py.
PANJANG_SANDI_MINIMAL = 8


def tulis_admin_hash(path_env, hash_baru):
    """Ganti HANYA baris ADMIN_PASSWORD_HASH di .env, sisanya utuh byte demi byte.

    Berkas dibaca dan ditulis dengan newline="" supaya gaya akhir baris (LF
    atau CRLF) tidak diubah. Ditulis ke berkas sementara dulu lalu os.replace,
    jadi proses yang terputus di tengah tidak pernah meninggalkan .env yang
    separuh tertulis - .env rusak berarti aplikasi tidak bisa dijalankan
    sama sekali.

    Return True kalau baris lama ditemukan dan diganti, False kalau baris
    ditambahkan di akhir karena belum ada.
    """
    path_env = str(path_env)
    with open(path_env, encoding="utf-8", newline="") as f:
        baris_semua = f.readlines()

    diganti = False
    for i, baris in enumerate(baris_semua):
        if baris.startswith("ADMIN_PASSWORD_HASH="):
            akhir = baris[len(baris.rstrip("\r\n")):]   # pertahankan LF/CRLF
            baris_semua[i] = f"ADMIN_PASSWORD_HASH={hash_baru}{akhir}"
            diganti = True
            break
    if not diganti:
        if baris_semua and not baris_semua[-1].endswith("\n"):
            baris_semua[-1] += "\n"
        baris_semua.append(f"ADMIN_PASSWORD_HASH={hash_baru}\n")

    sementara = path_env + ".tmp"
    with open(sementara, "w", encoding="utf-8", newline="") as f:
        f.writelines(baris_semua)
    os.replace(sementara, path_env)
    return diganti
