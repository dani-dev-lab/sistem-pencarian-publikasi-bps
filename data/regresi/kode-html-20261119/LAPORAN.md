# Kode HTML di judul/abstrak publikasi (19 Nov 2026)

Temuan pemilik project: abstrak "Kecamatan Kintap Dalam Angka 2026"
menampilkan "Kintap&nbsp;selama" mentah.

## Yang terkena
Dihitung sebelum perbaikan, di produksi dan database uji sama:
- **25 abstrak** memuat kode `&nbsp;` (30 kemunculan; 15 publikasi
  kecamatan). Tidak ada kode HTML lain.
- **1 judul** memuat karakter spasi tak-putus mentah (U+00A0, "Agustus 2024"
  di Keadaan Angkatan Kerja). Tidak tertangkap hitungan pertama karena
  bukan kode `&...;`. Ikut dibersihkan karena kasusnya sama.
- Akibatnya `&nbsp;` tampil mentah di kartu, dan "nbsp" ikut masuk teks
  pencocokan publikasi.

## Perbaikan
- `normalisasi_data.bersihkan_html`: `html.unescape` + spasi tak-putus ->
  spasi biasa.
- `pipeline_data.simpan_metadata` membersihkan judul dan abstrak dari API
  sebelum disimpan, jadi publikasi baru tidak membawa kode HTML.
- Data lama: `scripts/bersihkan_kode_html.py (--db-uji | --produksi) [--coba]`.
  - Judul/abstrak dibersihkan, `teks_ternormalisasi` publikasi dihitung
    ulang, `versi_data` naik.
  - Satu transaksi, idempoten, dan menghormati kunci pembaruan.

## Bukti
- **Database uji:**
  - 26 dibersihkan; jalan kedua 0;
  - entri sama; versi +1;
  - halaman: 2/28 berubah, hanya kartu publikasi yang dibersihkan
    (`cc314c14`, skor 57,4 -> 57,5; `&nbsp;`-nya di luar 400 karakter
    cuplikan). Kartu entri dan bagian lain identik.
- **Produksi:**
  - cadangan `cadangan-bps/db_pencarian_bps-20261119-sebelum-kode-html.sql`;
  - `--coba` 26, lalu muat;
  - per id: **26 publikasi berubah** = daftar yang dibersihkan = daftar
    database uji. Kolomnya hanya `abstrak`+`teks_ternormalisasi` (25) dan
    `judul` (1), plus `updated_at`;
  - entri, `log_pencarian`, `kategori`, `publikasi_kategori` sama;
  - `versi_data` 530 -> 531;
  - halaman produksi sama dengan database uji: 2/28 berubah, hanya kartu
    `cc314c14`.
  - Sisa `&nbsp;`, "nbsp", dan U+00A0 di judul: 0.
- Contoh Kintap 2026 sekarang: "...Kintap selama..." (`contoh_kintap.txt`).
