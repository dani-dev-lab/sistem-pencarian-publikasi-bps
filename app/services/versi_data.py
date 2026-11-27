"""Penanda versi data pencarian: satu baris di tabel `versi_data`.

Mesin pencari menyimpan korpus di memori proses server (lihat
mesin_pencari.korpus()). Data bisa diubah dari PROSES LAIN - perbarui.py lewat
.bat atau halaman admin - dan dari tombol "Terapkan ke data" di proses server
sendiri. Supaya korpus di memori tidak pernah basi, setiap penulis data
menaikkan `versi` DI TRANSAKSI YANG SAMA dengan perubahannya, dan setiap
pencarian membaca `versi` (satu SELECT berkunci primer, murah). Versi berbeda
-> korpus dimuat ulang.

Kenapa tabel, bukan berkas penanda: berkas ditulis SESUDAH commit, sehingga
penulis yang berhenti di antara keduanya meninggalkan data baru dengan penanda
lama. Kenaikan di transaksi yang sama membuat keduanya berubah bersamaan atau
tidak sama sekali.

Kenapa tidak COUNT/MAX(id): "Terapkan ke data" hanya mengubah
teks_ternormalisasi, tanpa mengubah jumlah atau id baris.

PENTING: CREATE TABLE di MySQL memaksa commit transaksi yang sedang berjalan.
pastikan_tabel() karena itu dipanggil SEBELUM transaksi penulis dimulai
(perbarui.pastikan_skema, awal normalisasi_data.jalankan, pembacaan pertama),
bukan dari naikkan() yang berjalan di tengah transaksi.
"""

from sqlalchemy import text

from app.models import db

_SIAP = False


def pastikan_tabel():
    """Buat tabel dan barisnya kalau belum ada. Idempoten; sekali per proses."""
    global _SIAP
    if _SIAP:
        return
    db.session.execute(text(
        "CREATE TABLE IF NOT EXISTS versi_data ("
        " id TINYINT NOT NULL PRIMARY KEY,"
        " versi BIGINT NOT NULL,"
        " diubah DATETIME NOT NULL"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"))
    db.session.execute(text(
        "INSERT IGNORE INTO versi_data (id, versi, diubah) VALUES (1, 0, UTC_TIMESTAMP())"))
    db.session.commit()
    _SIAP = True


def naikkan():
    """Naikkan versi DI DALAM transaksi pemanggil (tidak commit sendiri)."""
    db.session.execute(text(
        "UPDATE versi_data SET versi = versi + 1, diubah = UTC_TIMESTAMP() WHERE id = 1"))


def baca():
    """Versi data saat ini."""
    pastikan_tabel()
    return db.session.execute(text("SELECT versi FROM versi_data WHERE id = 1")).scalar()
