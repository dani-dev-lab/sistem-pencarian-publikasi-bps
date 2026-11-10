# Penarikan 13 kab/kota: pemeriksaan hasil (10 Nov 2026)

Run: `perbarui-data.bat` dijalankan pemilik project 9 Nov 20:30 - 10 Nov 01:32
(log `data/log_pembaruan/20261109-203005.log`, tidak di-commit). Jaringan:
Wi-Fi rumah "PEGASUS 5G", webapi.bps.go.id -> 203.123.60.70.

Ringkasan run: 14/14 domain sukses, 234 publikasi diproses (227 kab/kota
baru + 7 provinsi yang diperbarui BPS), 0 gagal, entri 6.738 -> 23.461,
5,0 jam (unduh 4,1 jam, ekstraksi 49 menit). Unduhan putus 2x, keduanya
pulih di percobaan ulang; putaran ulang tidak diperlukan.

## 1. Hitungan per domain: database vs --hanya-periksa
Untuk ke-14 domain: publikasi lolos filter di `--hanya-periksa`
(`pemeriksaan-14-domain-20261109.json`) = publikasi di database = PDF di
disk = `jumlah_publikasi` di ringkasan run. Total 306 = 306 = 306.

| Domain | Publikasi | Entri | Publikasi 0 entri |
|---|---|---|---|
| 6300 Provinsi | 79 | 6.738 | 0 |
| 6301 Tanah Laut | 17 | 1.421 | 0 |
| 6302 Kotabaru | 17 | 1.153 | 0 |
| 6303 Banjar | 15 | 1.310 | 0 |
| 6304 Barito Kuala | 18 | 1.343 | 0 |
| 6305 Tapin | 17 | 1.317 | 2 |
| 6306 Hulu Sungai Selatan | 17 | 1.295 | 0 |
| 6307 Hulu Sungai Tengah | 16 | 1.182 | 1 |
| 6308 Hulu Sungai Utara | 19 | 1.314 | 0 |
| 6309 Tabalong | 17 | 1.078 | 0 |
| 6310 Tanah Bumbu | 16 | 1.051 | 0 |
| 6311 Balangan | 16 | 1.121 | 0 |
| 6371 Banjarmasin | 23 | 1.684 | 0 |
| 6372 Banjarbaru | 19 | 1.454 | 2 |

`teks_ternormalisasi` kosong: 1. Itu entri isi berjudul "|" di PDRB Tanah
Laut, sampah kecil yang tidak akan pernah cocok dengan kueri; dibiarkan.

## 2. Tujuh publikasi provinsi yang diperbarui BPS
**Kode parser, normalisasi, preprocessing, dan kamus sinonim identik**
antara baseline `potret-79-sesudah-C2.json` (commit 57bb7ba) dan HEAD
(`git diff --stat` kosong). Jadi SEMUA perbedaan di provinsi berasal dari
isi PDF.

Ketujuh PDF memang berkas baru. Ukurannya berbeda dibanding sidik di
cadangan sebelum run (cadangan dipulihkan ke DB uji, lalu DB uji dihapus):

| Publikasi | Ukuran lama -> baru | Entri |
|---|---|---|
| Tinjauan PDRB Kab/Kota (`11487263`) | 4,46 -> 4,55 MB | identik |
| Gambaran Ekonomi Makro (`1c688dd3`) | 11,52 -> 11,54 MB | identik |
| Statistik Keuangan Pemda (`9ab3d434`) | 1,86 -> 2,13 MB | identik |
| Master File Desa Sem II 2025 (`b99ddcad`) | 26,85 -> 27,36 MB | identik |
| **Statistik Perhotelan 2025** (`aabde615`) | 3,09 -> **4,35 MB** | 54 -> 54; halaman cetak 26, halaman fisik 49, judul 1 berubah |
| **Statistik Perhubungan 2025** (`dcb62e21`) | 3,14 -> 2,71 MB | 85 -> 85; 7 tabel/gambar bergeser +1 halaman; gambar 3.9 sumber keduanya -> daftar (halaman fisik tetap 47) |
| **Statistik Ekspor Impor 2025** (`ff0ff482`) | 16,55 -> **5,27 MB** | 61 -> 61; 6 judul ("US$ Juta" -> "US$ juta", "2024–2025" -> "2024 – 2025"), 2 sumber daftar -> keduanya, 1 halaman |

Di ketiganya tidak ada kunci yang hilang atau bertambah, dan tidak ada
`halaman_fisik` yang hilang. Perubahan Perhotelan berupa halaman tambahan
(geseran halaman cetak +1 s.d. +20) dan satu koreksi judul di sumber
("2023 – 2024" -> "2023 – 2025"). 72 publikasi provinsi lainnya identik
dengan baseline.

**Master File Desa "336 entri tanpa nomor halaman" bukan hal baru dan bukan
cacat.** Peringatan yang sama sudah ada di log pemuatan sebelumnya (7 dan
9 Nov). Ketiga edisi MFD sejak baseline: 334-336 entri, semuanya jalur badan,
semuanya PUNYA `halaman_fisik`. Publikasi ini tidak punya halaman Daftar,
jadi memang tidak ada nomor halaman cetak; tombol PDF tetap menuju halaman
yang tepat. Peringatan `perlu_diperiksa` untuk kasus ini adalah peringatan
palsu. Catatan CLAUDE.md "3 × Master File Desa: 0 entri" sudah usang sejak
ekstraksi badan (September) dan diluruskan.

## 3. Sampel acak 40 entri kab/kota (seed 20261110), dibaca satu per satu
Bukti per entri:
- baris pemicu di halaman fisik (keterangan bernomor persis, keterangan
  bertumpuk, atau judul bab utuh);
- folio halaman itu;
- baris Daftar bernomor sama.

| Penilaian | Jumlah | Sampel |
|---|---|---|
| Benar | 33 | |
| Benar, judul sedikit kotor | 2 | Buklet Banjarbaru tabel 4 berawalan ": "; PDRB Kotabaru tabel 13 berawalan "/ " dan menyisipkan "Table 13" |
| **Halaman fisik menunjuk halaman Daftar** | 1 | Kesra Kotabaru lampiran 35 -> hal. 18 (lanjutan Daftar Lampiran ber-leader "……") |
| Halaman fisik isi meleset 4 halaman | 1 | KAK Balangan Agt 2025 "Bab III": sampul bab (hal. 57) tanpa lapisan teks, sehingga yang cocok judul seksi di hal. 53 |
| Judul isi diawali kop | 1 | PDRB Tabalong "Halaman/Page IV. PERKEMBANGAN AGREGAT ..." |
| KAK tanpa nomor | 2 | KAK Kotabaru Agt 2025 dan KAK HST Agt 2024: pola judul di atas baris nomor (keterbatasan KAK Agt 2024 yang ditunda) |

Sampel #14 sempat dibuka di publikasi yang salah (KAK Balangan Agt 2024,
bukan 2025) karena pencarian alat memakai awal judul. Penilaian diambil
dari pembukaan ulang menurut ID entri.

### Temuan: leader elipsis di halaman Daftar lanjutan
Lanjutan Daftar ber-leader "……" (U+2026) tidak dikenali `_halaman_daftar`
(yang menghitung "....."), sehingga `lengkapi_halaman_fisik` bisa mengambil
halaman Daftar sebagai halaman keterangan. Ini keterbatasan yang sudah
tercatat sejak 7 Nov, kini dengan dampak nyata. Penyaring heuristik
(halaman ≤ 40, > 3 deret elipsis, ≥ 3 baris berakhir leader + nomor,
tidak dikenali sebagai Daftar) menemukan **31 entri di 8 publikasi**:
- Indikator Kesra Banjarbaru (10);
- PDRB HSS (6);
- Kesra Kotabaru (5);
- Survei Kebutuhan Data Balangan (5);
- 4 KAK (1-2).

Angka ini calon, belum dibaca satu per satu. **Usulan, belum
dikerjakan:** `_halaman_daftar` ikut menghitung deret "……" sebagai dot
leader. Ini perubahan parser, jadi butuh persetujuan.

## 4. Lima publikasi 0 entri: tidak punya lapisan teks
Diperiksa satu per satu: jumlah huruf non-watermark, objek halaman
(pdfplumber dan pdfium), dan render. Satu-satunya teks di kelimanya adalah
watermark URL miring 45 derajat, yang memang dibuang parser.

| Publikasi | Bentuk isi | Bukti |
|---|---|---|
| **Kabupaten HST Dalam Angka 2026** (`aafda0cf`, 320 hal.) | huruf diubah menjadi kurva vektor | hal. 20 dirender: Daftar Tabel terbaca jelas, tersusun dari 2.470 kurva dan 0 huruf selain 37 huruf watermark; 316 dari 320 halaman berkurva banyak |
| PDRB Tapin Pengeluaran (`f338cd99`, 99 hal.) | kurva vektor | 3.293 kurva di hal. 20 |
| Profil Tenaga Kerja Tapin Agt 2024 (`47c94280`) | teks dirasterkan menjadi potongan gambar | 46 gambar di hal. 20; render terbaca |
| Statistik Daerah Banjarbaru 2025 (`8db55ef6`) | potongan gambar + sedikit path | halaman isi: 8-21 gambar; halaman lain kosong |
| PDRB Banjarbaru LU (`a818fdde`) | gambar satu halaman penuh | gambar menutupi 100% halaman di hal. 21, 33, 103 |

**Bukan cacat parser.** Tanpa lapisan teks, satu-satunya jalan adalah OCR
(spike OCR di daftar revisi awal). Kelimanya tetap bisa ditemukan lewat
pencarian tingkat publikasi (judul + abstrak).

Pemindaian ke-227 PDF kab/kota (halaman dengan < 20 huruf non-watermark)
menemukan **8 publikasi** dengan ≥ 50% halaman tanpa teks: kelima di atas,
ditambah dua edisi PDRB Tapin LU (91%, 41 entri dari Daftar yang masih
bertekst) dan PDRB Tabalong (64%, 1 entri). Rasio di 213 PDF lain < 30%
(halaman kosong, pembatas bab, infografis).

## 5. Baseline baru
`potret-306-sesudah-13-domain.json`: 306 publikasi, 23.461 entri, SHA-256
`0b824d75f671a68812b59f3202976fe388475417a3d6400c306cb108e775e808`.
Salinan di `~/cadangan-bps/`. Cadangan sebelum run:
`db_pencarian_bps-20261109-1951-sebelum-13-domain.sql`.

## 6. Waktu pencarian dengan 14 domain
`data/ukur_kinerja/20261110-0846-sesudah-13-domain.json`. Diukur
bergantian dalam satu sesi, tanpa proses lain. Data 79 publikasi =
cadangan sebelum run yang dipulihkan ke DB uji (lalu dihapus).

| Urutan | Data | Rata-rata median | p95 | Ambil korpus (median) |
|---|---|---|---|---|
| 1 | 14 domain, 23.461 entri | **430 ms** | 452 ms | **308 ms** |
| 2 | 79 publikasi, 6.738 entri | 116 ms | 140 ms | 84 ms |
| 3 | 14 domain, 23.461 entri | 427 ms | 451 ms | 307 ms |

| Kueri | 79 pub | 14 domain | Entri dinilai (14 domain) |
|---|---|---|---|
| tpk | 100 ms | 355 ms | 37 |
| penduduk tanah laut (wilayah) | 115 ms | 434 ms | 5.445 |
| luas panen padi kotabaru (wilayah) | 106 ms | 382 ms | 1.736 |
| jumlah penduduk menurut kecamatan (terlambat) | 143 ms | **539 ms** | 14.260 |

- Waktu naik ±3,7x, sebanding dengan jumlah entri (3,5x), dan kini
  **melewati batas 300 ms** di CLAUDE.md.
- **Sekitar 70% waktunya adalah mengambil SELURUH korpus dari MySQL di setiap
  kueri** (308 ms). Kueri yang hanya menilai 37 entri pun butuh 355 ms.
- Usulan untuk rancangan filter wilayah (belum dikerjakan):
  1. **simpan korpus di memori proses**, dimuat sekali dan dibuat ulang
     sesudah pembaruan data atau "Terapkan ke data". Ini menghilangkan
     ±300 ms per kueri;
  2. filter wilayah menyaring daftar di memori itu, tanpa query baru.

  Dengan (1), perkiraan waktu kembali ke ±50-230 ms tergantung jumlah entri
  yang dinilai. Perkiraan, belum diukur.

## 7. Kecepatan unduhan
Dari 234 baris "unduh X MB, Y KB/detik" di log:
- per berkas: min 38, median 1.036, maks 17.992 KB/detik;
- median menurut ukuran: < 5 MB 674, 5-15 MB 842, ≥ 15 MB 2.883 KB/detik.
  Berkas besar tidak lebih lambat, jadi tidak ada batas per berkas.

Menurut jam (durasi per domain dijumlahkan dari awal run; perkiraan
selesai 01:31, log mencatat 01:32):

| Domain | Mulai | Unduh | MB | KB/detik |
|---|---|---|---|---|
| 6300-6304 | 20:30-23:18 | 201 menit | 732 | 51-78 |
| 6305 | 00:07 | 30 menit | 212 | 117 |
| 6306 | 00:42 | 10 menit | 144 | 232 |
| 6307 | 00:56 | 3 menit | 197 | 1.074 |
| 6308-6372 | 01:05-01:27 | ±0,4-1,4 menit per domain | ±1.220 | 2.800-10.300 |

**Jawaban atas hipotesis "konsisten ±40-60 KB/detik per koneksi": benar
hanya untuk 20:30-00:00.** Selama periode itu kecepatannya memang rata
38-75 KB/detik berapa pun ukuran berkasnya, mirip pembatasan. Tetapi dengan
koneksi tunggal yang sama, kecepatan naik bertahap sejak ±00:00 sampai
±7-10 MB/detik sesudah 01:00. Jadi bukan batas tetap per koneksi di server,
melainkan **kapasitas yang berubah menurut jam**: jam sibuk malam, entah di
jaringan rumah/ISP atau di server BPS. Data yang ada belum bisa membedakan
keduanya. Sebagai pembanding, uji 9 Nov pukul 19:42 mencatat ±5.360
KB/detik.

81% waktu unduh (3,35 jam) habis untuk 29% data (732 MB) sebelum tengah
malam.

**Usulan soal unduhan paralel 2-3: belum layak dikerjakan sekarang.**
- Pembaruan rutin sesudah ini kecil (publikasi baru per bulan, puluhan
  hingga ratusan MB). Bahkan pada 50 KB/detik itu ±1 jam, dan bisa
  dijadwalkan sesudah tengah malam.
- Belum terbukti bahwa paralel membantu. Kalau hambatannya kapasitas jalur
  (ISP), 2-3 koneksi hanya membagi kecepatan yang sama.
- Term of Use meminta tidak membebani server. Koneksi paralel menambah
  beban per waktu tepat di jam sibuk.

Kalau tetap ingin diuji: satu percobaan terkendali di jam lambat (±21:00),
1 vs 2 unduhan bersamaan berkas berbeda, masing-masing ±5 menit. Kalau 2
koneksi memberi ±2x, hambatannya per koneksi, dan maksimal 2 pekerja dengan
jeda 1 detik antar permintaan masih wajar. Kalau tidak, cukup jadwalkan
penarikan besar sesudah tengah malam.
