"""Migrasi database dan folder PDF ke struktur multi-domain.

Yang dilakukan:
  1. Menambah kolom baru di publikasi dan log_pencarian.
  2. Mengisi kolom baru untuk publikasi lama dari dua berkas JSON lama.
  3. Memindahkan PDF ke data/publikasi_pdf/<domain>/. Ukuran dan waktu ubah
     berkas tidak berubah, jadi sidiknya tetap cocok.

IDEMPOTEN: aman dijalankan berulang. Baris yang kolom `domain`-nya sudah terisi
tidak disentuh, dan berkas yang sudah pindah dilewati. Berkas JSON hanya dibaca
kalau masih ada baris yang perlu diisi.

updt_date_diproses sengaja DIKOSONGKAN untuk PDF yang diunduh sebelum updt_date
terakhirnya. PDF itu kemungkinan usang, dan kolom yang berbeda dari
updt_date_api membuatnya otomatis diunduh ulang saat pembaruan online pertama.

Sengaja memakai SQL langsung, bukan model: model sudah memuat kolom baru, jadi
query lewat model pasti gagal pada database yang belum dimigrasi.

Jalankan:  venv/Scripts/python.exe scripts/migrasi_multidomain.py
"""

import json
import os
import sys
from datetime import date, datetime

DIR_PROYEK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR_PROYEK)

import sqlalchemy as sa

from app import create_app
from app.models import db
from app.services.pipeline_data import tanggal
from app.services.sumber_bps import path_pdf
from app.services.wilayah import muat_wilayah

FILE_META = os.path.join(DIR_PROYEK, "data", "publikasi_2025_2026.json")
FILE_EKSTRAKSI = os.path.join(DIR_PROYEK, "data", "hasil_ekstraksi.json")
DIR_PDF = os.path.join(DIR_PROYEK, "data", "publikasi_pdf")

DOMAIN_LAMA = "6300"    # seluruh data sebelum migrasi berasal dari domain ini

KOLOM_BARU = [
    ("publikasi", "domain", "CHAR(4) NULL"),         # NOT NULL setelah terisi
    ("publikasi", "wilayah", "VARCHAR(100) NULL"),   # NOT NULL setelah terisi
    ("publikasi", "updt_date_api", "DATE NULL"),
    ("publikasi", "updt_date_diproses", "DATE NULL"),
    ("publikasi", "sidik_ukuran", "BIGINT NULL"),
    ("publikasi", "sidik_mtime", "BIGINT NULL"),
    ("publikasi", "diekstrak_pada", "DATETIME NULL"),
    ("publikasi", "galat_ekstraksi", "TEXT NULL"),
    ("publikasi", "catatan_ekstraksi", "JSON NULL"),
    ("log_pencarian", "durasi_ms", "FLOAT NULL"),
    ("log_pencarian", "wilayah_filter", "CHAR(4) NULL"),    # filter wilayah, 10 Nov 2026
    ("publikasi", "halaman_ocr", "INT NULL"),               # OCR, 12 Nov 2026
]


def tambah_kolom(c):
    for tabel, nama, tipe in KOLOM_BARU:
        ada = c.execute(sa.text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :n"),
            {"t": tabel, "n": nama}).scalar()
        if ada:
            print(f"  {tabel}.{nama}: sudah ada")
        else:
            c.execute(sa.text(f"ALTER TABLE {tabel} ADD COLUMN {nama} {tipe}"))
            print(f"  {tabel}.{nama}: ditambahkan")


def _baca_json(path):
    if not os.path.exists(path):
        raise SystemExit(f"{path} tidak ada, padahal masih ada publikasi yang "
                         "perlu diisi. Ambil dari tag Git arsip-sebelum-rombakan:\n"
                         f"    git show arsip-sebelum-rombakan:{os.path.relpath(path, DIR_PROYEK).replace(os.sep, '/')} > {os.path.relpath(path, DIR_PROYEK)}\n"
                         "lalu ulangi.")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _catatan(h):
    """Bagian diagnosis dari catatan hasil_ekstraksi.json lama."""
    return {
        "heading_ditemukan": h["heading_ditemukan"],
        "jumlah_entri": h["jumlah_entri"],
        "per_tipe": h["per_tipe"],
        "per_sumber": h.get("per_sumber", {}),
        "tanpa_halaman": h["tanpa_halaman"],
        "mode_tanpa_label": h["mode_tanpa_label"],
        "dari_daftar": h.get("dari_daftar", 0),
        "dari_badan": h.get("dari_badan", 0),
        "halaman_fisik_dilengkapi": h.get("halaman_fisik_dilengkapi", 0),
    }


def isi_publikasi_lama(c, nama_wilayah):
    """Isi kolom baru untuk baris lama. Return daftar PDF yang kemungkinan usang."""
    belum = [r[0] for r in c.execute(sa.text(
        "SELECT id FROM publikasi WHERE domain IS NULL ORDER BY id"))]
    if not belum:
        print("  tidak ada baris yang perlu diisi")
        return []

    meta = {p["pub_id"]: p for p in _baca_json(FILE_META)["publikasi"]}
    berkas = _baca_json(FILE_EKSTRAKSI)
    ekstraksi = {h["publikasi_id"]: h for h in berkas["hasil"]}
    waktu_ekstraksi = datetime.fromisoformat(berkas["diperbarui_pada"]).replace(tzinfo=None)

    usang = []
    masalah = []
    for pid in belum:
        p = meta.get(pid)
        h = ekstraksi.get(pid)
        if p is None or h is None:
            masalah.append(f"{pid}: tidak ada di "
                           f"{'metadata' if p is None else 'hasil ekstraksi'}")
            continue

        # Saat migrasi, PDF masih di folder lama.
        path = os.path.join(DIR_PDF, f"{pid}.pdf")
        if not os.path.exists(path):
            path = path_pdf(DOMAIN_LAMA, pid)
        if not os.path.exists(path):
            masalah.append(f"{pid}: berkas PDF tidak ditemukan")
            continue

        st = os.stat(path)
        sidik = [st.st_size, int(st.st_mtime)]
        if h.get("sidik_pdf") != sidik:
            masalah.append(f"{pid}: sidik PDF tidak cocok dengan hasil ekstraksi")
            continue

        updt = tanggal(p.get("updt_date"))
        tanggal_unduh = date.fromtimestamp(st.st_mtime)
        kemungkinan_usang = updt is not None and updt > tanggal_unduh
        if kemungkinan_usang:
            usang.append((pid, updt, tanggal_unduh, p["title"]))

        c.execute(sa.text("""
            UPDATE publikasi SET domain = :domain, wilayah = :wilayah,
                updt_date_api = :updt, updt_date_diproses = :diproses,
                sidik_ukuran = :ukuran, sidik_mtime = :mtime,
                diekstrak_pada = :diekstrak, galat_ekstraksi = :galat,
                catatan_ekstraksi = :catatan
            WHERE id = :id AND domain IS NULL
        """), {
            "id": pid, "domain": DOMAIN_LAMA, "wilayah": nama_wilayah,
            "updt": updt, "diproses": None if kemungkinan_usang else updt,
            "ukuran": sidik[0], "mtime": sidik[1],
            "diekstrak": None if h.get("galat") else waktu_ekstraksi,
            "galat": h.get("galat"),
            "catatan": json.dumps(_catatan(h), ensure_ascii=False),
        })

    if masalah:
        print("  MASALAH - migrasi dibatalkan, tidak ada baris yang berubah:")
        for m in masalah:
            print(f"    {m}")
        raise SystemExit(1)

    print(f"  {len(belum)} publikasi diisi")
    return usang


def kunci_kolom(c):
    """Jadikan domain + wilayah wajib, dan beri indeks pada domain."""
    c.execute(sa.text("ALTER TABLE publikasi MODIFY domain CHAR(4) NOT NULL"))
    c.execute(sa.text("ALTER TABLE publikasi MODIFY wilayah VARCHAR(100) NOT NULL"))
    ada = c.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'publikasi' "
        "AND INDEX_NAME = 'ix_publikasi_domain'")).scalar()
    if not ada:
        c.execute(sa.text("CREATE INDEX ix_publikasi_domain ON publikasi (domain)"))


def pindahkan_pdf(c):
    """Pindahkan PDF lepas di folder induk ke subfolder domainnya."""
    domain_per_id = dict(c.execute(sa.text("SELECT id, domain FROM publikasi")).all())
    pindah = 0
    masalah = []
    for nama in sorted(os.listdir(DIR_PDF)):
        asal = os.path.join(DIR_PDF, nama)
        if not (os.path.isfile(asal) and nama.lower().endswith(".pdf")):
            continue
        domain = domain_per_id.get(nama[:-4])
        if domain is None:
            masalah.append(f"{nama}: tidak ada di tabel publikasi, dibiarkan")
            continue
        tujuan = path_pdf(domain, nama[:-4])
        if os.path.exists(tujuan):
            masalah.append(f"{nama}: sudah ada di {domain}/, dibiarkan")
            continue
        os.makedirs(os.path.dirname(tujuan), exist_ok=True)
        try:
            os.replace(asal, tujuan)
        except OSError as e:
            # Di Windows berkas yang sedang dibuka aplikasi tidak bisa dipindah.
            masalah.append(f"{nama}: gagal dipindah ({e}), jalankan ulang script ini")
            continue
        pindah += 1
    print(f"  {pindah} berkas dipindahkan")
    for m in masalah:
        print(f"  PERHATIAN {m}")


def main():
    os.chdir(DIR_PROYEK)
    nama = {w["kode"]: w["nama"] for w in muat_wilayah()}[DOMAIN_LAMA]

    app = create_app()
    with app.app_context():
        # ALTER TABLE di MySQL selalu commit sendiri, jadi langkah kolom tidak
        # bisa dibatalkan. Itu aman: kolomnya baru dan boleh kosong, dan
        # menjalankan ulang script ini melewatinya. Pengisian baris tetap dalam
        # satu transaksi supaya masalah data tidak meninggalkan isian separuh.
        print("1. Kolom baru")
        with db.engine.begin() as c:
            tambah_kolom(c)

        print("2. Isi publikasi lama")
        with db.engine.begin() as c:
            usang = isi_publikasi_lama(c, nama)

        print("3. Kunci kolom wajib")
        with db.engine.begin() as c:
            kunci_kolom(c)

        print("4. Pindahkan PDF ke subfolder domain")
        with db.engine.connect() as c:
            pindahkan_pdf(c)

    if usang:
        print()
        print(f"PDF kemungkinan usang ({len(usang)}), diunduh ulang saat pembaruan "
              "online pertama:")
        for pid, updt, unduh, judul in sorted(usang, key=lambda x: x[1], reverse=True):
            print(f"  {pid}  updt_date {updt}, diunduh {unduh}  {judul[:50]}")
    print()
    print("Migrasi selesai.")


if __name__ == "__main__":
    main()
