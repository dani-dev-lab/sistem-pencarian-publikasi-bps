"""Baca .env dan sediakan konfigurasi aplikasi (termasuk koneksi database)."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    # `or`, bukan nilai default os.getenv: variabel yang ADA tapi KOSONG di
    # .env tetap mengembalikan "" dan itu membuat session Flask mati
    # (flash message gagal dengan HTTP 500).
    SECRET_KEY = os.getenv("SECRET_KEY") or "kunci-pengembangan-lokal"

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
