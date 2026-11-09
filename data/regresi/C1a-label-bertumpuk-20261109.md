# C1(a): penanda label bertumpuk di `lengkapi_halaman_fisik` (9 Nov 2026)

Langkah pertama dari usulan `penyelidikan-C-20261107.md`.

## Perubahan
- `_penanda_bertumpuk(kelompok)` mengenali keterangan Dalam Angka yang
  menumpuk label, nomor, dan label Inggris di kolom kiri ("Tabel" / "1.1.1" /
  "Table"), sejajar dengan judul di kolom kanan.
- **Syaratnya:**
  - baris diawali label TANPA nomor DAN memuat teks judul, sehingga kop
    "LAMPIRAN" di atas nomor halaman berjalan tertolak;
  - dalam 2 baris sesudahnya ada baris berisi SATU token nomor, letaknya di
    antara x label dan x awal judul.
- **Kekuatan penanda:** dianggap sekuat "awal baris". Syarat kata judul yang
  sudah ada tetap berlaku.
- **Seperti sebelumnya:** hanya MENGISI kolom kosong, tanpa entri baru dan
  tanpa judul yang berubah.

## Regresi 79 PDF (uji kering vs database = baseline `potret-79-sesudah-halaman-isi.json`)
Pembanding memasangkan entri menurut kunci `(tipe, nomor)`.

| Syarat | Hasil |
|---|---|
| `(publikasi, tipe, nomor)` hilang / bertambah | 0 / 0 |
| Entri kehilangan `halaman_fisik` | 0 |
| `halaman_fisik` berpindah | 2, keduanya koreksi (lihat bawah) |
| Sumber berubah | 0 |
| Entri berubah | 639, SEMUANYA hanya `halaman_fisik` |

`halaman_fisik` baru: 637.

| Publikasi | Tambahan |
|---|---|
| Dalam Angka 2025 | 308 |
| Dalam Angka 2026 | 295 |
| PDRB Pengeluaran 2026 (`f11b837f`) | 32 |
| PDRB Kab/Kota (`83f521a7`) | 2 |

Per tipe: tabel 630, lampiran 5, gambar 4.

### Dua yang berpindah
Keduanya di PDRB Pengeluaran:
- **Gambar 3.1: 60 → 59.** Folio hal. 59 = "45" = halaman cetak entri.
- **Tabel 3.1: 74 → 57.** Nilai lama berasal dari **bug lama**: penanda
  "tabel 3.1" dicocokkan dengan `startswith`, sehingga ikut cocok dengan
  baris "Tabel 3.12 …" di hal. 74. Penanda bertumpuk memakai kecocokan
  persis, jadi tidak terkena.

Bug awalan itu masih berlaku untuk penanda biasa. Calon korban di korpus
(entri yang berhalaman fisik sama dengan entri bernomor "awalan + digit"):
4 entri.
- Tinjauan PDRB Kab/Kota `11487263` gambar 2.2 (= gambar 2.20);
- PDRB LU `2223fbff` dan `fed52821` gambar 2 (= gambar 23/25);
- IKR `b4541a05` lampiran 1 (= lampiran 13).

Ini belum dibuktikan per halaman dan belum diperbaiki. Perbaikannya (batas
kata pada penanda) sebaiknya menjadi perubahan tersendiri.

### Ketepatan
Sebaran selisih fisik−cetak per publikasi:

| Publikasi | Selisih |
|---|---|
| Dalam Angka 2026 | +56 (291), tanpa cetak 4 |
| Dalam Angka 2025 | +56 (293), tanpa cetak 12, +54/+55 (3) |

Semua yang menyimpang dibuka halamannya:
- **Dalam Angka:** pemicunya keterangan bertumpuk dengan nomor persis, dan
  folio halaman cocok. Yang meleset nomor halaman CETAK dari jalur daftar
  (misalnya 1.1.8 tertulis 20 padahal foliony 18), bukan halaman fisiknya.
- **PDRB Pengeluaran:** entri jalur daftar publikasi ini memang kacau
  (judul dan nomor tertukar). Ini publikasi asal entri gabungan "ekspor
  batubara". Pengisiannya mengikuti NOMOR, dan keterangan "Tabel 3.2/3.3"
  memang ada di hal. 58/61.

**Sampel acak 30 (seed 20261109), dibaca satu per satu: 30 benar.** Untuk
setiap sampel, baris pemicunya keterangan bertumpuk dengan nomor persis dan
judul yang sama dengan entri. Di sampel yang foliony terbaca, folio =
halaman cetak.

## Sampel kab/kota (tidak masuk DB utama)
Dibandingkan dengan parser sebelum C1(a), dijalankan dari salinan versi git
HEAD.

| Ukuran | Hasil |
|---|---|
| Kunci hilang / `halaman_fisik` hilang atau pindah / sumber berubah | 0 / 0 / 0 |
| `halaman_fisik` baru | 496 (6371: 232, 6306: 166, 6302: 98) |
| Selisih 6371 | +54 untuk semua yang bercetak |
| Selisih 6306 | +44 untuk semua kecuali 2 (+43) |
| Selisih 6302 | +36 untuk 68 entri; 24 entri +65 s.d. +70 |

Ke-24 entri 6302 itu dibuka satu per satu dan halaman fisiknya BENAR:
folio = fis − 36 di semua halaman. Yang salah adalah halaman cetak dari
jalur daftar 6302 mulai bab 7 (misalnya tabel 7.1-7.6 semuanya "182",
padahal foliony 210-215). Itu masalah lama jalur daftar atau sumbernya,
belum diselidiki.

Sisa tanpa `halaman_fisik` di ketiga Dalam Angka kab/kota: 2 entri.

Sebagai informasi, A+B (kemarin) pada sampel yang sama: +63
`halaman_fisik` entri isi, tanpa perubahan lain.

## Pemuatan dan baseline
- Cadangan: `~/cadangan-bps/db_pencarian_bps-20261109-0829-sebelum-C1a.sql`,
  terbukti bisa dipulihkan.
- Dimuat dengan `perbarui.py --lokal --paksa` (log `C1a_muat_log.txt`,
  exit 0, tanpa kunci API).
- Database = uji kering di 79/79 publikasi, medan dan urutan sama;
  `teks_ternormalisasi` kosong: 0.
- **Baseline:** `potret-79-sesudah-C1a.json`, 79 publikasi, 6.824 entri,
  SHA-256 `5e616f8f7192c1487058caba2541481104881a3e9b4aaf8265897772a630d080`.
  Terhadap baseline sebelumnya: 639 perbedaan, semuanya `halaman_fisik`.
- **Daftar perubahan disengaja per entri:** `C1a-perubahan-20261109.tsv`.
