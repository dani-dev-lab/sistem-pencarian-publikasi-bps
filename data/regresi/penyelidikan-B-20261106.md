# Penyelidikan B: nomor halaman di judul, halaman kosong, halaman fisik salah (6 Nov 2026)

Penyelidikan saja. Parser belum diubah. Data: 79 publikasi domain 6300 dan
6.812 entri, sesudah regresi 2 ulang (`b7779cb`). Semua alat bantu hanya
membaca DB dan PDF. Alat yang menjalankan parser memanggil fungsi parser
apa adanya, tidak ada salinan yang diubah.

## Dua kasus yang dilaporkan

### 1. "Koefisien GINI ... 2021−2024 26" (TPB 2024, Gambar 30, tombol "hal. 7")
Halaman fisik 7 **adalah halaman Daftar Gambar**, bukan gambarnya. Angka 26 di
ujung judul adalah nomor halaman di baris daftar itu. Tandanya memang U+2212,
tapi tanda itu tidak berperan di sini.

Rantai sebabnya:
1. `_baca_daftar` berhenti di halaman lanjutan yang memuat heading, **apa pun
   tipenya**: `if heading_tipe: break`. TPB 2024 mengulang judul "DAFTAR
   GAMBAR" di halaman fisik 5, 6, dan 7. Akibatnya jalur daftar hanya membaca
   Gambar 1-13, dan Gambar 14-38 hilang dari jalur daftar.
2. `ekstrak_badan` **tidak melewati halaman Daftar**, berbeda dengan
   `lengkapi_halaman_fisik` yang melewatinya. Di halaman 6-7 sebagian baris
   daftar berwarna (0.14, 0.12, 0.12) di atas badan hitam (0.0). Aturan warna
   pun menerimanya sebagai keterangan. Dot leader dibuang
   `_bersihkan_judul`, tapi nomor halamannya tertinggal di judul.

Bukti yang dipakai keputusan: baris `Gambar 30 Koefisien GINI ... 2021−2024……..….. 26`
di fisik 7 lolos `RE_KETERANGAN`, dengan gaya `Century 10.0 (0.14, 0.12, 0.12)`
berbeda dari dominan `Century 10.0 (0.0,)`. Baris teratas halaman itu: `DAFTAR GAMBAR`.

### 2. "7.1 Perkembangan Penduduk Miskin" (Inkesra 2025, isi, hal. 107) tanpa halaman_fisik
Ini **struktural**, bukan kegagalan khusus entri ini. Tidak satu pun dari
1.562 entri `isi` punya halaman_fisik, karena:
- `ekstrak_badan` hanya mengenali label Tabel/Gambar/Grafik/Lampiran;
- `lengkapi_halaman_fisik` sengaja melewati `tipe == "isi"` dan entri tanpa
  nomor.

Bab itu sebenarnya bisa dilacak. Di fisik 131 ada baris
`7.1 Perkembangan Penduduk Miskin` bergaya `Metropolis-Bold 18.0 (0.92, 0.54, 0.11)`,
sedangkan badan halaman bergaya `Metropolis-Regular 11.0` hitam. Selisih
cetak→fisik (131-107 = 24) sama dengan selisih Tabel 7.1 di publikasi yang
sama (hal 109, fisik 133).

## Sebaran pola di 79 publikasi

| Pola | Jumlah | Publikasi | Catatan |
|---|---|---|---|
| Judul diakhiri angka 1-3 digit (kandidat) | 209 | 38 | dipecah di bawah |
| Tanpa `halaman` | 2.028 | 57 | 1.589 dari jalur badan memang tidak punya nomor cetak; **439 dari jalur daftar** adalah kegagalan sebenarnya, di 40 publikasi |
| Tanpa `halaman_fisik` | 2.797 | 76 | 1.562 `isi` (struktural); 1.235 non-isi di 40 publikasi (544 tanpa nomor, 691 bernomor) |
| `halaman_fisik` menunjuk halaman Daftar | 13 | 3 | TPB 2024 10, IHK 2024 2, Sakernas Agt 2024 1 |
| Tangkapan jalur badan yang jatuh di halaman Daftar | 166 | 10 | 45 di antaranya memengaruhi DB, lihat bawah |

### Tangkapan jalur badan di halaman Daftar (sumber utama pola 1 dan 4)
`ekstrak_badan` dijalankan apa adanya pada halaman depan saja, lalu tiap
tangkapan diperiksa apakah halamannya halaman Daftar: ada heading DAFTAR di 6
baris teratas, atau ada >=3 baris ber-dot-leader. Ada 166 tangkapan di 10
publikasi. Pengaruhnya ke DB:

| Akibat | Entri |
|---|---|
| Judul di DB = versi halaman Daftar (sering membawa nomor halaman) | 43 |
| `halaman_fisik` di DB = halaman Daftar | 13 |
| Entri HANYA ada karena tangkapan ini (jalur daftar terpotong) | 9 (semua TPB 2024) |
| Tidak berpengaruh (dikalahkan keterangan asli di badan) | 121 |

Kontrol silang: angka 13 sama persis dengan hitungan P4 yang diperoleh dari
jalur bukti lain, yaitu pemeriksaan halaman yang dirujuk DB.

Kenapa judulnya ikut tercemar walaupun halaman fisiknya benar: `_gabung`
memakai judul badan kalau LEBIH PANJANG. Versi dari halaman Daftar lebih
panjang karena membawa nomor halaman. Halaman fisiknya lalu ditimpa
keterangan asli yang muncul belakangan, jadi hanya judulnya yang rusak.

Per publikasi: Indikator Pasar Tenaga Kerja Agt 2024 45 (berdampak 15),
Laporan Perekonomian 2025 30 (2), Analisis Isu Terkini 2025 28 (11), IPM 2024
16 (2), PDRB Lapangan Usaha (dua edisi) 16+10 (0), TPB 2024 13 (12), IHK 2024
6 (2), Sakernas Agt 2024 1 (1), Statistik Perhubungan 2024 1 (0).

### Heading DAFTAR bertipe sama di lebih dari satu halaman (penyebab daftar terpotong)
3 publikasi:
- TPB 2024: gambar di 5, 6, 7.
- PDRB Kabupaten/Kota: gambar di 12, 13; lampiran di 14, 15.
- Statistik Daerah 2026: gambar di 10, 11.

Yang sudah diperiksa terpotong baru TPB 2024. Dua lainnya diduga sama,
**belum diverifikasi**.

### Kandidat "judul diakhiri nomor halaman" (209) menurut sebab
| Kelas | Entri | Publikasi |
|---|---|---|
| 1. Judul diambil jalur badan dari halaman Daftar | 40 | 6 |
| 2. Entri gabungan (utang teknis lama: beberapa judul jadi satu) | 127 | 19 |
| 3. Entri daftar dengan angka ujung = kolom halaman | 0 | 0 |
| 4. Entri daftar tanpa halaman, angka ujung kemungkinan nomor halaman yang gagal dipisah | 11 | 6 |
| 5. Lainnya | 31 | 17 |

Kelas 5 sebagian besar BUKAN nomor halaman: penanda catatan kaki "1" (Polkam,
Podes), tahun yang terbelah ("202 4 dan 202 5"), dan "Status 1, 2, dan 7". Ada
satu cacat nyata di dua edisi Kerangka Sampel: "Grid 6 km x km 34" dengan
hal=6. Angka "6" dari judul terambil sebagai nomor halaman, sedangkan 34
yang benar tertinggal di judul.

Kelas 2 sebagian besar dari Keadaan Angkatan Kerja (Sakernas, dwibahasa) dan
Gambaran Ekonomi Makro. Kelas ini sama dengan utang teknis "764 entri terlalu
panjang" di CLAUDE.md, bukan pola baru.

### Sampel acak 40 kandidat (seed 20261106), dibaca satu per satu
Hasil pembacaan manual:

| Penilaian | Sampel |
|---|---|
| Nomor halaman menempel di judul satu entri | 9 (sampel 1-4, 19, 22, 27, 36, 37) |
| Entri gabungan; angka = nomor halaman entri yang ikut tergabung | 21 |
| Sampah kop tabel dari jalur badan ("Penduduk 40 Penduduk 40 Penduduk 20") | 2 |
| Bukan nomor halaman (judul sah / tahun terbelah) | 2 |
| Ragu (catatan kaki, nomor halaman cetak di kaki halaman) | 6 |

Bukti tiap sampel adalah baris yang benar-benar memicu keputusan: untuk
jalur badan, baris yang lolos `RE_KETERANGAN` + aturan gaya; untuk jalur
daftar, baris di halaman Daftar. Contoh:
- Sampel 19, Indikator Pasar Tenaga Kerja, Gambar 20. Pemicunya
  `Gambar 20 Pekerja Paruh Waktu ... Agustus 2024 ...49` di Daftar Gambar,
  fisik 16, bergaya Bold di atas badan Regular. Judul di DB: "... Agustus
  2024 49". `halaman_fisik` 67 benar, karena ditimpa keterangan asli.
- Sampel 1, IHK 2024, Lampiran 5. Pemicunya
  `Lampiran 5 Grafik Inflasi Per bulan ... 2024 ………… 28` di halaman Daftar
  Lampiran (fisik 11). Di DB `halaman_fisik` = 11, padahal itu halaman Daftar.

Sampel 12 tangkapan badan di halaman Daftar (seed 7) juga dibaca. Ke-12 nya
benar ada di halaman Daftar: 9 punya heading DAFTAR di 6 baris teratas, 3
halaman lanjutan tanpa heading dengan 10-15 baris ber-dot-leader.

## Usulan perbaikan (belum dikerjakan, menunggu persetujuan)

1. **`_baca_daftar`: heading bertipe SAMA tidak menghentikan daftar.** Ubah
   `if heading_tipe: break` menjadi berhenti hanya kalau tipenya lain, dan
   lewati baris heading itu. Jalur daftar mendapat entri lebih banyak, tidak
   pernah lebih sedikit. Berpotensi terdampak: 3 publikasi (baru TPB 2024
   yang terbukti terpotong).
2. **`ekstrak_badan` melewati halaman Daftar** dengan memakai pemeriksaan yang
   SUDAH ADA di `lengkapi_halaman_fisik`: heading di 6 baris teratas, atau
   lebih dari 3 "....." di halaman. Pemeriksaan itu dipindah ke satu fungsi
   bersama, dan perilaku `lengkapi_halaman_fisik` tidak berubah. Sudah
   diperiksa (7 Nov): ke-20 halaman Daftar tempat 166 tangkapan itu berada
   semuanya sudah dilewati pemeriksaan ini, jadi kriterianya tidak perlu
   diperluas. (Versi awal laporan ini menyebut pemeriksaan itu melewatkan
   dot leader "……" dan halaman lanjutan tanpa heading. Itu klaim yang belum
   diuji, dan ternyata keliru.)
   **Usulan ini sendiri BUKAN superset**: 166 tangkapan jalur badan hilang.
   Karena itu harus dipasangkan dengan usulan 1, dengan syarat lolos terukur:
   - himpunan `(publikasi, tipe, nomor)` sesudah perubahan ⊇ sebelum
     (9 entri TPB 2024 harus kembali lewat jalur daftar);
   - keterangan di halaman non-Daftar tidak berubah sama sekali.
   Aturan gaya (font/ukuran ATAU warna) tidak disentuh.
3. **`halaman_fisik` untuk entri `isi`** dari judul bab. Caranya: cari baris
   yang SAMA dengan judul bab dan bergaya beda dari badan, di pemindaian yang
   sudah dilakukan `lengkapi_halaman_fisik`, jadi tanpa pembacaan halaman
   tambahan. Hanya mengisi kolom kosong, sesuai sifat tahap pelengkap.
   Hasilnya belum diukur. Usul: purwarupa di luar parser pada 5-8 publikasi
   dulu, lalu periksa 25-40 sampel acak sebelum diputuskan.
4. **Ditunda / penyelidikan terpisah**:
   - 439 entri daftar tanpa halaman. 319 di antaranya dari tiga edisi Keadaan
     Angkatan Kerja (format dwibahasa) dan berkait dengan utang teknis entri
     gabungan.
   - 631 entri Dalam Angka 2025/2026 tanpa halaman_fisik (format tanpa label
     dan tanpa nomor, sehingga `lengkapi_halaman_fisik` tidak bisa
     mencocokkannya).
   - "Grid 6 km x km 34" (2 entri).

## Ralat catatan sebelumnya
- Baris log_pencarian 34 BUKAN U+FFFD. Isinya U+2013 ("0–59 Bulan").
- "Nomor �" dan "2021�202" di keluaran uji UI juga bukan data rusak. Itu
  tanda — dan – yang dicetak konsol cp1252.

DB berisi 0 judul dan 0 nomor dengan U+FFFD.
