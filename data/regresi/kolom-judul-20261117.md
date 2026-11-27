# Tebakan kolom judul: nomor halaman di baris sendiri (17 Nov 2026)

Perbaikan untuk Kabupaten Tabalong Dalam Angka 2025 (`34b2075e`, domain 6309),
disetujui pemilik project 17 Nov 2026 dengan syarat regresi ke SELURUH 306
publikasi di database uji. Produksi TIDAK disentuh; pemuatan menunggu
persetujuan.

## Masalah

Daftar Tabel publikasi ini memakai format tanpa label (nomor bertumpuk di kolom
kiri). Nomor halamannya tercetak di baris sendiri, di ujung dot leader:

```
 x 74   Jumlah Sekolah, Guru, dan Murid Sekolah Menengah
 x 43   4.1.7
 x 77   Atas (SMA) di Bawah Kementerian Pendidikan, ...
 x 43   Number of Schools, Teachers, and Pupils in ...
 x 76   by District in Tabalong Regency, ... ..................  105
```

`_mode_tanpa_label` menebak kolom judul dari x0 baris yang berakhir nomor
halaman. Di sini baris seperti itu umumnya hanya berisi dot leader + nomor
(x0 = 245-377), sehingga tebakannya jatuh ke kolom dot leader. Akibatnya semua
baris judul (x0 = 77) dibuang sebagai kolom kiri, halaman Daftar ke-4
menghasilkan 0 entri, dan `_baca_daftar` berhenti membaca. 11 halaman Daftar
Tabel sisanya tidak pernah terbaca: hanya 25 tabel yang masuk.

## Perbaikan

`app/services/ekstraksi_pdf.py`:
- `RE_LEADER_NOMOR_SAJA` + `_hanya_leader_nomor(baris)`: baris yang isinya
  hanya dot leader + nomor halaman.
- Di `_mode_tanpa_label`, baris seperti itu tidak ikut menebak kolom judul.
  Kalau sesudah itu tidak tersisa baris berakhir nomor yang bisa dipakai,
  kolom ditebak dari x0 semua baris lain, kecuali nomor tunggal, kop kolom,
  dan kop halaman.
- Jalur lama tidak berubah selama masih ada baris berakhir nomor yang bukan
  "leader saja". Karena itu publikasi lain tidak tersentuh (dibuktikan di
  bawah).

Kasus uji baru di `tests/uji_pipeline.py` bagian I
("kolom-judul-nomor-baris-sendiri"). Hasilnya 10/10 dengan kode baru; parser
lama mengembalikan `[]` untuk kasus itu.

## Regresi: 306 publikasi, database uji

`perbarui.py --db-uji --lokal --paksa`: sukses, 5.541 detik, kode keluar 0
(log `data/log_pembaruan/20261117-081517.log`). Potret sebelum/sesudah ada di
folder `kolom-judul-20261117/`, dibandingkan per kunci `(tipe, nomor)`
(`perubahan.txt`):

| | Hasil |
|---|---|
| Publikasi berubah | **1** (Tabalong DA 2025) |
| Kunci hilang | **0** |
| Kunci bernomor yang isinya berubah | 0 |
| Kunci baru | 71 (semuanya tabel) |
| Entri tanpa nomor baru | 4 |

305 publikasi lain identik, dan edisi 2026 juga tidak berubah. Tabalong 2025:
71 → 146 entri (tabel 25 → 100; gambar 26 dan isi 20 tetap).

Ke-71 tabel baru semuanya punya `halaman_fisik` asli dari penanda bertumpuk
C1(a), bukan perkiraan; 61 punya halaman cetak.

## Sampel manual: 30 tabel baru (seed 20261117)

Tiap entri dicocokkan dengan baris Daftar Tabel di PDF (dibaca termasuk teks
miring) dan dengan halaman fisiknya (keterangan "Tabel N" + folio).

| Medan | Benar |
|---|---|
| Nomor | 30/30 |
| Halaman fisik (tombol PDF menuju tabelnya) | 30/30 |
| Judul + halaman cetak sesuai Daftar | **25/30** |

Lima yang cacat:

| Tabel | Cacat | Sebab |
|---|---|---|
| 4.1.2 | menyerap judul 4.1.3, tanpa halaman cetak | nomor halaman "92" tercetak miring |
| 4.1.11 | menyerap judul 4.1.12, tanpa halaman cetak | "115" miring |
| 4.4.4 | berawalan sisa entri sebelumnya, berakhir kop seksi Inggris, tanpa halaman cetak | "143"/"144" miring |
| 7.2 | judul berakhir "xxi", tanpa halaman cetak | entri terbelah halaman Daftar; folio menempel |
| 13.6 | judul berakhir "xxv", tanpa halaman cetak | sama |

Catatan halaman cetak: di bab 5 dan 6 (23 tabel), Daftar mencetak angka satu
LEBIH KECIL dari folio badan. Contohnya 5.1.1: Daftar 154, folio 155. Ini
kesalahan sumber, polanya sama dengan Kotabaru Dalam Angka 2026. Entri
mengikuti Daftar (dinilai benar), dan halaman fisik tetap menuju tabel yang
tepat.

## Sisa cacat di Tabalong 2025 (di luar rancangan, TIDAK diubah)

Dibandingkan dengan Daftar Tabel di PDF (103 tabel), sesudah perbaikan ada 95
tabel bernomor asli. Yang tidak ada:

1. **Nomor halaman miring dibuang sebagai watermark (6 tabel: 4.1.3, 4.1.12,
   4.3.1, 4.3.5, 4.4.2, 4.4.3).**
   - Di halaman Daftar fisik 17-20, baris Inggris ditulis miring sintetis
     (matriks (10, 0, 0,875, 10): `m[1]` = 0, `m[2]` ≠ 0).
   - `_bukan_watermark` membuang karakter bila `m[1]` ATAU `m[2]` ≠ 0, sehingga
     11 dari 83 nomor halaman di Daftar Tabel ikut terbuang.
   - Entri tanpa nomor halaman tidak ditutup, jadi entri berikutnya tergabung
     ke dalamnya. Judul yang tertelan tetap bisa dicari, tetapi tombol PDF-nya
     menuju tabel pertama.
   - Dari sebab ini juga: 4.2.5, 4.3.2, 4.3.3, 4.3.4, 4.4.1, 4.4.4 cacat judul
     atau tanpa halaman cetak.
2. **Entri terbelah halaman Daftar (7.2, 12.7, 13.6, 4.3.3).** Baris Inggris
   dan nomor halamannya ada di halaman berikutnya. Ini utang teknis yang sudah
   tercatat 16 Nov: lanjutan di awal halaman berikutnya belum ditempel, dan
   folio di baris sendiri menempel ke judul. Empat entri tanpa nomor baru
   berasal dari sini dan dari sebab 1 ("Tabalong, 2023/2024 dan 2024/2025",
   "Cleared in Tabalong Regency, 2024", "Number of Available Rooms ...",
   "Percentage Distribution of GRDP ...").
3. **3.1.3 dan 4.1.1 hilang, dan kop seksi "4.1 PENDIDIKAN" menjadi entri
   tabel "4.1".** Ketiganya SUDAH ADA sebelum perbaikan ini (ada di potret
   sebelum) dan tidak berubah. Halaman Daftar fisik 16 mencampur format
   bertumpuk (3.1.3) dengan nomor sebaris (3.2.1-3.2.4).

## Temuan: teks miring sintetis di korpus

Pindai 307 PDF (60 halaman pertama): 54 publikasi punya karakter bermatriks
shear (`m[1]` = 0, `m[2]` ≠ 0), 44 di antaranya di sekitar halaman Daftar.
Hampir semuanya teks Inggris atau hiasan. Angka miring hanya signifikan di
Tabalong DA 2025 (292 angka). Kecil di Banjar DA 2026 (36), Indikator Ekonomi
Banjarmasin (33), PDRB Banjarmasin (30), KAK Tanah Bumbu (28), dan PDRB
Kab/Kota Provinsi (13).

**Usulan (BELUM disetujui, BELUM dikerjakan):** `_bukan_watermark` hanya
membuang karakter bila `m[1]` ≠ 0 (rotasi). Watermark BPS diputar 45 derajat,
jadi `m[1]` ≠ 0. Teks miring yang tidak diputar dipertahankan.
- Manfaat: 6 tabel Tabalong 2025 kembali, dan nomor halaman di publikasi lain
  ikut terbaca.
- Risiko: baris Inggris miring di 54 publikasi akan ikut masuk ke judul dan ke
  penanda gaya jalur badan. Banyak judul bisa berubah, jadi butuh regresi
  penuh dan sampel tersendiri. Perkiraan: setengah hari termasuk regresi
  (±1,5 jam).

## Pemuatan ke produksi (17 Nov 2026, disetujui pemilik project)

Pemuatan terarah 1 publikasi (`kolom-judul-20261117/muat_kolom_terarah.py`,
salinan skrip 16 Nov), bukan `perbarui.py --paksa`.

1. **Cadangan:** `C:/Users/Dani/cadangan-bps/db_pencarian_bps-20261117-sebelum-kolom-judul.sql`
   (perintah PANDUAN bagian 7). Dipulihkan ke database sementara: 6/6 tabel
   sama jumlah baris dan CHECKSUM, lalu database sementaranya dihapus.
2. **`--coba` ke produksi: LULUS, tanpa menulis.**
   - Target sama dengan potret sebelum regresi.
   - 305 publikasi lain = database uji per kunci.
   - IPM HSU (`a21060d6`) hanya ada di produksi, karena masuk lewat pembaruan
     16 Nov 15.20. Publikasi ini diekstrak kering dengan kode baru dan hasilnya
     identik dengan isi produksi, jadi perbaikan ini tidak mengubahnya.
3. **Muat:** 146 entri, 32 detik. Hasilnya dibandingkan per kunci dengan
   database uji sebelum ditulis. Log: `kolom-judul-20261117/muat-produksi.log`.
4. **Bukti** (`bukti_pemuatan.py`, keluaran di `bukti-pemuatan.txt`):
   - 306 publikasi produksi = database uji per kunci (0 beda);
   - baris publikasi lain: 24.386 sebelum = 24.386 sesudah, 0 berubah per id;
   - baris Tabalong 2025: 71 -> 146;
   - tabel `publikasi`, dibandingkan per kolom dengan cadangan: hanya baris
     `34b2075e` yang berubah (waktu ekstraksi);
   - `versi_data` 508 -> 509;
   - `log_pencarian` (113) dan `kategori` CHECKSUM sama;
   - `entri_dokumen` 24.457 -> 24.532.
5. **Uji tombol** lewat test_client, dengan konfigurasi produksi dan log
   dimatikan:
   - "angka partisipasi murni" dengan wilayah Tabalong menampilkan kartu tabel
     4.1.10 "Halaman 114" dan "Buka PDF hal. 150";
   - `/pdf/34b2075e…` HTTP 200;
   - `log_pencarian` tetap 113 baris.
