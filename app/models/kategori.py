"""Model Kategori publikasi dan tabel penghubungnya.

Relasi ke publikasi many-to-many karena `subject_csa` dari WebAPI berbentuk
array - satu publikasi bisa punya lebih dari satu subjek.
"""

from app.models import ARGS_TABEL, db

# Tabel penghubung. Banyak publikasi TIDAK punya baris di sini sama sekali
# (43 dari 72 tanpa subject_csa); itu kondisi normal, bukan data rusak.
publikasi_kategori = db.Table(
    "publikasi_kategori",
    db.Column("publikasi_id", db.String(32),
              db.ForeignKey("publikasi.id", ondelete="CASCADE"),
              primary_key=True),
    db.Column("kategori_id", db.Integer,
              db.ForeignKey("kategori.id", ondelete="CASCADE"),
              primary_key=True),
    **ARGS_TABEL,
)


class Kategori(db.Model):
    __tablename__ = "kategori"
    __table_args__ = ARGS_TABEL

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama = db.Column(db.String(191), nullable=False, unique=True)

    publikasi = db.relationship(
        "Publikasi",
        secondary="publikasi_kategori",
        back_populates="kategori",
    )

    def __repr__(self):
        return f"<Kategori {self.nama!r}>"
