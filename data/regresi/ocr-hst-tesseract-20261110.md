# OCR HST Dalam Angka 2026 penuh: Tesseract + parser yang ada (10 Nov 2026)

Lanjutan spike OCR (`spike-ocr-20261110.md`), atas keputusan pemilik project.
Hari ini hanya Tesseract; EasyOCR dijalankan besok dengan struktur cache yang
sama.

- **Parser produksi TIDAK diubah, MySQL produksi TIDAK disentuh.** Hasilnya
  hanya berkas.
- Bukti ada di `ocr-hst-tesseract-20261110/`:
  - keluaran parser;
  - deteksi;
  - penilaian manual per butir;
  - lembar bukti sampel;
  - salinan skrip.

## Lokasi tetap (di luar repo)
| Apa | Lokasi |
|---|---|
| Tesseract 5.4.0 portabel + data ind/eng/osd | `C:\Users\Dani\alat-ocr\tesseract\` |
| venv EasyOCR (torch CPU, 1,1 GB) | `C:\Users\Dani\alat-ocr\venv-ocr\` |
| Model EasyOCR (94 MB) | `C:\Users\Dani\.EasyOCR\model\` |
| Installer Tesseract asli (SHA-256 cocok winget) | `C:\Users\Dani\alat-ocr\tess-unduh\` |
| Skrip: `bangun_cache_ocr.py`, `parser_ocr.py`, `bukti_sampel.py`, `spike_ocr.py`, `nilai_ocr.py` | `C:\Users\Dani\alat-ocr\` |
| Cache OCR per halaman | `data/ocr_cache/` di proyek, **di-gitignore** |

- Semuanya dipindah dari scratchpad sesi, yang bisa hilang saat sesi
  ditutup.
- venv yang dipindah sudah diuji: `import easyocr, torch` berhasil.
- `git status` bersih dari semua berkas itu.

## Kriteria "halaman tanpa lapisan teks"
- Halaman di-OCR bila jumlah karakter **non-watermark** yang bukan spasi
  **< 20**.
- "Non-watermark" ditentukan oleh penyaring yang sama dengan parser
  (`_bukan_watermark`): karakter yang matriks transformasinya tidak miring
  45 derajat.
- Untuk HST Dalam Angka 2026: **320 dari 320 halaman** berisi **0**
  karakter non-watermark. Satu-satunya teks di PDF ini adalah watermark.
- Deteksi butuh ±6 menit, karena pdfplumber mengurai semua kurva vektor.

## Cache OCR
- Lokasi: `data/ocr_cache/<domain>/<pub_id>/<hal:04d>-<mesin>.json`. Nama
  mesin ada di nama berkas, supaya Tesseract dan EasyOCR tidak saling timpa.
- Isi: mesin, versi, dpi (300), ukuran halaman, detik OCR, dan kata
  `{text, x0, x1, top, bottom, conf, baris}`.
  - Koordinatnya dalam **poin PDF**, sama dengan pdfplumber.
  - `baris` = (blok, paragraf, baris) Tesseract.
- Ditulis atomik (`.tmp` lalu rename), dan halaman yang sudah ada dilewati.
- HST: 320 berkas, 6,8 MB.
- Waktu: rata-rata **1,4 detik OCR per halaman**, 4 proses paralel
  (`OMP_THREAD_LIMIT=1`), seluruh 320 halaman ±2,5 menit.
- Perintah EasyOCR besok (struktur sama, mesin `easyocr`):
  `venv-ocr\Scripts\python.exe bangun_cache_ocr.py hst-deteksi.json C:/sistem-pencarian-bps easyocr 0 1`

## Adaptor ke parser (`parser_ocr.py`)
Urutan langkahnya sama dengan `ekstrak_lengkap()`:

```
cari_heading → _baca_daftar → ekstrak_badan → _gabung → lengkapi_halaman_fisik → lengkapi_halaman_isi
```

Halaman tanpa teks diganti objek yang menyediakan `.filter()` dan
`.extract_words()` dari cache. Batasannya:
- OCR tidak memberi font atau warna. Karena itu `size` = tinggi median baris
  OCR (dibulatkan 0,5 pt), `fontname` = "OCR", dan warna hitam.
- Kata watermark dibuang menurut teks (memuat "bps"/"go.id"), karena OCR
  tidak punya matriks. Di cache HST tidak ada satu pun.

## Hasil otomatis
| | HST 2026 via Tesseract | HST 2025 (bertekst, di DB) |
|---|---|---|
| Entri | 153 | 157 |
| Tabel | 135 | 137 |
| **Tabel bernomor** | **58 (43%)** | 135 (99%) |
| Tabel berhalaman cetak | 115 | 135 |
| Tabel ber-`halaman_fisik` | 32 | 135 |
| Isi | 18 | 20 |
| Jalur badan | **0** | - |
| Gambar | 0 | 0 |
| Waktu parser | 0,8 detik | - |

Penyebab yang sudah dibuktikan:
- **Jalur badan 0** karena pembeda keterangan adalah gaya huruf, yang tidak
  dimiliki OCR. Ini sesuai dugaan.
- **Gambar 0 bukan masalah OCR.** Heading "DAFTAR GAMBAR/LIST OF FIGURES" di
  halaman 31 terbaca sempurna, tetapi `cari_heading` hanya mencari di
  `BATAS_HALAMAN_CARI = 25` halaman pertama. Batas yang sama berlaku untuk
  PDF bertekst: HST 2025 di DB juga 0 gambar. Ini temuan parser, dicatat dan
  tidak diubah.
- **Nomor yang hilang** cocok dengan celah urutannya, misalnya 4.1.1-4.1.4,
  4.1.6-4.1.9, 5.2.1, 5.2.3-5.2.9, 3.2.1-3.2.4.

## Nomor di kolom kiri (masalah di spike): masih bermasalah
Diperiksa langsung di kotak kata cache (kata dengan x0 < 65 pt):

| Halaman | Yang terbaca di kolom kiri |
|---|---|
| 10 | 1.1.2, 1.1.3, 1.1.4, 2.1.1 benar; **1.1.1 tidak ada** |
| 20 | hanya "4.5" (kode bagian); **4.5.1-4.5.4 tidak ada sama sekali** (koreksi: versi pertama laporan ini menulis 4.5.1-4.5.6 tanpa membaca gambarnya. Halaman 20 hanya memuat 4.5.1-4.5.4, lalu 5.1.1-5.1.3) |
| 31 | titik desimal lepas: "11", "21", "41", "71" untuk 1.1, 2.1, 4.1, 7.1 |

Jadi **kotak kata saja tidak menyelesaikan masalah spike**. Yang hilang
sudah hilang di tingkat OCR, bukan di parser. Nomor halaman di kolom kanan
terbaca rapi.

## Uji psm 4 dan psm 6 pada Daftar Tabel (hal. 10-30), atas permintaan pemilik project
- **Acuan dibaca manual:** nomor tabel di kolom kiri ke-21 halaman, dari
  potongan render PDF asli (`kolom-kiri-1..3.png`). Hasilnya **139 nomor
  tabel** (`acuan-kolom-kiri.json`), tanpa kode bagian bercetak tebal seperti
  "4.5" atau "5.".
- **Cache:** `<hal>-tesseract-psm6.json` dan `<hal>-tesseract-psm4.json`
  (42 berkas, ±1 menit).
- **Cara menghitung:** nomor dianggap terbaca bila ada sebagai token utuh di
  kolom kiri (x0 < 65 pt) halaman yang benar. Token kolom kiri lain yang
  bukan nomor acuan dan bukan kode bagian dihitung sebagai salah baca.

| Mode Tesseract | Nomor kolom kiri terbaca | Salah baca di kolom kiri | Angka halaman di kolom kanan | Kata judul conf ≥ 80 |
|---|---|---|---|---|
| psm 3 (bawaan) | 56 / 139 (40%) | 8 | 130 | 4.516 |
| psm 6 | 22 / 139 (16%) | 112 (titik hilang: "112" untuk 1.1.2) | 109 | 4.447 |
| **psm 4** | **106 / 139 (76%)** | 33 (titik hilang: "421", "41.10") | 122 | 4.517 |

- psm 4 = "satu kolom teks berukuran beragam". Mode ini tidak memisahkan
  kolom nomor menjadi blok sendiri, sehingga nomornya ikut terbaca bersama
  baris judulnya.
- Kesalahan psm 4 yang tersisa sebagian besar berupa **titik yang hilang**
  ("4.2.1" terbaca "421"). Halaman 17 paling buruk.

**Parser penuh, psm 4 hanya untuk halaman 10-30, psm 3 untuk sisanya**
(`hst-parser-tesseract-psm4daftar.json`). Ini angka otomatis, **belum
dinilai manual**:

| | psm 3 semua | psm 4 di Daftar |
|---|---|---|
| Entri / tabel | 153 / 135 | 168 / 150 (acuan 139 tabel) |
| Nomor tabel yang cocok dengan acuan | 44 / 139 | **103 / 139** |
| Nomor asing (salah baca) | 14 | 32 |
| Tabel berhalaman cetak | 115 | 123 |
| Tabel ber-`halaman_fisik` | 32 | **85** |

Jumlah tabel 150 melebihi acuan 139, dan judul yang diawali sampah titik
pemandu naik (heuristik kasar: 40 → 69). Mutunya baru bisa disimpulkan dari
sampel manual.

**Usul untuk perbandingan besok:** sampel 30 entri ditetapkan menurut
**identitas tabel** (30 nomor acak dari 139 nomor acuan, seed 20261110),
bukan menurut indeks keluaran parser. Daftar entri tiap mesin berbeda, jadi
indeks yang sama tidak menunjuk tabel yang sama. Dengan begitu Tesseract
psm 3, Tesseract psm 4, dan EasyOCR dinilai pada 30 tabel yang persis sama.

## Penilaian manual: 30 entri acak (seed 20261110)
Setiap entri dibandingkan dengan potongan gambar halaman Daftar asli (render
PDF, bukan teks OCR) dan, bila ada, dengan halaman fisiknya. Rinciannya per
butir ada di `penilaian-tesseract.tsv`, dan lembar buktinya di `sampel/`.

| Ukuran | Hasil |
|---|---|
| Nomor tabel benar | **8 / 28** |
| Halaman cetak benar | **19 / 30** (6 salah, 5 tak terverifikasi) |
| `halaman_fisik` benar (bila ada) | **7 / 7** |
| Judul bersih | 6 / 30 |
| Judul lengkap tetapi berawalan sampah | 17 / 30 |
| Judul rusak (terpotong, gabungan dua tabel, urutan kata kacau) | 7 / 30 |
| Judul lengkap + halaman benar (bisa dipakai pencarian) | **15 / 30** |
| Benar seluruhnya | 2 / 30 |

Pola cacatnya berurutan sebab-akibat:
1. **Titik pemandu** terbaca sebagai deret huruf ("cessssssessssuscss..."),
   jadi tidak dikenali sebagai dot leader.
2. **Nomor kolom kiri hilang** (lihat di atas), sehingga batas entri dalam
   mode tanpa label tidak terlihat. Akibatnya:
   - ekor bahasa Inggris dan sampah entri sebelumnya menempel di awal judul
     (17 entri);
   - kadang dua judul tabel bergabung jadi satu (#7);
   - kadang baris pertama judul tertinggal di entri sebelumnya (#8, #17,
     #23, #28).
3. **Entri yang diawali ekor entri sebelumnya membawa halaman milik entri
   sebelumnya.** Contohnya #9: IPG (4.5.4) mendapat 139, milik IPM. Ini
   terjadi di semua kasus yang terverifikasi (#7, #9, #11, #13, #25).
4. **`halaman_fisik` yang terisi selalu benar** (7/7). Keterangan "Tabel
   4.4.5" di halaman badan terbaca baik oleh OCR.

## Jebakan alat selama penilaian (prinsip verifikasi)
Lembar bukti otomatis tiga kali menampilkan potongan yang SALAH sebelum
dipakai menilai:
1. **Pencarian mencakup halaman 1-40.** Sebagian entri ditunjukkan di halaman
   badan 33-40. Dibatasi ke halaman Daftar 9-31.
2. **Judul yang diawali sampah dicari dengan sampahnya.** Sampah cocok dengan
   sampah di baris lain (#2, #7, #9, #13 menunjuk baris 5.6.2). Sekarang
   dicari dengan bagian sesudah token sampah terakhir.
3. **`fuzz.partial_ratio` selalu mencocokkan string yang LEBIH PENDEK di
   dalam yang lebih panjang**, sehingga baris pendek ("Sungai Tengah,
   2021-2024") dapat 100 di halaman mana pun (#1 menunjuk halaman 24).
   Jarumnya kini 40 karakter pertama judul bersih, dan hanya baris
   sepanjang itu yang dibandingkan.

Penilaian dilakukan sesudah ketiganya diperbaiki. Tujuh entri dengan skor
cocok < 100 dinilai dari teks judul dan pita halaman sekitarnya.

## Kesimpulan sementara (Tesseract saja)
- **Untuk HST Dalam Angka 2026, Tesseract + parser yang ada mengubah 0
  entri menjadi 153.** Separuh sampel (15/30) memuat judul lengkap dengan
  halaman benar, jadi bisa ditemukan lewat pencarian. Mutunya masih jauh di
  bawah publikasi bertekst: nomor 8/28, dan 7/30 judul rusak.
- Masalah spike (nomor kolom kiri), dengan psm 3: kotak kata tidak menolong,
  karena nomornya memang tidak keluar dari OCR.
- **psm 4 di halaman Daftar menaikkan nomor terbaca dari 40% ke 76%** di
  tingkat OCR. Di keluaran parser, nomor yang cocok naik 44 → 103 dari 139.
  Mutunya belum dinilai manual.
- Besok: EasyOCR dengan cache dan adaptor yang sama, lalu penilaian manual
  dengan seed yang sama. Di spike, EasyOCR membaca 39/44 nomor.
- Kemungkinan perbaikan, BELUM dicoba dan perlu persetujuan:
  - OCR kedua khusus kolom kiri (psm 6/7 pada potongan kolom nomor);
  - menormalkan token sampah titik pemandu menjadi "....." di adaptor;
  - menaikkan `BATAS_HALAMAN_CARI`. Ini perubahan parser, jadi perlu
    regresi penuh.
