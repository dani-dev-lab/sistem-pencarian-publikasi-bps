"""Model LogPencarian: rekam jejak kueri untuk evaluasi relevansi.

Dipakai untuk closed-loop improvement - kueri berskor rendah direview berkala
untuk memperkaya kamus sinonim.
"""

from datetime import datetime, timezone

from app.models import ARGS_TABEL, db


class LogPencarian(db.Model):
    __tablename__ = "log_pencarian"
    __table_args__ = ARGS_TABEL

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    keyword = db.Column(db.String(255), nullable=False)
    keyword_ternormalisasi = db.Column(db.String(255))
    jumlah_hasil = db.Column(db.Integer, nullable=False, default=0)
    skor_tertinggi = db.Column(db.Float)

    # Waktu pencarian per kueri nyata petugas. ukur_kinerja.py hanya mengukur
    # kueri uji; kolom ini menjawab apakah pencarian melambat di pemakaian
    # sebenarnya setelah data 13 kabupaten/kota masuk. Baris lama kosong.
    durasi_ms = db.Column(db.Float)

    # Kode wilayah filter yang AKTIF saat kueri ini dicari ("6301"), dipilih
    # lewat dropdown maupun dipasang otomatis dari nama wilayah di kueri.
    # Kosong = semua wilayah. Baris sebelum 10 Nov 2026 kosong. Kolomnya
    # ditambahkan ke database lama oleh app/models/skema.py.
    wilayah_filter = db.Column(db.CHAR(4))
    waktu_pencarian = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self):
        return f"<LogPencarian {self.keyword!r} n={self.jumlah_hasil}>"

