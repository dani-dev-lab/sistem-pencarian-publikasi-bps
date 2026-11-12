# OCR HST Dalam Angka 2026: EasyOCR vs Tesseract pada 30 tabel yang sama (12 Nov 2026)

Lanjutan `ocr-hst-tesseract-20261110.md`, atas rencana pemilik project.
- **Parser produksi tidak diubah untuk OCR, dan tidak ada yang dimuat ke
  MySQL.**
- Bukti ada di `ocr-hst-easyocr-20261112/`:
  - acuan;
  - kartu penilaian;
  - penilaian manual per butir;
  - potongan halaman;
  - keluaran parser EasyOCR.

## EasyOCR penuh
- **320 halaman**, satu proses (CPU, torch 2.15 CPU), 07.54-09.13 =
  **78 menit**.
  - Rata-rata **14,6 detik OCR per halaman**, tanpa render. Tesseract
    1,4 detik.
  - 0 galat.
- Cache: `data/ocr_cache/6307/<pub_id>/<hal>-easyocr.json`, struktur sama
  dengan Tesseract (di-gitignore).
- **Hasil parser: 163 entri** (tabel 141, isi 16, gambar 6).
  - 132 dari 139 nomor tabel acuan muncul.
  - Tabel berhalaman cetak 136, ber-`halaman_fisik` 119.
- **Catatan keadilan perbandingan:** EasyOCR dijalankan dengan parser
  working tree yang sudah memuat aturan batas heading baru (lihat
  `batas-heading-20261112.md`), sehingga Daftar Gambar hal. 31 ikut terbaca
  (6 gambar). Kedua keluaran Tesseract dibuat dengan parser lama.
  Perbandingan di bawah hanya mencakup TABEL, yang tidak terpengaruh aturan
  itu.

## Sampel 30 tabel yang sama
- **Sampelnya:** 30 nomor acak dari 139 nomor tabel acuan (seed
  20261110), bukan indeks keluaran parser. Dengan begitu ketiga mesin dinilai
  pada tabel yang persis sama.
- **Acuan dibaca manual** dari potongan render baris Daftar Tabel asli
  (`acuan30-*.png`): judul Indonesia dan halaman cetak.
  - Halaman cetak 4.1.1, 4.1.6, dan 4.1.8 terpotong di gambar, jadi tidak
    dinilai (27 halaman dinilai).
- **Halaman fisik** dinilai dari bagian atas halaman yang ditunjuk
  (`fisik30-*.png`, 32 pasangan). Semua `halaman_fisik` yang diisi mesin
  memuat keterangan "Tabel X.Y.Z" milik entrinya sendiri.
- **Cara menilai:** setiap tabel dinilai manual per mesin dari kartu
  `nilai30.txt`.
  - "Tidak ada" berarti mesin itu tidak punya entri yang mewakili tabel
    tersebut: tergabung ke entri lain, atau hanya cocok di awalan judul yang
    sama dengan tabel lain.

| | Tesseract psm 3 | Tesseract psm 4 di Daftar | **EasyOCR** |
|---|---|---|---|
| Ada entrinya | 20 / 30 | 28 / 30 | **29 / 30** |
| Judul bersih / bersampah / rusak | 5 / 14 / 1 | 12 / 13 / 3 | **27** / 1 / 1 |
| Nomor benar | 6 / 30 | 25 / 30 | **29 / 30** |
| Halaman cetak benar | 12 / 27 | 19 / 27 | **25 / 27** |
| `halaman_fisik` terisi (semuanya benar) | 3 | 21 | **27** |
| Judul lengkap + halaman benar | 12 / 30 | 19 / 30 | **28 / 30** |
| **Benar seluruhnya** | 3 / 30 | 12 / 30 | **27 / 30** |
| Waktu OCR per halaman | 1,4 s | ±1,4 s | 14,6 s |

"Bersampah" artinya judulnya lengkap, tetapi diawali atau diakhiri sampah
titik pemandu, kepala bab, atau ekor entri sebelumnya.

### Kesalahan EasyOCR (3 tabel)
- **3.2.1 dan 3.2.2 tergabung jadi satu entri.** Penyebabnya keanehan
  sumbernya: halaman 49 tercetak menempel pada tahun ("Regency, 202549", tanpa
  titik pemandu, terlihat di `acuan30-1.png`).
  - EasyOCR membacanya sebagai satu token, sehingga entri 3.2.1 tidak tertutup
    dan kehilangan halamannya, dan 3.2.2 tidak punya entri sendiri.
  - Nomor "3.2.2" sendiri terbaca benar di kolom kiri.
- **5.3.1** diawali kepala seksi ("ESTATE CROPS Ay").
- Tanda baca: koma sering terbaca titik koma. Ini tidak mengganggu
  pencarian, karena tanda baca dibuang saat normalisasi.

### Kelebihan tabel psm 4 (150 vs 139 acuan)
Golongan per entri ada di `psm4-150-golongan.json`.

| Golongan | Jumlah | Isi |
|---|---|---|
| Nomor cocok acuan | 103 | tabel asli, tanpa nomor kembar |
| Nomor tanpa titik | 32 | **tabel asli** yang nomornya kehilangan titik ("221" = 2.2.1, "41.10" = 4.1.10). Semua 32 cocok dengan satu nomor acuan setelah titik dibuang |
| Tanpa nomor | 15 | **potongan palsu**: ekor bahasa Inggris, sampah titik pemandu saja, "2025/2026" |

Jadi kelebihannya bukan tabel fiktif. Beberapa tabel terbelah menjadi dua
entri: satu membawa nomor dan sampah, satu lagi membawa potongan judul. Dari
pembacaan manual, enam entri bernomor judulnya hanya sampah titik pemandu.
Heuristik otomatis hanya menangkap tujuh di golongan tanpa nomor, jadi
heuristik itu tidak dipakai untuk menyimpulkan.

## Kesimpulan untuk keputusan berikutnya
- **Mutu: EasyOCR jauh lebih baik.** Benar seluruhnya 27/30, dibanding 12/30
  (psm 4) dan 3/30 (psm 3). EasyOCR tidak menghasilkan sampah titik pemandu,
  dan nomor di kolom kiri terbaca.
- **Biaya EasyOCR:**
  - 10× lebih lambat: 78 menit untuk HST, perkiraan ±5 jam untuk kedelapan
    publikasi tanpa teks;
  - pemasangan 1,1 GB + model 94 MB.

  Untuk pembaruan rutin, yang hanya sesekali bertemu publikasi tanpa teks,
  waktunya masih wajar. Waktu itu hanya terpakai sekali per publikasi, karena
  hasilnya di-cache.
- **Tesseract psm 4** setengah jalan (12/30). Perbaikan di adaptor
  (menormalkan nomor tanpa titik, membuang token titik pemandu) mungkin
  menaikkannya, tetapi itu kerja tambahan dan belum diuji.
- **Belum ada yang dipasang ke pipeline.** Keputusan mesin dan cara
  memasangnya (cache per halaman di pipeline, kapan OCR dipicu) ada di tangan
  pemilik project.
