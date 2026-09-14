"""Baca .env dan sediakan konfigurasi aplikasi (termasuk koneksi database)."""

import os
from pathlib import Path

from dotenv import load_dotenv

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

    # WebAPI BPS
    BPS_API_KEY = os.getenv("BPS_API_KEY", "")
    BPS_API_BASE_URL = os.getenv("BPS_API_BASE_URL", "https://webapi.bps.go.id/v1/api")
    BPS_DOMAIN = os.getenv("BPS_DOMAIN", "6300")  # Kalimantan Selatan

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'pencarian_bps.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Path data
    DIR_PUBLIKASI_PDF = BASE_DIR / "data" / "publikasi_pdf"
    DIR_SAMPEL_PDF = BASE_DIR / "data" / "sampel_pdf"
    FILE_KAMUS_SINONIM = BASE_DIR / "data" / "kamus_sinonim.json"


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
    masalah = []
    if not config_class.SECRET_KEY or config_class.SECRET_KEY == SECRET_KEY_LAMA:
        masalah.append(PESAN_SECRET_KEY)
    if not config_class.ADMIN_PASSWORD_HASH:
        masalah.append(PESAN_ADMIN_HASH)
    if masalah:
        garis = "=" * 72
        raise SystemExit(
            f"\n{garis}\nKONFIGURASI BELUM LENGKAP - aplikasi tidak dijalankan\n"
            f"{garis}\n\n" + "\n".join(masalah)
            + f"\nContoh isian lengkap ada di .env.example.\n{garis}"
        )
