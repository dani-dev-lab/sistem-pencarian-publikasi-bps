# Jalur badan menolak keterangan tak terlihat (9 Nov 2026)

Pilihan (b) dari `C2-nomor-sebaris-20261109.md`, atas keputusan pemilik
project. Ini pengecualian kedua terhadap aturan superset gaya: **teks yang
tidak terlihat pembaca bukan keterangan asli.**

## Rumus dan alasannya
Keterangan ditolak bila:
- **ukuran label < 0,7 × ukuran teks badan halaman**, dengan ukuran badan =
  ukuran gaya dominan, yang juga dipakai aturan gaya; DAN
- halaman punya minimal **20 kata** berukuran dominan (halaman yang benar-benar
  punya teks badan).

| Pilihan | Alasan |
|---|---|
| Relatif, bukan angka mati | Lampiran IHK dicetak 6 pt di halaman yang seluruhnya 6 pt (rasio 1,0) dan **terlihat** (dirender, hal. 39: "LAMPIRAN 1 / INDEKS HARGA KONSUMEN" di atas tabel). Angka mati 7 pt akan membuangnya. Publikasi kab/kota berhuruf kecil juga aman. |
| 0,7 | Dari sebaran 4.246 keterangan yang diterima jalur badan (79 PDF + 6 sampel kab/kota): keterangan asli terkecil berasio **0,772** (6301 "Tabel 19.2"), lalu 0,778 (Ternak, PDRB fed52821) dan 0,789 (Statistik Daerah 2026). Salinan tersembunyi KAK berasio **0,396-0,63**. 0,7 ada di celah itu. |
| Syarat 20 kata | Halaman pembatas Lampiran `ceddeca5` hal. 85 hanya berisi 5 kata, dengan "LAMPIRAN" dekoratif 37 pt, sehingga "ukuran badan"-nya palsu. Folio "LAMPIRAN 71" (7 pt, rasio 0,19) yang terlihat di situ tidak boleh ikut terbuang. |
| Bukan warna putih | Warna tidak bisa dipakai sendiri: ada keterangan putih berasio > 1 (mis. "Lampiran 35" di `6062f26c`), kemungkinan di atas pita berwarna, yang justru terlihat. |

## Bukti: SEMUA keterangan yang terbuang, satu per satu
Daftar lengkap: `tak-terlihat-terbuang-20261109.tsv` (322 baris: berkas,
halaman, ukuran, ukuran badan, rasio, warna isi, bidang di bawahnya, kontras
piksel, teks).

| Pemeriksaan | Hasil |
|---|---|
| Jumlah yang terbuang | 322: KAK Feb 2025 97, KAK Feb 2026 94, KAK Agt 2025 131. **0 di publikasi lain, 0 di 6 sampel kab/kota.** |
| Warna isi teks | 322/322 putih |
| Digambar di atas bidang tak putih (kotak isi, kurva, gambar) | **0** |
| Kontras piksel di kotak KATA keterangan itu sendiri (render 150 dpi) | 314 nol kontras. 8 berkontras 8-9% dan dirender lalu diperiksa mata: kotaknya kosong putih tepat di atas pita oranye kepala tabel; kontrasnya dari tepi pita yang tersentuh pembulatan, bukan huruf |
| Kontrol: 40 keterangan terlihat dari publikasi yang sama | kontras median 24,6% |

**Kesimpulan: 0 keterangan terlihat terbuang.**

### Dua kesalahan alat selama pembuktian (dicatat, tidak dipakai menyimpulkan)
1. Pengukuran kontras pertama memakai kotak satu baris hasil
   `_kelompokkan_baris`, padahal baris itu memuat kata lain yang terlihat
   (angka pangkat tabel, ekor huruf "Table" 12 pt). Diganti: hanya kata
   keterangan itu sendiri.
2. Pemeriksa mencari baris menurut teks saja. Di KAK Feb 2025 salinan
   tersembunyi berteks PERSIS sama dengan keterangan terlihatnya, sehingga
   yang terukur baris 12 pt di atasnya: 108 "terlihat" palsu. Diganti:
   cocokkan teks DAN ukuran. Jebakan ini dicatat di CLAUDE.md.

## Regresi 79 PDF (uji kering vs database = baseline `potret-79-sesudah-awalan.json`)

| Syarat | Hasil |
|---|---|
| `(publikasi, tipe, nomor)` hilang / bertambah | 0 / 0 |
| Entri kehilangan `halaman_fisik` | 0 |
| Entri berubah | 314, semuanya di tiga KAK |
| ... sumber "keduanya" → "badan" | 314 (lihat bawah) |
| ... judul | 308 |
| ... `halaman_fisik` pindah | 196 (KAK Feb 2026 dan Agt 2025) |

**Sumber "keduanya" → "badan" bukan penurunan dari jalur daftar.** Dulu
salinan tersembunyi dan keterangan terlihat SAMA-SAMA tangkapan jalur badan
untuk satu tabel. `_gabung` menandai kunci kembar dari dua tangkapan badan
sebagai "keduanya". Kini tinggal satu tangkapan, sehingga "badan". (Saat C2
dimuat, jalur daftar ikut menemukannya dan sumbernya menjadi "keduanya" yang
sebenarnya.)

**Halaman fisik sesudahnya:** semua entri berhalaman fisik di ketiga KAK
menunjuk halaman yang memuat keterangan TERLIHAT bernomor persis (101/101,
139/139, 103/103). Sebelumnya 10/101 dan 32/137 di dua KAK yang nomornya
berbeda.

Sampel kab/kota: 0 perubahan.

## Dampak ke C2
C2 diuji ulang di atas aturan ini (`C2-nomor-sebaris-20261109.md`).
Hitungannya sama dengan uji C2 pertama: 0 kunci bernomor hilang, 424 blok
sampah hilang, 341 bertambah. Bedanya di KAK: selisih fisik−cetak kini
konstan (+52 101/101, +64 125/125, +50 100/100), dan 6 sampel KAK acak
benar semua (judul = keterangan terlihat di halaman fisik, folio = halaman
cetak).

## Pemuatan dan baseline
- Cadangan: `~/cadangan-bps/db_pencarian_bps-20261109-1218-sebelum-tak-terlihat.sql`,
  terbukti bisa dipulihkan.
- Dimuat dengan `perbarui.py --lokal --paksa` (log
  `tak-terlihat_muat_log.txt`, exit 0, tanpa kunci API).
- Database = uji kering di 79/79 publikasi, medan dan urutan sama;
  `teks_ternormalisasi` kosong: 0.
- **Baseline:** `potret-79-sesudah-tak-terlihat.json`, 79 publikasi, 6.821
  entri, SHA-256
  `05cc83cab92506979ede4122f393c7a26eecb94718140b088e3f85e772f63ea2`.
- **Daftar perubahan disengaja:** `tak-terlihat-perubahan-20261109.tsv`
  (satu baris per medan yang berubah; 314 entri).
