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
    waktu_pencarian = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self):
        return f"<LogPencarian {self.keyword!r} n={self.jumlah_hasil}>"
