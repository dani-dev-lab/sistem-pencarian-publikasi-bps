"""Server aplikasi untuk tangkapan layar (24 Nov 2026): DATABASE UJI, waitress.

Sandi admin SEMENTARA hanya di memori proses ini (hash di app.config), jadi
.env tidak dibaca untuk sandi dan tidak diubah. Log pencarian mati
(KonfigurasiUji). Jalankan: venv/Scripts/python.exe server_tangkapan.py PORT
Variabel BPS_API_BASE_URL boleh diarahkan ke WebAPI tiruan (cek dulu).
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

SANDI = "sandi-tangkapan-layar"

app = create_app(KonfigurasiUji)
app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash(SANDI)
serve(app, host="127.0.0.1", port=int(sys.argv[1]), threads=4)
