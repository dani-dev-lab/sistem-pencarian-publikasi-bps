# Definisi halaman Daftar (A) dan halaman fisik entri isi (B), 7 Nov 2026

Dua perubahan parser, diuji terpisah dan berurutan: B baru dipasang sesudah
A lolos.

## A. Halaman Daftar = heading DAFTAR atau lanjutan langsungnya

`_halaman_daftar(teks_baris, lanjutan_daftar)` sekarang:
- heading DAFTAR di 6 baris teratas, termasuk heading yang terbelah dua baris;
- ATAU dot leader > 3 DAN halaman fisik sebelumnya halaman Daftar (halaman
  tanpa teks memutus rangkaian).

Ambang ">3" tidak diubah. Pemakainya: `ekstrak_badan` dan
`lengkapi_halaman_fisik`; keduanya memindai berurutan dan meneruskan status
halaman sebelumnya.

### Perubahan tingkat halaman
Dipetakan di 79 PDF provinsi + 6 sampel kab/kota. Definisi lama vs baru
dihitung dua kali, dengan ekstraksi kata yang sama persis seperti kedua
pemakainya.

| Kelompok | Halaman | Penilaian |
|---|---|---|
| Pembuka bab, Kata Pengantar, Statistik Kunci, Penjelasan Umum - Dalam Angka 2025/2026 | 28 | badan, BENAR tidak dilewati (yang diharapkan) |
| Sama, 3 Dalam Angka kab/kota | 36 | badan, benar |
| Halaman konsep/definisi Sakernas (3 publikasi KAK) | 4 | badan, benar |
| Kuesioner lampiran Podes | 2 | badan, benar |
| Teks hias rusak "KKKK PPPP" PDRB Pengeluaran hal. 5-6 | 2 | bukan Daftar; tidak berdampak |
| Daftar Isi tanpa heading, Gambaran Ekonomi Makro (`6fc864b9`) hal. 9 | 1 | halaman Daftar yang kini TIDAK dilewati; tidak berdampak (lihat bawah) |
| Daftar Gambar/Lampiran Statistik Daerah 2025 hal. 11-13 | 3 | halaman Daftar - **ditutup dengan pengenalan heading terbelah** |

Statistik Daerah 2025 mencetak heading dalam dua baris ("DAFTAR" /
"GAMBAR"), dan halaman kosong di hal. 10 memutus rangkaian. Tanpa penanganan,
`lengkapi_halaman_fisik` bisa menunjuk halaman itu untuk entri yang belum
punya halaman fisik. Pemindaian 30 halaman depan seluruh korpus: heading
terbelah HANYA ada di publikasi ini (2 halaman). Dengan kode final, hal. 9,
11, 12, 13 bernilai True dan hal. 15 (pembuka bab) False.

Hal. 9 `6fc864b9` tidak berdampak karena dua hal:
- halaman itu tidak memuat label "Tabel N";
- publikasi itu tidak punya entri isi (heading Daftar Isinya tidak ada).

### Regresi A
Dua uji kering 79 PDF dijalankan: sebelum dan sesudah tambahan heading
terbelah. Hasil keduanya identik byte demi byte.

| Syarat | Hasil |
|---|---|
| `(publikasi, tipe, nomor)` hilang | 0 |
| Entri kehilangan `halaman_fisik` | 0 |
| Sumber turun ke 'daftar' | 0 |
| Entri berubah (medan apa pun) | **0** |

Nol perubahan itu sempat dicurigai, lalu alatnya diperiksa:
- Uji kering dimulai 13 detik SESUDAH berkas parser terakhir diubah.
- Pembanding diberi tiga perubahan suntikan (satu entri dihapus, satu
  `halaman_fisik`, satu sumber) dan menangkap ketiganya.

Sebab nol yang sebenarnya: halaman pembuka bab tidak memuat keterangan
"Tabel N", sehingga dampaknya baru terlihat di B.

## B. Halaman fisik entri isi

`lengkapi_halaman_isi()` mengikuti purwarupa `coba_isi.py` kemarin. Ada dua
perbedaan:
- memakai definisi halaman Daftar yang baru;
- baris halaman diambil dari pemindaian `ekstrak_badan` (parameter
  `baris_halaman`), bukan membaca PDF lagi.

Uji asap pada IHK dan Statistik Daerah 2026: hasilnya identik dengan
purwarupa (3/3 dan 25/25). Waktu uji kering penuh 1.196 detik, tidak lebih
lama dari sebelumnya.

### Regresi B (uji kering vs database lama)

| Syarat | Hasil |
|---|---|
| `(publikasi, tipe, nomor)` hilang / bertambah | 0 / 0 |
| Entri kehilangan `halaman_fisik` / berpindah | 0 / 0 |
| Sumber berubah | 0 |
| Entri berubah | 916, SEMUANYA tipe `isi`, SEMUANYA hanya `halaman_fisik` None → N |

### Cakupan dan ketepatan
- **916 dari 1.562 entri isi (59%)**, di 73 publikasi; 2 dari 75 publikasi
  ber-entri isi mendapat 0. Purwarupa kemarin: 75/145 di 8 publikasi.
  Dalam Angka 2026 naik dari 3/22 ke 14/22 berkat A.
- **Sampel acak 40 (seed 20261107), dibaca satu per satu: 39 benar,
  1 meleset 2 halaman.**

Bukti per sampel adalah baris PEMICU yang benar-benar cocok, ditambah bukti
yang tidak bergantung pencocokan:
- 33 sampel: selisih fisik−cetak sama dengan entri bernomor terdekat,
  dan/atau folio di halaman = halaman cetak.
- 7 sampel dibuka halamannya:

| Sampel | Bukti di halaman | Penilaian |
|---|---|---|
| Gambaran Ekonomi Makro, IKK | folio 33 = cetak 33 | benar |
| Tinjauan PDRB Kab/Kota, 3.3.3.2 | folio 66 | benar |
| Tinjauan PDRB Kab/Kota, 3.2.3.4 | folio 58 | benar |
| NTP 3.4 / 3.5 (dua subbab satu halaman) | folio 9 | benar |
| Laporan Perekonomian 5.6 | judul tercetak di hal. 89 (folio 75); Daftar Isi sumbernya menulis 77, padahal hal. cetak 77 adalah Daftar Pustaka | benar |
| **KSA Bab 3** | terpilih sampul bab (hal. 43, folio 15); Daftar Isi menunjuk halaman isi pertama (folio 17, hal. 45) | **meleset 2 halaman** |

Penyebab utama tidak terisi:
- **Judul bab dwibahasa:** Daftar Isi menulis "Indonesia/ Inggris" dalam
  satu baris, padahal di badan keduanya tercetak di kolom terpisah. PDRB
  Lapangan Usaha 0/52 dan 2/51.
- **Entri halaman depan:** entri seperti "Daftar Isi" berada di halaman
  Daftar itu sendiri.

## Pemuatan dan baseline baru
- Cadangan sebelum memuat:
  `~/cadangan-bps/db_pencarian_bps-20261107-2223-sebelum-halaman-isi.sql`.
  Terbukti bisa dipulihkan ke DB uji terpisah, dengan checksum kelima tabel
  sama.
- Dimuat dengan `scripts/perbarui.py --lokal --paksa`; log ada di
  `halaman-isi_muat_log.txt`, exit 0.
- Database = uji kering B di 79/79 publikasi, medan dan urutan sama persis.
  `teks_ternormalisasi` kosong: 0.
- **Baseline baru:** `potret-79-sesudah-halaman-isi.json`, 79 publikasi,
  6.824 entri, SHA-256
  `8bc4586328fc578d41dfc678a314570f11521bb93ec14b576837ec0e2899c385`.
  Salinannya ada di `~/cadangan-bps/`.
- **Perubahan disengaja terhadap baseline sebelumnya**
  (`potret-79-sesudah-perbaikan-daftar.json`): 916 perbedaan di 73
  publikasi, semuanya `halaman_fisik` None → N pada entri isi. Daftar per
  entri ada di `halaman-isi-perubahan-20261107.tsv`, berisi pub_id, judul,
  halaman cetak, dan halaman fisik baru.
