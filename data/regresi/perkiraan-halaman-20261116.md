# Perkiraan halaman fisik dari halaman tetangga (16 Nov 2026)

Database uji `db_pencarian_bps_uji` saja. Produksi hanya dibaca (CHECKSUM
`publikasi`, `entri_dokumen`, `log_pencarian`, `versi_data` sama di awal dan
akhir sesi).

## Masalah

Tabel/gambar/lampiran yang halaman fisiknya tidak ditemukan jalur badan
membuka PDF di halaman 1. Di database uji (= produksi 14 Nov) ada 2.393 entri
seperti itu:
- 275 tidak punya halaman cetak, jadi tidak mungkin diperkirakan;
- **2.118 target**, semuanya berhalaman cetak angka.

## Aturan

Kode: `app/services/perkiraan_halaman.py`. Fungsi murni, tidak bergantung
pada urutan entri.
- **Jangkar**: entri tipe apa pun (termasuk isi) yang halaman cetaknya angka
  dan halaman fisiknya ASLI. Perkiraan tidak pernah jadi jangkar.
- **Jangkar setipe didahulukan**: kalau tipe target punya jangkar tersaring,
  hanya jangkar setipe yang dipakai; kalau tidak, jangkar semua tipe.
- **Saringan**: halaman cetak yang jangkarnya tidak sepakat dibuang; jangkar
  dipakai hanya kalau selisihnya sama dengan jangkar tetangganya.
- **Diisi kalau**:
  - ada jangkar di halaman cetak yang sama; atau
  - jangkar terdekat di bawah DAN di atas berselisih sama; atau
  - target di tepi dan jangkar terdekat paling jauh 10 halaman cetak.

  Selain itu dibiarkan kosong.

Pemasangan:
- `entri_dokumen.halaman_fisik_perkiraan` TINYINT(1) NOT NULL DEFAULT 0
  (`skema.pastikan_kolom`).
- `pipeline_data.simpan_entri` menghitung perkiraan di transaksi yang sama;
  nilai hasil baca PDF tidak pernah diganti.
- `scripts/isi_perkiraan_halaman.py (--db-uji | --produksi) [--coba]` untuk
  data yang sudah ada; menghormati `data/pembaruan.lock`; idempoten.
- UI: "Buka PDF ±hal. N" dengan tooltip; "Halaman PDF ±N" kalau tanpa
  halaman cetak (saat ini tidak terjadi, perkiraan selalu berhalaman cetak).

## Leave-one-out (sebelum menulis kode)

Halaman fisik yang sudah diketahui disembunyikan satu per satu lalu ditebak.
Dua publikasi "Luas Panen dan Produksi Padi" dipisahkan karena cacat datanya
(lihat bawah).

| Aturan | Tepat | Meleset >= 10 hal. | Target terisi |
|---|---|---|---|
| jangkar non-isi saja, tanpa saringan | 95,6% | - | 462 |
| + isi sebagai jangkar | 97,0% | 108 | 1.063 |
| + saringan jangkar | 97,2% (11.970/12.320) | 107 | 1.037 |
| **+ setipe didahulukan (BERLAKU)** | **97,7% (11.999/12.276)** | **61** | **1.036** |

Varian setipe ditambahkan SESUDAH sampel manual pertama menemukan kasus
Tabalong Dalam Angka 2026 (lihat S04). Karena itu sampel kedua diambil baru.

## Hasil pengisian (database uji, aturan berlaku)

- **1.036 dari 2.118 target terisi**: tabel 823, gambar 86, lampiran 127;
  di 121 publikasi.
- Masih kosong: 1.082 tidak memenuhi syarat dan 275 tanpa halaman cetak.
  Contohnya semua Keadaan Angkatan Kerja yang tidak punya jangkar apa pun.
- **Per id** (24.373 baris, dipasangkan menurut id dengan potret sebelum):
  - 23.337 identik dengan penanda 0;
  - 1.036 berubah HANYA `halaman_fisik` NULL -> angka dengan penanda 1;
    semuanya tabel/gambar/lampiran berhalaman cetak;
  - 0 hilang, 0 baru, 0 perubahan lain.
- 0 perkiraan melewati jumlah halaman PDF-nya.
- Run kedua: 0 diisi, 0 diubah, 0 dihapus.

## 12 kueri uji

`ukur_kinerja.KUERI`, `mesin_pencari.cari`, database uji, sebelum vs sesudah:
- **12/12 identik di semua medan** (urutan, skor, jumlah, publikasi) kecuali
  `halaman_fisik`/`halaman_fisik_perkiraan`;
- 18 dari 366 kartu entri mendapat halaman perkiraan, semuanya dari NULL.

Jebakan alat yang terjadi saat membandingkan: `sorot` dibangun dari `set` lalu
diurutkan menurut panjang. Urutan kata yang sama panjang berubah antarproses
(acakan hash Python), sehingga pembanding pertama melaporkan 7 kueri
"BERBEDA". Bandingkan `sorot` sebagai himpunan.

## Sampel manual

Setiap entri dibaca di PDF aslinya. Untuk tiap entri ditampilkan teks halaman
perkiraan (baris atas, folio bawah), dan halaman sekitar yang paling cocok
dengan judulnya. Halaman tanpa lapisan teks atau berisi tabel berkurva dirender
menjadi gambar, lalu dilihat. Halaman OCR dibaca dari cache EasyOCR.
- "Tepat" = isi entri ada di halaman perkiraan.
- Entri sampah (potongan judul Inggris, judul tanpa nomor) dinilai menurut
  halaman cetak yang tercantum di Daftar.

### Sampel 1 (seed 20261116, diambil dengan aturan pertama)

| # | Publikasi | Entri | Cetak -> perkiraan | Hasil |
|---|---|---|---|---|
| 1 | PDRB Tapin Pengeluaran | tabel 5 | 64 -> 78 | tepat (render) |
| 2 | PDRB Tapin Pengeluaran | tabel 13 | 85 -> 99 | tepat (render) |
| 3 | Balangan DA 2025 | potongan Inggris (8.1.2) | 181 -> 211 | tepat |
| 4 | Tabalong DA 2026 | gambar tanpa nomor (13.2) | 247 -> 283 | **meleset 53**; aturan setipe -> 336, **tepat** |
| 5 | Profil TK Tapin (OCR) | gambar gabungan sampah | 36 -> 50 | tepat untuk halaman cetaknya (Gambar 2.3, render); Gambar 2.4 yang ikut di judul ada di hal. 52 |
| 6 | Podes HSU | tabel 3.2 | 40 -> 66 | tepat |
| 7 | Podes Provinsi | tabel 2.6 | 28 -> 54 | tepat |
| 8 | PDRB Tapin LU (OCR) | tabel 3.2 | 105 -> 123 | tepat (render) |
| 9 | Polkam Barito Kuala | gambar 4.1 | 22 -> 36 | tepat |
| 10 | Ringkasan Eksekutif Padi | gambar 4 | 20 -> 34 | tepat (render) |
| 11 | PDRB Tapin Pengeluaran (OCR) | tabel "3.71" | 61 -> 73 | tepat (teks OCR) |
| 12 | Tanah Bumbu DA 2025 | potongan (13.4) | 342 -> 374 | tepat |
| 13 | HSS DA 2026 | potongan (5.3.4) | 219 -> 263 | tepat |
| 14 | Banjarmasin DA 2026 | potongan (12.1.8) | 485 -> 539 | tepat |
| 15 | Podes Tabalong | tabel 7.3 | 83 -> 109 | tepat |
| 16 | Podes HSS | tabel 3.1 | 39 -> 65 | tepat |
| 17 | Kesra Provinsi | tabel 8.2 | 136 -> 170 | tepat |
| 18 | Podes Tapin | tabel 3.2 | 42 -> 68 | tepat |
| 19 | Banjarmasin DA 2026 | potongan (4.1.7) | 137 -> 191 | tepat |
| 20 | Balangan DA 2025 | potongan Inggris (4.3.3) | 114 -> 144 | tepat |
| 21 | Potensi Kel. Banjarmasin | tabel 7.2 | 82 -> 108 | tepat |
| 22 | PDRB Kotabaru LU | lampiran 4 | 124 -> 148 | **meleset 2, kesalahan sumber** |
| 23 | Statda Banjarmasin | gambar 5.2 | 28 -> 44 | tepat (render) |
| 24 | Tapin DA 2025 | potongan Inggris (8.1.7) | 395 -> 445 | tepat |
| 25 | Banjar DA 2026 | tabel 5.3.1 | 270 -> 320 | tepat |
| 26 | Podes Tapin | tabel 4.7 | 57 -> 83 | tepat |
| 27 | Ringkasan Eksekutif Padi | gambar 2 | 13 -> 27 | tepat |
| 28 | PDRB Tapin Pengeluaran | tabel 11 | 78 -> 92 | tepat |
| 29 | Tanah Bumbu DA 2026 | potongan (3.2.2) | 70 -> 104 | tepat |
| 30 | Potensi Kel. Banjarbaru | tabel "2025" (5.2) | 63 -> 89 | tepat |

- Aturan pertama: **28/30**. Aturan berlaku: **29/30**. Nilai 29 entri lain
  diperiksa ulang di database dan tidak berubah.

### Sampel 2 (seed 20261117, aturan berlaku, 0 entri sama dengan sampel 1)

| # | Publikasi | Entri | Cetak -> perkiraan | Hasil |
|---|---|---|---|---|
| 1 | Podes Kotabaru | tabel 7.3 | 83 -> 109 | tepat |
| 2 | Podes Provinsi | tabel 6.4 | 78 -> 104 | tepat |
| 3 | Podes Tapin | tabel 7.1 | 87 -> 113 | tepat |
| 4 | Tapin DA 2025 | potongan Inggris (4.6.4) | 205 -> 255 | tepat |
| 5 | PDRB Tapin Pengeluaran | tabel 15 | 87 -> 101 | tepat (render) |
| 6 | Podes Tabalong | tabel 2.5 | 25 -> 51 | tepat |
| 7 | PDRB HSU LU | lampiran 3 | 97 -> 111 | tepat |
| 8 | PDRB Tapin Pengeluaran | tabel 18 | 92 -> 106 | tepat (render) |
| 9 | Podes Tabalong | tabel 2.7 | 27 -> 53 | tepat |
| 10 | Statda Banjarmasin | tabel 13.2 | 63 -> 79 | tepat (render) |
| 11 | PDRB Kab/Kota Provinsi | lampiran 32 | 122 -> 148 | tepat |
| 12 | Podes Provinsi | tabel 2.3 | 24 -> 50 | tepat |
| 13 | Podes Tabalong | tabel 6.1 | 72 -> 98 | tepat |
| 14 | Podes HST | tabel 6.3 | 74 -> 98 | tepat |
| 15 | Podes HST | tabel 3.2 | 40 -> 64 | tepat |
| 16 | Potensi Kel. Banjarbaru | tabel 4.1 | 48 -> 74 | tepat |
| 17 | PDRB Kotabaru LU | lampiran 2 | 122 -> 148 | **meleset 2, kesalahan sumber** (Tabel 2 di hal. 150) |
| 18 | Tanah Bumbu DA 2026 | potongan Inggris (4.1.8) | 141 -> 175 | tepat |
| 19 | Banjarbaru DA 2026 | potongan Inggris (4.1.7) | 143 -> 201 | tepat |
| 20 | Podes Banjar | tabel 4.8 | 55 -> 81 | tepat |
| 21 | Podes Kotabaru | tabel 1.2 "Kawasan Hutan" | 9 -> 35 | **tabelnya tidak ada di badan** |
| 22 | PDRB HSU LU | lampiran 5 | 99 -> 113 | tepat |
| 23 | Podes Kotabaru | tabel 3.2 | 40 -> 66 | tepat |
| 24 | Podes Tapin | tabel 7.3 | 89 -> 115 | tepat |
| 25 | Podes Banjar | tabel 2.3 | 22 -> 48 | tepat |
| 26 | Tapin DA 2026 | potongan Inggris (5.5.1) | 307 -> 357 | tepat |
| 27 | Podes Tanah Laut | tabel 1.2 | 9 -> 35 | tepat |
| 28 | Sakernas Kotabaru Agt 2025 | tabel tanpa nomor (Tabel 8) | 19 -> 65 | tepat |
| 29 | Provinsi DA 2026 | potongan Inggris (10.1.12) | 672 -> 728 | tepat |
| 30 | PDRB Kab/Kota Provinsi | tabel 3.7 | 51 -> 74 | **meleset 3** (benar 71) |

- **27/30 tepat.**
- Gabungan kedua sampel dengan aturan berlaku: **56/60 (93,3%)**.
- Yang meleset paling jauh 3 halaman.

### Mengapa sampel di bawah angka leave-one-out (97,7%)

Leave-one-out hanya mengukur pemetaan halaman cetak -> fisik. Ia tidak bisa
melihat halaman cetak yang SALAH di Daftar, padahal tiga dari empat kegagalan
sampel berasal dari sana:
- **Kesalahan sumber PDRB Kotabaru LU (2 entri sampel, 2 edisi).**
  - Daftar Lampiran mencetak 121-127, sedangkan folio badan 123-129.
  - Perkiraannya tepat menunjuk folio yang tercantum, tetapi tabelnya ada
    2 halaman sesudahnya. Kemungkinan ke-7 lampiran di tiap edisi meleset 2.
  - Pola yang sama dengan Daftar Tabel Kotabaru Dalam Angka 2026 (6302).
- **Podes Kotabaru Tabel 1.2.** Tercantum di Daftar, tetapi tidak dicetak di
  badan. Halaman 35 berfolio 9 sesuai Daftar, tetapi isinya Tabel 1.2
  "Sumber Penerangan Jalan Utama".
- **PDRB Kab/Kota Provinsi tabel 3.7 (meleset 3).** Jangkar tabel 'keduanya'
  di publikasi ini sudah salah pasang sebelum fitur ini: Daftar 3.4-3.6
  bergeser satu nomor terhadap keterangan badan, sehingga selisihnya 22-23,
  sedangkan isi/gambar 20. Aturan gabungan akan memberi 71 (tepat). Ini harga
  aturan setipe, yang secara keseluruhan lebih baik (leave-one-out 97,2% ->
  97,7%, meleset >=10 halaman 107 -> 61).

## Cacat data lama yang ditemukan (utang teknis, TIDAK diperbaiki)

**Luas Panen dan Produksi Padi Provinsi Kalimantan Selatan, dua edisi**
(`3d61cea5`, `335ac15d`).
- ±140 lampiran Daftar tertukar nomor dan halaman cetaknya: lampiran
  bernomor "55" sebenarnya halaman cetak 55 (fisik 83 = 55 + 28), sedangkan
  kolom halaman berisi 141.
- Saringan jangkar mencegahnya merusak perkiraan; di leave-one-out kedua
  publikasi itu hanya 62% tepat.
- Keputusan pemilik project 16 Nov 2026: dicatat, tidak diperbaiki sekarang.

## Uji otomatis

`tests/uji_pipeline.py` bagian F; lihat CLAUDE.md untuk hasil run.
