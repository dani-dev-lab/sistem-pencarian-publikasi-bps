# Perkiraan halaman fisik untuk entri ISI + dua cacat Daftar Isi (16 Nov 2026)

Database uji saja. Produksi BELUM dimuat (menunggu persetujuan pemilik project).
Lanjutan dari `perkiraan-halaman-20261116.md`.

## Pemicu

Uji coba di aplikasi: kartu yang tidak melompat ke halaman ternyata entri ISI
(subbab). Contohnya kueri "ekspor impor" dengan wilayah Balangan (6311) dan
Kotabaru (6302): "2.6 Ekspor dan Impor" dan "3.7 Perkembangan Net Ekspor" di
PDRB Menurut Pengeluaran.

## Aturan untuk isi: menyimpang dari "tetangga sejenis dulu"

Permintaan awal: aturan yang sama, tetangga sejenis dulu. Pengukuran
menunjukkan jangkar sejenis (halaman fisik isi yang sudah ada) tidak bisa
dipercaya untuk ini.
- Halaman fisik isi dicari dari teks judul (`lengkapi_halaman_isi`). Di
  sebagian publikasi hasilnya bergeser dari halaman yang dirujuk Daftar Isi:
  - **+2 di PDRB**: sampul bab tanpa teks, judulnya tercetak lagi 2 halaman
    sesudahnya (Balangan Pengeluaran: bab 1 cetak 1 -> hal. 21 = folio 3);
  - **+1 di Booklet Sakernas**: folio = halaman fisik, tetapi Konsep dan
    Definisi 8 -> 9, Penjelasan Teknis 22 -> 23.
- **Leave-one-out tidak bisa menilai ini**, karena kunci jawabannya halaman
  fisik isi itu sendiri. Ukuran yang dipakai: apakah folio di halaman
  perkiraan sama dengan halaman cetak di Daftar Isi (angka di 2 baris atas
  atau bawah).

Dari 2.197 isi yang halaman fisiknya ada, 377 tidak sepakat dengan perkiraan
dari jangkar tabel/gambar/lampiran. Menurut folio:
- 180 kasus membenarkan jangkar non-isi;
- 42 kasus membenarkan jangkar isi;
- 9 kasus keduanya;
- 146 kasus folionya tidak terbaca.

Varian untuk target isi, dinilai dengan folio:

| Varian | Terisi | Folio = cetak | Folio meleset 1-2 | Tepat dari yang terbaca |
|---|---|---|---|---|
| isi dulu (permintaan awal) | 2.048 | 1.345 | 302 | 78% |
| gabungan | 2.178 | 1.536 | 181 | 85% |
| non-isi dulu, cadangan isi | 2.120 | 1.536 | 161 | 86% |
| - bagian dari jangkar non-isi | 1.798 | 1.378 | 63 | **91%** |
| - bagian dari cadangan jangkar isi | 322 | 158 | 98 | **61%** |

**BERLAKU: entri isi HANYA memakai jangkar tabel/gambar/lampiran.** Tanpa
jangkar non-isi, entri isi dibiarkan kosong ("kalau ragu biarkan kosong").
Tabel/gambar/lampiran tidak berubah (setipe dulu, lalu gabungan).

Sebagai catatan, leave-one-out isi terhadap halaman fisik isi yang ada (yang
bias):
- isi dulu 91,1%;
- gabungan 85,2%;
- non-isi dulu 82,5%.

Angka ini SENGAJA tidak dipakai untuk memilih, karena alasan di atas.

## Hasil di database uji

- **1.798 entri isi terisi** (dari 3.832 isi berhalaman cetak tanpa halaman
  fisik; 2.034 tetap kosong karena halaman romawi, tidak ada jangkar non-isi,
  atau tidak memenuhi syarat).
- **Per id** (24.373 baris):
  - 1.798 berubah HANYA `halaman_fisik` NULL -> angka dan penanda 0 -> 1,
    semuanya isi berhalaman cetak angka;
  - 22.575 identik, termasuk 1.036 perkiraan tabel/gambar/lampiran;
  - 0 hilang, 0 baru.
- Run kedua: 0 diisi, 0 diubah, 0 dihapus.
- Sesudah varian "cadangan isi" dibuang, skrip menghapus 322 perkiraan, dan
  per id tetap bersih.
- **12 kueri uji**: identik di semua medan kecuali kolom halaman fisik
  (sorot dibandingkan sebagai himpunan). 9 kartu isi mendapat perkiraan, 0
  perubahan lain.

### Kartu contoh dari uji coba

`ekspor impor`, w=6311 dan w=6302. Halaman perkiraan dibaca:

| Kartu | Cetak -> perkiraan | Bukti di halaman |
|---|---|---|
| Balangan 2026 "3.7 Perkembangan Net Ekspor" | 55 -> 73 | "3.7 Perkembangan Net Ekspor 3.7 The Trend of Net Exports", folio 55 |
| Balangan 2025 "4.5 Perbandingan Net Ekspor Terhadap PMTB" | 67 -> 83 | "4.5 PERBANDINGAN EKSPOR TERHADAP PMTB" |
| Kotabaru 2025 "2.6 Ekspor dan Impor" | 45 -> 59 | "2.6 Ekspor dan Impor 2.6 Export and Import" |
| Kotabaru 2025 "Inventory 3.7 Perkembangan Ekspor" | 70 -> 84 | "3.7 Perkembangan Ekspor 3.7 Trend of Export" |
| Kotabaru 2026 "2.6 Ekspor dan Impor" | 35 -> 51 | "2.6 Ekspor dan Impor … 2.6 Export and Import" |
| Kotabaru 2026 "3.7 Perkembangan Net Ekspor" | 53 -> 69 | "3.7 Perkembangan Net Ekspor 3.7 The Trend of Net Exports" |
| **Balangan 2026 "2.6 Ekspor dan Impor … 35"** | vii -> (kosong) | **Tidak terisi**: halaman cetaknya "vii" (cacat A di bawah) |

## Sampel manual

Kriteria: judul bab/subbab tercetak di halaman perkiraan (dicari baris yang
diawali nomor subbab, di halaman perkiraan ±3). Untuk bab dan bagian
seperti Daftar Pustaka, halaman sampulnya juga dihitung tepat. Sampul bergambar
dirender dan dilihat.

### Sampel isi 2 (seed 20261119, aturan berlaku): 30/30 tepat

- 21 subbab: heading bernomor ada di halaman perkiraan. 4.8 dan 2.3 ditemukan
  lewat nomor saja, karena judul di Daftar berbahasa Inggris.
- 7 bab: sampul atau halaman pembuka bab, 5 di antaranya dirender (sampul
  bergambar Bab 2, 3, 4, 5, 8).
- Laporan Perekonomian bab II: halaman pembatas "Dinamika Ekonomi".
- KAK Tabalong "Daftar Pustaka" (165 -> 227): halaman pembatas Daftar Pustaka,
  folio 165. Isinya mulai 2 halaman sesudahnya.

### Sampel isi 1 (seed 20261118, diambil saat aturan masih memakai cadangan isi)

- Dari 30 entri, 10 tidak diperkirakan lagi dengan aturan berlaku: Booklet
  Sakernas, yang semuanya meleset +1 dengan aturan lama.
- 20 lainnya bernilai sama dengan aturan berlaku: **18 tepat, 2 meleset**:
  - NTP 2024 "6.1 Nilai Tukar Petani": 29, benar 31 (−2);
  - PDRB Provinsi LU "1.1 Pengertian PDRB": 20, benar 21 (−1).

**Gabungan dengan aturan berlaku: 48/50 (96%).** Yang meleset paling jauh 2
halaman.

## Butir 2: dua cacat Daftar Isi (parser TIDAK diubah)

### A. Folio halaman Daftar tercetak sebaris dengan entri terakhir

Contohnya Balangan PDRB Pengeluaran 2021–2025: `2.6 Ekspor dan Impor/Export and
Import ......35 vii`.
- Folio "vii" sebaris dengan entri terakhir halaman Daftar Isi, dan kata
  paling kanan dianggap nomor halaman. Akibatnya halaman = "vii" dan 35
  masuk ke judul.
- Di halaman Daftar berikutnya, kop "Halaman / Page" menempel ke entri
  pertama: "Page BAB 3 … 39 3.1 …", yaitu BAB 3 dan 3.1 dalam satu entri
  berhalaman 42.

Luasnya (kandidat disaring heuristik, lalu SEMUA dibaca):
- **Halaman romawi + judul berakhir angka: 9 entri isi di 9 publikasi, 9/9
  benar cacat.**
  - PDRB Pengeluaran Balangan, Kotabaru 2026, dan Provinsi;
  - IPM Provinsi;
  - Booklet Sakernas Balangan;
  - 4 Gambaran Ekonomi Makro 2025. Di sana satu entri menelan 2-3 subbab
    ("11. Indeks Pembangunan Manusia 61 12. NTP dan Inflasi Perdesaan 67
    Daftar Pustaka 73").
- **"Page BAB 3 … 39 3.1 …": 6 publikasi PDRB Pengeluaran edisi 2026**
  (Balangan, HSS, HSU, Tanah Bumbu, Tanah Laut, Provinsi). BAB 3 tidak punya
  entri sendiri.
- Akibat bagi petugas:
  - entri itu tampil "Halaman vii" dan membuka PDF halaman 1;
  - perkiraan tidak bisa dibuat, karena halaman romawi;
  - subbab yang tertelan tidak bisa dicari sebagai entri tersendiri.

### B. Nomor halaman di baris PERTAMA, lanjutan judul di baris berikutnya

Contohnya Kotabaru PDRB Pengeluaran 2020–2024:
- Posisi kata: "3.6 Perkembangan Perubahan Inventori/Trend of Change in"
  bernomor 69 di baris yang sama (y=175). "Inventory" di baris berikutnya
  tanpa nomor.
- Parser menutup entri di baris bernomor, sehingga baris lanjutan menempel
  ke AWAL entri berikutnya: "Inventory 3.7 Perkembangan Ekspor".
- Ini format daftar ke-3 di CLAUDE.md ("nomor halaman di baris pertama, judul
  menyambung ke bawah"), tetapi tidak dikenali di publikasi ini.

Luasnya:
- Kandidat (isi diawali potongan teks lalu nomor subbab): 152 di 39
  publikasi.
- **Sistematis di 9 publikasi** (>= 5 per publikasi, 116 entri, 11-51% entri
  isi publikasinya):
  - Kotabaru: PDRB Pengeluaran 2025 (18/35), PDRB LU dua edisi (17/49,
    17/48);
  - Tanah Bumbu: PDRB Pengeluaran (18/38), PDRB LU dua edisi (15/49, 12/46);
  - HSS PDRB LU dua edisi (8/46, 5/46);
  - Indikator Pekerjaan Layak Provinsi 2025 (6/51).
- Sisanya (1-3 per publikasi) campuran: sebagian bentuk A (kop "Page"),
  sebagian sungguh B ("Wajib 2.15 Jasa Pendidikan"), sebagian teks OCR rusak.
- **Halaman cetaknya BENAR untuk subbab yang dimulai di baris bernomor.** Yang
  rusak hanya judulnya: awalan sampah di entri ini, dan ekor yang hilang di
  entri sebelumnya, biasanya kata Inggris. Diperiksa di halaman PDF untuk
  Kotabaru 2.6 dan 3.7, dan Tanah Bumbu bab III. Perkiraan halaman fisiknya
  tepat.

### Temuan sampingan: kop "Halaman" sebagai entri sendiri

- **98 entri tabel/gambar/lampiran di 24 publikasi berjudul hanya kop
  halaman Daftar** ("Halaman", "Halaman/ Page", "Halaman Tables Pages xix").
  Semuanya tanpa nomor dan tanpa halaman cetak.
- Kebanyakan di Statistik Kesejahteraan Rakyat kab/kota (7-8 per publikasi)
  dan Statistik Perhubungan.
- Kartunya tampil "Nomor —" dan "Halaman —". Ini cocok dengan dugaan pemilik
  project soal "Nomor —" dari uji coba 14 Nov, tetapi belum dicocokkan dengan
  kueri yang sebenarnya.
- Selain itu, 80 entri di 68 publikasi berawalan kop yang menempel.
