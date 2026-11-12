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

    # Kode domain BPS pemilik publikasi ("6300", "6301", ...). Sejak aplikasi
    # mencakup 14 domain, pub_id saja tidak menunjukkan asal publikasi. Dipakai
    # menyusun path PDF per domain, membatasi pemrosesan per domain, dan
    # mendeteksi pub_id yang bertabrakan antar-domain.
    domain = db.Column(db.CHAR(4), nullable=False, index=True)

    # Nama tampil ("Kab. Tanah Laut"), disalin dari data/wilayah.json dan
    # disegarkan tiap pembaruan. Disimpan di sini supaya hasil pencarian tidak
    # perlu membaca berkas konfigurasi untuk setiap baris.
    wilayah = db.Column(db.String(100), nullable=False)

    # updt_date TERAKHIR dari API, sekadar apa kata BPS saat ini. Tidak pernah
    # ditimpa nilai kosong: API sempat mengosongkan field ini, dan kosong bukan
    # berarti publikasinya berubah.
    updt_date_api = db.Column(db.Date)

    # updt_date saat PDF lokal terakhir BERHASIL diunduh dan diekstrak. Sengaja
    # terpisah dari updt_date_api: kalau hanya satu kolom dan terisi saat
    # metadata ditarik, unduhan yang gagal membuat perubahan itu tidak pernah
    # diproses (bug yang sama dengan 4 publikasi yang dulu tertinggal).
    # Berbeda dari updt_date_api = PDF lokal perlu diunduh ulang.
    updt_date_diproses = db.Column(db.Date)

    # Penanda berkas PDF saat diekstrak: mendeteksi PDF yang diganti di disk
    # tanpa membaca ratusan MB. BIGINT karena mtime berupa detik epoch dan
    # ukuran berkas bisa melewati batas INT.
    sidik_ukuran = db.Column(db.BigInteger)
    sidik_mtime = db.Column(db.BigInteger)

    # Kapan ekstraksi terakhir berhasil. Kosong = belum pernah. Menggantikan
    # aturan "belum punya entri", yang akan mengekstrak ulang publikasi yang
    # memang sah tanpa entri pada setiap pembaruan.
    diekstrak_pada = db.Column(db.DateTime)

    # Pesan galat ekstraksi terakhir, kosong kalau terakhir berhasil. Dipakai
    # supaya kegagalan tetap terlihat setelah proses selesai, dan menjelaskan
    # kenapa publikasi itu dicoba lagi pada pembaruan berikutnya.
    galat_ekstraksi = db.Column(db.Text)

    # Diagnosis ekstraksi: heading yang ditemukan, mode tanpa label, jumlah per
    # jalur. Sebelumnya hanya ada di hasil_ekstraksi.json, padahal laporan
    # "perlu diperiksa" butuh membedakan "daftarnya memang tidak ada" dari
    # "daftarnya ada tapi gagal dibaca".
    catatan_ekstraksi = db.Column(db.JSON)

    # Jumlah halaman yang dibaca lewat OCR (halaman tanpa lapisan teks,
    # app/services/ocr.py). Kosong = publikasi ini tidak memakai OCR.
    # Ditambahkan ke database lama oleh app/models/skema.py (12 Nov 2026).
    halaman_ocr = db.Column(db.Integer)

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
