"""Server aplikasi untuk tangkapan layar (25 Nov 2026): DATABASE UJI, waitress.

Sama dengan form-pembaruan-20261124/server_tangkapan.py, ditambah satu hal
KHUSUS ALAT INI: kalau berkas SISA_DISK_MB.txt ada di folder ini, sisa ruang
disk yang dibaca halaman /admin/perbarui diganti angka di berkas itu (MB),
supaya status merah "Ruang disk tidak cukup" bisa dipotret tanpa mengisi
disk. Kode aplikasi tidak diubah; penggantian hanya di proses server ini.

Sandi admin SEMENTARA hanya di memori proses ini; .env tidak dibaca untuk
sandi dan tidak diubah. BPS_API_BASE_URL diarahkan ke WebAPI tiruan oleh
pemanggil, jadi "Cek dulu" tidak menghubungi BPS.

  venv/Scripts/python.exe server_tangkapan.py PORT
"""
import os
import sys

FOLDER = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.dirname(os.path.dirname(os.path.dirname(FOLDER)))
sys.path.insert(0, DIR)
os.chdir(DIR)

from waitress import serve  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from app import create_app  # noqa: E402
from app.config import KonfigurasiUji  # noqa: E402
from app.services import ringkasan_pembaruan  # noqa: E402

assert os.environ.get("BPS_API_BASE_URL", "").startswith("http://127.0.0.1:"), "harus ke WebAPI tiruan"
SANDI = "sandi-tangkapan-layar"
_asli = ringkasan_pembaruan.sisa_ruang_mb


def _sisa(path=None):
    f = os.path.join(FOLDER, "SISA_DISK_MB.txt")
    return float(open(f).read()) if os.path.exists(f) else _asli(path)


ringkasan_pembaruan.sisa_ruang_mb = _sisa
app = create_app(KonfigurasiUji)
app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash(SANDI)
serve(app, host="127.0.0.1", port=int(sys.argv[1]), threads=4)
