"""Model data sesuai ERD sistem pencarian publikasi BPS.

Objek `db` dibuat di sini lalu dipakai seluruh modul model. Impor di bawah
definisi `db` memang disengaja: model membutuhkan `db`, sementara pemakai modul
ini cukup mengimpor dari satu tempat.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# MySQL perlu utf8mb4: judul entri memuat en-dash (2023–2025) dan karakter
# non-ASCII lain yang tidak muat di utf8 tiga byte.
ARGS_TABEL = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}

from app.models.entri_dokumen import EntriDokumen
from app.models.kategori import Kategori, publikasi_kategori
from app.models.log_pencarian import LogPencarian
from app.models.publikasi import Publikasi

__all__ = [
    "ARGS_TABEL",
    "EntriDokumen",
    "Kategori",
    "LogPencarian",
    "Publikasi",
    "db",
    "publikasi_kategori",
]
