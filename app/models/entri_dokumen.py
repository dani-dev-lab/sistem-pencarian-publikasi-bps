"""Model EntriDokumen: baris Daftar Isi/Tabel/Gambar/Lampiran hasil ekstraksi.

Tabel inilah yang memungkinkan sistem menjawab "di BAGIAN MANA", bukan cuma
"di publikasi mana".
"""

from app.models import ARGS_TABEL, db

TIPE_ENTRI = ("isi", "tabel", "gambar", "lampiran")
SUMBER_ENTRI = ("daftar", "badan", "keduanya")


class EntriDokumen(db.Model):
    __tablename__ = "entri_dokumen"
    __table_args__ = (
        db.Index("ix_entri_publikasi_tipe", "publikasi_id", "tipe"),
        ARGS_TABEL,
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    publikasi_id = db.Column(
        db.String(32),
        db.ForeignKey("publikasi.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipe = db.Column(db.Enum(*TIPE_ENTRI, name="tipe_entri"), nullable=False)

    # Nullable, dan string - BUKAN integer. Formatnya bermacam-macam
    # ("1", "2.1", "1.1.1"), dan entri tipe `isi` tidak pernah punya nomor.
    nomor = db.Column(db.String(20))

    judul = db.Column(db.Text, nullable=False)

    # Nullable juga, dan string: Daftar Isi memakai angka romawi ("v", "ix")
    # untuk halaman depan, dan 94 entri memang tidak punya nomor halaman.
    halaman = db.Column(db.String(10))

    # Halaman FISIK PDF (indeks halaman + 1), dari ekstraksi badan dokumen.
    # Berbeda dari `halaman` yang berisi nomor CETAK dari halaman daftar.
    # Inilah yang berguna untuk membuka PDF langsung di halaman itu.
    halaman_fisik = db.Column(db.Integer)

    # Asal entri: 'daftar' (halaman daftar depan), 'badan' (keterangan di badan
    # dokumen), atau 'keduanya'. Dipakai untuk menilai mutu tiap jalur.
    sumber = db.Column(db.Enum(*SUMBER_ENTRI, name="sumber_entri"),
                       nullable=False, default="daftar")

    # Diisi minggu 5 (stemming + normalisasi sinonim); sengaja kosong dulu.
    teks_ternormalisasi = db.Column(db.Text)

    publikasi = db.relationship("Publikasi", back_populates="entri")

    def __repr__(self):
        return f"<EntriDokumen {self.tipe} {self.nomor} {self.judul[:30]!r}>"
