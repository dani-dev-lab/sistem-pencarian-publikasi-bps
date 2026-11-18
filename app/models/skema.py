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
    ("entri_dokumen", "halaman_fisik_perkiraan",
     "TINYINT(1) NOT NULL DEFAULT 0 AFTER halaman_fisik"),                  # perkiraan, 16 Nov 2026
    ("publikasi", "kecamatan", "VARCHAR(60) NULL AFTER wilayah"),           # kecamatan, 18 Nov 2026
    ("log_pencarian", "sertakan_kecamatan", "TINYINT(1) NULL AFTER wilayah_filter"),  # 19 Nov 2026
]

_SIAP = False


def sinkron_kecamatan():
    """Samakan publikasi.kecamatan dengan judul + pola_kecamatan (wilayah.json).

    Idempoten; hanya baris yang berbeda yang ditulis. Menangani data lama
    (kolom baru masih NULL) dan pola yang diedit. Kalau ada yang ditulis,
    versi_data dinaikkan di transaksi yang sama supaya korpus pencarian di
    proses lain dimuat ulang. Dipanggil dari pastikan_kolom(), sesudah DDL.
    Return jumlah baris yang ditulis.
    """
    from app.services import versi_data
    from app.services.wilayah import kecamatan_dari_judul

    versi_data.pastikan_tabel()          # DDL sebelum transaksi penulis
    berubah = 0
    for pid, judul, lama in db.session.execute(sa.text(
            "SELECT id, judul, kecamatan FROM publikasi")).all():
        k = kecamatan_dari_judul(judul)
        baru = k[0] if k else None
        if baru != lama:
            db.session.execute(sa.text("UPDATE publikasi SET kecamatan = :k WHERE id = :i"),
                               {"k": baru, "i": pid})
            berubah += 1
    if berubah:
        versi_data.naikkan()
    db.session.commit()
    return berubah


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
        ada_publikasi = c.execute(sa.text(
            "SELECT COUNT(*) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'publikasi'")).scalar()
    if ada_publikasi:
        sinkron_kecamatan()
    _SIAP = True
