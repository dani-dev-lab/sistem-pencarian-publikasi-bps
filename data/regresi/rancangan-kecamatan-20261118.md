# Rancangan: perbaikan parser Daftar untuk 3 kelompok cacat kecamatan (18 Nov 2026)

STATUS: RANCANGAN, menunggu persetujuan pemilik project. Kode belum diubah.
Latar: `kecamatan-mutu-20261118.md` (sampel 20/30).
Alat bukti: `rancangan-kecamatan-20261118/diagnosa_daftar.py <pid> [hal]`. Alat ini
hanya membaca PDF dan mencetak baris `_kelompokkan_baris`, dengan `[x0-x1]` per kata
dan mode yang dipilih parser.

Temuan utama: **pola 2 dan pola 3 berakar sama.** Pada kedua pola, dot leader
tercetak menimpa kolom nomor halaman, sehingga digit nomor halaman bercampur
dengan titik leader. Pola 3 (blok tanpa nomor) adalah akibatnya: nomor halaman
tidak dikenali, sehingga mode nomor-sebaris tidak aktif. Bedanya di bentuk
katanya, jadi tetap dua commit.

## Pola 1: Tanah Laut 2025, nomor tabel berspasi

**Bukti** (Bumi Makmur 2025 `eb93beef`, hal. 13; mode `sebaris=(True, 91)`):
```
[57-70]2.1.  [73-77]1  [91-119]Jumlah  [121-146]Rukun ...
[57-63]1.    [66-71]2  [91-111]Jarak ...
```
pdfplumber memotong nomor menjadi dua kata, dengan celah 3 pt. Di
`_parse_baris_nomor_sebaris`, sebuah baris dianggap bernomor hanya kalau kata ke-2
diawali huruf. Kata ke-2 di sini "1", jadi baris itu dianggap "kolom kiri tanpa
nomor": entri ditutup dan barisnya dibuang. Akibatnya hanya 4 entri tabel jalur
daftar per publikasi yang tersisa (judul seksi). Tabel lain hanya masuk lewat
jalur badan, tanpa halaman cetak (593 entri badan).

**Perubahan:** fungsi baru `_gabung_nomor_terbelah(baris)`, dipanggil di
`_baca_daftar` sesudah `_kelompokkan_baris`. Fungsi ini menggabungkan dua kata
pertama baris menjadi satu ("2.1." + "1" -> "2.1.1"), hanya kalau SEMUA syarat
ini terpenuhi:
- kata 1 cocok `^\d+(\.\d+)*\.$`, yaitu nomor yang diakhiri titik;
- kata 2 cocok `^\d{1,2}$`;
- celah kata 1 ke kata 2 <= 4 pt;
- kata 3 ada dan diawali huruf.

**Risiko ke format lain:**
- Baris Daftar yang memang diawali "N." lalu angka 1-2 digit yang terpisah lalu
  judul sekarang dibaca sebagai satu nomor. Contohnya daftar bernomor "1." yang
  judulnya diawali angka ("1. 10 Desa Terluas").
- Hanya halaman Daftar yang terkena (bukan badan, bukan `lengkapi_halaman_fisik`).
- Mode deteksi (`_mode_nomor_sebaris`) bisa aktif di halaman yang dulu tidak aktif.
  Regresi akan menunjukkannya.

## Pola 2: Banjar 2026, nomor halaman = kata tersendiri yang ditimpa leader

**Bukti** (Martapura Barat 2026 `7dd02f9e`, hal. 13; Aluh-Aluh 2026
`c19781f8`, hal. 13):
```
[198-368].........................  [367-376]3..5.
[225-368].........................  [367-376]6.2
[242-367].........................  [367-376].7..0.
```
x1 leader (368) melewati x0 nomor halaman (367): titik leader masuk ke kata nomor
halaman. `_pisah_nomor_halaman` menolak "3..5." dan "6.2", sehingga halaman cetak
kosong. Lalu `_bersihkan_judul` mengubah "3..5." menjadi "3 5", dan itu menempel
ke judul (627 judul di Banjar 2026). Kalau baris halaman yang bersih (33, 66, 69)
cukup banyak, mode sebaris tetap aktif. Karena itu nomor entri benar, hanya
halaman dan judulnya yang rusak.

**Perubahan:** fungsi baru `_rapikan_nomor_halaman(baris)`, juga dipanggil di
`_baca_daftar`. Teks kata terakhir W diganti dengan digitnya saja ("3..5." ->
"35") kalau SEMUA syarat ini terpenuhi:
- W hanya berisi digit dan `.…�`, dengan 1-3 digit;
- ada minimal satu titik SESUDAH digit pertama. Bentuk lain sudah ditangani:
  "....54" oleh `strip`, "33" memang bersih;
- kata sebelumnya P adalah leader (memuat >= 3 titik berturut);
- **P menimpa W: P.x1 >= W.x0 - 0,5.** Celah normal leader ke nomor halaman di
  korpus ±2 pt (364 -> 366).

Sesudah itu, semua jalur di hilir (`_batas_kanan`, deteksi mode, `_rakit_entri`)
melihat "35" yang bersih. Fungsi-fungsi itu tidak diubah.

**Risiko:**
- Satu-satunya salah tafsir yang mungkin: angka desimal sungguhan di ujung kanan
  baris Daftar ("... 3.4"), DITIMPA leader. Syarat tumpang tindih membuat ini
  hampir mustahil.
- Nomor bab yang salah cetak di sumber ("1.1" untuk 7.1, Aluh-Aluh) dan nomor
  halaman yang melayang di tengah baris ("[145-154]63") TIDAK diperbaiki. Itu
  kesalahan sumber.

## Pola 3: Balangan 2025, digit di DALAM kata leader -> blok tanpa nomor

**Bukti** (Tebing Tinggi 2025 `515f59aa`, hal. 15; mode
`sebaris=(False, None)`; Tebing Tinggi 2026 `fe50dcfe`, hal. 16 sama):
```
[331-377]................4..2..
[308-378]............................4..3..  [378-381].
[209-363]..........................................5.8
```
Digit nomor halaman menjadi bagian kata leader itu sendiri, kadang diikuti kata
"." sendirian. Tidak ada baris yang dikenali berakhir nomor halaman, sehingga
`_mode_nomor_sebaris` gagal di syarat 4 (>= 3 baris berhalaman). Parser lalu jatuh
ke jalur berlabel: tanpa label, entri dipotong per 8 baris menjadi blok gabungan
tanpa nomor (54 di Balangan 2025, 12 di Balangan 2026).

**Perubahan:** perluasan `_rapikan_nomor_halaman` (commit terpisah dari pola 2):
- W boleh diawali >= 3 karakter leader, lalu digit dan titik bercampur
  ("....4..2.." -> "42"), dengan syarat 1-3 digit dan ada titik sesudah digit
  pertama;
- kata terakhir yang hanya berisi titik dan berdiri di kanan W dibuang, HANYA
  kalau W memenuhi syarat di atas.

Sesudah halaman dikenali, mode nomor-sebaris aktif (sudah terbukti di Balangan
2026 hal. 16, di mana baris "59", "65" bersih membuatnya aktif). Entri dibuka per
nomor. Halaman yang dicetak dua kali (Indonesia + Inggris) sudah ditangani `tutup()`.

**Risiko:**
- "....3.4" (leader menempel ke angka desimal dalam SATU kata) akan dibaca 34.
  Di halaman Daftar, kata itu selalu nomor halaman; nomor entri ada di kiri.
- Daftar Isi Balangan yang folio romawinya juga bercampur titik
  ("v i.i.i.", "x i.") TIDAK tercakup: 4 entri isi gabungan per publikasi
  tetap ada.

## Rencana uji

1. **Uji kering, 38 publikasi terdampak** (11 Tanah Laut 2025, 20 Banjar 2026,
   7 Balangan 2025), satu proses, tanpa DB, sesudah tiap commit pola.
   - Pembanding = isi database uji sekarang.
   - Alat diuji dulu: 2 publikasi diekstrak dengan kode LAMA harus identik per
     kunci dengan database uji.
   - Dibandingkan per kunci `(tipe, nomor)`, bukan per posisi. Dilaporkan: kunci
     hilang (harus 0), kunci baru, halaman cetak terisi, judul berubah, dan blok
     tanpa nomor.
2. **Sesudah OCR selesai: regresi penuh di database uji.**
   - 306 publikasi produksi yang ada di database uji: `perbarui.py --db-uji
     --lokal --paksa` (OCR dari cache).
   - IPM HSU (`a21060d6`, hanya di produksi): ekstraksi kering.
   - 312 kecamatan: pemuat terarah ke database uji, karena `--kecamatan` ditolak
     bersama `--paksa`.
   - Potret per kunci sebelum/sesudah.
   - Syarat: 0 kunci bernomor hilang di 307 publikasi produksi. Setiap perubahan
     di sana harus bisa ditunjuk ke pola 1/2/3 lewat kata yang dirapikan; satu
     saja tidak terjelaskan = berhenti dan lapor.
3. **Sampel manual 30 entri baru/berubah** dari 38 publikasi (seed tetap):
   nomor, judul, halaman cetak, tombol PDF.
4. **`uji_pipeline.py` bagian I:** kasus sintetis baru, minimal:
   - pola 1: "2.1." + "1" bergabung; "1." + "10" + judul angka tetap terpisah
     kalau celahnya > 4 pt;
   - pola 2: "3..5." yang ditimpa leader -> 35; "3.4" TANPA tumpang tindih
     tidak berubah;
   - pola 3: "....4..2.." + "." -> 42, dan halaman blok mode sebaris
     menghasilkan entri bernomor.
5. **Commit:** satu per pola (1, 2, 3), lalu satu commit untuk uji bagian I.
   Tanpa push. Produksi tidak disentuh.

## Di luar cakupan (dicatat)
- Folio romawi Daftar Isi yang bercampur titik (Balangan).
- Nomor bab salah cetak dan nomor halaman melayang (Banjar 2026, sumber).
- Perkiraan halaman yang salah untuk entri kepala bab "1 Geografi" (sampel #29).
- Balangan 2026 (8 publikasi) dan Banjar 2025 (17) tampaknya ikut membaik
  (mekanismenya sama, terlihat di Tebing Tinggi 2026). Hasilnya akan terlihat di
  regresi penuh, bukan di uji kering 38.
