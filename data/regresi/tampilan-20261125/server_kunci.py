"""Server uji hitung mundur login terkunci (26 Nov 2026): DATABASE UJI, waitress.

Sama dengan form-pembaruan-20261124/server_tangkapan.py (sandi admin sementara
di memori, .env tidak dibaca untuk sandi dan tidak diubah, log pencarian mati),
ditambah dua pengaturan HANYA di proses alat ini:
  DETIK          lama penguncian (aplikasi: 300), supaya akhir hitung mundur
                 bisa diamati tanpa menunggu 5 menit;
  tanpa-riwayat  beranda admin seolah belum pernah ada pembaruan
                 (ringkasan_terakhir -> None), tanpa menyentuh berkas data.

  venv/Scripts/python.exe server_kunci.py PORT DETIK [tanpa-riwayat]
"""
import os
import sys

DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, DIR)
os.chdir(DIR)

from waitress import serve  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from app import create_app  # noqa: E402
from app.config import KonfigurasiUji  # noqa: E402
from app.routes import admin as A  # noqa: E402

SANDI = "sandi-tangkapan-layar"
A.LAMA_KUNCI_DETIK = int(sys.argv[2])
if "tanpa-riwayat" in sys.argv[3:]:
    A.pembaruan.ringkasan_terakhir = lambda uji=False: None

app = create_app(KonfigurasiUji)
app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash(SANDI)
serve(app, host="127.0.0.1", port=int(sys.argv[1]), threads=4)
