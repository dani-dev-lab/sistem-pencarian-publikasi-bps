"""Isi kolom teks_ternormalisasi untuk entri_dokumen DAN publikasi.

Memakai `app.services.preprocessing.normalisasi()` - fungsi yang SAMA persis
dengan yang dipakai saat memproses kueri petugas. Kalau keduanya berbeda, skor
kemiripan jadi tidak bermakna.

IDEMPOTEN: menulis ulang nilai, bukan menambah baris. Aman dijalankan lagi
setiap kali kamus sinonim diperbarui - dan memang HARUS dijalankan ulang,
karena isi kolom ini bergantung pada kamus.

Dipanggil dari dua tempat: scripts/isi_normalisasi.py (terminal) dan tombol
"Terapkan ke data" di /admin/kamus. Logikanya di sini, di dalam paket app,
supaya route admin tidak perlu mengimpor berkas dari folder scripts/.
"""

import time
from collections import Counter

import sqlalchemy as sa

from app.models import EntriDokumen, Publikasi, db
from app.services import versi_data
from app.services.preprocessing import kamus_default, normalisasi, stem_kata

UKURAN_BATCH = 500


def _pastikan_kolom():
    """Tambah kolom publikasi.teks_ternormalisasi kalau belum ada.

    Project ini belum memakai alat migrasi, dan db.create_all() tidak mengubah
    tabel yang sudah terlanjur ada. Pengecekan ini membuat proses tetap aman
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
            return True
    return False


def teks_publikasi(judul, abstrak):
    """Teks ternormalisasi satu publikasi: judul + abstrak.

    Keduanya digabung supaya istilah yang HANYA muncul di abstrak (misalnya
    nama instansi sumber data) tetap bisa dicari. Satu fungsi untuk pipeline
    pembaruan maupun tombol "Terapkan ke data", supaya hasilnya tidak berbeda.
    """
    return normalisasi(f"{judul or ''} {abstrak or ''}")


def _isi_publikasi():
    """Normalkan judul + abstrak seluruh publikasi."""
    diubah = 0
    tanpa_abstrak = 0
    for p in Publikasi.query.all():
        if not p.abstrak:
            tanpa_abstrak += 1
        baru = teks_publikasi(p.judul, p.abstrak)
        if p.teks_ternormalisasi != baru:
            p.teks_ternormalisasi = baru
            diubah += 1
    return diubah, tanpa_abstrak


def _diam(*_args, **_kwargs):
    pass


def jalankan(cetak=_diam):
    """Isi teks_ternormalisasi. HARUS dipanggil di dalam app context.

    `cetak` menerima fungsi bergaya print untuk laporan rinci di terminal;
    dari halaman web dibiarkan diam dan hanya ringkasannya yang dipakai.

    Return dict ringkasan:
      entri_total, entri_diubah, entri_tidak_berubah, entri_terisi,
      entri_kosong (judul yang habis setelah normalisasi),
      publikasi_total, publikasi_diubah, publikasi_terisi, waktu_detik.
    Return None kalau tabel entri_dokumen masih kosong.
    """
    if _pastikan_kolom():
        cetak("kolom publikasi.teks_ternormalisasi ditambahkan")
    versi_data.pastikan_tabel()     # DDL sebelum transaksi, lihat versi_data.py
    kamus = kamus_default()
    total = EntriDokumen.query.count()
    if not total:
        cetak("Tabel entri_dokumen kosong - jalankan perbarui-data.bat dulu.")
        return None

    cetak(f"Menormalkan {total} entri (kamus: {len(kamus)} pemetaan varian)")
    mulai = time.time()

    diisi = 0
    tidak_berubah = 0
    kosong = []               # judul yang habis setelah normalisasi
    per_tipe = Counter()

    # Seluruh baris diambil dulu ke memori (ribuan baris, ringan). Melakukan
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
            cetak(f"  {i}/{total} ...", flush=True)

    pub_diubah, pub_tanpa_abstrak = _isi_publikasi()
    versi_data.naikkan()            # korpus pencarian di memori perlu dimuat ulang
    db.session.commit()

    # -------------------------- Verifikasi --------------------------
    terisi = EntriDokumen.query.filter(
        EntriDokumen.teks_ternormalisasi.isnot(None),
        EntriDokumen.teks_ternormalisasi != "").count()
    pub_total = Publikasi.query.count()
    pub_terisi = Publikasi.query.filter(
        Publikasi.teks_ternormalisasi.isnot(None),
        Publikasi.teks_ternormalisasi != "").count()
    waktu = time.time() - mulai

    cetak()
    cetak("=" * 70)
    cetak("RINGKASAN NORMALISASI")
    cetak("=" * 70)
    cetak(f"Entri diproses      : {total}")
    cetak(f"Nilai ditulis/diubah: {diisi}")
    cetak(f"Sudah sama (dilewat): {tidak_berubah}")
    cetak(f"Terisi di database  : {terisi}/{total}")
    cetak(f"Kosong setelah normalisasi: {total - terisi}")
    cetak()
    cetak(f"Publikasi diproses  : {pub_total}")
    cetak(f"  nilai diubah      : {pub_diubah}")
    cetak(f"  terisi            : {pub_terisi}/{pub_total}")
    cetak(f"  tanpa abstrak     : {pub_tanpa_abstrak} (judul saja)")
    cetak(f"Waktu               : {waktu:.1f} detik")

    if per_tipe:
        cetak()
        cetak("Yang berubah, per tipe:")
        for t, n in sorted(per_tipe.items()):
            cetak(f"  {t:<10} {n:>6}")

    if kosong:
        cetak()
        cetak(f"JUDUL YANG HABIS SETELAH NORMALISASI ({len(kosong)}):")
        for eid, pid, judul in kosong[:20]:
            cetak(f"  entri {eid} (pub {pid[:8]}): {judul[:60]!r}")
        if len(kosong) > 20:
            cetak(f"  ... dan {len(kosong) - 20} lainnya")

    # Contoh hasil, supaya bisa dilihat sekilas apakah masuk akal.
    cetak()
    cetak("Contoh hasil:")
    for e in EntriDokumen.query.filter(
            EntriDokumen.teks_ternormalisasi != "").limit(5):
        cetak(f"  {e.judul[:52]}")
        cetak(f"    -> {e.teks_ternormalisasi[:70]}")

    cetak()
    cetak(f"cache stemmer: {stem_kata.cache_info()}")

    return {
        "entri_total": total,
        "entri_diubah": diisi,
        "entri_tidak_berubah": tidak_berubah,
        "entri_terisi": terisi,
        "entri_kosong": len(kosong),
        "publikasi_total": pub_total,
        "publikasi_diubah": pub_diubah,
        "publikasi_terisi": pub_terisi,
        "waktu_detik": waktu,
    }
