"""Muat hasil pengambilan metadata dan ekstraksi PDF ke database.

Sumber:
  data/publikasi_2025_2026.json  -> tabel publikasi, kategori, publikasi_kategori
  data/hasil_ekstraksi.json      -> tabel entri_dokumen

IDEMPOTEN: aman dijalankan berulang. Publikasi di-upsert berdasarkan pub_id,
dan entri_dokumen milik publikasi yang sedang diproses dihapus dulu lalu diisi
ulang - supaya menjalankan ulang setelah parser diperbaiki tidak menggandakan
data maupun menyisakan entri basi.

Jalankan:  venv/Scripts/python.exe scripts/muat_ke_database.py
"""

import json
import os
import re
import sys
from collections import Counter
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlalchemy as sa
from isi_normalisasi import jalankan as isi_normalisasi

from app import create_app
from app.models import EntriDokumen, Kategori, LogPencarian, Publikasi, db

FILE_PUBLIKASI = "data/publikasi_2025_2026.json"
FILE_EKSTRAKSI = "data/hasil_ekstraksi.json"

TIPE = ("isi", "tabel", "gambar", "lampiran")
SUMBER = ("daftar", "badan", "keduanya")

# Kolom yang ditambahkan belakangan. Project ini belum memakai alat migrasi dan
# db.create_all() tidak mengubah tabel yang sudah ada.
KOLOM_TAMBAHAN = {
    "halaman_fisik": "INT NULL",
    "sumber": ("ENUM('daftar','badan','keduanya') NOT NULL DEFAULT 'daftar'"),
}


def _pastikan_kolom():
    with db.engine.begin() as c:
        for nama, tipe_sql in KOLOM_TAMBAHAN.items():
            ada = c.execute(sa.text(
                "SELECT COUNT(*) FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'entri_dokumen' "
                "AND COLUMN_NAME = :n"), {"n": nama}).scalar()
            if not ada:
                c.execute(sa.text(
                    f"ALTER TABLE entri_dokumen ADD COLUMN {nama} {tipe_sql}"))
                print(f"kolom entri_dokumen.{nama} ditambahkan")


def tanggal(teks):
    """rl_date -> date. Return None kalau tidak terbaca."""
    if not teks:
        return None
    cocok = re.match(r"\s*(\d{4})-(\d{2})-(\d{2})", str(teks))
    if cocok:
        return date(*(int(g) for g in cocok.groups()))
    return None


def daftar_subjek(p):
    """subject_csa bisa list, null, atau string. Selalu kembalikan list str.

    Publikasi tanpa subjek mengembalikan list kosong - itu kondisi normal
    (43 dari 72), bukan data rusak.
    """
    nilai = p.get("subject_csa")
    if not nilai:
        return []
    if isinstance(nilai, list):
        return [str(s).strip() for s in nilai if str(s).strip()]
    return [str(nilai).strip()]


def muat_json(path):
    if not os.path.exists(path):
        print(f"{path} tidak ada.")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def baca_hasil_ekstraksi(path):
    """Baca berkas hasil ekstraksi, terima format lama maupun baru.

    Format baru membungkus daftar hasil dalam dict berpenanda kelengkapan.
    Berkas yang ditandai BELUM selesai ditolak - memuat hasil separuh ke
    database jauh lebih berbahaya daripada berhenti dengan pesan jelas.
    """
    with open(path, encoding="utf-8") as f:
        isi = json.load(f)

    if isinstance(isi, list):          # format lama, sebelum ada penanda
        return isi

    if not isi.get("selesai"):
        print(f"{path} menandai dirinya BELUM SELESAI "
              f"({isi.get('publikasi_terproses')}/{isi.get('total_publikasi')} "
              f"publikasi). Jalankan ulang scripts/ekstrak_semua.py dulu.")
        sys.exit(1)

    return isi["hasil"]


def main():
    sumber_pub = muat_json(FILE_PUBLIKASI)["publikasi"]
    sumber_ekstrak = baca_hasil_ekstraksi(FILE_EKSTRAKSI)
    entri_per_pub = {h["publikasi_id"]: h["entri"] for h in sumber_ekstrak}

    app = create_app()
    with app.app_context():
        db.create_all()
        _pastikan_kolom()

        # ---------------- Kategori (get-or-create per nama) ----------------
        nama_semua = sorted({s for p in sumber_pub for s in daftar_subjek(p)})
        sudah = {k.nama: k for k in Kategori.query.all()}
        kategori_baru = 0
        for nama in nama_semua:
            if nama not in sudah:
                k = Kategori(nama=nama)
                db.session.add(k)
                sudah[nama] = k
                kategori_baru += 1
        db.session.flush()

        # ---------------- Publikasi (upsert per pub_id) ----------------
        pub_baru = pub_diperbarui = 0
        for p in sumber_pub:
            pid = p["pub_id"]
            pub = db.session.get(Publikasi, pid)
            if pub is None:
                pub = Publikasi(id=pid)
                db.session.add(pub)
                pub_baru += 1
            else:
                pub_diperbarui += 1

            rilis = tanggal(p.get("rl_date"))
            pub.judul = (p.get("title") or "").strip()
            pub.abstrak = p.get("abstract")
            pub.tanggal_rilis = rilis
            pub.tahun_terbit = rilis.year if rilis else None
            pub.url_pdf = p.get("pdf")
            pub.url_cover = p.get("cover")
            pub.issn = p.get("issn")

            # Ganti seluruh kaitan kategori, bukan menambah - supaya perubahan
            # subjek di sumber tidak meninggalkan kaitan lama.
            pub.kategori = [sudah[n] for n in daftar_subjek(p)]

        db.session.flush()

        # ---------------- Entri dokumen (hapus lalu isi ulang) ----------------
        entri_masuk = Counter()
        pub_tanpa_entri = []
        for p in sumber_pub:
            pid = p["pub_id"]
            daftar = entri_per_pub.get(pid, [])

            EntriDokumen.query.filter_by(publikasi_id=pid).delete(
                synchronize_session=False)

            if not daftar:
                pub_tanpa_entri.append(pid)
                continue

            for e in daftar:
                db.session.add(EntriDokumen(
                    publikasi_id=pid,
                    tipe=e["tipe"],
                    nomor=e.get("nomor"),
                    judul=e["judul"],
                    halaman=e.get("halaman"),
                    halaman_fisik=e.get("halaman_fisik"),
                    sumber=e.get("sumber", "daftar"),
                    teks_ternormalisasi=None,   # diisi minggu 5
                ))
                entri_masuk[e["tipe"]] += 1

        db.session.commit()

        # ------------------------- Ringkasan + verifikasi -------------------------
        n_pub = Publikasi.query.count()
        n_kat = Kategori.query.count()
        n_entri = EntriDokumen.query.count()
        n_kaitan = db.session.execute(
            db.text("SELECT COUNT(*) FROM publikasi_kategori")).scalar()

        print("=" * 70)
        print("RINGKASAN PEMUATAN")
        print("=" * 70)
        print(f"Publikasi   : {n_pub} di database "
              f"({pub_baru} baru, {pub_diperbarui} diperbarui)")
        print(f"Kategori    : {n_kat} ({kategori_baru} baru)")
        print(f"Kaitan pub-kategori : {n_kaitan}")
        print(f"Entri dokumen       : {n_entri}")
        print(f"Publikasi tanpa entri: {len(pub_tanpa_entri)}")

        print()
        print("Sebaran entri per sumber:")
        for s_ in SUMBER:
            n = EntriDokumen.query.filter_by(sumber=s_).count()
            print(f"  {s_:<10} {n:>6}")
        n_fisik = EntriDokumen.query.filter(
            EntriDokumen.halaman_fisik.isnot(None)).count()
        print(f"  punya halaman_fisik: {n_fisik}")

        print()
        print("Sebaran entri per tipe (database vs JSON sumber):")
        cocok_semua = True
        for t in TIPE:
            di_db = EntriDokumen.query.filter_by(tipe=t).count()
            di_json = sum(1 for d in entri_per_pub.values()
                          for e in d if e["tipe"] == t)
            tanda = "OK" if di_db == di_json else "TIDAK COCOK"
            cocok_semua = cocok_semua and di_db == di_json
            print(f"  {t:<10} db={di_db:>6}  json={di_json:>6}   {tanda}")

        # Verifikasi menyeluruh terhadap sumber.
        total_json_entri = sum(len(d) for d in entri_per_pub.values())
        total_json_pub = len(sumber_pub)
        total_json_kaitan = sum(len(daftar_subjek(p)) for p in sumber_pub)

        print()
        print("Verifikasi terhadap JSON sumber:")
        for label, db_n, js_n in (
            ("publikasi", n_pub, total_json_pub),
            ("entri dokumen", n_entri, total_json_entri),
            ("kaitan kategori", n_kaitan, total_json_kaitan),
        ):
            tanda = "OK" if db_n == js_n else "TIDAK COCOK"
            cocok_semua = cocok_semua and db_n == js_n
            print(f"  {label:<18} db={db_n:>6}  json={js_n:>6}   {tanda}")

        print()
        print("SEMUA COCOK" if cocok_semua
              else "ADA YANG TIDAK COCOK - periksa sebelum lanjut")

        # Pemuatan MENGHAPUS lalu mengisi ulang entri, sehingga
        # teks_ternormalisasi ikut kosong. Tanpa langkah ini pencarian
        # mengembalikan 0 hasil tanpa penjelasan - jadi dijalankan otomatis di
        # sini, bukan diserahkan ke ingatan orang.
        print()
        print("=" * 70)
        print("NORMALISASI (otomatis, karena pemuatan mengosongkan kolomnya)")
        print("=" * 70)
        isi_normalisasi()
        print(f"log_pencarian saat ini: {LogPencarian.query.count()} baris "
              f"(diisi saat aplikasi dipakai)")


if __name__ == "__main__":
    main()
