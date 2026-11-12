# Perbaikan batas heading Daftar: aturan, uji kering, regresi (12 Nov 2026)

Lanjutan `batas-heading-20261110.md` (pengukuran dampak), atas keputusan
pemilik project.
- Perubahannya ada di `cari_heading` (`app/services/ekstraksi_pdf.py`).
- **Belum dimuat ke database produksi**, menunggu persetujuan.
- Bukti ada di `batas-heading-20261112/`.

## Aturan baru
Heading Daftar dicari di **halaman depan**: 25 halaman pertama (seperti
sebelumnya), **ditambah perpanjangan selama blok halaman Daftar belum
putus**. Sesudah halaman 25, sebuah halaman meneruskan blok kalau:
- **halaman Daftar** menurut `_halaman_daftar` yang sudah ada (heading
  DAFTAR di 6 baris teratas, atau dot leader > 3 pada lanjutan langsung);
- **lanjutan langsung yang membawa kop kolom Daftar** di 3 baris teratas
  ("Tabel ... Halaman", "Gambar ... Page"). Daftar KAK tidak memakai dot
  leader sama sekali; yang diulang di setiap halaman lanjutannya hanya kop
  kolom ini;
- **halaman kosong atau hampir kosong** (≤ 3 baris tanpa dot leader:
  halaman pemisah, folio "xxvi" saja, kop kolom tanpa isi). Halaman ini
  tidak memutus blok, tetapi paling banyak 2 berturut-turut.

Halaman pertama sesudah halaman 25 yang bukan salah satu di atas mengakhiri
pencarian.

**Kenapa tidak sekadar menaikkan angka 25?** Daftar Gambar Dalam Angka ada
di hal. 27-49, tergantung panjang Daftar Tabel-nya. Angka berapa pun hanya
memindahkan masalah ke publikasi berikutnya yang Daftarnya lebih panjang.
Batas yang mengikuti blok Daftar tidak bergantung pada panjangnya.

**Kenapa tidak "sampai bab pertama dimulai"?** Untuk itu halaman cetak bab
pertama dari Daftar Isi harus dipetakan ke halaman fisik, padahal selisih
cetak-fisik terbukti berubah-ubah di dalam satu publikasi. Selain itu,
halaman awal bab bentuknya berbeda-beda di 306 publikasi. Aturan blok
Daftar hanya memakai definisi halaman Daftar yang sudah dipakai jalur badan
sejak 7 Nov.

**Sifat superset:** pemeriksaan heading per halaman tidak berubah, dan
`setdefault` mempertahankan heading pertama. Tipe yang sudah ditemukan
sebelum halaman 25 tidak berubah; aturan ini hanya menambah daftar yang
tadinya terlewat.

### Perkembangan aturan selama uji kering 30 publikasi terdampak
1. **Rangkaian halaman Daftar murni** (heading atau dot leader lanjutan)
   hanya menangkap 16/30. Ke-14 kegagalannya berhenti tepat di halaman sela:
   - halaman kosong pemisah (Tabalong 2026 hal. 28, Banjarmasin 2025
     hal. 44, Barito Kuala 2025 hal. 38);
   - halaman berisi folio atau kop kolom saja (Balangan 2026 hal. 26:
     "Tabel Halaman / Table Page / xxiv");
   - lanjutan Daftar KAK tanpa dot leader (Tanah Bumbu, berhenti di hal. 26
     padahal heading Lampiran ada di hal. 29).
2. **Ditambah kop kolom dan halaman kosong ≤ 2:** **30/30** tertangkap,
   heading lama di setiap publikasi tetap sama, dan pencarian berhenti 1-12
   halaman sesudah heading terakhir, yaitu di akhir blok Daftar.

### Jebakan saat memasang kode
Regex kop kolom pertama kali tertulis dengan **karakter backspace (0x08)**
sebagai pengganti `\b`, karena escape di skrip penyunting. Akibatnya regex
tidak pernah cocok. Ketahuan karena pola regex dicetak dan diuji dengan
contoh sebelum dipakai, lalu diperbaiki di tingkat byte. Sesudah itu,
`cari_heading` di kode parser memberi hasil yang sama dengan calon aturan
uji kering di 30/30 publikasi.

## Regresi
| Langkah | Hasil |
|---|---|
| Cadangan | `C:/Users/Dani/cadangan-bps/db_pencarian_bps-20261112-0916-sebelum-batas-heading.sql`, 8,0 MB, SHA-256 `e5cd9f87...c5e86`, tanpa `USE`. Dipulihkan ke salinan `db_uji_batas_heading`: 6 tabel, jumlah baris dan `CHECKSUM TABLE` **sama** dengan produksi |
| Potret sebelum (produksi) | 306 publikasi, 23.461 entri. **Isinya sama persis dengan baseline** `potret-306-sesudah-elipsis.json`; satu-satunya medan yang beda adalah `dibuat_pada` |
| Uji kering 306 publikasi (kode parser sebenarnya, `pipeline_data.ekstrak_berkas`, dibandingkan per kunci `(tipe, nomor)` / `(tipe, judul)` untuk entri tanpa nomor) | **hanya 30 publikasi berubah**, tepat ke-30 publikasi terdampak; **0 kunci hilang**; 0 kunci kembar berubah jumlah; +484 kunci (478 gambar, 6 lampiran) = +487 entri; 17 entri berubah |
| Kode parser vs uji kering monkeypatch kemarin | identik di ke-30 publikasi |
| Pemuatan ke **salinan** `db_uji_batas_heading` (`muat_salinan.py`: `sidik_pdf` → `ekstrak_berkas` → `simpan_entri`, jalur yang sama dengan `perbarui.py`; menolak jalan bila database-nya produksi, dan diuji sungguhan: DITOLAK) | 30 publikasi dimuat. `versi_data` naik tepat 30 (315 → 345) |
| Potret salinan vs potret sebelum, per kunci | 306 publikasi, 23.948 entri: **30 publikasi berubah, 0 entri hilang, +487, 17 berubah**, metadata publikasi tidak berubah. Publikasi yang berubah = hasil uji kering, dan entri baru uji kering ada utuh di salinan (30/30) |
| Produksi sesudah semua langkah | potret ulang: **isinya identik** dengan potret sebelum (produksi tidak tersentuh) |
| Pencarian di salinan | "peta wilayah barito kuala" → Gambar 1.1 kedua edisi; "angka melek aksara" → Gambar 4.2 provinsi; "jumlah pelanggan listrik tanah bumbu" → Tabel dan Gambar 6.2. Entri tanpa `teks_ternormalisasi`: 1 (entri "\|" lama yang sudah dikenal) |

### 17 entri berubah
Semuanya gambar Tanah Laut 2025/2026 yang dulu hanya dari jalur badan. Kini
juga cocok dengan Daftar Gambar:
- `sumber` badan → keduanya;
- halaman cetak terisi;
- judul lebih panjang (aturan judul terpanjang: judul Daftar membawa
  padanan Inggris).

### 487 entri baru
| Golongan | Jumlah | Catatan |
|---|---|---|
| Gambar bernomor | 464 (461 kunci + 3 kembar) | 455 berhalaman cetak, **460 ber-`halaman_fisik`** (penanda label bertumpuk C1(a) ikut bekerja untuk gambar) |
| Sampah tanpa nomor | 23 (4,7%) | rincian di bawah |

**Sampah tanpa nomor (23):**
- 6 lampiran KAK tergabung ("Halaman Appendices Pages 1 Kesalahan Baku
  Relatif ..."). Ini duplikat lampiran 1/2 yang sudah ada dari jalur badan,
  karena nomor "1" dan "2" berdiri sendiri di kolom kiri Daftar KAK.
- ±13 potongan baris bahasa Inggris tanpa nomor. Keterbatasan yang sama
  sudah tercatat untuk Daftar Tabel Dalam Angka.
- 4 kop berjalan halaman Daftar ("KABUPATEN HULU SUNGAI UTARA DALAM ANGKA
  2026 xxxi"). Ini jenis sampah baru.

**3 nomor kembar = KESALAHAN SUMBER**, dibuktikan pada gambar halamannya
(`cek-kembar.png`):
- Barito Kuala Dalam Angka 2026 dan 2025 mencetak "Gambar 1.2" dua kali,
  baik di Daftar maupun di keterangan badan (hal. 57 "Persentase Luas Daerah"
  dan hal. 58 "Jumlah Curah Hujan").
- Tanah Bumbu 2026 mencetak "Gambar 4.1" dua kali.
- Parser membacanya dengan benar. Akibatnya, kembaran kedua mendapat
  `halaman_fisik` kembaran pertama (57, seharusnya 58), karena penanda
  "Gambar 1.2" pertama yang dipakai. Dampaknya 3 entri.

### Sampel manual 30 gambar baru (seed 20261112)
Dari uji kering 30 publikasi, yang terbukti identik dengan uji kering 306.
Setiap entri dibandingkan dengan potongan **baris Daftar Gambar asli** dan
**halaman fisik penuh** (`sampel-gambar/`, `penilaian-gambar.tsv`).

| Ukuran | Hasil |
|---|---|
| Nomor benar | **30 / 30** |
| Judul benar (Indonesia + Inggris) | **30 / 30** |
| Halaman cetak benar | **30 / 30** (2 diverifikasi lewat folio halaman fisik, karena angkanya terpotong di pita Daftar) |
| `halaman_fisik` memuat keterangan "Gambar X.Y" yang sama | **30 / 30** |

- Satu ketidakcocokan **di sumber**: Tabalong 2026 gambar 7.2 tertulis
  hal. 173 di Daftar, tetapi folio halamannya 222. Parser membaca yang
  tercetak, dan halaman fisiknya benar.
- **Jebakan alat selama penilaian:**
  1. Pencari baris Daftar gagal pada 25/30 sampel, karena nomor gambar
     Dalam Angka berdiri sendiri, sejajar tengah di antara dua baris judul.
     Diperbaiki dengan mencocokkan judul ke baris itu ditambah baris di atas
     dan di bawahnya.
  2. Potongan 45% atas halaman fisik tidak memperlihatkan keterangan gambar,
     yang di Dalam Angka ada di bawah grafik. Diganti halaman penuh.

## Pemuatan ke produksi (disetujui pemilik project, 12 Nov 2026)
Hanya ke-30 publikasi terdampak, lewat jalur pemuatan yang sama
(`muat_produksi.py`).
- Isinya sama dengan pemuat salinan, kecuali pengamannya: hanya mau jalan
  ke `db_pencarian_bps` dengan flag `--produksi-disetujui`. Diuji: tanpa
  flag, DITOLAK.
- Waktu: 10.17-10.43.

| Pemeriksaan | Hasil |
|---|---|
| Cadangan baru sebelum memuat | `C:/Users/Dani/cadangan-bps/db_pencarian_bps-20261112-1017-sebelum-muat-batas-heading.sql`, 8,0 MB, SHA-256 `8f31fee7...95922`; 6 `CREATE TABLE`, diakhiri "Dump completed", tanpa `USE` |
| Produksi vs salinan `db_uji_batas_heading` | 30 publikasi terdampak: **identik** (seluruh isi publikasi). Seluruh potret produksi = potret salinan |
| 276 publikasi lain | **identik** dengan potret sebelum |
| `versi_data` | 315 → **345** (+30) |
| Aplikasi yang SUDAH BERJALAN sebelum pemuatan (server uji dengan korpus lama di memori) | pencarian pertama sesudah pemuatan 817 ms (korpus dimuat ulang; sebelumnya ±16 ms). Gambar baru ditemukan, diperiksa per kartu: "peta wilayah barito kuala" → Gambar 1.1 kedua edisi, PDF hal. 56; "angka melek aksara" → Gambar 4.2 provinsi kedua edisi, PDF hal. 227; "jumlah rumah makan tabalong" → Gambar 7.1/7.2, PDF hal. 257/258. Sebelum pemuatan ketiganya tidak ada |
| Baseline baru | `potret-306-sesudah-batas-heading.json`, 306 publikasi, 23.948 entri, SHA-256 `81f3effdbb222d06256149b849a66dda1ce7bbd6e1940e24454d07fae2228def` |

**Jebakan alat saat menguji pencarian:**
1. Fitur sorot membungkus kata kunci dengan `<mark>`, sehingga `grep` judul
   di HTML selalu 0. Diperiksa dengan kontrol (judul yang pasti ada), lalu
   tag dibuang dulu.
2. `grep -A` mengambil tautan PDF milik kartu berikutnya. Diganti
   pemeriksaan per `<article>`.

Database salinan `db_uji_batas_heading` disimpan dulu, dan dihapus hanya
sesudah konfirmasi pemilik project.
