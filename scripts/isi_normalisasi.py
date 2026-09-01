"""Isi kolom teks_ternormalisasi untuk entri_dokumen DAN publikasi.

Memakai `app.services.preprocessing.normalisasi()` - fungsi yang SAMA persis
dengan yang dipakai saat memproses kueri petugas. Kalau keduanya berbeda, skor
kemiripan jadi tidak bermakna.

IDEMPOTEN: menulis ulang nilai, bukan menambah baris. Aman dijalankan lagi
setiap kali `data/kamus_sinonim.json` diperbarui - dan memang HARUS dijalankan
ulang, karena isi kolom ini bergantung pada kamus.

Jalankan:  venv/Scripts/python.exe scripts/isi_normalisasi.py
"""

import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlalchemy as sa

from app import create_app
from app.models import EntriDokumen, Publikasi, db
from app.services.preprocessing import kamus_default, normalisasi, stem_kata

UKURAN_BATCH = 500


def _pastikan_kolom():
    """Tambah kolom publikasi.teks_ternormalisasi kalau belum ada.

    Project ini belum memakai alat migrasi, dan db.create_all() tidak mengubah
    tabel yang sudah terlanjur ada. Pengecekan ini membuat script tetap aman
    dijalankan di database lama maupun baru.
    """
    with db.engine.begin() as c:
        ada = c.execute(sa.text(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'publikasi' "
            "AND COLUMN_NAME = 'teks_ternormalisasi'")).scalar()
        if not ada:
            c.execute(sa.text(
                "ALTER TABLE publikasi ADD COLUMN teks_ternormalisasi TEXT"))
            print("kolom publikasi.teks_ternormalisasi ditambahkan")


def _isi_publikasi():
    """Normalkan judul + abstrak tiap publikasi.

    Keduanya digabung supaya istilah yang HANYA muncul di abstrak (misalnya
    nama instansi sumber data) tetap bisa dicari.
    """
    diubah = 0
    tanpa_abstrak = 0
    for p in Publikasi.query.all():
        if not p.abstrak:
            tanpa_abstrak += 1
        baru = normalisasi(f"{p.judul or ''} {p.abstrak or ''}")
        if p.teks_ternormalisasi != baru:
            p.teks_ternormalisasi = baru
            diubah += 1
    return diubah, tanpa_abstrak


def jalankan():
    """Isi teks_ternormalisasi. HARUS dipanggil di dalam app context.

    Dipisah dari main() supaya bisa dipanggil langsung oleh
    scripts/muat_ke_database.py di akhir pemuatan - pemuatan mengosongkan
    kolom ini, jadi menjalankannya terpisah adalah jebakan: kalau lupa,
    aplikasi mengembalikan 0 hasil tanpa penjelasan.
    """
    _pastikan_kolom()
    kamus = kamus_default()
    total = EntriDokumen.query.count()
    if not total:
        print("Tabel entri_dokumen kosong - jalankan muat_ke_database.py dulu.")
        return

    print(f"Menormalkan {total} entri (kamus: {len(kamus)} pemetaan varian)")
    mulai = time.time()

    diisi = 0
    tidak_berubah = 0
    kosong = []               # judul yang habis setelah normalisasi
    per_tipe = Counter()

    # Seluruh baris diambil dulu ke memori (4.219 baris, ringan). Melakukan
    # flush di tengah iterasi streaming akan memutus kursor unbuffered
    # PyMySQL dan diam-diam menghentikan proses di tengah jalan.
    semua = EntriDokumen.query.all()

    for i, entri in enumerate(semua, 1):
        baru = normalisasi(entri.judul)

        if not baru:
            # Judul yang seluruh isinya terbuang - biasanya judul yang hanya
            # berisi angka/tanda baca. Dicatat, bukan disembunyikan.
            kosong.append((entri.id, entri.publikasi_id, entri.judul))

        if entri.teks_ternormalisasi == baru:
            tidak_berubah += 1
        else:
            entri.teks_ternormalisasi = baru
            diisi += 1
            per_tipe[entri.tipe] += 1

        if i % UKURAN_BATCH == 0:
            print(f"  {i}/{total} ...", flush=True)

    pub_diubah, pub_tanpa_abstrak = _isi_publikasi()
    db.session.commit()

    # -------------------------- Verifikasi --------------------------
    terisi = EntriDokumen.query.filter(
        EntriDokumen.teks_ternormalisasi.isnot(None),
        EntriDokumen.teks_ternormalisasi != "").count()
    null_atau_kosong = total - terisi

    print()
    print("=" * 70)
    print("RINGKASAN NORMALISASI")
    print("=" * 70)
    print(f"Entri diproses      : {total}")
    print(f"Nilai ditulis/diubah: {diisi}")
    print(f"Sudah sama (dilewat): {tidak_berubah}")
    print(f"Terisi di database  : {terisi}/{total}")
    print(f"Kosong setelah normalisasi: {null_atau_kosong}")

    pub_total = Publikasi.query.count()
    pub_terisi = Publikasi.query.filter(
        Publikasi.teks_ternormalisasi.isnot(None),
        Publikasi.teks_ternormalisasi != "").count()
    print()
    print(f"Publikasi diproses  : {pub_total}")
    print(f"  nilai diubah      : {pub_diubah}")
    print(f"  terisi            : {pub_terisi}/{pub_total}")
    print(f"  tanpa abstrak     : {pub_tanpa_abstrak} (judul saja)")
    print(f"Waktu               : {time.time() - mulai:.1f} detik")

    if per_tipe:
        print()
        print("Yang berubah, per tipe:")
        for t, n in sorted(per_tipe.items()):
            print(f"  {t:<10} {n:>6}")

    if kosong:
        print()
        print(f"JUDUL YANG HABIS SETELAH NORMALISASI ({len(kosong)}):")
        for eid, pid, judul in kosong[:20]:
            print(f"  entri {eid} (pub {pid[:8]}): {judul[:60]!r}")
        if len(kosong) > 20:
            print(f"  ... dan {len(kosong) - 20} lainnya")

    # Contoh hasil, supaya bisa dilihat sekilas apakah masuk akal.
    print()
    print("Contoh hasil:")
    for e in EntriDokumen.query.filter(
            EntriDokumen.teks_ternormalisasi != "").limit(5):
        print(f"  {e.judul[:52]}")
        print(f"    -> {e.teks_ternormalisasi[:70]}")

    print()
    print(f"cache stemmer: {stem_kata.cache_info()}")




def main():
    app = create_app()
    with app.app_context():
        jalankan()


if __name__ == "__main__":
    main()
