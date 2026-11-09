# C2: varian "nomor sebaris" di mode tanpa-label (9 Nov 2026), BELUM DIMUAT

Kode ada di `C2-nomor-sebaris-20261109.patch` (diuji, `git apply --check`
lolos terhadap HEAD `5904220` (sesudah perbaikan awalan)). Parser di working tree
dan database TIDAK diubah: dua KAK menunjukkan efek yang butuh keputusan
pemilik project (lihat "Temuan yang menahan pemuatan").

## Perubahan dalam patch
- `_mode_nomor_sebaris`: aktif bila tidak ada baris berlabel (kop kolom dan
  kata label tunggal tidak dihitung, `_kop_kolom`), minimal 3 baris diawali
  nomor + huruf dengan awal judul pada kolom yang sama, DAN minimal 3 baris
  diakhiri nomor halaman (tanpa syarat terakhir, halaman BADAN berisi daftar
  prosa bernomor di Statistik Air Bersih ikut terbaca).
- `_parse_baris_nomor_sebaris`: entri dibuka baris bernomor dan ditutup
  baris bernomor berikutnya (bukan nomor halaman - Kecamatan Dalam Angka
  mencetak nomor halaman dua kali). Dibuang: baris kiri tak bernomor, kepala
  bab kapital semua, judul seksi tanpa halaman yang disusul sub-nomornya,
  folio di kolom judul, kop "Hal." yang sebaris dengan entri pertama, dan
  nomor halaman ganda di ujung judul.
- `_lanjutan_masuk_akal` menerima halaman lanjutan berpola sama; `jejak`
  mencatat `tipe:halN:sebaris`.

## Regresi 79 PDF (uji kering vs database = baseline `potret-79-sesudah-awalan.json`)

| Syarat | Hasil |
|---|---|
| `(publikasi, tipe, nomor)` BERNOMOR hilang | **0** |
| Entri kehilangan `halaman_fisik` / berpindah | 0 / 0 |
| Sumber turun | 0 (yang ada hanya badan → keduanya: 479) |
| Entri tanpa nomor hilang | 424, semuanya blok gabungan jalur daftar lama |
| Entri bernomor bertambah | 341, semuanya berhalaman cetak |
| Entri berubah | 801 (halaman cetak didapat 781, sumber 479, judul 312) |
| Entri total | 6.821 → 6.738 |

**Cakupan lebih luas dari perkiraan penyelidikan: 18 publikasi, bukan 6.**
Penghitung penyelidikan mensyaratkan nomor bertitik ("1.1"); format yang
sama dengan nomor bulat ("1", "2") ada di 4 KAK, 7 Gambaran Ekonomi Makro,
dan Buklet padi `18e4b6e4`.

### Bukti independen: selisih fisik−cetak per publikasi
Entri yang kini punya halaman cetak DAN halaman fisik (fisik dari jalur
badan/pelengkap, tidak diubah C2):

| Publikasi | Selisih |
|---|---|
| 7 × Gambaran Ekonomi Makro | +18 (51-55 per publikasi), kecuali 1 entri di 2 publikasi (lihat bawah) |
| Kesra `26d401fd` | +34 (174 dari 175) |
| KAK Feb 2025 `83fff1db` | +50 (100 dari 100) |
| Pemotongan Ternak `579f5146` | +14 (26/26) |
| Air Bersih `9f4c3cc4` | +18 (33 dari 34) |
| IPM `1bc84df2` | +14 (16 dari 19) |
| **KAK Feb 2026 `193ca993`, KAK Agt 2025 `afd64a18`** | **menyebar 58-61 / 64-68, dan TURUN untuk tabel berurutan** |

Pemeriksaan kedua: untuk setiap entri bernomor berhalaman fisik di 11
publikasi, apakah halaman fisiknya memuat keterangan TERLIHAT (≥7 pt) dengan
nomor persis (sebaris atau bertumpuk)? Ya untuk semua entri di 9 publikasi;
**tidak untuk 91/101 entri `193ca993` dan 105/137 entri `afd64a18`**.

### Sampel per publikasi (2 acak per publikasi, 36 sampel, seed 20261109)
Bukti: baris Daftar pemicu (baris berawalan nomor entri) + halaman fisik.
- **27 benar** - Podes, IPM, Kesra, Ternak, 7 Gambaran Ekonomi Makro, PDRB
  Kab/Kota (tabel dan lampiran), Air Bersih, KAK Feb 2025.
- **4 salah - KAK `193ca993`/`afd64a18`**: halaman fisik menunjuk tabel lain;
  satu judul juga milik tabel lain (lihat temuan 1).
- **2 judul terpotong - KAK Agt 2024 `2ddab8a8`** (temuan 2).
- **2 bukan cacat C2**: Buklet gambar 6 cetak "1" (judul berakhir "2025¹"
  terbaca "20251" lalu dipecah aturan lama `_pisah_nomor_halaman` menjadi
  tahun + halaman 1); IPM gambar 4.2 selisih 11 (halaman fisiknya benar -
  keterangan "Gambar 4.2" ada di hal. 54; Daftar sumber menulis 43, folio 40).
- 4 sampel tanpa baris Daftar di alat bukti (alat hanya mencari 8 halaman
  sesudah heading, Daftar Kesra/PDRB/KAK lebih panjang); judul dan selisihnya
  konsisten.

### Cacat kecil C2 yang diketahui (dibiarkan)
- Gambaran Ekonomi Makro tabel 41 (1c688dd3, 7d1c21c1): judul "(P₁) ...
  (P₂)" - angka indeks "2" di ujung baris terbaca nomor halaman (cetak 2,
  semestinya 53).
- Air Bersih: nomor "13" di Daftar tercetak terbelah, sehingga muncul entri
  sampah "tabel 3" (cetak 28, "Kalimantan Selatan Selama Tahun 2024") dan
  tabel 13 tidak punya entri jalur daftar.
- PDRB Kab/Kota tabel 3.4: judul prosa dari jalur badan ("di bawah
  menyajikan be- ...") menang aturan judul terpanjang - cacat badan lama.
- Kecamatan Dalam Angka (sampel 6301): judul seksi di AKHIR halaman ("6.2
  Transportasi/Transportation") lolos sebagai entri, karena sub-nomornya baru
  di halaman berikut. Publikasi jenis ini tidak ditarik (`kecualikan_judul`).

## Temuan yang menahan pemuatan
**1. KAK Feb 2026 dan Agt 2025: keterangan 5 pt bernomor lama.** Halaman
tabel KAK memuat DUA keterangan: yang terlihat (12 pt, mis. "Tabel 11 ...
di Perdesaan") dan salinan 5 pt dengan nomor LAIN ("Tabel 5 ..."), kemungkinan
sisa penomoran edisi lain di berkas sumbernya. Jalur badan sejak dulu
menerima salinan 5 pt (gayanya beda dari badan), sehingga di database:
- SEBELUM C2: entri "tabel 5" = judul + halaman fisik tabel 11 (isi dan
  halaman cocok, NOMOR salah);
- SESUDAH C2: entri itu digabung dengan "tabel 5" versi Daftar yang benar
  (judul + halaman cetak tabel 5), tetapi `halaman_fisik` tetap menunjuk
  tabel 11. Kalau judul versi badan lebih panjang, judul tabel 11 yang
  menang. Tombol "Buka PDF hal. N" membuka tabel lain.

Teks kecil yang lolos jalur badan (dipindai di 79 PDF): KAK Feb 2026 94, KAK
Feb 2025 102 (nomornya SAMA dengan yang terlihat - tidak berbahaya), KAK
Agt 2025 131, IHK 3 ("LAMPIRAN 1/2/..." 6 pt). Tidak ada di publikasi lain.

**2. KAK Agt 2024 `2ddab8a8`: baris pertama judul di ATAS baris nomor.**
Daftar Tabelnya: "Persentase Penduduk Usia Kerja ..." / "Tabel" / "15 Jumlah
Jam Kerja ...". Baris pertama menempel ke entri SEBELUMNYA dan entri ini
kehilangan awal judulnya. Sebelum C2 bagian ini menghasilkan 8 blok sampah;
sesudah C2 5 entri bernomor dengan judul tergeser. Ini salah satu dari dua
publikasi yang Anda tunda.

## Pilihan
- **(a) Muat C2 apa adanya.** 16 publikasi membaik dengan bukti kuat; di dua
  KAK, ±196 entri berganti dari "nomor salah, halaman cocok" ke "nomor &
  judul Daftar benar, halaman fisik menunjuk tabel lain"; KAK Agt 2024 judul
  tergeser.
- **(b) Dulu: jalur badan mengabaikan keterangan < 7 pt** (pengecualian aturan
  superset, butuh izin Anda - teks 5 pt bukan keterangan yang terlihat
  pembaca), lalu C2. Dua KAK jadi konsisten: halaman fisik diisi pelengkap
  dari keterangan terlihat. IHK "LAMPIRAN" 6 pt perlu dicek dulu (mungkin
  keterangan asli yang memang kecil - ambangnya bisa 6 atau dibuat relatif
  terhadap ukuran badan).
- **(c) Muat C2 untuk semua kecuali tiga KAK** - butuh pengecualian per
  publikasi di parser; tidak saya sarankan (aturan mati).

Saran saya: **(b)**, dengan KAK Agt 2024 (temuan 2) sebagai perbaikan kecil
terpisah di jalur nomor-sebaris (baris kolom judul sebelum baris "Tabel"
tunggal dianggap awal entri berikutnya).

## Sampel kab/kota (tidak masuk DB utama), vs parser sesudah perbaikan awalan
Hanya Kecamatan Pelaihari (6301 `122bdbc9`) yang berubah: 5 blok sampah
hilang; 42 entri badan kini juga ditemukan jalur daftar (badan → keduanya,
judul lebih lengkap, halaman cetak didapat); gambar 1 dan 3 bertambah; 1
judul seksi akhir halaman ("6.2 Transportasi/Transportation") ikut
bertambah. Lima berkas lain: 0 perubahan.
