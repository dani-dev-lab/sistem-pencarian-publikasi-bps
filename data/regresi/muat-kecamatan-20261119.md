# Pemuatan publikasi Kecamatan Dalam Angka ke PRODUKSI (Kamis 19 Nov 2026, 08.02-08.20)

Rencana: `rencana-muat-kecamatan-20261119.md`, disetujui pemilik project
(18 Nov malam). Keputusannya:
- salin dari database uji;
- `kecualikan_judul.aktif` = false;
- 5 publikasi pola 2+3 dimuat di langkah terpisah.

**Semua bukti cocok.** Skrip dan keluaran ada di `muat-kecamatan-20261119/`.

## Sebelum pemuatan: seksi Publikasi diperbaiki (`3db1e8b`)
Temuan pemilik project di browser: dengan centang + Kec. Kintap, publikasi
"Kecamatan Kintap Dalam Angka 2026" tidak muncul di seksi Publikasi.
- **Perbaikan:**
  - publikasi kecamatan kini ikut dinilai dengan skor yang sama;
  - yang dipilih didahulukan;
  - publikasi utama tidak pernah tergeser;
  - publikasi kecamatan lain paling banyak 10.
- **Uji:**
  - salinan produksi 28/28 identik;
  - `uji_pipeline.py --hanya V`: 11 lulus, termasuk V5 baru (Kec. Binuang,
    domain uji). V3 kini membandingkan putaran tercepat dari 3, karena
    lonjakan sesaat 111/113 ms sempat menggagalkannya tanpa sebab kode;
  - Playwright 36/36.

## Langkah dan bukti
| # | Langkah | Hasil |
|---|---|---|
| 0 | Prasyarat | Tidak ada `pembaruan.lock`, aplikasi produksi tidak berjalan. Sidik sumber (database uji): 312 publikasi, 19.955 entri (`sumber_uji_sidik.txt`). |
| 1 | Cadangan | `cadangan-bps/db_pencarian_bps-20261119-sebelum-kecamatan.sql` (8,8 MB). Dipulihkan ke database sementara: **6/6 tabel sama** (baris + CHECKSUM), lalu dihapus. |
| 2 | Kolom baru | `publikasi.kecamatan`, `log_pencarian.sertakan_kecamatan` (0 terisi). Sidik kolom lama sebelum = sesudah ALTER. Potret produksi SEBELUM (28 URL, log mati). |
| 3 | `--coba` | 312/19.955 tersisip lalu ROLLBACK; produksi tidak berubah (sidik sama, versi 509). Penghitung AUTO_INCREMENT tidak ikut di-rollback (MySQL), sehingga id entri yang dimuat melompat ±20 ribu. Tidak berbahaya. |
| 4 | Muat | Satu transaksi, 08.04.27-08.04.29: publikasi 312, entri 19.955, versi_data 509 -> 510. |
| 5 | 5 publikasi pola 2+3 | Per publikasi: PDF/sidik cocok di produksi dan uji; entri produksi = keadaan sebelum regresi; hasil ekstraksi = database uji SEBELUM ditulis dan SESUDAH ditulis. 22->24, 23->24, 57->60, 57->60, 89->90; versi 510 -> 515. |
| 6 | `wilayah.json` | `kecualikan_judul` pola kecamatan `aktif: false` (0 pola aktif); `pola_kecamatan` tetap menandai. |
| 8 | Pembaruan rutin online | 08.14-08.17, kode keluar 0. 13 kab/kota "tidak_ada_baru", 0 dikecualikan, tidak ada "tidak lagi di daftar". **1 publikasi baru dari BPS**: Profil Tenaga Kerja Provinsi Februari 2026 (rilis 17 Nov, 51 entri). Tidak ada kecamatan yang diunduh ulang. Versi 515 -> 530. |

**Bukti (langkah 7):**
- **Isi kecamatan produksi = database uji baris demi baris** (berurutan dan
  multiset): publikasi 312, entri 19.955 (`bukti_isi_kecamatan.txt`). Entri
  5 publikasi pola 2+3: 258 = 258.
- **Per id, dibandingkan dengan cadangan yang dipulihkan** (`bukti_per_id.txt`):
  - 24.284 entri publikasi lain identik, 0 entri baru di luar target;
  - publikasi lama hanya berubah di 5 target, hanya
    `diekstrak_pada`/`catatan_ekstraksi`;
  - `log_pencarian` (143) dan `kategori` sama.
- **Tanpa centang identik, langsung di produksi:** potret SESUDAH vs SEBELUM
  28/28 identik setelah widget kecamatan dibuang (`bukti_potret_produksi.txt`).
  Potret sesudah memang memuat widget (beranda, dropdown, kotak info), jadi
  yang dipotret adalah produksi yang sudah berisi kecamatan.
- **Dengan centang** (`bukti_centang.txt`): 3 kueri, seksi kecamatan tampil;
  tombol PDF 5 kartu per kueri = **15/15** halaman memuat nomor/awal judul.
  Versi alat pertama menandai Gambar 4 Mataraman 2025 hal. 41 sebagai CEK.
  Sebabnya: publikasi itu publikasi OCR, dan alatnya hanya membaca lapisan
  teks. Halamannya dirender dan dicek: benar. Alat lalu memakai cache OCR.
- **Kinerja** (`kinerja_produksi.txt`):
  - `ukur_kinerja.py` 122 ms, tetapi laptop sedang ±2x lebih lambat (muat
    ulang korpus 1.716 vs 860 ms kemarin);
  - bergantian dengan salinan produksi sebelum pemuatan, putaran
    tercepat: produksi **110,9 ms**, salinan 120,5 ms (-7,9%);
  - memori korpus 144 MB.
- **Sesudah pembaruan rutin:** entri kecamatan tidak tersentuh (sidik =
  sumber). Hanya `url_pdf` 312 publikasi kecamatan yang berganti, yaitu URL
  bertoken dari BPS.

## Uji tambahan (permintaan pemilik project): kecamatan dari kabupaten lain
Produksi, hanya baca, log mati (`bukti_publikasi_kecamatan_lain.txt`):
Martapura Timur (Banjar), Tanjung (Tabalong), Banjarmasin Utara.
- **Judul publikasinya + kecamatan dipilih:** 6/6 publikasi kecamatan itu
  paling atas berlabel "Kec. X" (edisi 2026 dan 2025).
- **Tanpa centang:** 3/3 tanpa publikasi kecamatan.
- **"penduduk" + kecamatan dipilih:** Tanjung dan Banjarmasin Utara di paling
  atas. **Martapura Timur tidak muncul di seksi Publikasi**, karena abstrak
  kedua edisinya tidak menyebut "penduduk" (tidak lolos ambang; Tanjung
  berskor 66). Tabel penduduknya tetap ada di seksi kecamatan.
  - Ini aturan yang berlaku (didahulukan di antara yang cocok), bukan
    kesalahan pemuatan. Kriteria uji saya mengandaikan publikasi yang dipilih
    selalu tampil.
  - **Keputusan terbuka:** apakah publikasi kecamatan yang dipilih SELALU
    ditampilkan di seksi Publikasi, walau tidak cocok dengan kata kunci.

## Keadaan produksi sekarang
- 620 publikasi (312 kecamatan) dan 44.548 entri.
- `versi_data` 530.
- `log_pencarian` 143.
- Aplikasi belum dijalankan ulang sesudah pemuatan. Saat dijalankan, korpus
  dimuat dengan kecamatan, dan kotak centang tampil (bawaan mati).
