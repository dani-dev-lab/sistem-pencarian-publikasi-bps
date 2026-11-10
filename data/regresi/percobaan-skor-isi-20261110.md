# Percobaan skor: judul bab (`isi`) vs tabel/gambar/lampiran (10 Nov 2026)

**Percobaan saja. Kode skor produksi TIDAK diubah.** Keputusan final menunggu
uji coba petugas PST.

**Keputusan pemilik project (10 Nov 2026):** skor produksi TIDAK diubah;
hasil percobaan ini dibawa ke uji coba PST.

**Masalah utama "penduduk tanah laut" adalah kueri satu kata yang terlalu
umum, bukan entri bab vs tabel.**
- Sesudah kata wilayah dibuang, topiknya tinggal "penduduk".
- Di Tanah Laut ada 45 tabel/gambar lain yang juga memuat kata itu dan
  berskor lebih tinggi daripada tabel yang dicari. Rinciannya di bagian
  "Kasus penduduk tanah laut".
- Tidak ada varian bobot atau urutan yang membawa tabel itu ke halaman
  hasil. Yang membawanya adalah kueri yang lebih spesifik.

- Skrip: `scripts/percobaan_skor_isi.py`. Skrip ini membaca daftar kandidat
  lengkap dari `mesin_pencari._cari_entri` lewat jalur filter wilayah yang
  sama dengan halaman `/hasil`, lalu menyusun ulang peringkatnya di luar
  mesin.
- Data mentah: `percobaan-skor-isi-20261110.json`.
- Kueri: 17 = 12 kueri uji `ukur_kinerja.py` + 5 kueri wilayah ("penduduk
  miskin tala", "inflasi bjm", "pdrb hss", "jumlah sekolah banjar",
  "penduduk kotabaru").
- Data: 306 publikasi, 23.461 entri.

**Bukti alatnya benar:**
- varian A skrip ini = tampilan produksi (entri_id dan urutan, ditemukan +
  saran), **17/17 kueri**;
- varian C terbukti menghasilkan urutan yang berbeda.

## Varian
| | Aturan | Skor tampil | Ambang |
|---|---|---|---|
| A sekarang | urut skor | asli | 75 / 50 |
| B bobot isi | skor entri `isi` × 0,9 (disapu juga 0,95, 0,85, 0,8), lalu urut dan kelompok ulang | isi ikut turun (96,7 tampil 87,0) | 75 / 50 terhadap skor baru |
| C tabel dulu | di dalam tiap kelompok (ditemukan, saran), tabel/gambar/lampiran lebih dulu; urutan skor dipertahankan di dalam golongan | asli | tidak berubah |

## Hasil: 10 teratas yang tampil
| Kueri | Filter | isi di top-10, A / B / C | non-isi pertama, A / B / C |
|---|---|---|---|
| statistik ekspor impor | - | 10 / 9 / 0 | tidak ada di 40 tampil / 8 / 1 |
| negara tujuan ekspor | - | 1 / 1 / 0 | 2 / 1 / 1 |
| banyaknya akomodasi kabupaten kota | - | 0 / 0 / 0 | 1 / 1 / 1 |
| jumlah hotel kabupaten kota 2024 | - | 0 / 0 / 0 | 1 / 1 / 1 |
| tingkat penghunian kamar | - | 2 / 2 / 2 | 3 / 1 / 1 |
| tpk | - | 2 / 2 / 2 | 3 / 1 / 1 |
| penduduk miskin | - | 5 / 0 / 0 | 6 / 1 / 1 |
| population by regency | - | 0 / 0 / 0 | 1 / 1 / 1 |
| ekspor batubara | - | 4 / 0 / 3 | 1 / 1 / 1 |
| jumlah penduduk menurut kecamatan | - | 0 / 0 / 0 | 1 / 1 / 1 |
| **penduduk tanah laut** | 6301 | **10 / 5 / 3** | **11 / 6 / 1** |
| luas panen padi kotabaru | 6302 | 0 / 0 / 0 | 1 / 1 / 1 |
| penduduk miskin tala | 6301 | 4 / 1 / 4 | 1 / 1 / 1 |
| inflasi bjm | 6371 | 3 / 0 / 0 | 1 / 1 / 1 |
| pdrb hss | 6306 | 9 / 0 / 5 | 10 / 1 / 1 |
| jumlah sekolah banjar | 6303 | 0 / 0 / 0 | 1 / 1 / 1 |
| penduduk kotabaru | 6302 | 8 / 4 / 3 | 9 / 2 / 1 |
| **Total isi di top-10** | | **58 / 24 / 22** | non-isi di #1: **9 / 14 / 17** |

Polanya: judul bab menguasai puncak untuk kueri **pendek dan umum**
("penduduk", "pdrb", "statistik ekspor impor"). Untuk kueri yang spesifik
("jumlah hotel kabupaten kota 2024"), tidak ada perbedaan sama sekali.

## Sapuan bobot isi (17 kueri)
| Bobot | isi di top-10 | non-isi di #1 | Total ditemukan | isi ditemukan | isi turun < 50 (di seluruh kandidat) |
|---|---|---|---|---|---|
| 1,0 (A) | 58 | 9 | 406 | 69 | 0 |
| 0,95 | 40 | 11 | 364 | 27 | 187 |
| **0,9** | **24** | **14** | **357** | **20** | **352** |
| 0,85 | 11 | 14 | 341 | 4 | 407 |
| 0,8 | 5 | 16 | 339 | 2 | 477 |
| C | 22 | 17 | 406 | 69 | 0 |

## Dampak ke ambang 75/50
- **Varian C tidak menyentuh ambang.** Jumlah ditemukan/saran sama persis
  dengan A, karena hanya urutan tampil yang berubah.
- **Varian B (× 0,9) menggeser ambang efektif untuk entri isi** menjadi
  83,3 (ditemukan) dan 55,6 (saran):
  - **49 entri isi pindah dari "ditemukan" ke "saran"** (skor asli
    75-83,3). "Bagian yang ditemukan" lebih pendek:
    - pdrb hss 15 → 5;
    - penduduk tanah laut 20 → 12;
    - penduduk kotabaru 22 → 12;
    - penduduk miskin 63 → 49.
  - Tidak ada kueri yang kehilangan seluruh "ditemukan"-nya.
  - **352 entri isi jatuh di bawah 50**, tetapi hampir semuanya sudah di
    luar 20 saran yang tampil. Yang benar-benar hilang dari layar hanya
    **23 entri**, dan contohnya memang derau: "1.2 Tujuan" ×6, "3.6 Net
    Ekspor", "3.2 Impor Menurut Negara Asal" untuk "negara tujuan ekspor".
  - Akibatnya, kalau B dipakai, ambang 75/50 perlu dikalibrasi ulang
    bersama bobotnya. Bobot dan ambang tidak bisa dinilai terpisah.
- **Efek samping C:** di dalam satu kelompok, skor tampil tidak lagi
  menurun. Contohnya "Penduduk" 96,7% tampil di bawah gambar 75,9%. Petugas
  bisa bingung kenapa yang "lebih relevan" ada di bawah.

## Kasus "penduduk tanah laut"
Pesan pemilik project menyebut tabel yang dicari "baru muncul di ~72".
Dalam data ini:
- tabel/gambar pertama ada di **urutan 11** dengan skor 77,0 ("Piramida
  Penduduk Kabupaten Tanah Laut, 2024");
- angka 72,2 adalah skor gambar "Perkembangan Jumlah Penduduk Miskin di
  Tanah Laut".

Tabel yang paling mungkin dicari petugas, **"Penduduk Menurut Kecamatan dan
Jenis Kelamin di Kabupaten Tanah Laut (jiwa), 2025"**, berskor **70,3**,
urutan **60 dari 201 kandidat**, dan **tidak tampil di varian mana pun**
karena tiap kelompok dibatasi 20 hasil. Tanpa batas itu posisinya:

| Varian | A | B × 0,9 | B × 0,8 | C |
|---|---|---|---|---|
| Urutan | 60 | 53 | 48 | 59 |

Di atasnya selalu ada **45 tabel/gambar lain** yang juga memuat
"penduduk". Rincian skornya: set 100, coverage 100, tetapi sort 7,4,
karena judulnya 23 token terhadap kueri 1 token.

Jadi untuk kueri ini masalahnya **bukan isi vs tabel**, melainkan topik
satu kata yang terlalu umum di dalam satu wilayah. Tidak ada alternatif
yang menyelesaikannya. Yang menolong adalah kueri yang lebih spesifik
("jumlah penduduk menurut kecamatan" + filter Tanah Laut), dan itu bisa
diamati di uji coba PST lewat `log_pencarian`.

## Ringkasan untuk keputusan
- **B (× 0,9)** mengurangi isi di top-10 dari 58 ke 24. Biayanya: skor isi
  yang tampil ikut turun, dan ambang efektif isi bergeser, sehingga perlu
  dikalibrasi ulang. Sisi baiknya, derau isi di sekitar ambang 50 ikut
  tersaring.
- **C** paling kuat (isi 22, non-isi di #1 pada 17/17 kueri) dan tidak
  mengubah skor maupun ambang. Biayanya: skor tampil tidak monoton di
  dalam kelompok. Bab yang memang dicari ("Bab II Kependudukan") turun ke
  bawah semua tabel di kelompoknya.
- Untuk kueri spesifik, keduanya tidak berpengaruh.
- Bahan yang perlu dikumpulkan saat uji coba PST:
  - apakah petugas memakai entri bab (tombol PDF ke awal bab) atau hanya
    tabel;
  - seberapa sering kueri satu kata dipakai (`log_pencarian`).
