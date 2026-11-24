# Penilaian sampel manual, tarik kecil Tanah Laut rilis 2024 (24 Nov 2026)

Sampel acak 25 entri, `random.Random(20261124).sample`, dari semua entri
domain 6301 yang dirilis 2024 (3.726 entri), dan dengan seed yang sama dari
6301 rilis 2025-2026 sebagai pembanding. Bukti per entri:
`sampel-2024-verifikasi.txt`, `sampel-2025-2026-verifikasi.txt` (dibuat
`verifikasi_sampel.py`, hanya membaca). Bukti yang dipakai menilai:

- baris Daftar yang diawali nomor entri (halaman cetak yang tercetak);
- halaman badan yang memuat keterangan bernomor itu, beserta folionya;
- halaman yang dituju tombol PDF (`halaman_fisik`).

"Benar" = judul, nomor, halaman cetak, dan halaman PDF ada dan tepat.
Alat pertama (`sampel_entri.py`) tidak menemukan satu pun baris Daftar.
Halaman cetak di Daftar Sensus Pertanian ada di baris ke-3/4, sehingga
alatnya yang salah, bukan datanya. Alat itu diganti, dan hasil di bawah
memakai alat kedua.

## Rilis 2024

| # | Publikasi | Entri | Nilai |
|---|---|---|---|
| 1 | Podes 2024 | isi "Penjelasan Teknis", hal xxv | judul, hal benar; **tanpa tombol PDF** (halaman depan romawi) |
| 2 | Podes 2024 | isi BAB 10, hal 119, PDF 149 | benar (folio 149 = 119) |
| 3 | Kec. Batu Ampar DA 2024 | tabel 5.11, hal 98, PDF 126 | benar |
| 4 | Kesra 2024 | tabel 5.1, hal 45, PDF 67 | nomor, hal, PDF benar; **judul bersampah** (kop kolom "... Milik Sendiri Lainnya 1") |
| 5 | ST2023 Kehutanan | tabel 4.54, hal 318, ±PDF 376 | benar (perkiraan tepat) |
| 6 | ST2023 Kehutanan | tabel 5.27.10, hal 472 | hal benar (badan 530, folio 472); **tanpa tombol PDF** |
| 7 | ST2023 Kehutanan | tabel 5.34.2, hal 536 | hal benar (badan 594); **tanpa tombol PDF** |
| 8 | Kec. Bumi Makmur DA 2024 | isi "5. Pertanian", hal 77, PDF 105 | benar |
| 9 | ST2023 Hortikultura | tabel 4.18, hal 219, ±PDF 279 | benar (perkiraan tepat) |
| 10 | ST2023 Hortikultura | tabel 5.7.3, hal 377 | hal benar (badan 437); **tanpa tombol PDF** |
| 11 | ST2023 Hortikultura | tabel 5.13.11, hal 487 | hal benar (badan 547); **tanpa tombol PDF** |
| 12 | ST2023 Hortikultura | tabel 5.27.6, hal 591 | hal benar (badan 651); **tanpa tombol PDF** |
| 13 | Tanah Laut DA 2024 | tabel 8.1.4, hal 447, PDF 503 | benar |
| 14 | ST2023 Tanaman Pangan | tabel 4.42, hal 306, ±PDF 354 | benar (perkiraan tepat) |
| 15 | Kec. Bajuin DA 2024 | tabel 4.3.4, hal 58, PDF 86 | benar |
| 16 | Kec. Bajuin DA 2024 | tabel 5.2, hal 83, PDF 111 | benar |
| 17 | Statistik Daerah 2024 | gambar 14.3, PDF 33 | nomor dan PDF benar; **judul terpotong** ("Jumlah Kendaraan Bermotor di"); **tanpa hal cetak** (Daftar bertulisan rapat tanpa spasi) |
| 18 | ST2023 Perkebunan | tabel 5.5.4, hal 370 | hal benar (badan 422); **tanpa tombol PDF** |
| 19 | ST2023 Perkebunan | tabel 5.24.3, hal 517 | hal benar (badan 569); **tanpa tombol PDF** |
| 20 | ST2023 Perkebunan | tabel 6.15, hal 609 | hal benar (badan 661); **tanpa tombol PDF** |
| 21 | ST2023 Peternakan | tabel 3.29, hal 136, ±PDF 180 | benar (perkiraan tepat) |
| 22 | ST2023 Peternakan | tabel 4.9, hal 189, ±PDF 233 | benar (perkiraan tepat) |
| 23 | ST2023 Peternakan | tabel 5.13.1, hal 416 | hal benar (badan 460); **tanpa tombol PDF** |
| 24 | ST2023 Peternakan | tabel 5.34.4, hal 501 | hal benar (badan 545); **tanpa tombol PDF** |
| 25 | Kec. Kintap DA 2024 | tabel 4.1.2, hal 53, PDF 81 | benar |

**Benar seluruhnya 12/25. Nilai yang salah 0/25:** setiap nomor, halaman
cetak, dan halaman PDF yang terisi memang tepat, termasuk 5/5 perkiraan.
Kekurangannya:
- 11 tanpa tombol PDF: 10 tabel Sensus Pertanian 2023 dan 1 halaman romawi;
- 2 judul cacat.

## Rilis 2025-2026 (pembanding, alat dan seed sama)

| # | Publikasi | Entri | Nilai |
|---|---|---|---|
| 1 | PDRB Pengeluaran | isi Penjelasan Umum, hal xiii, PDF 15 | benar |
| 2 | PDRB Pengeluaran | isi 2.4, hal 24 | hal benar (badan 40); **tanpa tombol PDF** |
| 3 | Kec. Kurau DA 2026 | isi Preface, viii, PDF 10 | benar |
| 4 | Kec. Kurau DA 2026 | tabel 7.3, hal 108, PDF 134 | benar |
| 5 | Kec. Kintap DA 2025 | tabel 5.6, PDF 110 | PDF benar; **tanpa hal cetak** (Daftar Tanah Laut 2025 "1. 1", utang lama) |
| 6 | PDRB LU | isi 4.4, hal 118, ±PDF 136 | benar |
| 7 | PDRB LU | tabel 1.1, hal 11, PDF 29 | benar |
| 8 | Kec. Jorong DA 2025 | tabel 5.5, PDF 107 | PDF benar; **tanpa hal cetak** (sama dengan #5) |
| 9 | Kec. Bumi Makmur DA 2026 | "tabel 4.2" "Kesehatan/Health", ±PDF 80 | **cacat: judul subbab tercatat sebagai tabel** |
| 10 | Tanah Laut DA 2026 | tabel 9.7, PDF 544 | PDF benar; **tanpa hal cetak** (folio Daftar "xliii" di baris sendiri, utang lama) |
| 11 | Kec. Bati-Bati DA 2026 | isi Preface, ix, PDF 11 | benar |
| 12 | PDRB Pengeluaran | isi 3.2.6, hal 48, ±PDF 64 | benar |
| 13 | Tanah Laut DA 2025 | isi Daftar Isi, ix | hal benar; **tanpa tombol PDF** |
| 14 | Tanah Laut DA 2025 | tabel 3.2.6, hal 95, PDF 147 | benar |
| 15 | Tanah Laut DA 2025 | tabel 4.3.2, hal 210, PDF 262 | benar |
| 16 | Tanah Laut DA 2025 | tabel 5.5.10, hal 397, PDF 449 | benar |
| 17 | Kec. Kurau DA 2025 | tabel 2.1.6, PDF 48 | PDF benar; **tanpa hal cetak** (sama dengan #5) |
| 18 | Kec. Kurau DA 2025 | tabel 5.2, PDF 104 | PDF benar; **tanpa hal cetak** (sama dengan #5) |
| 19 | PDRB LU | isi 4.13, hal 129, ±PDF 147 | benar (folio 129) |
| 20 | Kec. Tambang Ulang DA 2025 | isi Daftar Singkatan, xxi | hal benar (badan 23); **tanpa tombol PDF** |
| 21 | Kec. Takisung DA 2026 | gambar 3, hal 9, PDF 35 | benar |
| 22 | Kesra 2025 | lampiran 19, hal 101, PDF 123 | nomor, hal, PDF benar; **judul bersampah** (kop kolom) |
| 23 | Kesra 2025 | lampiran 32, hal 114, PDF 136 | benar |
| 24 | Kec. Batu Ampar DA 2026 | tabel 5.7, hal 78, PDF 108 | benar terhadap Daftar. Daftar mencetak 78, folio badan 80: **kesalahan sumber**, tombol PDF tepat |
| 25 | Kec. Bajuin DA 2025 | isi 2.1, hal 19, ±PDF 43 | benar |

**Benar seluruhnya 15/25.** Kekurangannya:
- 3 tanpa tombol PDF (semuanya entri isi);
- 5 tanpa halaman cetak (utang lama Tanah Laut 2025 dan folio Daftar);
- 2 cacat: judul bersampah, dan subbab tercatat sebagai tabel.

## Kesimpulan perbandingan

- Mutu per entri setara. Rilis 2024 tidak punya nilai yang salah tunjuk
  (0/25), dan cacatnya berjenis sama dengan 2025-2026: kop tabel menempel ke
  judul, dan judul terpotong di Daftar yang bertulisan rapat.
- Selisihnya (12 vs 15 benar seluruhnya) hampir seluruhnya dari **satu seri
  yang hanya ada di rilis 2024: Hasil Pencacahan Lengkap Sensus Pertanian 2023
  Tahap II** (6 publikasi, 1.967 entri, 53% dari tarikan ini). Tata letak
  keterangannya: "Tabel <judul>" / "<nomor> <judul lanjutan>" / "Table". Jalur
  badan dan `lengkapi_halaman_fisik` tidak mengenali satu pun tabelnya (halaman
  PDF asli 3,4%, perkiraan mengisi sebagian, 1.240 tabel tanpa tombol PDF).
  Nomor, judul, dan halaman cetak dari Daftarnya tetap benar.
- Tanpa Sensus Pertanian, kab/kota rilis 2024: halaman cetak 94,8%, halaman
  PDF 86,6%. Kab/kota rilis 2025-2026: halaman cetak 95,9%, halaman PDF 88,3%.
- Kecamatan Dalam Angka 2024 lebih lengkap halaman cetaknya (100%) daripada
  edisi 2025-2026 (58,1%), karena Daftar 2024 tidak berformat "1. 1" seperti
  Tanah Laut 2025.
