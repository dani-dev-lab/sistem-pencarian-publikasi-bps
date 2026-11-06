# Laporan migrasi multi-domain ke data asli - 6 November 2026

## Kesimpulan

Migrasi ke `db_pencarian_bps` dan `data/publikasi_pdf/` **berhasil**. Kedua tes
regresi menghasilkan isi yang **IDENTIK** dengan baseline sebelum rombakan
(`potret-79-sebelum-rombakan.json`: 79 publikasi, 6.812 entri).

Kode yang dijalankan adalah commit `06f12ae` di branch `revisi-pst`.

## Urutan yang dijalankan

| Waktu | Langkah | Hasil |
|---|---|---|
| 09.43 | Pemeriksaan awal | Tidak ada aplikasi atau pembaruan yang berjalan. Data sama dengan 5 November sore: 0 publikasi berbeda dari potret |
| 09.43 | Cadangan baru | `db_pencarian_bps-20261106-0943-sebelum-migrasi.sql` (SHA-256 `66d52d2b…`). Dipulihkan ke DB terpisah: lima tabel cocok jumlah baris dan checksumnya, termasuk 30 baris log |
| 09.44 | Migrasi | Exit 0, 2 detik. 10 kolom ditambahkan, 79 publikasi diisi, 79 PDF dipindah ke `6300/` |
| 09.44 | Regresi 1 | **IDENTIK** |
| 09.46-10.16 | Regresi 2 (`perbarui.py --lokal --paksa`) | 79 diproses, 0 gagal, 1.839 detik. **IDENTIK** |

## Pemeriksaan sesudah migrasi

| Pemeriksaan | Hasil |
|---|---|
| Domain dan wilayah | 79 dari 79: `6300`, "Provinsi Kalimantan Selatan" |
| `updt_date` | 7 usang ditandai, 18 tanpa tanggal, 54 cocok |
| `diekstrak_pada`, sidik, catatan | Terisi 79 dari 79, galat 0 |
| Kolom `domain` | `char(4)` NOT NULL, indeks `ix_publikasi_domain` ada |
| PDF di path baru | 79 dari 79 utuh, sidik di DB cocok dengan berkas |
| `/pdf/<id>` | 79 dari 79 menyajikan berkas lokal, tanpa redirect |
| Tombol Buka PDF di `/hasil` | 40 dari 40 tanpa redirect |
| Rencana `--lokal` | 0 tugas, 7 menunggu unduhan online |

## Pemeriksaan sesudah regresi 2

| Pemeriksaan | Hasil |
|---|---|
| Jumlah data | 79 publikasi, 6.812 entri, 30 log |
| 7 PDF usang | Tetap ditandai: `--lokal --paksa` tidak memajukan `updt_date_diproses` |
| `teks_ternormalisasi` kosong | 0 |
| Galat ekstraksi | 0 |
| Sidik PDF | 79 dari 79 cocok |
| Laporan "perlu diperiksa" | 23 publikasi, sama dengan daftar `ekstrak_semua.py` pada 5 November |

## Kejadian selama migrasi

Pemeriksaan tombol Buka PDF lewat route `/hasil` **mencatat 1 kueri uji ke
`log_pencarian` asli** ("statistik ekspor", `id` 31), karena route itu memang
mencatat setiap pencarian. Baris itu dihapus berdasarkan `id`-nya setelah
diperiksa. Log kembali 30 baris, sama dengan isi cadangan. Sesudah itu,
pemeriksaan pada data asli tidak lagi memanggil `/hasil`.

## Potret yang tidak di-commit

Kedua potret baru isinya sama dengan baseline, yang sudah ada di Git; yang
berbeda hanya cap waktu `dibuat_pada`. Berkasnya disimpan di
`C:\Users\Dani\cadangan-bps\`, di luar repo.

| Berkas | SHA-256 |
|---|---|
| `potret-79-sesudah-migrasi.json` | `30ec1ec2345e10bde24c5334765a522e967408a877537031635006d7479a4000` |
| `potret-79-sesudah-regresi2.json` | `0f4d0901644414c54c7a2dc2e9e5ceb5140ed3d392dc1bd6ff0e1f2d099e4916` |

## Sesudah JSON dihapus (commit `11f759c`)

Tag `arsip-sebelum-rombakan` dibuat di `06f12ae` SEBELUM penghapusan. Kelima
belas berkas yang dibahas ada di tag itu dan identik dengan versi di disk. Tiga
baseline yang berukuran sama juga terbukti identik isinya.

Uji asap tanpa API dan tanpa menulis `log_pencarian`:

| Uji | Hasil |
|---|---|
| `run.py` (waitress) di port terpisah | Menjawab. `/` tampil dengan notice BPS, `/api/saran` memberi 8 saran, `/pdf/<id>` menyajikan berkas lokal |
| `/hasil?q=tingkat penghunian kamar` | 200: 2 publikasi, 23 bagian, 25 tombol PDF. Pencatatan log diganti penangkap, jadi tidak ada yang ditulis |
| `perbarui.py --lokal` | Exit 0, `tidak_ada_baru`, 0 diproses, 7 menunggu unduhan, 0 gagal |
| `log_pencarian` | 30 baris di awal dan akhir |
| Berkas JSON lama yang dibuka selama uji | **Tidak ada.** Dicatat dengan audit hook Python yang dibuktikan dulu lewat kontrol positif: membuka `data/hasil_ekstraksi.json` dengan dua bentuk path, dan keduanya tertangkap |

Rujukan yang tersisa (grep): kode yang akan rusak kalau dijalankan, yaitu
`ambil_publikasi.py`, `unduh_pdf.py`, `ekstrak_semua.py`, dan
`muat_ke_database.py`. Keempatnya tidak termasuk daftar hapus yang disetujui
dan masih menunggu keputusan. Rujukan lainnya disengaja atau sekadar catatan
sejarah:

- `migrasi_multidomain.py`: hanya kalau masih ada baris yang belum dimigrasi.
- `tests/uji_pipeline.py`: khusus keadaan sebelum migrasi.
- Komentar model, `CLAUDE.md` (belum diperbarui), log lama, data
  `ukur_kinerja`, dan laporan.

## Waktu ekstraksi

| Run | Tanggal | Detik |
|---|---|---:|
| Uji kontrol, kode lama tanpa `cari_heading()` terpisah | 5 Nov 11.19 | 1.215 |
| Uji terisolasi, run 2 | 5 Nov | 1.560 |
| Uji terisolasi, run 3 | 5 Nov | 1.685 |
| Regresi 2 pada data asli | 6 Nov 09.46 | 1.839 |

### Penyelidikan (6 Nov 10.43-10.50)

Sepuluh PDF (5 s.d. 19 detik per PDF pada uji kontrol) diukur bergantian dengan
urutan A-B-B-A dalam satu proses. Yang dicatat: waktu jam dinding dan waktu CPU
proses.

- A = cara uji kontrol: `ekstrak_lengkap()` saja.
- B = jalur baru: `ekstrak_berkas()`, yaitu `cari_heading()` terpisah lalu
  `ekstrak_lengkap()`.

| Ukuran (10 PDF) | Jam dinding | CPU |
|---|---:|---:|
| A, uji kontrol 5 Nov | 85,4 | - |
| A, hari ini (rata-rata A1 dan A2) | 89,1 | 88,5 |
| B, hari ini (rata-rata B1 dan B2) | 103,3 | 103,0 |
| `cari_heading()` saja | 16,1 | 15,9 |

Temuan:

1. **Jalur baru lebih lambat sekitar 16% karena heading dicari dua kali.**
   `ekstrak_lengkap()` sudah memanggil `cari_heading()` di dalamnya, lalu
   `ekstrak_berkas()` memanggilnya lagi untuk mencatat heading. Selisih B dan A
   (14,2 detik) setara dengan biaya `cari_heading()` sendirian (16,1 detik).
   `ekstrak_semua.py` lama juga memanggilnya dua kali, jadi pipeline lama
   menanggung biaya yang sama. Yang tidak menanggungnya hanya uji kontrol, dan
   karena itu angka 1.215 detik bukan waktu pipeline lama.
2. **Tidak ada proses yang menunggu.** Waktu jam dinding hampir sama dengan
   waktu CPU di semua pengukuran, jadi waktu tidak habis untuk menunggu disk
   atau pemindaian berkas.
3. **Windows Search bukan penyebab.** Kueri indeks menemukan 108 item di
   Start Menu dan ≥5.000 di Documents (kontrol positif), tetapi 0 di
   `C:\sistem-pencarian-bps`.
4. **Defender tidak berpengaruh berarti.** Perlindungan real-time aktif. Salinan
   baru 3 PDF yang belum pernah dibuka memberi selisih jam dinding dan CPU hanya
   +0,03 s.d. +0,07 detik pada pembukaan pertama. Tidak ada peristiwa pindai
   hari ini. Pindai cepat 5 Nov 14.50-14.52 bertepatan dengan run 2, tetapi
   hanya 3 menit. Daftar pengecualian Defender tidak bisa dibaca tanpa hak admin.
5. **Sisanya belum terjelaskan.** Dengan +16%, 1.215 detik menjadi sekitar
   1.410 detik, padahal yang teramati 1.560-1.839 detik. PDF yang sama
   bervariasi sampai ±50% antar-ulangan dalam hitungan menit, dan waktu CPU-nya
   ikut naik. Ini cocok dengan kecepatan CPU yang berubah-ubah (boost/suhu),
   tetapi belum dibuktikan. Perlambatan bertahap dalam satu proses panjang
   (79 PDF) juga belum diuji.

**Saran untuk revisi 3:** jangan bandingkan angka dari run atau hari yang
berbeda. Ukur pipeline lama dan baru bergantian dalam satu sesi. Sebagai
alternatif, catat waktu per PDF di `catatan_ekstraksi` supaya sebaran waktunya
terlihat.

## Belum dikerjakan

- Keputusan tentang `ambil_publikasi.py`, `unduh_pdf.py`, `ekstrak_semua.py`, dan
  `muat_ke_database.py`.
- Pembaruan `PANDUAN.md`, `README.md`, dan `CLAUDE.md`.
- Pembaruan online pertama (masih menunggu DNS), termasuk potret 7 publikasi
  usang sebelum dan sesudahnya.
