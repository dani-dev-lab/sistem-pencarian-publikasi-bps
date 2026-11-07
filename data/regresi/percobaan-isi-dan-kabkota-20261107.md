# Percobaan halaman fisik entri isi, dan parser pada sampel kab/kota (7 Nov 2026)

Dua percobaan di luar database utama. Parser TIDAK diubah untuk keduanya.

## 1. Halaman fisik untuk entri `isi` (usulan 3), purwarupa di luar parser

Script: `scratchpad/coba_isi.py`. Script ini memakai fungsi bantu parser
apa adanya dan hanya membaca. Cara kerjanya, untuk tiap entri isi:
- Halaman Daftar dilewati (`_halaman_daftar`).
- Yang dicari: baris, atau gabungan 2-3 baris berurutan, yang teksnya SAMA
  dengan judul bab setelah dinormalisasi DAN bergaya beda dari badan halaman
  itu (`_beda_dari_badan`). Ada cadangan kedua: judul tanpa nomor bab
  ("BAB 7" / "7.1").
- Kalau cocok di beberapa halaman, yang diambil adalah yang pertama setelah
  halaman pilihan entri isi sebelumnya (Daftar Isi terurut).

Delapan publikasi dengan format berbeda:

| Publikasi | Terisi |
|---|---|
| Indikator Kesejahteraan Rakyat 2025 | 36/44 |
| TPB 2024 | 3/5 |
| Dalam Angka 2026 | 3/22 |
| Statistik Daerah 2026 | 19/25 |
| PDRB Kabupaten/Kota (dwibahasa) | 2/16 |
| Keadaan Angkatan Kerja Agt 2025 (dwibahasa) | 4/11 |
| IHK 2024 | 1/3 |
| Statistik Potensi Desa 2025 (dwibahasa) | 7/19 |
| **Total** | **75/145 (52%)** |

**Ketepatan, dari 30 sampel acak di antara yang terisi (seed 20261107),
dibaca satu per satu: 29 benar, 1 salah.**
- **26 sampel** didukung bukti yang tidak bergantung pada pencocokan:
  - nomor folio di halaman itu = nomor halaman cetak, dan/atau
  - selisih cetak→fisik sama dengan entri tabel/gambar di publikasi yang
    sama.
- **3 sampel dibuka halamannya:**
  - Podes hal. 41 ("BAB II PERUMAHAN DAN LINGKUNGAN") dan Dalam Angka hal.
    127 ("BAB 03 PENDUDUK"): halaman pembuka bab, benar.
  - IHK hal. 23: subjudul "3.2 Inflasi Kelompok Pengeluaran" ada di
    halaman itu, benar.
- **1 salah, Dalam Angka 2026 bab 11:**
  - terpilih hal. 760 (halaman ulasan di dalam bab 11);
  - yang benar hal. 753, 7 halaman lebih awal.

**Penyebab utama tidak terisi, dan juga penyebab satu-satunya kesalahan:
halaman pembuka bab Dalam Angka memuat daftar isi mini ber-dot-leader,
sehingga `_halaman_daftar` menganggapnya halaman Daftar dan melewatinya.**
Bukti:

| Halaman | "....." | `_halaman_daftar` |
|---|---|---|
| hal. 753, pembuka bab 11 | 8 | True |
| hal. 127, pembuka bab 3 | 3 | False, lolos hanya karena tepat 3 |

Kalau dipakai, percobaan ini butuh pembeda halaman Daftar yang lebih tepat.
Mengubah ambang ">3" saja tidak cukup. Usulan, belum dikerjakan: halaman
Daftar = halaman yang punya heading DAFTAR, atau halaman lanjutan langsung
dari halaman Daftar sebelumnya (berurutan sejak heading). Halaman ber-dot-
leader yang terpisah jauh dari rangkaian halaman Daftar depan tidak dihitung.

Penyebab lain yang terlihat:
- **Entri halaman depan** (Kata Pengantar, Daftar Isi, dll.) tidak bergaya
  beda, atau berada di halaman Daftar itu sendiri.
- **Judul bab dwibahasa** ditulis berbeda di badan: huruf kapital tanpa
  nomor, terbagi beberapa baris.

Belum dipasang ke parser, menunggu keputusan pemilik project.

## 2. Parser (sesudah perbaikan 1+2) pada 6 sampel PDF kab/kota

Berkas `data/sampel_pdf/63xx_*.pdf`, 6 berkas utuh (%PDF + %%EOF).
Diproses ke JSON di scratchpad, TIDAK ke database utama.

| Berkas | Hal. | Entri | Per tipe | Tanpa `halaman` | Non-isi tanpa `halaman_fisik` |
|---|---|---|---|---|---|
| 6301 `122bdbc9` | 144 | 62 | isi 15, tabel 44, gambar 3 | 42 | 5 |
| 6301 `1a79b82e` | 47 | 66 | isi 25, tabel 6, gambar 33, lampiran 2 | 2 | 1 |
| 6302 `b99360b3` (Dalam Angka) | 332 | 127 | isi 21, tabel 106 | 4 | 104 |
| 6306 `2cb93305` (Dalam Angka) | 380 | 205 | isi 21, tabel 184 | 18 | 184 |
| 6371 `4eef35cf` (Dalam Angka) | 560 | 261 | isi 19, tabel 242 | 8 | 242 |
| 6371 `9a9fc81e` (PDRB LU) | 146 | 73 | isi 51, tabel 15, lampiran 7 | 1 | 1 |

Catatan:
- **6301 `122bdbc9`:** 42 dari 62 entri hanya dari jalur badan, padahal
  heading DAFTAR TABEL ditemukan. Penyebabnya belum diperiksa.
- **Dalam Angka kab/kota:** hampir semua tabelnya tanpa halaman fisik.
  Polanya sama dengan Dalam Angka provinsi (631 entri, ditunda). Label di
  badan ditumpuk vertikal: "Tabel" / "1.1.1" / "Table" di tiga baris terpisah,
  dengan judul di sebelahnya, sehingga penanda "tabel 1.1.1" tidak pernah
  muncul dalam satu baris. Diamati di Dalam Angka provinsi 2026 hal. 65-67.
  Ini kemungkinan besar penyebab 631 entri itu, BUKAN halaman pembuka bab.
  Penyelidikannya tetap ditunda.

**25 sampel acak (seed 20261107), dibaca satu per satu.** Buktinya adalah
baris pemicu di halaman Daftar: token nomor yang persis sama ±2 baris. Untuk
entri badan, buktinya baris "Tabel N" di halaman fisik.

| Penilaian | Sampel |
|---|---|
| Benar (judul dan halaman) | 17 |
| Benar, tapi judul diawali kepala seksi Daftar Tabel ("POVERTY", "CLIMATE CONDITION", "ADMINISTRATIVE AREA", "KOTA/ REGENCY/MUNICIPAL COMPARISON") | 5 |
| Potongan baris bahasa Inggris jadi entri sendiri ("2024/2025 and 2025/2026") | 1 |
| Tanpa nomor halaman (6306 tabel 4.1.7; 6306 tabel 2.3.5, yang judulnya juga terpotong di akhir halaman Daftar) | 2 |

Catatan alat: versi pertama alat bukti menampilkan baris yang SALAH pada 5
sampel. Penyebabnya: alat itu mencari baris pertama yang memuat kata judul,
bukan baris yang memicu entri. Alat itu diganti sebelum menilai, dan semua
sampel dinilai dari bukti versi kedua.
