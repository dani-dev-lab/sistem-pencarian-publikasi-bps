# Dampak batas 25 halaman untuk heading Daftar (10 Nov 2026)

`cari_heading` hanya mencari heading DAFTAR di `BATAS_HALAMAN_CARI = 25`
halaman pertama. Pengukuran ini dilakukan atas permintaan pemilik project.
**Batasnya TIDAK diubah**, parser tidak disentuh, dan database hanya dibaca.

- Skrip: `batas-heading-20261110/ukur_batas_heading.py`.
- Data per publikasi: `batas-heading.json`.

## Cara mengukur
1. **Saringan cepat:** pypdfium2 mencari halaman ke-26 sampai akhir yang
   teksnya memuat "daftar". Ada 236 publikasi dengan halaman calon.
2. **Pemeriksaan heading:** halaman calon diperiksa dengan pemeriksa heading
   parser yang SAMA (`RE_HEADING` pada 6 baris teratas sesudah watermark
   dibuang, lalu `_tipe_dari_heading`).
3. **Hanya yang terlewat yang dihitung:** heading tabel/gambar/lampiran yang
   tipenya TIDAK ditemukan di 25 halaman pertama. Heading yang hanya diulang
   di halaman lanjutan tidak dihitung.
4. **Uji kering:** daftar yang terlewat dibaca dengan `_baca_daftar` tanpa
   menulis apa pun. Entrinya dicocokkan dengan entri publikasi itu di
   database menurut kunci `(tipe, nomor)`.

Database berisi **306 publikasi** (bukan 309), dan semuanya diperiksa tanpa
galat. HST Dalam Angka 2026 tidak termasuk karena tidak punya lapisan teks
(lihat `ocr-hst-tesseract-20261110.md`).

## Hasil
**30 publikasi** punya heading Daftar sesudah halaman 25 yang tidak pernah
dibaca:

| Jenis | Publikasi | Entri di daftar terlewat | Bernomor | Sudah di DB lewat jalur badan |
|---|---|---|---|---|
| **Daftar Gambar Dalam Angka** (hal. 27-49) | **24** (provinsi + 12 kab/kota, kedua edisi) | **498** | 481 | **17** (hanya Tanah Laut 2025/2026) |
| Daftar Lampiran Keadaan Angkatan Kerja (hal. 26-39) | 6 | 6 (uji kering menggabungkan 2 lampiran jadi 1) | 0 | 11 dari 12 lampiran sebenarnya sudah ada |

### Daftar Gambar Dalam Angka: dampak besar
- **±464 entri gambar bernomor tidak terindeks** di 24 Dalam Angka (481
  bernomor dikurangi 17 yang sudah ada).
- Per publikasi: provinsi 29 entri tiap edisi, kab/kota 4-37 entri.
- **Ini mengoreksi catatan C1(b) di CLAUDE.md.** Catatan itu menyebut grafik
  Dalam Angka tidak terindeks "karena Dalam Angka tidak punya Daftar
  Gambar". Kenyataannya **Dalam Angka punya Daftar Gambar**, letaknya
  sesudah Daftar Tabel yang panjang (hal. 27-49), dan terlewat karena batas
  25 halaman.
  - Perkiraan C1(b) ("±55 grafik provinsi + ±5 per kab/kota") juga tidak
    cocok dengan data: Daftar Gambar provinsi memuat 29 entri.
- **Diperiksa pada gambar halamannya:** Daftar Gambar Dalam Angka Provinsi
  2026 hal. 49 (`cek-heading-26plus.png`). Entri hasil uji kering cocok:
  1.1 Peta Wilayah → 7, 1.2 Luas Daerah → 8, 2.1 Jumlah Desa/Kelurahan → 33.
- **Mutu ke-498 entri ini BELUM dinilai dengan sampel manual 25-40.** Yang
  diperiksa baru contoh di atas.

### Daftar Lampiran KAK: dampak kecil
- Isinya 2 lampiran: "1 Kesalahan Baku Relatif" dan "2 Kuesioner Sakernas".
- Uji kering menggabungkannya menjadi 1 entri tanpa nomor, karena "1" dan
  "2" berdiri sendiri di kolom kiri.
- Jalur badan sudah menangkap 11 dari 12 lampiran itu, lengkap dengan
  `halaman_fisik`. KAK Banjar hanya lampiran 1. Yang hilang hanya nomor
  halaman cetaknya.

## Yang perlu diputuskan (tidak dikerjakan)
- **Menaikkan atau menghapus `BATAS_HALAMAN_CARI`** akan menambah ±464 entri
  gambar Dalam Angka. Ini perubahan parser, jadi butuh:
  - regresi penuh 306 PDF;
  - sampel manual;
  - kepastian bahwa heading "DAFTAR ..." di badan dokumen tidak ikut
    terbaca sebagai daftar.
- Sebelum itu perlu dicek berapa heading pertama yang muncul jauh di
  belakang. Di pengukuran ini, semua heading terlewat ada di hal. 26-49.
