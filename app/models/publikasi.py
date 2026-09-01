"""Model Publikasi: metadata publikasi hasil WebAPI BPS."""

from datetime import datetime, timezone

from app.models import ARGS_TABEL, db


class Publikasi(db.Model):
    __tablename__ = "publikasi"
    __table_args__ = ARGS_TABEL

    # pub_id dari BPS dipakai langsung sebagai primary key: stabil, dan membuat
    # impor ulang bisa upsert tanpa perlu tabel pemetaan.
    id = db.Column(db.String(32), primary_key=True)
    judul = db.Column(db.Text, nullable=False)
    abstrak = db.Column(db.Text)
    tahun_terbit = db.Column(db.SmallInteger, index=True)
    tanggal_rilis = db.Column(db.Date, index=True)
    url_pdf = db.Column(db.Text)
    url_cover = db.Column(db.Text)
    issn = db.Column(db.String(50))

    # Judul + abstrak yang sudah dinormalisasi, untuk pencarian tingkat
    # publikasi. Diisi oleh scripts/isi_normalisasi.py.
    teks_ternormalisasi = db.Column(db.Text)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    entri = db.relationship(
        "EntriDokumen",
        back_populates="publikasi",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    kategori = db.relationship(
        "Kategori",
        secondary="publikasi_kategori",
        back_populates="publikasi",
    )

    def __repr__(self):
        return f"<Publikasi {self.id} {self.judul[:40]!r}>"
