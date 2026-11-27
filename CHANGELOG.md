# Catatan Perubahan

## v1.0.0 — 27 November 2026 (serah terima)

Versi pertama yang dibekukan untuk diserahkan ke BPS Provinsi Kalimantan
Selatan. Rincian operasional ada di [PANDUAN.md](PANDUAN.md); bukti tiap
perubahan ada di laporan `data/regresi/`.

### Pencarian
- Satu kotak pencarian untuk publikasi Provinsi Kalimantan Selatan, 13
  kabupaten/kota, dan "Kecamatan … Dalam Angka". Data: rilis 2025–2026,
  622 publikasi, 44.649 bagian terindeks per 27 November 2026.
- Hasil menunjukkan publikasi DAN bagiannya: tabel, gambar, lampiran,
  bab. Tombol **Buka PDF** membuka langsung halaman yang tepat.
  - 39.694 bagian (88,9%) punya nomor halaman PDF;
  - 5.012 di antaranya halaman perkiraan, bertanda "±hal.".
- Pemrosesan kata kunci: kata dasar Bahasa Indonesia (Sastrawi), kamus
  sinonim (101 kelompok, 212 kata), fuzzy matching dengan skor 0–100.
  Ambang 75/50 masih sementara.
- Filter wilayah lewat daftar pilihan, atau dikenali dari kata kunci (nama
  dan singkatan resmi kab/kota). Pilihan kecamatan lewat kotak centang.
- Saran kata kunci saat mengetik, sampul publikasi di kartu publikasi,
  tombol "Ke atas", dan tampilan ponsel.
- Kembali dari halaman admin ke hasil pencarian terakhir, dengan posisi
  gulir yang sama.

### Data dan pembaruan
- Penarikan dari WebAPI BPS dengan jeda 1 detik antar permintaan, sesuai
  Term of Use.
- Pembacaan PDF berbasis koordinat kata, dua jalur (halaman Daftar dan badan
  dokumen). OCR opsional (EasyOCR) untuk PDF tanpa lapisan teks; 34
  publikasi memakainya.
- **Formulir pembaruan** di halaman admin: wilayah, jenis (kab/kota atau
  kecamatan), dan tahun rilis.
  - Tombol **Cek dulu** menampilkan perkiraan jumlah, ukuran, dan lama
    unduhan, dengan status warna, sebelum ada yang diunduh.
  - Ruang disk yang kurang membuat pembaruan ditolak.
- Hanya satu pembaruan pada satu waktu, baik dari browser maupun dari skrip.
  Ringkasan hasil dan log tiap run tersimpan.
- Sampul resmi dari WebAPI. Kalau unduhannya gagal, dipakai halaman 1 PDF.

### Halaman admin
- Terpisah dari halaman pencarian, dibuka lewat tombol **Halaman Admin**.
  Satu kata sandi bersama.
- Fitur: Kamus Sinonim (ubah lalu "Terapkan ke data"), Log Pencarian, Perbarui
  Data, Ganti Kata Sandi. Kartu beranda admin menampilkan angka terbaru.
- Keamanan:
  - sesi berakhir sesudah tidak aktif (`SESI_ADMIN_MENIT`, bawaan 120
    menit);
  - login dikunci 5 menit sesudah 5 sandi salah, dengan hitung mundur;
  - dukungan reverse proxy (`JUMLAH_PROXY`);
  - alamat kembali yang aman (tidak bisa dipakai untuk mengalihkan ke situs
    lain).

### Pemasangan dan portabilitas
- Windows: `jalankan-aplikasi.bat`, `perbarui-data.bat`; server waitress;
  port dari `.env`.
- Linux: padanan `.sh` untuk tiap `.bat`. Teruji di Ubuntu 22.04 (Python
  3.12, MySQL 8.0): hasil pencarian sama persis dengan di Windows (28/28
  halaman).
  - Layanan systemd dan pemasangan lewat `apt` belum diuji (PANDUAN 7.4).
- Paket serah terima di `data/serah_terima/` (tidak masuk Git; lihat
  `BACA-DULU.txt` di dalamnya):
  - cadangan database;
  - manifest sidik PDF/sampul/cache OCR;
  - pemeriksa `scripts/periksa_sidik.py`.
- `tests/uji_pipeline.py`: uji ujung ke ujung di database uji (tidak
  menyentuh produksi dan tidak menghubungi BPS).

### Utang teknis yang masih terbuka
Rincian di PANDUAN bagian 11 ("Keterbatasan yang diketahui dan utang
teknis") dan bagian 12 ("Saran pengembangan"). Yang terpenting:

- **Ambang skor:** 75/50 belum dikalibrasi dengan kata kunci asli petugas.
- **Mutu pembacaan PDF:**
  - beberapa judul tabel kadang tergabung menjadi satu bagian;
  - sekitar 2,5–3% judul dari badan dokumen tercampur teks sekitarnya;
  - sebagian Daftar di PDF sumber salah cetak.
- **Sensus Pertanian 2023 Tahap II** (rilis 2024, di luar cakupan
  2025–2026): format keterangan tabelnya belum dikenali.
- **Pencarian belum punya:** toleransi salah ketik satu kata, filter tahun,
  pencarian isi sel tabel, deteksi nama kecamatan dari kata kunci.
- **Pengelolaan:**
  - penguncian login hanya disimpan di memori aplikasi;
  - log belum mencatat hasil seksi kecamatan dan klik "Buka PDF".
- **Lisensi berkas model OCR** belum jelas (PANDUAN 7.3).
- **Linux:** layanan systemd, `apt`, membuka arsip `tar` di Linux, dan bagian
  uji P, D, W, Q, G belum dijalankan di Linux.
