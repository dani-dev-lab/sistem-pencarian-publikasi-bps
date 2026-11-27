# Perbaikan parser Daftar: pola C, A2, A1, A', B (16 Nov 2026)

Database uji saja. Produksi tidak disentuh (CHECKSUM `publikasi`,
`entri_dokumen`, `log_pencarian`, `versi_data` sama sebelum dan sesudah).
Belum di-push. Rancangan disetujui pemilik project; laporan pemicunya ada di
`perkiraan-halaman-isi-20261116.md` (butir 2).

## Perubahan (satu commit per pola)

| Commit | Pola | Mekanisme yang dibuktikan | Perubahan |
|---|---|---|---|
| `c0ca28a` | **C** kop "Halaman"/"Page" | Jalur normal hanya melewati "HALAMAN"/"HAL". "Lampiran … Halaman" diawali label, sehingga jadi entri tanpa nomor berjudul "Halaman"; "Page" menempel ke judul berikutnya. | Kata baris kop dibuang dari JUDUL di `_rakit_entri` (`_kop_halaman`). Batas entri, label, dan nomor tidak berubah. Entri yang judulnya habis dibuang. |
| `a7a62ce` | **A2** kata+leader+nomor | Balangan: kata terakhir `REVIEW.....39` satu kata, tidak dikenali, sehingga BAB 3 menelan 3.1. | `_pisah_nomor_halaman` mengenali teks + >= 3 karakter leader + angka (romawi untuk isi). Tahun 4 digit bukan halaman. |
| `3b2d835` | **A1** folio sebaris | Balangan: folio "vii" (x1=573) sebaris dengan "...35" (x1=524). | `_folio_sebaris`: romawi HURUF KECIL di ujung, didahului nomor arab di margin kanan, maka nomor arab dipakai. |
| `3107579` | **A'** batas kanan | GEM: kata terjauh x1=488, batas 390, kolom nomor 386-387, sehingga seluruh Daftar Isi jadi 3-4 gumpalan. | `_batas_kanan` turun (tidak pernah naik) ke kolom nomor halaman kalau >= 3 baris sejajar (<= 4 pt) di 40% kanan. |
| `b109b5e` | **B** nomor di baris pertama | Kotabaru: "3.6 ... Change in ... 69" lalu "Inventory" tanpa nomor, sehingga "Inventory 3.7 ...". | `_lanjutan_judul`: baris tanpa nomor, sejajar kolom teks judul yang menjorok, sesudah entri yang ditutup oleh nomor di baris pembukanya, ditempel ke entri SEBELUMNYA. Penjaga lihat-depan: baris berikutnya bukan baris sejajar bernomor yang bukan awal entri. |
| `89ff6fa` | uji | | `uji_pipeline.py` bagian I: 9 kasus sintetis. 7 kasus cacat mereproduksi gejala aslinya di parser lama (`f66559e`); 2 kasus penjaga lulus di keduanya. |

### Yang berubah dari rancangan karena uji kering

- **C versi pertama** melewati baris kop di `_parse_baris`. Akibatnya **kunci
  bernomor hilang** di Banjarmasin Dalam Angka (gambar 13.2, tabel 13.1.4)
  dan Podes Tanah Laut (lampiran 1). Di Dalam Angka, label pada kop
  "Gambar ... Halaman" adalah satu-satunya label yang membuka entri pertama.
  Diganti: kop hanya dibuang dari judul.
- **B versi pertama** baru memperbaiki sebagian, karena kegagalannya
  berantai:
  - penjaga lihat-depan menolak "DATA SOURCE": subbab "2.1 ... 17" menjorok
    tepat ke kolom teks judul bab;
  - satu lanjutan yang gagal membuat entri berikutnya dua baris, sehingga
    syarat "entri satu baris" gugur untuk sisanya.

  Diperbaiki: lihat-depan mengecualikan awal entri, dan rantai juga
  berlanjut kalau baris penutup adalah awal entri.
- **A1 diterapkan ke semua tipe**, bukan hanya isi. Uji kering menemukan
  folio sebaris juga di Daftar Tabel (GEM: penanda "v" di tepi, sebaris
  dengan "1 PDRB ... 2").

### Jebakan alat selama pengerjaan (dicatat sesuai prinsip verifikasi)

- **`grep -B30` mengaitkan perubahan ke publikasi yang salah**, sehingga
  "856e507e tabel 1 berubah" disangka tak terjelaskan. Atribusi dengan awk
  per blok `###` menunjukkan publikasinya 49c5df1b, 8b097d58, dan a44895e1.
- **Alat baris Daftar mencocokkan "4.17 Jasa Lainnya" ke baris "2.17 Jasa
  Lainnya"** (judul sama di dua bab). Diperbaiki: baris harus diawali nomor
  subbab yang sama.

## Regresi penuh

`perbarui.py --db-uji --lokal --paksa`, 306 PDF:
- 10.39-11.54, status sukses, 306 diproses, 0 gagal;
- OCR dari cache.

Pembanding: potret sebelum/sesudah. Tabel/gambar/lampiran bernomor per kunci
`(tipe, nomor)`; entri tanpa nomor sebagai multiset `(tipe, judul,
halaman)`. Ditambah uji kekekalan kata: kata di entri baru harus berasal dari
entri lama publikasi yang sama; yang boleh hilang hanya angka, romawi, dan
kata kop.

| Ukuran | Hasil |
|---|---|
| **Kunci bernomor hilang** | **0** |
| Publikasi berubah | 138 dari 306 |
| Kunci bernomor baru | 11 (pemisahan A2, misalnya tabel 3.8/3.9, lampiran 2/6, tabel 4.2.4/4.2.14 Dalam Angka) |
| Kunci bernomor berubah | 147, di antaranya 110 halaman cetak |
| Entri tanpa nomor hilang / baru | 451 / 482 |
| - entri sampah kop yang terbuang (C) | 103 |
| Publikasi yang gagal uji kekekalan kata | 22, semuanya dibaca (di bawah) |

**22 publikasi yang dibaca: semuanya terjelaskan.**
- GEM dan IPM: kop publikasi di halaman Daftar Isi tidak lagi jadi entri
  (A'); tabel 1 hal. 2 (A1).
- Angka "baru muncul": halaman kosong yang kini terisi (A2). Judul lama
  berasal dari jalur badan, jadi angkanya tidak tampak di judul.
- Nomor subbab "hilang" ("3.8", "3.5", "4.2.14", "4.2.4"): kini menjadi kunci
  sendiri (pemisahan A2).
- Tanda baca: Banjarmasin tabel 4.2 berasal dari teks yang memang rusak di
  sumber.

**110 halaman cetak bernomor yang berubah**, diuji dengan selisih
fisik - cetak terhadap modus publikasinya (dari entri yang tidak berubah):
- 99 dari kosong menjadi angka dan konsisten;
- 6 dari angka ke angka dan konsisten;
- 5 sisanya dibaca:
  - Tanah Bumbu Kesra tabel 4.1/5.1: tabel +20, lampiran +21, dua selisih
    dalam satu publikasi;
  - Banjarbaru tabel 3.7: 58 -> 56, pemisahan 3.7/3.8. Judul lama memuat
    "... 2021–2025 **56** Perkembangan ... Pemerintah";
  - 2 lampiran tanpa halaman fisik.

  Kelimanya angka yang memang tercetak di Daftar.

## Sampel manual (seed 20261116)

Tiap entri dicocokkan dengan baris aslinya di halaman Daftar PDF.

- **Entri baru di 8 publikasi pola B: 30/30 tepat.** Judul utuh termasuk
  semua baris lanjutan ("4.16 ... Social Work" + "Activities"; "IV. ..." + 2
  baris), dan halaman sama dengan angka di baris Daftar.
- **Entri baru di publikasi lain (A2/A1/A'/C): 27/30 tepat, 3 membaik tetapi
  masih cacat lama**:
  - 2 GEM "Kata Pengantar v Daftar Isi": sisa A', romawi sedikit di luar
    kolom;
  - KAK lampiran 1+2 masih satu entri; kop "Halaman Appendices Pages" sudah
    hilang.

  0 entri memburuk.

## Pencarian (12 kueri uji, database uji)

9 identik. 3 berubah, semuanya karena pola dan semuanya membaik:
- **"luas panen padi kotabaru"**: awalan kop "Halaman" hilang (C); skor
  83,5 -> 84,5.
- **"penduduk miskin"**: 3 gumpalan GEM ("3. Ekspor-Impor 19 4. Hotel 25
  ...") keluar (A'), digantikan tabel kemiskinan Balangan/Banjar/Banjarbaru.
- **"statistik ekspor impor"**: Balangan "2.6 Ekspor dan Impor" kini
  hal. 35 (A1).

## Sisa yang diketahui (tidak dikejar)

- **A'**: entri berhalaman romawi atau satu digit yang sedikit keluar kolom
  masih tergabung (GEM "Kata Pengantar v Daftar Isi", "1. PDRB 1 2.
  Inflasi"; IPM "Daftar Tabel ix Daftar Gambar xi 1. ...").
- **Folio di BARIS SENDIRI** yang menempel ke judul ("... 2025 xiv") tidak
  termasuk A1.
- **B lintas halaman**: lanjutan di awal halaman Daftar berikutnya.
- **Indikator Pekerjaan Layak** dan Tabalong Pengeluaran tidak berubah
  (layoutnya berbeda dari syarat B).
- **Nomor tabel KAK** ("84 Penduduk ...") tetap di awal judul (mode
  tanpa-label, cacat lama).

## Uji otomatis

`tests/uji_pipeline.py` lengkap tanpa argumen: lihat CLAUDE.md, titik
berhenti 16 Nov.
