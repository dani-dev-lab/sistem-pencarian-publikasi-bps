"""Kolom tambahan untuk database lama, ditambahkan sekali per proses.

Project ini belum memakai alat migrasi, dan db.create_all() tidak mengubah
tabel yang sudah ada. Tanpa kolom-kolom ini SEMUA query ORM ke tabelnya gagal
(halaman admin, pencarian) dan pencatatan log gagal diam-diam.

ALTER TABLE memaksa commit di MySQL, jadi dipanggil di awal request web dan
di perbarui.pastikan_skema(), sebelum transaksi apa pun.
"""

import sqlalchemy as sa

from app.models import db

# (tabel, kolom, definisi) - tambahkan di sini kalau model mendapat kolom baru.
KOLOM_TAMBAHAN = [
    ("log_pencarian", "wilayah_filter", "CHAR(4) NULL AFTER durasi_ms"),   # filter wilayah, 10 Nov 2026
    ("publikasi", "halaman_ocr", "INT NULL"),                               # OCR, 12 Nov 2026
]

_SIAP = False


def pastikan_kolom():
    global _SIAP
    if _SIAP:
        return
    with db.engine.begin() as c:
        for tabel, kolom, definisi in KOLOM_TAMBAHAN:
            ada_tabel = c.execute(sa.text(
                "SELECT COUNT(*) FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"), {"t": tabel}).scalar()
            ada = c.execute(sa.text(
                "SELECT COUNT(*) FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :k"),
                {"t": tabel, "k": kolom}).scalar()
            if ada_tabel and not ada:
                c.execute(sa.text(f"ALTER TABLE {tabel} ADD COLUMN {kolom} {definisi}"))
    _SIAP = True
