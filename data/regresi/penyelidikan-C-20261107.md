# Penyelidikan C: Dalam Angka, format daftar kelima, kepala seksi (7 Nov 2026)

Penyelidikan saja. **Parser TIDAK diubah untuk ketiga pola ini** sampai
disetujui pemilik project. Semua angka berasal dari:
- 79 PDF provinsi (`data/publikasi_pdf/6300/`);
- 6 sampel kab/kota (`data/sampel_pdf/63xx_*.pdf`), yang tidak masuk
  database utama.

Script pengukur ada di scratchpad sesi:
- `selidik_tumpuk.py` (C1);
- `selidik_sebaris.py` (C2);
- `simulasi_c3.py` + pembanding per kunci (C3).

Ringkasan dampak:

| Pola | Terdampak | Usulan | Risiko |
|---|---|---|---|
| C1 label bertumpuk | 1.129 entri tanpa `halaman_fisik` bisa diisi (prov 633, 3 Dalam Angka kab/kota 496); ±200 keterangan sah belum terindeks | (a) penanda kedua di `lengkapi_halaman_fisik`; (b) kemudian di `ekstrak_badan` | (a) rendah, (b) sedang |
| C2 format daftar kelima | 7 publikasi (6 prov + Kecamatan Dalam Angka); 113 entri daftar yang hampir semuanya blok gabungan, padahal ada ±423 baris bernomor | perluas mode tanpa-label | sedang |
| C3 kepala seksi dwibahasa | 132 judul di 5 Dalam Angka (prov 31+31, kab/kota 18+20+32) | buang baris kapital semua di awal entri, mode tanpa-label saja | rendah (disimulasikan) |

## C1. Label bertumpuk di badan Dalam Angka

### Pola
Diamati di Dalam Angka provinsi 2026 hal. 65 dan 67:

```
x=42  "Tabel  Luas Daerah dan Jumlah Pulau Menurut Kabupaten/Kota"    <- label + judul baris 1 (kolom judul x=119)
x=72  "1.1.1"                                                         <- nomor sendirian, di antara baris
x=42  "Table  di Provinsi Kalimantan Selatan, 2025"                   <- label Inggris + judul baris 2
x=119 "Total Area and Number of Islands by Regency/Municipality"
```

Kolom label ("Tabel" / "1.1.1" / "Table") dan kolom judul tergabung dalam
satu baris karena `top`-nya sama. Akibatnya:
- `RE_KETERANGAN` (jalur badan) tidak cocok, karena sesudah "Tabel" bukan
  nomor;
- penanda `"tabel 1.1.1"` di `lengkapi_halaman_fisik` tidak pernah muncul
  dalam satu baris.

Halaman lanjutan ("Lanjutan Tabel/ Continued Table 1.1.1") tidak cocok
dengan pola ini, dan memang tidak seharusnya.

### Jumlah terdampak
Deteksi: baris diawali label TANPA nomor, lalu dalam 2 baris berikutnya ada
baris berisi SATU token nomor yang letaknya di antara x label dan x judul.
Halaman Daftar dilewati (definisi baru A).

| Publikasi | Entri bernomor tanpa `halaman_fisik` | Bisa diisi | Kunci baru berjudul |
|---|---|---|---|
| Dalam Angka 2026 | 295 | **295** | 28 (gambar 27, tabel 1) |
| Dalam Angka 2025 | 311 | **306** | 30 (gambar 27, tabel 3) |
| PDRB Pengeluaran 2026 (`f11b837f`) | 33 | **30** | 3 |
| PDRB Kab/Kota (`83f521a7`) | 12 | 2 | 4 |
| Kesra (`26d401fd`) | 0 | 0 | **107 tabel** |
| KAK Agt 2024 (`2ddab8a8`, ditunda) | 3 | 0 | 159 (156 bergaya SAMA dengan badan) |
| 6302 Dalam Angka | 99 | **99** | 25 |
| 6306 Dalam Angka | 166 | **165** | 6 |
| 6371 Dalam Angka | 233 | **232** | 28 |

Inilah penyebab "631 entri Dalam Angka tanpa halaman fisik" yang tercatat
sebelumnya, BUKAN halaman pembuka bab. Pengisiannya:

| Ukuran | Hasil |
|---|---|
| Total entri terisi | 1.129 (prov 633, kab/kota 496) |
| Kemiripan judul hasil rekonstruksi vs judul entri ≥0,8 (heuristik penyaring) | 1.127 |
| Sampel acak 30 (seed 20261107) dibaca satu per satu | **30 benar** |

Bukti penilaian 30 sampel tidak bergantung pada pencocokan: selisih halaman
fisik terhadap halaman cetak KONSTAN dalam tiap publikasi.

| Publikasi | Selisih |
|---|---|
| Dalam Angka 2025 | +56 |
| Dalam Angka 2026 | +56 |
| 6371 | +54 |
| 6302 | +36 |
| 6306 | +44 |

Satu sampel halamannya benar tetapi judulnya tercemar pola C3.

### Derau dan temuan sampingan
- **"LAMPIRAN" + folio:** sebanyak 99 deteksi berupa label SAJA (tanpa
  judul di baris yang sama) dengan nomor halaman berjalan di bawahnya
  (Perhotelan, Statistik Hotel, dll.). Semuanya tersaring dengan syarat
  "ada teks judul di baris label".
- **Halaman fisik lama yang SALAH:** 4 entri di PDRB Kab/Kota (`83f521a7`)
  punya `halaman_fisik` dari jalur badan dengan judul potongan prosa dua
  kolom ("di atas, dapat juga dili- it can also be obse"). Pola bertumpuk
  menunjuk ke keterangan aslinya, 1 halaman dari situ. Ini cacat jalur badan
  yang sudah ada; dicatat, tidak dikejar.
- **Dalam Angka punya keterangan grafik** ("Gambar"/"1.1"/"Figure") di
  halaman infografis tiap bab, sekitar 27-30 per publikasi. Semuanya tidak
  terindeks karena Dalam Angka tidak punya Daftar Gambar.
- **Kesra:** 107 keterangan tabel sah. Daftarnya berformat kelima (C2),
  sehingga entri jalur daftarnya rusak. Judul di keterangannya dimulai satu
  baris DI ATAS label, sehingga rekonstruksi judul harus menyerap ke atas.
- **KAK:** keterangannya juga bertumpuk, tetapi gayanya sama dengan badan
  halaman tabel. Ini tidak lolos aturan gaya jalur badan, tetapi tetap bisa
  dipakai jalur pelengkap (a).

### Usulan
**(a) Dulu - `lengkapi_halaman_fisik`: penanda kedua untuk label bertumpuk.**
Syaratnya:
- baris diawali label tanpa nomor DAN ada teks judul di baris itu;
- dalam 2 baris berikutnya ada baris berisi hanya token nomor entri,
  letaknya di antara x label dan x judul;
- syarat kata judul yang sudah ada (`MIN_KATA_JUDUL`) tetap berlaku.

Seperti sekarang, hanya MENGISI kolom kosong untuk entri yang sudah dikenal
dari daftar. Tidak ada entri baru, tidak ada judul berubah. Perkiraan dampak
+633 `halaman_fisik` di provinsi.

**(b) Sesudah (a) - `ekstrak_badan`: kenali keterangan bertumpuk sebagai
keterangan.** Aturan gaya tidak diubah. Yang perlu dikerjakan:
- rekonstruksi judul ke atas (Kesra);
- buang label tanpa judul.

Dampak: entri baru ±200 di provinsi (gambar Dalam Angka ±55, tabel Kesra
107, lainnya), dan entri yang sudah ada bisa berganti sumber menjadi
'keduanya'. Risikonya lebih besar, jadi butuh sampel manual sendiri.

## C2. Format daftar kelima: nomor sebaris dengan judul, tanpa label

### Pola
Contoh dari Kecamatan Pelaihari Dalam Angka (6301 `122bdbc9`), Daftar Tabel
hal. 15:

```
x=57  "1.1 Luas Daerah Menurut Desa/Kelurahan di Kecamatan Pelaihari, 2025 10"
x=91  "Total Area by Villages/Subdistricts in Pelaihari District, 2025 10"
x=57  "2.1 Wilayah Administratif/Administrative Area"        <- judul seksi, TANPA nomor halaman
x=57  "2.1.1 Jumlah Rukun Warga (RW) dan Rukun Tetangga (RT) Menurut"
x=91  "Desa/Kelurahan di Kecamatan Pelaihari, 2025 18"
```

Empat format yang sudah ditangani tidak mencakup ini:
- tidak ada kata label;
- nomor TIDAK berdiri sendiri di barisnya (syarat `_mode_tanpa_label`).

Akibatnya:
- jalur normal memotong entri per 8 baris (`MAKS_BARIS_PER_ENTRI`);
- `_lanjutan_masuk_akal` menolak halaman lanjutan karena tidak ada label,
  jadi hanya halaman pertama yang terbaca.

Itu sebabnya berkas 6301 hanya menghasilkan 20 entri jalur daftar.

### Jumlah terdampak

| Publikasi | Baris bernomor di halaman Daftar* | Entri jalur daftar sekarang | Di antaranya gabungan/tanpa nomor |
|---|---|---|---|
| Statistik Potensi Desa 2025 (`19b4856c`) | 75 | 37 | 37 |
| IPM (`1bc84df2`) | 19 | 6 | 6 |
| Statistik Kesejahteraan Rakyat (`26d401fd`) | 200 | 6 | 4 |
| Statistik Pemotongan Ternak (`579f5146`) | 27 | 9 | 9 |
| PDRB Kab/Kota (`83f521a7`), bagian tabel | 6 | 46 | 46 |
| Statistik Air Bersih (`9f4c3cc4`) | 37 | 4 | 4 |
| Kecamatan Pelaihari DA (6301 `122bdbc9`) | 59 | 5 | 5 |
| **Total** | **±423** | **113** | **111** |

\* Batas atas: judul seksi seperti "2.1 Wilayah Administratif" ikut
terhitung.

Kaitan dengan utang teknis "entri terlalu panjang": entri >30 token di
database kini 1.210, dan 111 di antaranya dari keenam publikasi provinsi
ini. Sisanya kebanyakan judul dwibahasa Dalam Angka dan KAK yang memang
panjang.

### Usulan
Perluas `_mode_tanpa_label` dengan varian "nomor sebaris":
- **Aktif bila:** tidak ada baris berlabel, dan minimal `MIN_NOMOR_KOLOM`
  baris diawali token nomor di margin kiri yang langsung diikuti teks judul
  pada kolom yang sama dengan baris lanjutan.
- **Batas entri:** baris bernomor membuka entri; nomor halaman di kanan
  menutupnya.
- **Judul seksi:** baris bernomor yang disusul baris bernomor lain SEBELUM
  ada nomor halaman adalah judul seksi, dan dibuang. Contoh: "2.1 Wilayah
  Administratif" lalu "2.1.1 …".
- **Halaman lanjutan:** `_lanjutan_masuk_akal` menerima halaman lanjutan
  dengan pola yang sama.

Syarat "tidak ada baris berlabel" menjaga publikasi berformat biasa tetap
tidak tersentuh. Pola ini sama dengan cara mode tanpa-label dikurung
sekarang. Regresi penuh wajib; ketujuh publikasi akan berubah banyak, jadi
entrinya perlu dibaca per sampel.

## C3. Judul diawali kepala seksi dwibahasa

### Pola
Daftar Tabel Dalam Angka (kab/kota 6302, hal. 13):

```
x=42.5 Bold    "1.1 KEADAAN GEOGRAFI"     <- kolom kiri: sudah dibuang mode tanpa-label
x=76.5 BoldIt  "GEOGRAPHY CONDITION"      <- kolom JUDUL: ikut masuk ke entri berikutnya
x=76.5 Reg     "Luas Daerah dan Jumlah Pulau Menurut"
x=42.5 Reg     "1.1.1"
```

Padanan Inggris kepala seksi tercetak di kolom judul, sehingga menempel ke
entri pertama tiap seksi. Contoh: "GEOGRAPHY CONDITION Luas Daerah ...",
"POVERTY Garis Kemiskinan ...".

### Jumlah terdampak dan simulasi
Simulasi dijalankan DI LUAR parser: fungsi diganti sementara di proses
pengukur, berkas parser tidak diubah. Aturannya: di mode tanpa-label, baris
kolom judul yang SELURUHNYA huruf kapital saat buffer entri masih kosong
dibuang. Dibandingkan menurut kunci `(tipe, nomor)`:

| Publikasi | Kunci hilang | Awalan dibuang | Halaman cetak didapat | Potongan sampah tanpa nomor dibuang |
|---|---|---|---|---|
| Dalam Angka 2026 | 0 | 31 | 1 (4.1.1) | 2 |
| Dalam Angka 2025 | 0 | 31 | 0 | 2 |
| 6302 Dalam Angka | 0 | 18 | 1 (3.1.1) | 2 |
| 6306 Dalam Angka | 0 | 20 | 1 (3.1.1) | 1 |
| 6371 Dalam Angka | 0 | 32 | 2 (3.1.1, 4.1.1) | 2 |

Semua publikasi lain menghasilkan entri IDENTIK per posisi, jadi aturan ini
tidak menyentuh apa pun di luar Dalam Angka. Halaman cetak yang didapat
muncul karena baris kepala seksi tadinya memakan jatah 8 baris entri,
sehingga nomor halaman terlempar ke luar entri.

**Catatan alat:** simulasi pertama membandingkan menurut POSISI dan
melaporkan 260 perubahan di Dalam Angka 2026. Itu artefak, karena satu
entri sampah yang hilang menggeser semua pasangan sesudahnya. Angka di atas
berasal dari pembanding menurut kunci.

### Usulan
Pasang aturan simulasi apa adanya di `_parse_baris_tanpa_label`. Tetap
tersisa: potongan baris Inggris tanpa nomor sebagai entri sendiri (misalnya
"Municipality in Kalimantan Selatan Province, 2024/2025 and 2025/2026").
Penyebabnya entri yang kehilangan nomor halamannya; ini pola lain, belum
diselidiki.

## Urutan yang diusulkan
Tujuannya supaya ratusan publikasi 13 domain cukup diekstrak sekali:

1. **C1(a)**: risiko rendah, dampak terbesar untuk Dalam Angka.
2. **C3**: sudah disimulasikan, terkurung di mode tanpa-label.
3. **C2**: perluasan mode tanpa-label; dikerjakan sesudah C3 karena
   menyentuh fungsi yang sama.
4. **C1(b)**: entri baru dari badan; paling berisiko, butuh sampel
   sendiri.

Masing-masing satu perubahan dengan uji kering + regresi penuh, seperti
A dan B.
