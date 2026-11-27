# Perbaikan jalur daftar dan halaman Daftar di jalur badan (7 Nov 2026)

Usulan 1 dan 2 dari `penyelidikan-B-20261106.md`, dikerjakan sebagai satu
perubahan di `app/services/ekstraksi_pdf.py`:

1. `_baca_daftar`: heading DAFTAR yang SAMA PERSIS tipenya, bila diulang di
   halaman lanjutan, tidak lagi mengakhiri daftar. Heading bertipe lain
   tetap mengakhirinya.
2. `ekstrak_badan` melewati halaman Daftar lewat `_halaman_daftar()`. Ini
   pemeriksaan yang sudah dipakai `lengkapi_halaman_fisik`: heading di 6
   baris teratas, atau lebih dari 3 "....." di halaman itu. Pemeriksaannya
   dipindah apa adanya, jadi perilaku `lengkapi_halaman_fisik` tidak berubah.

Aturan gaya (font/ukuran ATAU warna) tidak disentuh. Pengecualian superset
diizinkan pemilik project; bunyi aturan barunya ada di CLAUDE.md.

## Cara uji
1. **Uji kering:** parser baru dijalankan pada 79 PDF, hasilnya ke JSON, DB
   tidak disentuh. Hasilnya dibandingkan per kunci `(publikasi, tipe, nomor)`
   dengan DB lama, yang sebelumnya terbukti IDENTIK dengan baseline.
2. **Cadangan DB:** `~/cadangan-bps/db_pencarian_bps-20261107-1748-sebelum-perbaikan-daftar.sql`.
3. **Pemuatan:** `perbarui.py --lokal --paksa` (exit 0; ekstraksi 1.180 d,
   muat 4,4 d). Log: `perbaikan-daftar_muat_log.txt`.
4. **Pemeriksaan pasca-muat:** DB = uji kering untuk 79/79 publikasi
   (semua medan entri, urutan, `catatan_ekstraksi`). Entri tanpa
   `teks_ternormalisasi`: 0.

## Syarat lolos
| Syarat | Hasil |
|---|---|
| Tidak ada `(publikasi, tipe, nomor)` yang hilang | 0 hilang. Entri tanpa nomor yang hilang: 0 |
| 13 `halaman_fisik` yang menunjuk halaman Daftar kini benar atau kosong | 8 pindah ke halaman yang bukan Daftar dan isinya sudah dicek; 5 kosong; 0 gagal |
| 43 judul tercemar kini bersih | 42 bersih. 1 tersisa (lihat bawah) |
| Entri yang bertambah dibaca semua dengan bukti baris PDF | 12 dari 12 dibaca. Halaman semuanya benar; 1 judul membawa folio "7" |
| Entri yang KEHILANGAN `halaman_fisik` (di luar 13 itu) | 0 di semua publikasi, termasuk Dalam Angka 2025/2026 (0 perubahan sama sekali) |
| `halaman_fisik` yang berpindah (di luar 13 itu) | 0 |
| `sumber` turun dari 'keduanya'/'badan' ke 'daftar' | 13, yaitu persis 13 entri di atas. 'badan'/'keduanya' mereka dulu berasal dari baris halaman Daftar |
| Aturan gaya tidak disentuh | `_gaya`, `_gaya_dominan`, `_beda_dari_badan` tidak ada di diff |

Halaman pembuka bab Dalam Angka (yang memuat daftar isi mini ber-dot-leader)
memang dilewati `_halaman_daftar`. Uji kering membuktikan tidak ada entri
yang kehilangan apa pun karenanya. Dampaknya baru terasa pada percobaan
halaman fisik entri isi; lihat `percobaan-isi-dan-kabkota-20261107.md`.

## Angka korpus sebelum → sesudah
| | Sebelum | Sesudah |
|---|---|---|
| Entri | 6.812 | 6.824 (+12, TPB 2024 8, Statistik Daerah 2026 4) |
| Judul diakhiri angka 1-3 digit | 209 | 172 |
| Entri punya `halaman_fisik` | 4.015 | 4.022 |
| Entri tanpa `halaman` | 2.028 | 2.006 |
| Perubahan sumber | | badan→keduanya 10, badan→daftar 9, keduanya→daftar 4 |

## Judul yang masih tercemar sesudah perubahan (4)
| Entri | Judul | Penyebab |
|---|---|---|
| Pasar Tenaga Kerja Agt 2024, Gambar 8 | "... Agustus 2024 38" | Di halaman Daftar tahun dan nomor halaman menempel ke dot leader dalam satu kata ("2024......38"), sehingga nomornya tidak terpisah. Versi badan yang bersih kalah oleh **aturan judul terpanjang** di `_gabung`. Sisa dari 43 judul tadi. |
| TPB 2024, Gambar 26 | "... 2021−2024 6" | Folio halaman Daftar ("6", baris terakhir halaman) terserap ke judul entri terakhir. Baru terlihat karena jalur daftar kini membaca halaman itu. Versi badan lebih pendek karena terpotong. |
| TPB 2024, Gambar 38 | "... (persen) 7" | Sama, folio "7". Entri ini baru. |
| Statistik Daerah 2026, Gambar 14.1 | "Kondisi Jalan di Kalimantan Selatan, 2024 Perkembangan Pinjaman dan Simpanan Kalimantan Selatan," | Di Daftar Gambar, baris judul Gambar 15.1 tercetak SEBELUM baris labelnya, lalu terserap ke 14.1. Versi badan "Kondisi Jalan di Kalimantan Selatan, 2025" yang bersih kalah oleh **aturan judul terpanjang**. |

Dua dari empat disebabkan atau dimenangkan oleh aturan dedup "judul
terpanjang". Sesuai keputusan, kodenya tidak diubah.

## Baseline baru
`data/regresi/potret-79-sesudah-perbaikan-daftar.json`, SHA-256
`cef17fe751f45b0f6964c9fe219fd5aa396b8c1090dcffbc1a4b73a6c52bcaf7`
(79 publikasi, 6.824 entri). Salinannya ada di `~/cadangan-bps/`.
Regresi berikutnya dibandingkan dengan berkas ini.
`potret-79-sebelum-rombakan.json` tetap disimpan sebagai riwayat.

`potret_db.py banding` lama → baru melaporkan 62 perbedaan pada 8
publikasi. Angkanya lebih besar dari daftar di bawah karena alat itu
membandingkan per POSISI, dan 8 entri baru di TPB 2024 menggeser posisi
entri sesudahnya. Daftar di bawah dibandingkan per kunci `(tipe, nomor)`.

## Daftar perubahan yang disengaja (per kunci)

### TPB 2024 (`2223fbffa401ff7bf9e66bc5`): 26 perubahan

| Entri | Perubahan |
|---|---|
| gambar 12 | judul: `…an Tinggi (PT) di Provinsi Kalimantan Selatan, 2021−2024 (persen) 16` → `…uruan Tinggi (PT) di Provinsi Kalimantan Selatan, 2021−2024 (persen)`; halaman_fisik: `5` → `16`; sumber: `keduanya` → `daftar` |
| gambar 14 | halaman: `None` → `18`; sumber: `badan` → `keduanya` |
| gambar 15 | **baru** (sumber daftar, hal 18, fisik 18): …uduk Usia 15 Tahun Ke Atas di Provinsi Kalimantan Selatan, 2021−2024 |
| gambar 16 | judul: `Proporsi Perempuan Umur 20-24 Gambar 17 Proporsi Perempuan yang Berada` → `…lum Umur 18 Tahun di Provinsi Kalimantan Selatan, 2021−2024 (persen)`; halaman: `None` → `19`; sumber: `badan` → `keduanya` |
| gambar 17 | judul: `…da di Posisi Manajerial di Provinsi Kalimantan Selatan, 2021−2024 19` → `…Posisi Manajerial di Provinsi Kalimantan Selatan, 2021−2024 (persen)`; halaman: `None` → `19`; halaman_fisik: `6` → `19`; sumber: `badan` → `daftar` |
| gambar 18 | **baru** (sumber daftar, hal 20, fisik 20): …gan Sabun dan Air di Provinsi Kalimantan Selatan, 2021−2024 (persen) |
| gambar 19 | **baru** (sumber daftar, hal 20, fisik 20): …s Air Minum Layak di Provinsi Kalimantan Selatan, 2021−2024 (persen) |
| gambar 20 | **baru** (sumber daftar, hal 21, fisik 21): …enggunaan Gas Rumah Tangga di Provinsi Kalimantan Selatan, 2021−2024 |
| gambar 21 | **baru** (sumber daftar, hal 22, fisik 22): … per Tenaga Kerja di Provinsi Kalimantan Selatan, 2021−2024 (persen) |
| gambar 22 | judul: `…DHK per Kapita (persen) di Provinsi Kalimantan Selatan, 2021−2024 22` → `…B ADHK per Kapita (persen) di Provinsi Kalimantan Selatan, 2021−2024`; halaman: `None` → `22`; halaman_fisik: `6` → `None`; sumber: `badan` → `daftar` |
| gambar 23 | halaman: `None` → `23` |
| gambar 24 | judul: `…er Jam Pekerja di Provinsi Kalimantan Selatan, 2021−2024 (rupiah) 23` → `…a per Jam Pekerja di Provinsi Kalimantan Selatan, 2021−2024 (rupiah)`; halaman: `None` → `23`; halaman_fisik: `6` → `None`; sumber: `badan` → `daftar` |
| gambar 25 | judul: `…ti Pelatihan di Provinsi Kalimantan Selatan, 2021−2024 ( persen ) 23` → `…ngikuti Pelatihan di Provinsi Kalimantan Selatan, 2021−2024 (persen)`; halaman: `None` → `23` |
| gambar 26 | judul: `Tingkat Pengangguran Terbuka di Provinsi Kalimantan` → `…at Setengah Pengangguran di Provinsi Kalimantan Selatan, 2021−2024 6`; halaman: `None` → `24`; sumber: `badan` → `keduanya` |
| gambar 27 | judul: `Jumlah Perjalanan Wisatawan` → `…isatawan Nusantara di Provinsi Kalimantan Selatan, 2021−2024 (orang)`; halaman: `None` → `24`; sumber: `badan` → `keduanya` |
| gambar 28 | judul: `Kontribusi PDRB Industri Pengolahan terhadap` → `…engolahan terhadap Total PDRB Kalimantan Selatan, 2021−2024 (persen)`; halaman: `None` → `25`; sumber: `badan` → `keduanya` |
| gambar 29 | judul: `… Pengolahan di Provinsi Kalimantan Selatan, 2021−2024 ( persen )… 25` → `…dustri Pengolahan di Provinsi Kalimantan Selatan, 2021−2024 (persen)`; halaman: `None` → `25`; halaman_fisik: `7` → `25`; sumber: `badan` → `daftar` |
| gambar 30 | judul: `…sentase Penduduk Miskin di Provinsi Kalimantan Selatan, 2021−2024 26` → `…Persentase Penduduk Miskin di Provinsi Kalimantan Selatan, 2021−2024`; halaman: `None` → `26`; halaman_fisik: `7` → `26`; sumber: `badan` → `daftar` |
| gambar 31 | judul: `… Persen dari Median Pendapatan di Kalimantan Selatan, 2020 − 2023 26` → `…ah 50 Persen dari Median Pendapatan di Kalimantan Selatan, 2020−2023`; halaman: `None` → `26`; halaman_fisik: `7` → `26`; sumber: `badan` → `daftar` |
| gambar 32 | judul: `…yak dan Terjangkau di Provinsi Kalimantan Selatan, 2024 (persen ) 27` → `…n Layak dan Terjangkau di Provinsi Kalimantan Selatan, 2024 (persen)`; halaman: `None` → `27`; halaman_fisik: `7` → `27`; sumber: `badan` → `daftar` |
| gambar 33 | judul: `…Transportasi Publik di Provinsi Kalimantan Selatan, 2020 (persen) 27` → `…ni Transportasi Publik di Provinsi Kalimantan Selatan, 2020 (persen)`; halaman: `None` → `27`; halaman_fisik: `7` → `27`; sumber: `badan` → `daftar` |
| gambar 34 | judul: `…Transportasi Publik di Provinsi Kalimantan Selatan, 2020 (persen) 27` → `…da Transportasi Publik di Provinsi Kalimantan Selatan, 2020 (persen)`; halaman: `None` → `27`; halaman_fisik: `7` → `27`; sumber: `badan` → `daftar` |
| gambar 35 | judul: `…dan DPRD) di Indonesia dan Provinsi Kalimantan Selatan, 2020-2024 30` → `…PR dan DPRD) di Indonesia dan Provinsi Kalimantan Selatan, 2020-2024`; halaman: `None` → `30` |
| gambar 36 | **baru** (sumber daftar, hal 30, fisik 30): … Pencatatan Sipil di Provinsi Kalimantan Selatan, 2020−2024 (persen) |
| gambar 37 | **baru** (sumber daftar, hal 31, fisik 31): …ang Mengakses Internet di Provinsi Kalimantan Selatan, 2024 (persen) |
| gambar 38 | **baru** (sumber daftar, hal 31, fisik 31): …hadap Kualitas Data BPS Provinsi Kalimantan Selatan, 2024 (persen) 7 |

### Indikator Pasar Tenaga Kerja Agt 2024 (`38778154d51012af9aa474be`): 13 perubahan

| Entri | Perubahan |
|---|---|
| gambar 3 | judul: `TPAK Menurut Kelompok Usia (persen), Agustus 2022 – Agustus 2024 35` → `TPAK Menurut Kelompok Usia (persen), Agustus 2022 – Agustus 2024` |
| gambar 5 | judul: `EPR (persen), Agustus 2022 – Agustus 2024 36` → `EPR (persen), Agustus 2022 – Agustus 2024` |
| gambar 7 | judul: `EPR Menurut Kelompok Usia (persen), Agustus 2022 – Agustus 2024 38` → `EPR Menurut Kelompok Usia (persen), Agustus 2022 – Agustus 2024` |
| gambar 10 | judul: `Persentase Pekerja Rentan, Agustus 2022 – Agustus 2024 41` → `Persentase Pekerja Rentan, Agustus 2022 – Agustus 2024` |
| gambar 11 | judul: `Pekerja Rentan Menurut Jenis Kelamin (persen), Agustus 2024 41` → `Pekerja Rentan Menurut Jenis Kelamin (persen), Agustus 2024` |
| gambar 16 | judul: `Tingkat Pekerja Paruh Waktu (Persen), Agustus 2022 – Agustus 2024 47` → `Tingkat Pekerja Paruh Waktu (Persen), Agustus 2022 – Agustus 2024` |
| gambar 20 | judul: `Pekerja Paruh Waktu Menurut Kabupaten/Kota (Persen), Agustus 2024 49` → `Pekerja Paruh Waktu Menurut Kabupaten/Kota (Persen), Agustus 2024` |
| gambar 21 | judul: `Persentase Penduduk Bekerja Menurut Jumlah Jam kerja, Agustus 2024 50` → `Persentase Penduduk Bekerja Menurut Jumlah Jam kerja, Agustus 2024` |
| gambar 29 | judul: `TPT Penduduk Usia Muda (Persen), Agustus 2022 – Agustus 2024 61` → `TPT Penduduk Usia Muda (Persen), Agustus 2022 – Agustus 2024` |
| gambar 32 | judul: `Share Pengangguran Muda (persen), Agustus 2022 – Agustus 2024 64` → `Share Pengangguran Muda (persen), Agustus 2022 – Agustus 2024` |
| tabel 3 | judul: `Tingkat Pengangguran Terbuka (Persen), Agustus 2022 – Agustus 2024 59` → `Tingkat Pengangguran Terbuka (Persen), Agustus 2022 – Agustus 2024` |
| tabel 4 | judul: `…PT Penduduk Muda Terhadap TPT Dewasa, Agustus 2022 – Agustus 2024 63` → `Rasio TPT Penduduk Muda Terhadap TPT Dewasa, Agustus 2022–Agustus 2024` |
| tabel 5 | judul: `… Menurut Tingkat Pendidikan (Persen), Agustus 2022 – Agustus 2024 66` → `TPT Menurut Tingkat Pendidikan (Persen), Agustus 2022 – Agustus 2024` |

### Analisis Isu Terkini 2025 (`a378694152b3182da042d887`): 11 perubahan

| Entri | Perubahan |
|---|---|
| gambar 2.1 | judul: `Persentase Pekerja Komuter Menurut Kabupaten/Kota Tempat Kerja 23` → `Persentase Pekerja Komuter Menurut Kabupaten/Kota Tempat Kerja` |
| gambar 3.1 | judul: `NTL dalam Grid 1 Km 2 Provinsi Kalimantan Selatan, 2014 39` → `NTL dalam Grid 1 Km 2 Provinsi Kalimantan Selatan, 2014` |
| gambar 3.2 | judul: `NTL dalam Grid 1 Km 2 Provinsi Kalimantan Selatan, 2024 40` → `NTL dalam Grid 1 Km 2 Provinsi Kalimantan Selatan, 2024` |
| gambar 3.4 | judul: `Delta NTL dalam Grid 1 Km 2 Provinsi Kalimantan Selatan, 2014–2024 43` → `Delta NTL dalam Grid 1 Km 2 Provinsi Kalimantan Selatan, 2014–2024` |
| gambar 3.5 | judul: `Hotspot Urban Provinsi Kalimantan Selatan, a) 2014 dan b) 2024 44` → `Hotspot Urban Provinsi Kalimantan Selatan, a) 2014 dan b) 2024` |
| tabel 1.2 | judul: `Hasil Analisis Regresi Logistik 11` → `Hasil Analisis Regresi Logistik` |
| tabel 2.2 | judul: `Goodness-of-fit 29` → `Goodness-of-fit` |
| tabel 2.3 | judul: `Model Fitting Information 29` → `Model Fitting Information` |
| tabel 2.4 | judul: `Variabel Bebas yang dikeluarkan dari Model Regresi Logistik 29` → `Variabel Bebas yang dikeluarkan dari Model Regresi Logistik` |
| tabel 2.5 | judul: `Likelihood Ratio Tests 30` → `Likelihood Ratio Tests` |
| tabel 2.6 | judul: `Pseudo R-Square 30` → `Pseudo R-Square` |

### Statistik Daerah 2026 (`c35054ac95c0c71da7234092`): 9 perubahan

| Entri | Perubahan |
|---|---|
| gambar 13.1 | halaman: `None` → `27`; sumber: `badan` → `keduanya` |
| gambar 13.2 | **baru** (sumber daftar, hal 27, fisik 39): Hutan Pinus Mentaos |
| gambar 13.3 | **baru** (sumber daftar, hal 28, fisik 40): Fasilitas Akomodasi Kalimantan Selatan |
| gambar 14.1 | judul: `Kondisi Jalan di Kalimantan Selatan, 2025` → `…Selatan, 2024 Perkembangan Pinjaman dan Simpanan Kalimantan Selatan,`; halaman: `None` → `29`; sumber: `badan` → `keduanya` |
| gambar 16.1 | judul: `Perkembangan Inflasi Kalimantan` → `Perkembangan Inflasi Kalimantan Selatan, 2025`; halaman: `None` → `33`; sumber: `badan` → `keduanya` |
| gambar 17.1 | **baru** (sumber daftar, hal 35, fisik 47): Neraca Perdagangan Kalimantan Selatan, 2025 |
| gambar 18.1 | halaman: `None` → `37`; sumber: `badan` → `keduanya` |
| gambar 19.1 | **baru** (sumber daftar, hal 39, fisik 51): Produk Domestik Regional Bruto Kalimantan Selatan, 2025 |
| gambar 20.1 | halaman: `None` → `41`; sumber: `badan` → `keduanya` |

### IHK 2024 (`ac3255bf717fb753419c9e05`): 2 perubahan

| Entri | Perubahan |
|---|---|
| lampiran 5 | judul: `Grafik Inflasi Per bulan Provinsi Kalimantan Selatan 2024 28` → `Grafik Inflasi Per bulan Provinsi Kalimantan Selatan 2024`; halaman_fisik: `11` → `None`; sumber: `keduanya` → `daftar` |
| lampiran 6 | halaman_fisik: `11` → `None`; sumber: `keduanya` → `daftar` |

### Laporan Perekonomian 2025 (`11487a617225d1ef21344169`): 1 perubahan

| Entri | Perubahan |
|---|---|
| gambar 4.5 | judul: `NTP Regional Kalimantan, 2025 71` → `NTP Regional Kalimantan, 2025` |

### Keadaan Angkatan Kerja Agt 2024 (`2ddab8a817f162547f27c505`): 1 perubahan

| Entri | Perubahan |
|---|---|
| tabel 13 | halaman_fisik: `12` → `None`; sumber: `keduanya` → `daftar` |

### IPM 2024 (`8367dad5dd6fc6310d9e991c`): 1 perubahan

| Entri | Perubahan |
|---|---|
| tabel 1.1 | judul: `Nilai Maksimum dan Nilai Minimum Indikator Komponen IPM 10` → `Nilai Maksimum dan Nilai Minimum Indikator Komponen IPM` |
