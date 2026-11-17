# Validasi ambang skor 75/50 (17 Nov 2026)

Data produksi, hanya baca (log pencarian dimatikan). Kode skor dan ambang
TIDAK diubah.

## Bahan

`log_pencarian`: 113 baris, 50 kata kunci unik (3-16 Nov). Isinya
pengembangan, uji coba pemilik project 14 Nov, dan percobaan 16 Nov, jadi
**bukan kata kunci asli petugas PST**. Kata kunci dikelompokkan dulu:

- **Judul entri yang ditempel utuh** (skor ±97). Tidak informatif untuk
  ambang, jadi tidak dinilai.
- **Judul publikasi Kecamatan Dalam Angka.** Publikasinya memang tidak
  ditarik, jadi tidak dinilai.
- **Kata kunci topik.** Inilah yang dinilai: 18 dari log dan dari 12 kata
  kunci uji (`ukur_kinerja.KUERI`), misalnya "tingkat penghunian kamar",
  "luas panen padi", "p1", "jumlah menginap", "konsumsi listrik".

Tiap kata kunci dicari dengan `mesin_pencari.cari(ambang_saran=35)`.
Semua hasil unik di pita 70-75 dan 75-80 (paling banyak 6 per kata kunci
per pita) dibaca satu per satu dan dinilai relevan atau tidak.

## Hasil

| Pita | Relevan / dinilai | Ketepatan |
|---|---|---|
| 75-80 (sekarang "ditemukan") | 45/50 | **90%** |
| 70-75 (sekarang "saran") | 69/89 | **78%** |

Yang salah di pita 70-75 menumpuk di kata kunci UMUM:
- "jumlah hotel kabupaten kota 2024": 0/6; isinya angkatan kerja,
  kejahatan, kendaraan "menurut kabupaten/kota";
- "population by regency": 0/6;
- "jumlah menginap": 2/6. "Pasien rawat inap" ikut, karena kata dasarnya
  sama, "inap".

Di kata kunci spesifik pita 70-75 hampir seluruhnya benar: TPK, luas panen
padi, P1, penduduk miskin, akomodasi, lama menginap, tenaga kerja.

### Tabel yang benar tetapi berskor di bawah 75

Skor langsung tabel yang cocok dengan pola judul:

| Kata kunci | Entri relevan | >= 75 | 70-75 | 50-70 | < 50 | Sebab |
|---|---|---|---|---|---|---|
| tingkat penghunian kamar | 39 | 3 | 31 | 5 | 0 | Judul tabel panjang; yang >= 75 hampir semuanya judul bab pendek. |
| luas panen padi | 51 | 29 | 20 | 2 | 0 | Sama. |
| p1 | 57 | 0 | 8 | 2 | 47 | Banyak judul menulis "P 1" terpisah, jadi tokenisasi, bukan ambang. |
| konsumsi listrik | 34 | 0 | 0 | 0 | 34 | Beda kosakata ("listrik terjual", "kWh"), jadi soal kamus sinonim. |
| jumlah menginap hotel | 42 | 1 | 0 | 30 | 11 | Kosakata ("wisatawan menginap", "tamu"). |

Kata kunci dengan skor terbaik di bawah 75 yang tabelnya memang TIDAK ADA di
korpus. Skor rendahnya benar, dan tidak ada yang tersembunyi:
- "konsumsi listrik per kapita" (69,3);
- "merasa aman" (56,6) dan variannya sampai "proporsi penduduk yang merasa
  aman berjalan sendirian" (68,6);
- "proporsi rumah tangga dengan layanan penuh pengumpulan sampah" (62,7).

## Kesimpulan

**Ambang 75/50 TIDAK diusulkan untuk diubah; statusnya tetap SEMENTARA,
perlu kata kunci asli petugas.**

- **Menurunkan "ditemukan" ke 70** akan memindahkan banyak tabel yang
  benar (TPK, luas panen) dari "saran" ke "ditemukan". Tetapi ketepatan
  pita itu 78%, dibanding 90% di 75-80, dan yang salah menumpuk di kata
  kunci umum yang justru paling mungkin diketik petugas. Buktinya tidak
  cukup jelas.
- **Ambang saran 50:** hasil benar di bawah 50 berasal dari beda kosakata
  dan tokenisasi, bukan dari ambang. Menurunkan 50 hanya menambah hasil
  acak.
- **Yang lebih berpengaruh daripada ambang** (dicatat, tidak dikerjakan):
  - kamus sinonim untuk "konsumsi" ~ "terjual" pada listrik;
  - "inap" (rawat inap vs menginap);
  - tokenisasi "P 1" -> "p1";
  - penalti panjang yang menurunkan judul tabel lengkap di bawah judul bab.

## Keterbatasan penilaian

- Kata kunci bukan dari petugas, dan sebagian dikarang pengembang.
- Penilai satu orang (pengembang), tanpa penilai kedua.
- Hanya 6 hasil unik per pita per kata kunci.
- Kata kunci kembar "tpk" dan "tingkat penghunian kamar" memberi hasil yang
  sama dan ikut terhitung dua kali (12 item).
