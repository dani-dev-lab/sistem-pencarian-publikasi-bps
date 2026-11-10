# Konteks Project: Sistem Pencarian Publikasi BPS Kalsel

## Ringkasan
Mesin pencari internal untuk petugas Pelayanan Statistik Terpadu (PST) di BPS Provinsi
Kalimantan Selatan. Tujuannya: petugas cukup mengetik kata kunci, sistem menunjukkan
publikasi mana DAN bagian mana (lampiran/tabel/gambar/halaman) yang memuat data tersebut.

Masalah yang dipecahkan: saat ini petugas mencari manual dengan membuka publikasi satu per
satu, atau bertanya ke rekan lewat WhatsApp.

Konteks: project magang/tugas akhir, dikerjakan sendiri, durasi ~10 minggu.
Mahasiswa Politeknik Negeri Banjarmasin.

## Batasan yang sudah disepakati dengan mentor
- **Scope data**: hanya publikasi dengan **tanggal rilis (`rl_date`) tahun 2025-2026**.
  Ini tahun RILIS, bukan tahun data yang dibahas di judul. Sudah dikonfirmasi ke mentor.
- **Deployment**: cukup lokal di laptop selama masa magang. Keputusan deploy ke
  infrastruktur BPS diserahkan ke instansi. Bekal untuk itu (login admin,
  server produksi, .bat, PANDUAN.md) ada di bagian "Persiapan serah terima".
- **Platform**: web app, Python + Flask. MySQL (via Laragon) sebagai database.
- **Cakupan kab/kota (keputusan 9 Nov 2026)**: publikasi "Kecamatan ... Dalam
  Angka" TIDAK ditarik. Alasannya permintaan tim PST: cakupannya 13
  kabupaten/kota, tidak sampai data per kecamatan/desa.
  - Ini PENGATURAN, bukan aturan di kode: daftar pola regex
    `kecualikan_judul` di `data/wilayah.json`, dibaca
    `wilayah.pola_judul_dikecualikan()` dan diterapkan di `perbarui.py`
    sesudah filter tahun.
  - Untuk menarik lagi, ubah `aktif` menjadi false; tidak perlu mengubah kode.
  - Publikasi yang sudah ada di database tidak dihapus oleh pengecualian ini.
  - Format daftar Kecamatan Dalam Angka ("nomor sebaris", C2) tetap
    diperbaiki, karena format yang sama ada di 6 publikasi provinsi.

## Sumber data
- **BPS WebAPI**: `https://webapi.bps.go.id/v1/api/list/model/publication/lang/ind/domain/6300/page/{page}/key/{key}/`
- Domain Kalsel = `6300`. API key disimpan di `.env` sebagai `BPS_API_KEY`.
- Pagination: 10 publikasi per halaman, total ~648 publikasi (~65 halaman) untuk semua tahun.
- Field penting: `pub_id`, `title`, `abstract`, `rl_date`, `pdf` (link unduh), `cover`, `subject_csa`.
- PDF publikasi diunduh dari field `pdf`, lalu diekstrak strukturnya.

### Perilaku unduhan dan daftar WebAPI (diuji 9 Nov 2026)
- **Daftar API terurut dari rl_date terbaru.** Dibuktikan di 14 domain dan
  5.246 publikasi: 0 rl_date naik dalam urutan API, 0 publikasi jendela yang
  terlewat. Pemeriksanya (`sumber_bps.cek_urutan`) diuji dengan urutan yang
  diacak dan menangkapnya.
  - Karena itu pembaruan berhenti begitu satu halaman penuh di luar jendela
    tahun (`DAFTAR_TERURUT_TERBARU = True`): ±82 dari ±530 halaman.
  - `--hanya-periksa` tetap menarik SEMUA halaman dan mencetak buktinya
    setiap kali. Kalau "terlewat" > 0, matikan.
- **URL PDF bertoken dan berganti.** URL dari metadata 5 Nov ditolak HTTP 400
  pada 9 Nov, sedangkan URL segar diterima. Jangan memakai `url_pdf` lama dari
  database untuk mengunduh.
- **Server PDF tidak mendukung Range.** Permintaan sebagian dijawab 200
  berkas penuh, tanpa `Accept-Ranges` maupun `Content-Length` (chunked).
  Unduhan yang putus tidak bisa dilanjutkan.
- **Unduhan putus acak** ("Response ended prematurely"), juga dari Wi-Fi
  rumah: 1 dari 2 percobaan pada uji 9 Nov. Kecepatan yang berhasil
  ±5.360 KB/detik (14,75 MB dalam 3 detik). Pengamannya:
  - `unduh_pdf`: 4 percobaan, jeda 5/15/45 detik, selalu dari nol. HTTP 4xx
    langsung berhenti karena URL kedaluwarsa.
  - `perbarui.putaran_ulang`: di akhir tiap domain, yang tetap gagal dicoba
    sekali lagi dengan URL segar (daftar domain ditarik ulang).
- **Ringkasan pembaruan** (`data/pembaruan_terakhir.json`, untuk revisi 3)
  kini memuat:
  - durasi per tahap;
  - statistik unduhan per domain dan total: byte, detik transfer, KB/detik,
    putus, percobaan ulang, putaran ulang, pulih;
  - `jaringan_dipakai`: SSID dan IP webapi.bps.go.id.
- **Keluaran tiap run disalin ke `data/log_pembaruan/<waktu>.log`**
  (di-gitignore).
- **Selama `perbarui.py` berjalan, Windows dicegah tidur**
  (`SetThreadExecutionState`). Ini tidak mencegah tidur karena layar laptop
  ditutup.

## Kewajiban dari Term of Use BPS (WAJIB dipatuhi)
1. UI harus menampilkan notice: **"Layanan ini menggunakan API Badan Pusat Statistik (BPS)"**
   (taruh di footer `base.html`).
2. API key tidak boleh bocor — selalu di `.env`, `.env` masuk `.gitignore`.
3. Jangan membebani server BPS — beri jeda antar request saat menarik data massal.

## Arsitektur

### Pipeline data (background, terjadwal)
BPS WebAPI → unduh metadata + PDF → ekstraksi struktur dokumen → simpan ke database (terindeks)

### Pipeline pencarian (dipakai petugas)
Keyword → preprocessing → fuzzy matching + scoring → hasil terurut dengan lokasi spesifik

### Ekstraksi struktur PDF
Parsing halaman DAFTAR ISI / DAFTAR TABEL / DAFTAR GAMBAR / DAFTAR LAMPIRAN menjadi entri
terstruktur: `{tipe, nomor, judul, halaman}`. Pakai `pdfplumber`.

Catatan format PDF BPS yang sudah diamati:
- Ada watermark URL (`https://kalsel.bps.go.id`) yang bisa ikut terekstrak sebagai teks — perlu dibersihkan.
- Judul entri sering membungkus ke lebih dari satu baris fisik — perlu digabung.
- Posisi halaman DAFTAR X berbeda-beda tiap publikasi — harus dicari, jangan hardcode.
- Ada publikasi yang menggabung heading, misal "DAFTAR TABEL, GRAFIK, DAN GAMBAR".
- Publikasi sering menulis istilah lengkap + akronim: "Tingkat Penghunian Kamar (TPK)".

### Algoritma pencarian (level yang dipilih: realistis, BUKAN embeddings)
Keputusan sadar: pakai fuzzy matching dulu, bukan semantic embeddings. Embeddings hanya
stretch goal kalau waktu tersisa di akhir.

1. **Preprocessing** (diterapkan ke query DAN ke data saat indexing):
   - lowercase + bersihkan tanda baca
   - stemming Bahasa Indonesia pakai **Sastrawi**
   - normalisasi sinonim ke bentuk kanonik (kamus di `data/kamus_sinonim.json`)
2. **Scoring** — rancangan awalnya dua sinyal (`token_set_ratio` bobot 0,7 +
   coverage bobot 0,3) dengan ambang 80/40. Rancangan itu **sudah diganti**
   setelah diuji terhadap data nyata; yang berlaku sekarang ada di bagian
   "Scoring pencarian — rumus dan ambang" di bawah, lengkap dengan alasan
   penggantiannya. Skor tetap 0-100, ditampilkan sebagai persentase relevansi.

### Kamus sinonim
Struktur kelompok kanonik (bukan pasangan 1-1):
```json
{ "banyaknya": ["banyaknya", "jumlah", "total", "keseluruhan"] }
```
Dibangun dari: ekstraksi akronim otomatis via regex + analisis frekuensi kata dari korpus +
review manual istilah teratas. Disimpan sebagai file JSON dulu (bukan tabel DB) demi kesederhanaan.

Penting: kamus dibangun di level **kata dasar setelah stemming**, bukan kata mentah.

## Temuan dari data aktual (dijalankan Agustus 2026)
- Total publikasi BPS Kalsel semua tahun: 648 (65 halaman @10)
- **Lolos filter rl_date 2025-2026: 72 publikasi** (48 rilis 2025, 24 rilis 2026)
- Semua 72 punya link PDF, abstract, dan issn — tidak ada yang perlu di-skip
- `subject_csa` hanya terisi 29/72 (43 tanpa kategori). Bentuknya ARRAY, bisa
  lebih dari satu per publikasi. Relasi kategori harus opsional dan many-to-many.
  Filter kategori jadi kurang berguna — turunkan prioritasnya.

## Korpus PDF (unduhan + verifikasi, Agustus 2026)
- 72 PDF terunduh lengkap ke `data/publikasi_pdf/` dengan nama `{pub_id}.pdf`,
  total 633 MB, nol kegagalan.
- Verifikasi: 72/72 bisa dibuka pdfplumber, TIDAK ADA PDF hasil scan
  (semua punya layer teks, tidak perlu OCR). Total 10.196 halaman.
- Field `size` dari API TIDAK AKURAT per file (meleset sampai 167%),
  meski agregatnya pas. Jangan pakai untuk verifikasi keutuhan file.
  Pakai penanda `%PDF` di awal + `%%EOF` di akhir — terbukti mendeteksi
  pemotongan 1% sekalipun.

## Temuan spike ekstraksi PDF (5 sampel)
- Heading DAFTAR ISI/TABEL/GAMBAR ada di 5/5; DAFTAR LAMPIRAN hanya 3/5 (opsional!)
- Watermark terekstrak masif (~500 jejak per publikasi) dan MENYUSUP KE DALAM KATA
  (contoh: "Pertaniano", "kKategori"). Pembersihan berbasis regex URL tidak cukup.
- 44% judul entri membungkus ke lebih dari satu baris — penggabungan wajib.
- 1 dari 5 sampel (PDRB) GAGAL TOTAL: layout dua kolom, dot leader berupa glyph
  aneh (U+FFFD), watermark menyisip ke dalam kata.
- Rencana minggu 3-4: pakai ekstraksi berbasis KOORDINAT KATA (pdfplumber
  extract_words dengan posisi x-y), bukan parsing baris teks. Satu strategi yang
  menangani kedua format, bukan dua parser terpisah.

## Hasil akhir ekstraksi 72 publikasi (parser produksi, Agustus 2026)
Parser ada di `app/services/ekstraksi_pdf.py`, berbasis KOORDINAT KATA
(`extract_words`), bukan parsing baris teks. Hasil di `data/hasil_ekstraksi.json`.

- Angka di bagian ini adalah hasil jalur DAFTAR saja (sebelum ekstraksi badan
  ditambahkan). Angka yang berlaku sekarang ada di bagian "Ekstraksi badan
  dokumen" di bawah: 5.927 entri.
- **Total 4.219 entri** dari 72 publikasi; 69 publikasi menghasilkan entri, 0 galat.
- Sebaran: tabel 1.601 (37,9%), isi 1.416 (33,6%), lampiran 669 (15,9%),
  gambar 533 (12,6%).
- **Entri tanpa nomor halaman: 94 dari 4.219 (2,2%)**.
- **Entri non-isi bernomor: 2.347 dari 2.803 (83,7%)**. Entri tipe `isi` memang
  tidak punya nomor (Daftar Isi memuat bab, bukan tabel bernomor) — jangan
  dihitung sebagai kegagalan.
- Waktu proses ~400 detik untuk seluruh korpus.

Format daftar yang ditangani satu parser (jangan dipecah jadi parser terpisah):
1. label + nomor satu baris ("Tabel 1 Judul ..... 7")
2. dua kolom, label dan nomor beda baris (PDRB)
3. nomor halaman di baris pertama, judul menyambung ke bawah
4. tanpa kata label, nomor berdiri sendiri di kolom kiri ("Dalam Angka")
5. tanpa kata label, nomor SEBARIS dengan judul ("1.1 Luas Daerah ... 10";
   Podes, Kesra, IPM, KAK, Gambaran Ekonomi Makro, dll.) - ditambahkan
   9 Nov 2026 (C2, `_mode_nomor_sebaris`)

Watermark dibuang lewat **matriks transformasi karakter** (miring 45 derajat),
bukan regex teks — itu sebabnya "Pertaniano" tidak lagi muncul.

## Scoring pencarian — rumus dan ambang (Agustus 2026)
Ada di `app/services/mesin_pencari.py`. Rumus yang BERLAKU sekarang:

```
skor_dasar = 0,5 * token_set_ratio + 0,2 * token_sort_ratio + 0,3 * coverage
skor_akhir = skor_dasar / (1 + ALPHA * ln(1 + panjang_entri / panjang_kueri))
ALPHA = 0,05
```

**Ambang SEMENTARA: >=75 ditemukan, 50-74 saran, <50 disembunyikan.**
Angka ini diturunkan dari sebaran skor **hanya 8 kueri uji**, dan sebagian kueri
itu dikarang sendiri — BUKAN kueri nyata dari petugas PST. Ambang final
ditentukan ulang setelah uji coba petugas (minggu 9-10) dan setelah
`log_pencarian` terisi kueri sungguhan. Jangan perlakukan 75/50 sebagai final.

### Riwayat kalibrasi (penting untuk laporan TA)
Angka-angka di atas diturunkan dari pengujian, bukan ditebak:

1. **Rumus awal `0,7 * token_set_ratio + 0,3 * coverage` GAGAL.** Kedua sinyal
   jenuh di 100 bersamaan: `token_set_ratio` mengembalikan 100 begitu seluruh
   token kueri terkandung di entri (tak peduli sepanjang apa entrinya), dan
   coverage juga 100 dalam kondisi yang sama. Akibatnya bobot 0,7/0,3 tidak
   berpengaruh sama sekali. Sebaran skor menumpuk di 100 dan zona 80-99 kosong,
   jadi menggeser ambang tidak akan menolong - yang salah rumusnya.
2. **Ditambah `token_sort_ratio`** sebagai sinyal ketiga. Metrik ini
   membandingkan urutan penuh sehingga entri panjang yang kebetulan memuat kata
   kunci ikut turun sendirinya. Bukti: entri gabungan 59 token dapat
   `set=100` tapi `sort=7,7`.
3. **Penalti panjang ALPHA=1 (bentuk rumus awal) TERLALU KERAS.** Penyebutnya
   `panjang_kueri`, sehingga kueri PENDEK justru dihukum paling berat - terbalik
   dari yang diinginkan. Kueri "tpk" (1 token) terhadap entri 11 token (median
   korpus) sudah membagi skor dengan 2,5. Sweep ALPHA 0/0,05/0,15/0,35/1,0
   menunjukkan seluruh hasil tenggelam di bawah ambang begitu ALPHA >= 0,15.
   Diredam ke **0,05** (potongan 9-17% tergantung panjang entri).
4. Setelah perbaikan: puncak skor turun dari 100 ke kisaran 87-90, kejenuhan
   hilang, top-1 kedelapan kueri uji tetap benar, waktu ~70 ms per kueri
   (4.219 entri, jauh di bawah batas 300 ms).
5. **Sesudah 13 kab/kota masuk (10 Nov 2026; 306 publikasi, 23.461 entri):**
   - Rata-rata median 430 ms, terlambat 539 ms. Ini **melewati 300 ms**.
     Data 79 publikasi dalam sesi yang sama: 116 ms.
   - ±70% waktunya adalah mengambil SELURUH korpus dari MySQL di setiap
     kueri (308 ms). Kueri yang hanya menilai 37 entri pun 355 ms.
   - Usulan: simpan korpus di memori proses dan buat ulang sesudah
     pembaruan data. Lihat `data/regresi/tarik-13-domain-20261110.md`.
6. **Korpus di memori proses (10 Nov 2026)**, di `mesin_pencari.korpus()`.
   Laporan: `data/regresi/korpus-memori-20261110.md`.
   - Korpus (entri + publikasi, token, judul publikasi ternormalisasi)
     dimuat sekali.
   - Korpus dimuat ulang kalau penanda `versi_data` berubah atau objek
     kamus berganti (`muat_ulang_kamus` dari halaman admin).
   - **Penanda versi** = tabel satu baris `versi_data`:
     - dinaikkan setiap penulis data DI TRANSAKSI YANG SAMA:
       `simpan_metadata`, `simpan_entri`, `normalisasi_data.jalankan`
       ("Terapkan ke data");
     - dibaca tiap pencarian lewat satu SELECT berkunci primer;
     - berlaku lintas proses (.bat, admin, skrip).
     - `CREATE TABLE` memaksa commit di MySQL, jadi `pastikan_tabel()`
       dipanggil SEBELUM transaksi penulis, tidak di tengahnya.
   - **Aman untuk banyak thread:** korpus baru disiapkan penuh lalu
     referensinya ditukar sekaligus. Objek `Korpus` tidak pernah diubah.
   - **Hasil identik** dengan versi lama untuk 12 kueri uji: seluruh medan,
     urutan, dan jumlah.
   - Angka waktu, waktu muat ulang, dan memori: lihat laporan.
7. **Filter wilayah (10 Nov 2026)**, di `app/services/pencarian_wilayah.py`.
   Laporan: `data/regresi/filter-wilayah-20261110.md`.
   - Dropdown (`?w=6301`) atau deteksi nama/singkatan wilayah dari kueri,
     dicocokkan per KATA UTUH (`wilayah.deteksi`). Hasil deteksi ditandai
     pita "dipasang otomatis" yang bisa dibatalkan (`abaikan`).
   - Parameter `wo` menandai wilayah yang dipasang otomatis. `w == wo`
     berarti petugas tidak memilihnya, jadi deteksi diulang.
   - Kata wilayah yang menjadi filter TIDAK ikut dinilai. Alasannya BUKAN
     "judul tabel kab/kota jarang menyebut wilayahnya": 75,6% tabel justru
     menyebutnya. Alasannya:
     - singkatan tidak pernah tercetak di judul;
     - hasilnya konsisten, apa pun cara wilayah dipilih;
     - di dalam filter, kata wilayah tidak membedakan relevansi.
   - Entri provinsi yang cocok dengan kueri tanpa kata wilayah tampil
     terpisah ("Juga ada di publikasi provinsi", maksimal 10).
   - "Semua wilayah" + kueri tanpa nama wilayah = jalur lama, hasilnya
     identik.
   - `log_pencarian.wilayah_filter` (CHAR(4), nullable) ditambahkan ke DB
     lama oleh `pastikan_kolom()` di awal request.
   - Waktu: tanpa filter +1 ms; dengan filter paling lambat 59 ms.

## Utang teknis: 764 entri terlalu panjang
Ekstraksi kadang menggabungkan BEBERAPA judul tabel menjadi SATU entri. Median
panjang entri 11 token, tapi 764 dari 4.219 entri melebihi 30 token (maksimum
128).

**Dampak: menurunkan presisi pencarian.** Entri gabungan memuat kata kunci dari
beberapa judul sekaligus, sehingga cocok dengan kueri yang sebenarnya tidak
dijawabnya. Bukti konkret - kueri "ekspor batubara":

- Satu-satunya entri di seluruh korpus yang memuat "ekspor" DAN "batubara"
  adalah entri gabungan 59 token yang isinya tiga judul tabel berbeda
  ("...Consumption Expenditure...", "...Nilai Net Ekspor...", "...Harga
  Komoditas Batubara..."). Tidak ada satu pun tabel yang benar-benar membahas
  ekspor batubara.
- Sebelum rumus diperbaiki entri itu berskor 100 dan tampil sebagai "ditemukan".
  Sesudahnya turun ke 69,6 "saran" - tertangani, tapi tetap peringkat 1.

Scoring hanya bisa meredam gejalanya. Perbaikan sebenarnya ada di parser:
memecah blok yang berisi lebih dari satu entri. Ditunda karena MVP lebih
diutamakan; kalau dikerjakan, jalankan ulang `ekstrak_semua.py` lalu
`muat_ke_database.py`.

`muat_ke_database.py` MEMANGGIL normalisasi otomatis di akhir. Dulu keduanya
terpisah dan itu jebakan: pemuatan mengosongkan `teks_ternormalisasi`, sehingga
lupa menjalankan normalisasi membuat pencarian mengembalikan 0 hasil tanpa
penjelasan. `isi_normalisasi.py` tetap bisa dijalankan sendiri - itu yang
dipakai setelah mengedit `data/kamus_sinonim.json` tanpa memuat ulang data.

## Ekstraksi badan dokumen (September 2026)
Sistem semula hanya mengindeks apa yang tercantum di halaman DAFTAR depan,
sehingga tabel yang tidak terdaftar tidak pernah bisa dicari. Masukan mentor:
"Tabel 1.3" di Master File Desa tidak ketemu padahal tabelnya ada di halaman 39.

Sekarang ekstraksi berjalan DUA JALUR lalu digabung:
- **daftar**: halaman DAFTAR depan -> memberi nomor halaman CETAK (kolom `halaman`)
- **badan**: keterangan tabel/gambar di seluruh halaman -> memberi halaman
  FISIK PDF (kolom `halaman_fisik`)

Pembeda keterangan asli dari kalimat prosa yang kebetulan menyebut "Gambar 3":
**GAYA VISUAL** (pasangan fontname + size). Keterangan selalu memakai gaya yang
BERBEDA dari teks badan halaman itu; prosa memakai gaya yang sama. Diuji pada 4
publikasi berlayout berbeda.

Hasil: **4.219 -> 5.975 entri (+42%)**, publikasi 0 entri **3 -> 0**.
Sumber: daftar 3.063, badan 1.522, keduanya 1.390. Punya `halaman_fisik`: 2.912.
Per tipe: tabel 2.774, isi 1.416, gambar 1.095, lampiran 690.
Waktu ekstraksi penuh ~23 menit (10.196 halaman).

Label keterangan yang dikenali: **Tabel, Gambar, Grafik, Lampiran**. Disurvei
pada 12 publikasi - tabel 256x, gambar 187x, lampiran 182x. "Diagram", "Peta",
"Boks", "Bagan", "Appendix" NOL kemunculan, sengaja tidak ditambahkan.
"Table"/"Figure" juga tidak: satu-satunya kemunculan adalah kop kolom dwibahasa
("Table 2022-2025"), bukan keterangan.

### Penanda gaya: font, ukuran, DAN warna - dihitung TERPISAH
Sebagian publikasi menulis keterangan dengan font dan ukuran SAMA PERSIS dengan
teks badan, hanya warnanya berbeda. Contoh: "Lampiran 1 Formula Perhitungan
Indeks Williamson" berwarna oranye `(0.976, 0.416, 0.106)` di atas badan hitam
`(0.0,)`. Tanpa warna, keterangan itu disangka prosa dan dibuang - menambahkan
"Lampiran" ke regex saja TIDAK cukup.

**Jebakan yang sudah pernah terjadi - jangan diulang:** menggabungkan warna ke
dalam SATU penanda gaya `(font, size, warna)` lalu mencari gaya dominan dari
gabungan itu justru MENGHILANGKAN entri yang sah. Sebabnya halus: baris data
tabel sering memuat beberapa warna sekaligus, sehingga hitungan gaya badan
terpecah-pecah dan gaya KETERANGAN naik menjadi yang paling banyak di halaman
itu - lalu keterangannya sendiri disangka teks badan. Terbukti menghilangkan
"Tabel 54 Nilai Tukar Usaha Rumah Tangga Pertanian".

**Aturan yang berlaku (superset dari aturan lama):** hitung `(font, size)` dan
warna secara TERPISAH, lalu terima keterangan kalau **font/ukuran berbeda ATAU
warna berbeda** dari teks badan. Karena syarat ini superset dari aturan lama
(yang hanya memeriksa font/ukuran), tidak ada keterangan yang tadinya diterima
bisa jadi tertolak. Itulah sebabnya penambahan lampiran + warna menghasilkan
**0 publikasi berkurang**.

**Bunyi aturan sejak 7 Nov 2026: superset terhadap KETERANGAN ASLI;
tangkapan dari halaman Daftar boleh dibuang asalkan tidak ada
`(publikasi, tipe, nomor)` yang hilang.** Pertahankan sifat ini kalau jalur
badan diubah lagi. Pengecualian ini diputuskan pemilik project setelah
penyelidikan B (`data/regresi/penyelidikan-B-20261106.md`). Alasannya:
aturan superset ada supaya keterangan asli tidak hilang, sedangkan baris di
halaman DAFTAR bukan keterangan asli. Baris daftar yang dicetak tebal atau
berwarna lolos aturan gaya, dan akibatnya:
- 13 `halaman_fisik` menunjuk halaman Daftar;
- 43 judul membawa nomor halaman daftar ("... 2021−2024 26").

**Pengecualian kedua, sejak 9 Nov 2026: teks yang TIDAK TERLIHAT pembaca
bukan keterangan asli.** Diputuskan pemilik project setelah C2
(`data/regresi/C2-nomor-sebaris-20261109.md`, `tak-terlihat-20261109.md`).
- Kasusnya: tiga KAK (Feb 2025, Feb 2026, Agt 2025) menyimpan salinan
  keterangan 5 pt berwarna PUTIH di bawah judul tabel. Di dua di antaranya
  nomornya beda dari yang terlihat (sisa edisi sebelumnya). Jalur badan
  dulu menerimanya, sehingga entri menunjuk tabel yang salah.
- Aturannya: `ekstrak_badan` menolak keterangan bila ukuran labelnya
  **< 0,7 × ukuran teks badan halaman** (ukuran gaya dominan), hanya kalau
  halaman itu punya minimal 20 kata berukuran dominan.
- Ambangnya RELATIF, bukan angka mati, atas syarat pemilik project:
  - Lampiran IHK yang dicetak 6 pt di halaman berbadan 6 pt (rasio 1,0)
    adalah keterangan asli dan terlihat;
  - publikasi kab/kota berhuruf kecil tidak boleh terpotong.
- Angka 0,7 jatuh di celah data: keterangan asli terkecil berasio 0,772,
  salinan tersembunyi paling besar 0,63.
- Syarat 20 kata ada karena halaman pembatas Lampiran yang berisi 5 kata
  dekoratif 37 pt tidak punya "ukuran badan". Folio 7 pt di halaman itu
  (rasio 0,19) tidak ikut terbuang.
- Bukti 9 Nov 2026: semua yang terbuang (322, di 79 PDF + 6 sampel kab/kota)
  diperiksa satu per satu. Hasilnya: semuanya berwarna putih, tidak ada yang
  digambar di atas bidang berwarna, dan render pikselnya kosong. **0
  keterangan terlihat terbuang.**
- Jebakan alat yang terjadi saat pembuktian, dan jangan diulang: salinan
  tersembunyi di KAK Feb 2025 berteks PERSIS sama dengan keterangan
  terlihatnya. Pemeriksa yang mencari baris menurut teks saja menemukan
  baris 12 pt di atasnya dan melaporkan 108 "terlihat". Cocokkan menurut
  teks DAN ukuran.

Halaman Daftar kini dilewati `ekstrak_badan` lewat `_halaman_daftar()`,
pemeriksaan yang sama dengan `lengkapi_halaman_fisik`. Perubahan ini
dipasangkan dengan perbaikan `_baca_daftar` (heading yang sama yang diulang
di halaman lanjutan tidak lagi mengakhiri daftar). Dengan begitu entri yang
dulu hanya didapat dari halaman Daftar kembali lewat jalur daftar.

### Halaman Daftar = heading DAFTAR atau lanjutan langsungnya (7 Nov 2026)
`_halaman_daftar(teks_baris, lanjutan_daftar)` dipakai `ekstrak_badan` dan
`lengkapi_halaman_fisik`. Halaman dianggap halaman Daftar kalau:
- punya heading DAFTAR di 6 baris teratas, termasuk heading yang terbelah
  dua baris ("DAFTAR" / "GAMBAR", hanya di Statistik Daerah 2025), ATAU
- dot leader > 3 DAN halaman fisik sebelumnya juga halaman Daftar.
  Halaman tanpa teks memutus rangkaian. Ambang ">3" tidak diubah.

Dulu dot leader > 3 di mana saja sudah cukup. Akibatnya halaman pembuka bab
Dalam Angka (daftar isi mini ber-dot-leader) ikut dilewati, sehingga judul
babnya tidak pernah terbaca. Di 79 publikasi, 76 halaman berganti status:
- pembuka bab Dalam Angka 2025/2026, Kata Pengantar, Statistik Kunci;
- halaman konsep Sakernas;
- kuesioner lampiran Podes.

Regresi: **0 entri berubah** (halaman-halaman itu tidak memuat keterangan
"Tabel N"); dampaknya baru muncul lewat halaman fisik entri isi.

Yang diketahui TIDAK tertangani:
- Daftar Isi tanpa heading sama sekali (Gambaran Ekonomi Makro, `6fc864b9`
  hal. 9) tidak dianggap halaman Daftar. Saat ini tidak berdampak, karena
  halaman itu tidak memuat label "Tabel N" dan publikasinya tidak punya
  entri isi.
- `cari_heading` (jalur daftar) BELUM mengenali heading terbelah, sehingga
  Daftar Gambar/Lampiran Statistik Daerah 2025 tidak dibaca jalur daftar
  (gambarnya tetap masuk lewat jalur badan).
- ~~Lanjutan Daftar ber-leader "……" (elipsis U+2026) tidak terhitung~~
  **DIPERBAIKI 10 Nov 2026:** `_jumlah_dot_leader` kini menghitung deret
  ≥3 "…" selain ".....". Syarat lanjutan dan ambang >3 tetap.
  - Regresi 306 PDF: 0 kunci hilang; 39 `halaman_fisik` berubah, dan
    semuanya dulu menunjuk halaman Daftar (dibuktikan per entri).
  - 23 kini menunjuk keterangan bernomor persis; 16 kosong karena di luar
    halaman Daftar tidak ada keterangannya (sumber keduanya -> daftar).

### Halaman fisik entri `isi` (7 Nov 2026)
`lengkapi_halaman_isi()` mencari judul bab/subbab di badan dokumen. Kondisinya:
- teksnya SAMA UTUH dengan judul entri setelah dinormalisasi, boleh gabungan
  1-3 baris;
- baris pertamanya bergaya beda dari badan, memakai aturan `_beda_dari_badan`
  yang sama dengan jalur badan;
- cadangan: judul tanpa nomor bab.

Kalau kecocokannya lebih dari satu (kop berjalan), yang dipilih adalah yang
pertama di atau sesudah halaman entri isi sebelumnya. Baris halaman diambil
dari pemindaian `ekstrak_badan` (parameter `baris_halaman`), jadi PDF tidak
dibaca ulang; waktu ekstraksi tidak bertambah terukur.

Hasil di 79 publikasi:
- **916 dari 1.562 entri isi (59%)** terisi.
- Regresi: hanya `halaman_fisik` entri isi yang berubah; 0 kunci hilang,
  0 sumber berubah.
- Sampel acak 40 (seed 20261107) dibaca satu per satu: **39 benar,
  1 meleset 2 halaman**. Pada yang meleset, terpilih sampul bab, sedangkan
  Daftar Isi menunjuk halaman isi pertama sesudahnya.
- Penyebab utama tidak terisi:
  - judul dwibahasa "Indonesia/ Inggris" di Daftar Isi yang di badan
    tercetak di dua kolom terpisah (PDRB Lapangan Usaha: 0/52 dan 2/51);
  - entri halaman depan yang ada di halaman Daftar sendiri.

### Dalam Angka: label bertumpuk dan kepala seksi (9 Nov 2026)
Penyelidikan lengkapnya ada di `data/regresi/penyelidikan-C-20261107.md`.
Masing-masing langkah punya laporan, baseline, dan TSV perubahan sendiri.
- **C1(a) label bertumpuk.** Keterangan Dalam Angka menumpuk "Tabel" /
  "1.1.1" / "Table" di kolom kiri, sejajar dengan judul. Penanda
  "tabel 1.1.1" karena itu tidak pernah satu baris.
  - `_penanda_bertumpuk` di `lengkapi_halaman_fisik` mengenalinya.
  - Hasil: +637 `halaman_fisik` (Dalam Angka 2025/2026 hampir semua
    tabelnya); sampel 30: 30 benar.
  - Inilah penyebab "631 Dalam Angka tanpa halaman_fisik" yang lama,
    BUKAN halaman pembuka bab.
- **C3 kepala seksi.** Padanan Inggris kepala seksi tercetak di kolom judul
  Daftar Tabel lalu menempel ke entri pertama seksi.
  - Sekarang dibuang di mode tanpa-label: baris kapital semua saat buffer
    entri kosong.
  - Hasil: 62 awalan dibuang di Dalam Angka 2025/2026, 0 kunci bernomor
    hilang, publikasi lain identik.
- **C2 format daftar kelima "nomor sebaris"** (`_mode_nomor_sebaris`,
  `_parse_baris_nomor_sebaris`).
  - Dikurung seketat mode tanpa-label: tidak boleh ada baris berlabel,
    minimal 3 baris bernomor sejajar kolom judul, minimal 3 baris berakhir
    nomor halaman. Syarat terakhir mencegah halaman badan berisi daftar
    prosa bernomor ikut terbaca.
  - Entri dibuka dan ditutup oleh baris bernomor, bukan oleh nomor halaman,
    karena sebagian publikasi mencetak nomor halaman dua kali.
  - Hasil: 18 publikasi; 424 blok gabungan diganti 341 entri bernomor
    berhalaman; 781 halaman cetak didapat; 0 kunci bernomor hilang.
  - Dimuat SESUDAH penolakan keterangan tak terlihat. Tanpa itu, di dua KAK
    halaman fisik akan menempel ke judul yang salah.
  - Laporan: `data/regresi/C2-nomor-sebaris-20261109.md`.
  - Cacat kecil yang diketahui:
    - angka indeks di ujung judul terbaca sebagai halaman (GEM tabel 41);
    - nomor "13" yang terbelah di Daftar Air Bersih;
    - judul seksi di akhir halaman (Kecamatan Dalam Angka).
- **C1(b), keterangan bertumpuk sebagai entri BARU di jalur badan:
  DITUNDA (keputusan 9 Nov 2026), saran pengembangan.** Rinciannya di
  `data/regresi/C1b-perkiraan-20261109.md`.
  - **KOREKSI 10 Nov 2026:** alasan "Dalam Angka tidak punya Daftar Gambar"
    di bawah ini SALAH. Dalam Angka punya Daftar Gambar di hal. 27-49, dan
    terlewat karena `BATAS_HALAMAN_CARI = 25`. Lihat
    `data/regresi/batas-heading-20261110.md`.
  - Manfaat: sekitar 55 grafik Dalam Angka provinsi ("Gambar" / "1.1" /
    "Figure" di halaman infografis bab) ditambah sekitar 5 per Dalam Angka
    kab/kota. Semuanya kini tidak terindeks, karena Dalam Angka tidak punya
    Daftar Gambar.
  - Risiko sedang-tinggi: aturan judul terpanjang bisa mengganti ratusan
    judul tabel Dalam Angka yang kini bersih dengan rekonstruksi badan.
  - Perkiraan waktu: 4-5 jam.
  - Cara meredam bila dikerjakan: versi "hanya menambah kunci yang belum
    ada", tanpa menyentuh entri yang sudah dikenal Daftar. Paling hemat
    dikerjakan bersamaan dengan ekstraksi ulang sesudah penarikan 13 domain.

Dedup memakai kunci `(tipe, nomor)` per publikasi. Kalau judulnya berbeda,
yang dipakai judul yang LEBIH PANJANG (`_gabung`: versi badan menggantikan
versi daftar hanya bila lebih panjang), bukan selalu versi badan. Alasan
awalnya: versi daftar kadang terpotong. Efek sampingnya: versi yang membawa
sampah (nomor halaman, kop tabel) juga lebih panjang, jadi aturan ini ikut
memenangkannya.

Kolom `sumber` bernilai 'daftar' | 'badan' | 'keduanya'.

`#page=` di tombol PDF memakai `halaman_fisik`, BUKAN `halaman`. Dulu fitur ini
dilewati karena selisih halaman cetak vs fisik terbukti tidak konsisten (5 dari
8 publikasi foliony tidak terbaca, sisanya selisihnya berubah-ubah di dalam satu
publikasi). Sekarang akurat tanpa tebakan karena halaman fisik dicatat langsung
saat ekstraksi.

## Prinsip verifikasi (dipelajari dari tiga kesalahan nyata)
**Alat verifikasi juga bisa salah, dan salahnya LEBIH BERBAHAYA daripada bug
biasa - karena kita mempercayainya dan berhenti memeriksa.** Sudah tiga kali
hampir menyesatkan kesimpulan di project ini:

1. **Audit heuristik melaporkan 0% deteksi palsu, padahal 2,5%.** Heuristiknya
   hanya mencari kata prosa ("di bawah ini", "menunjukkan"), sementara cacat
   yang sebenarnya berbentuk judul terpotong dan label sumbu grafik yang ikut
   terbaca. Ketahuan hanya setelah membaca sampel acak satu per satu.
2. **Pemeriksa halaman menampilkan baris yang SALAH.** Saat memverifikasi
   `halaman_fisik`, alatnya menampilkan baris PERTAMA yang memuat "Gambar 3.1"
   - yaitu kalimat prosa "Berdasarkan Gambar 3.1, ..." - bukan baris yang
   benar-benar memicu kecocokan, yaitu keterangan di awal baris pada halaman
   yang sama. Hasilnya ~30% sampel tampak salah padahal semuanya benar; nyaris
   membatalkan perbaikan yang sudah bekerja.
3. **Pembanding menurut POSISI melaporkan 260 entri berubah, padahal 33**
   (simulasi pembuangan kepala seksi Dalam Angka, 7 Nov 2026). Satu entri
   sampah tanpa nomor hilang, lalu semua pasangan sesudahnya bergeser.
   Dibandingkan menurut kunci `(tipe, nomor)`: 0 kunci hilang, 31 awalan
   dibuang. Pembanding hasil ekstraksi harus memasangkan entri menurut kunci,
   bukan urutan - `scripts/potret_db.py banding` juga membandingkan menurut
   posisi, jadi selisihnya setelah penyisipan entri bukan hitungan perubahan.

Aturan yang berlaku:
- **Verifikasi harus menampilkan bukti yang BENAR-BENAR DIPAKAI mengambil
  keputusan**, bukan bukti yang kebetulan ada di sekitarnya.
- **Untuk menilai mutu ekstraksi, baca sampel acak 25-40 entri satu per satu.**
  Heuristik boleh dipakai untuk menyaring kandidat, tidak untuk menyimpulkan.
- Kalau hasil verifikasi mengejutkan (terlalu bagus ATAU terlalu buruk),
  curigai alatnya dulu sebelum menyimpulkan tentang kodenya.

## Keterbatasan yang diketahui (sudah diverifikasi, bukan bug)
- **4 judul tercemar sisa perbaikan daftar (7 Nov 2026), DITUNDA.** Rincian
  di `data/regresi/perbaikan-daftar-20261107.md`:
  - Pasar Tenaga Kerja Agt 2024 Gambar 8 ("... 2024 38"): tahun dan nomor
    halaman menempel ke dot leader dalam satu kata.
  - TPB 2024 Gambar 26 ("... 6") dan Gambar 38 ("... 7"): folio halaman
    Daftar terserap ke entri terakhir halaman itu.
  - Statistik Daerah 2026 Gambar 14.1: menyerap judul Gambar 15.1 yang
    tercetak sebelum labelnya.

  Dua di antaranya (Gambar 8 dan 14.1) punya versi badan yang BERSIH, tapi
  kalah oleh **aturan judul terpanjang** di `_gabung` (lihat catatan dedup di
  bagian "Ekstraksi badan dokumen"). Aturan itu sengaja tidak diubah:
  mengubahnya menyentuh semua entri 'keduanya', jadi perlu regresi penuh
  tersendiri.
- **Dicatat 9 Nov 2026, belum dikejar:**
  - **Potongan baris Inggris tanpa nomor** menjadi entri sendiri di
    Dalam Angka (misalnya "Government-Approved Foreign Investment by
    Regency/Municipality ..."). Penyebabnya entri yang kehilangan nomor
    halamannya. C3 membuang sebagian (4 prov, 5 sampel kab/kota), sisanya
    tetap ada. Keputusan pemilik project: dicatat saja.
  - **Bug awalan penanda, DIPERBAIKI 9 Nov 2026.** Penanda "tabel 3.1" dulu
    ikut cocok dengan "Tabel 3.12", "Gambar 23", dan folio berjalan
    "Lampiran 137". Sekarang `_pola_penanda` berhenti di batas nomor.
    Hasilnya 8 `halaman_fisik` berubah dan semuanya dibuktikan per entri
    (`data/regresi/awalan-penanda-20261109.md`).
  - **Halaman cetak Daftar Tabel 6302 (Kotabaru Dalam Angka 2026) =
    KESALAHAN SUMBER, tidak dikejar.** Diperiksa sampai tingkat karakter
    PDF: nomor halaman yang tercetak di Daftar tidak monoton. Bab 6 tertulis
    198-201, bab 7 mundur ke 182 (semua tabelnya), bab 8 ke 191-193, bab 12
    240-251 sesudah 11.1 = 260. Folio sebenarnya naik terus (7.1 = 210).
    `halaman_fisik` dari C1(a) tetap benar.
  - **Dalam Angka 2026 tabel 10.3.1** menyerap judul 10.3.2 (sudah
    sebelum C3).
  - **KAK Agt 2024 (`2ddab8a8`): judul Daftar Tabel terpotong di depan,
    DITUNDA (9 Nov 2026).** Di Daftar-nya, baris pertama judul tercetak DI
    ATAS baris nomor ("Persentase Penduduk Usia Kerja ..." / "Tabel" /
    "15 Jumlah Jam Kerja ..."). Akibatnya, dengan jalur nomor-sebaris (C2),
    baris itu menempel ke entri SEBELUMNYA dan entri ini kehilangan awal
    judulnya (5 entri). Usulan perbaikan: baris kolom judul sebelum baris
    "Tabel" tunggal dianggap awal entri berikutnya.
- **8 kelompok `(publikasi, tipe, nomor)` kembar** di `entri_dokumen`. SEMUANYA
  berasal dari jalur `daftar` - nomor tabel yang bertabrakan di sumbernya atau
  salah baca parser pada daftar. Jumlahnya persis sama (8) sebelum maupun
  sesudah ekstraksi badan ditambahkan, jadi BUKAN akibat kegagalan dedup;
  dedup daftar-vs-badan bekerja. Diputuskan tidak dikejar sekarang.
- **Halaman admin SENGAJA tidak ditautkan dari UI utama.** Tidak ada tombol
  "Admin" di header - UI ini untuk petugas PST, dan tombol admin di tiap
  halaman mengganggu serta berisiko terklik. Halamannya tetap ada dan
  berfungsi, diakses lewat URL langsung:

  | Halaman | URL |
  |---|---|
  | Beranda admin | `http://localhost:5000/admin/` |
  | Kelola kamus sinonim | `http://localhost:5000/admin/kamus` |
  | Review log pencarian | `http://localhost:5000/admin/log` |
  | Periksa normalisasi kueri | `http://localhost:5000/admin/log/periksa?q=<kueri>` |

  | Masuk / keluar | `/admin/login` (GET+POST) / `/admin/logout` (POST) |
  | Ganti kata sandi | `http://localhost:5000/admin/sandi` |
  | Perbarui data dari BPS | `http://localhost:5000/admin/perbarui` |

  Ini mekanisme perawatan kamus sinonim SETELAH masa magang selesai - jangan
  dihapus. Setelah mengubah kamus lewat halaman ini, klik tombol
  **"Terapkan ke data"** (POST `/admin/kamus/terapkan`) supaya berlaku pada
  pencarian - itu memanggil `app.services.normalisasi_data.jalankan()`,
  fungsi yang sama dengan `scripts/isi_normalisasi.py`.
- **Autentikasi admin = satu kata sandi bersama**, bukan akun per orang
  (tabel `petugas` di ERD tetap tidak dipakai). Lihat bagian "Persiapan
  serah terima" di bawah. Tidak ditautkannya halaman admin dari UI BUKAN
  pengamanan - pengamanannya adalah login itu.
- **Sekitar 2,5-2,9% entri dari jalur `badan` cacat ringan.** Pemeriksaan manual 40
  entri acak menemukan 1 yang tercampur teks badan ("...di Jawa Barat 8.
  Pemberian atribut"). Diterima apa adanya. Catatan: audit heuristik otomatis
  sempat melaporkan 0% untuk kasus serupa - untuk menilai mutu jalur ini,
  PERIKSA SAMPEL ACAK SECARA MANUAL, jangan hanya mengandalkan heuristik.
- **Master File Desa: semua entri jalur badan, tanpa nomor halaman cetak.**
  Publikasi ini tidak punya halaman DAFTAR konvensional, hanya halaman
  navigasi bergaya grid.
  - Dulu (Agustus) hasilnya 0 entri. Sejak ekstraksi badan, tiap edisi
    334-336 entri, semuanya punya `halaman_fisik`.
  - Peringatan "336/336 entri tanpa nomor halaman" di ringkasan pembaruan
    adalah PERINGATAN PALSU: tombol PDF tetap menuju halaman yang tepat.
- **Publikasi tanpa lapisan teks (perlu OCR), ditemukan 10 Nov 2026:**
  - **5 publikasi kab/kota menghasilkan 0 entri:**
    - HST Dalam Angka 2026 dan PDRB Tapin Pengeluaran: huruf diubah menjadi
      kurva vektor;
    - Profil TK Tapin dan Statistik Daerah Banjarbaru 2025: teks
      dirasterkan menjadi potongan gambar;
    - PDRB Banjarbaru LU: gambar satu halaman penuh.
  - Tiga lainnya sebagian besar halamannya tanpa teks: PDRB Tapin LU dua
    edisi (91%) dan PDRB Tabalong (64%).
  - Satu-satunya teks di PDF-PDF ini adalah watermark. Ini bukan cacat
    parser; publikasinya tetap ditemukan lewat judul dan abstrak.
  - Rincian di `data/regresi/tarik-13-domain-20261110.md`.
- **Target utama spike OCR (revisi 4, sesudah filter wilayah):** delapan
  publikasi tanpa lapisan teks di atas. Lima menghasilkan 0 entri (HST Dalam
  Angka 2026, PDRB Tapin Pengeluaran, Profil TK Tapin, Statistik Daerah
  Banjarbaru 2025, PDRB Banjarbaru LU); tiga sebagian besar halamannya tanpa
  teks (PDRB Tapin LU dua edisi, PDRB Tabalong). Bentuknya ada dua:
  - huruf diubah menjadi kurva vektor;
  - teks dirasterkan menjadi gambar.

  Pendekatan OCR harus menangani keduanya, misalnya dengan merender halaman
  lalu meng-OCR hasil rendernya.
  - **Spike 10 Nov 2026** (`data/regresi/spike-ocr-20261110.md`), 16 halaman,
    93 butir acuan dibaca manual. Belum dipasang ke pipeline.
    - Kata terbaca: Tesseract 95,8%, EasyOCR 98,2%.
    - Nomor entri: Tesseract 29/44 (kolom nomor di kiri hilang), EasyOCR
      39/44. Halaman: 31/36 vs 35/36.
    - Waktu: 2,1 vs 16 detik per halaman (CPU). Ukuran: ±183 MB (portabel,
      tanpa admin) vs 1,1 GB.
    - Usulan berikutnya: uji HST Dalam Angka 2026 penuh lewat kotak kata
      ke parser koordinat.
  - **HST Dalam Angka 2026 penuh, Tesseract (10 Nov 2026)**
    (`data/regresi/ocr-hst-tesseract-20261110.md`).
    - Parser produksi tidak diubah, tidak ke MySQL.
    - Hasil: 0 -> 153 entri (HST 2025 bertekst: 157).
    - Sampel manual 30: nomor 8/28, halaman 19/30, fisik 7/7, judul +
      halaman benar 15/30.
    - Nomor kolom kiri tetap hilang di tingkat OCR.
    - Cache OCR di `data/ocr_cache/` (gitignore).
    - Alat dan venv di `C:/Users/Dani/alat-ocr/`.
    - EasyOCR besok.
  - **Temuan parser:** `BATAS_HALAMAN_CARI = 25` membuat Daftar yang headingnya
    sesudah halaman 25 tidak pernah dibaca. Belum diubah (keputusan pemilik
    project). Diukur di 306 publikasi (`data/regresi/batas-heading-20261110.md`):
    - 24 Daftar Gambar Dalam Angka (hal. 27-49): 498 entri, ±464 gambar
      bernomor tidak terindeks;
    - 6 Daftar Lampiran KAK: lampirannya sudah tertangkap jalur badan.
  - **Uji psm Daftar Tabel HST:** nomor kolom kiri terbaca psm 3 56/139,
    psm 6 22/139, psm 4 106/139.
- **5 publikasi hanya punya Daftar Isi** (Direktori Perusahaan Akomodasi,
  Direktori Perusahaan Konstruksi, Direktori Perusahaan Industri Manufaktur,
  Statistik Daerah, Buklet Survei Angkatan Kerja). Memang tidak ada daftar
  tabel/gambar/lampiran di dokumennya.
- **15 dari 348 entri "Dalam Angka 2025" tanpa nomor halaman** (edisi 2026 hanya
  4 dari 335). Sisa dari daftar tiga kolom dwibahasa yang paling rumit di korpus.
- **`subject_csa` dari API kini selalu `[]` (sejak ~Nov 2026).** Tarikan 5 Nov
  2026: 0 dari 79 publikasi terisi (tarikan Sep 2026: 31 dari 75). Akibatnya
  `publikasi_kategori` kosong dan 14 baris `kategori` tidak punya kaitan.
  Diputuskan DIBIARKAN KOSONG, tidak dipulihkan dari riwayat Git - aplikasi
  tidak memakai kategori sama sekali. Baris "kaitan kategori ... OK" di laporan
  `muat_ke_database.py` hanya berarti 0 = 0, bukan bukti datanya utuh.
- **Tidak ada pengujian otomatis.** `tests/test_ekstraksi_pdf.py` dan
  `tests/test_mesin_pencari.py` hanya stub berisi docstring dari scaffolding
  awal - `pytest` mengumpulkan 0 item. Seluruh verifikasi selama project
  dilakukan MANUAL per perubahan (regresi 72 PDF, sampel acak, test_client
  sekali jalan), bukan lewat suite yang bisa diulang. Diputuskan tidak
  dikerjakan sekarang; kalau ada yang mengubah parser atau scoring, jalankan
  ulang pemeriksaan manual yang dicatat di bagian-bagian terkait.
- **Deteksi wilayah: "banjar" juga nama suku.** "penduduk suku banjar"
  memasang filter Kab. Banjar; petugas membatalkannya lewat pita. Singkatan
  (tala, hss, bjm, ...) belum dikonfirmasi tim PST. Provinsi tidak dideteksi
  dari kueri, hanya bisa dipilih lewat dropdown.
- Judul publikasi dwibahasa menyimpan teks Indonesia DAN Inggris apa adanya.
  Ini disengaja — petugas bisa saja mencari dengan istilah Inggris, dan fuzzy
  matching yang akan menanganinya. Jangan dibuang saat preprocessing.

## Persiapan serah terima ke tim IT BPS (September 2026)
Bukan fitur baru - pengamanan dan kemudahan operasional supaya aplikasi bisa
dijalankan orang yang tidak pernah melihat kodenya. Dokumen operasionalnya
untuk tim IT ada di `PANDUAN.md` (bahasa awam, tanpa asumsi tahu Python).
Kata sandi admin dan isi `.env` DISERAHKAN TERPISAH - tidak ditulis di
PANDUAN.md maupun di Git.

### Rencana isi PANDUAN.md yang belum ditulis (tahap dokumentasi)
- **Pemecahan masalah jaringan:**
  - gejala: "connection reset" saat pembaruan padahal browser bisa;
  - cara cek: `Resolve-DnsName webapi.bps.go.id` (hasil 10.0.11.232 = DNS
    kantor);
  - solusi sementara: hosts file, hanya dengan izin. Lihat "Catatan
    lingkungan".
- **Penarikan besar sebaiknya dijadwalkan dini hari**, misalnya mulai
  sesudah 01:00. Bukti dari penarikan 13 kab/kota (9-10 Nov 2026), dengan
  koneksi tunggal yang sama:
  - pukul 20:30-00:00: 38-75 KB/detik per berkas, 3,35 jam untuk 732 MB;
  - sesudah 01:00: 7-10 MB/detik.

  Pembaruan rutin (beberapa publikasi baru per bulan) tidak terpengaruh
  berarti. Unduhan paralel sengaja TIDAK dibuat (keputusan 10 Nov 2026):
  - manfaatnya belum terbukti;
  - menambah beban ke server BPS di jam sibuk (Term of Use).
- **Korpus pencarian di memori.** Sesudah pembaruan data atau "Terapkan ke
  data", pencarian pertama sedikit lebih lambat karena korpus dimuat ulang.
  Ini normal, dan aplikasi tidak perlu di-restart.

### Konfigurasi wajib - aplikasi menolak jalan kalau kurang
`app/config.py:periksa_konfigurasi()` dipanggil di awal `create_app()` dan
`raise SystemExit(pesan)` kalau:
- `SECRET_KEY` kosong ATAU masih `"kunci-pengembangan-lokal"` (nilai fallback
  lama - sekarang ditolak, karena nilai yang ada di kode sumber sama saja
  dengan tidak ada). Pesan galatnya memuat perintah pembuatan nilai acak.
- `ADMIN_PASSWORD_HASH` kosong. Jangan pernah "diam-diam" membuka admin tanpa
  sandi; lebih baik tidak jalan.

Karena pemeriksaan ada di `create_app()`, SEMUA script yang memanggilnya
(`muat_ke_database.py`, `isi_normalisasi.py`, `uji_pencarian.py`,
`bangun_frekuensi_kata.py`) ikut menolak jalan kalau `.env` belum lengkap.
Ini disengaja: satu aturan, satu `.env`.

`SystemExit` (bukan `RuntimeError`) supaya pesannya tampil bersih tanpa
traceback, baik dari `run.py`, dari script, maupun dari `.bat`.

### Autentikasi admin
- Satu sandi bersama. Hash dibuat `scripts/buat_hash_sandi.py`
  (`werkzeug.security.generate_password_hash`, bawaan Flask - tidak ada
  dependensi baru), disimpan di `.env` sebagai `ADMIN_PASSWORD_HASH`.
  Hash scrypt memuat `$`, dan python-dotenv hanya mengekspansi `${VAR}` -
  sudah diuji, hash tersimpan utuh.
- Penjaga dipasang sebagai `@bp.before_request` di blueprint admin, bukan
  dekorator per-route, supaya route baru otomatis ikut terlindungi.
  Pengecualian hanya endpoint `admin.login`.
- Session Flask, kunci `admin_masuk`. `_tujuan_aman()` hanya mengizinkan
  `next` yang diawali `/admin` (mencegah open redirect).
- Tombol "Keluar" dirender di `base.html` HANYA kalau session admin aktif DAN
  path diawali `/admin` - halaman pencarian tidak pernah memperlihatkannya.
- Halaman pencarian (`/`, `/hasil`, `/api/saran`, `/pdf/<id>`) TIDAK butuh
  login. Diverifikasi dengan test_client dan lewat waitress sungguhan.

### Ganti kata sandi dari browser (`/admin/sandi`)
Alasan: server hanya bisa diakses tim IT, sedangkan pengelola kamus
sehari-hari belum tentu orang yang sama - ganti sandi tidak boleh menuntut
terminal. Ikut penjaga `before_request` (tidak ada dekorator khusus).
- Validasi berurutan: sandi lama cocok hash -> panjang >= 8
  (`PANJANG_SANDI_MINIMAL` di `app/config.py`, dipakai juga oleh
  `buat_hash_sandi.py` supaya satu aturan) -> ulangan sama -> berbeda dari
  yang lama. Ditolak = tidak ada yang ditulis.
- `config.tulis_admin_hash()` mengganti HANYA baris `ADMIN_PASSWORD_HASH=`
  di `.env`; baris lain dibiarkan byte demi byte, gaya akhir baris (LF/CRLF)
  dipertahankan lewat `newline=""`, ditulis ke `.env.tmp` lalu `os.replace`.
  Kalau `.env` tidak ada (hash dari variabel lingkungan sistem), halaman
  menolak dengan pesan - bukan membuat berkas baru.
- Tanpa restart: `current_app.config["ADMIN_PASSWORD_HASH"]` langsung
  diganti; `login()` membaca dari config, bukan dari modul. `.env` baru
  dipakai kali berikutnya aplikasi mulai.
- Sesudah sukses `session.clear()` + redirect ke login dengan flash - login
  ulang dengan sandi baru adalah konfirmasi bahwa sandinya berlaku.
- Diuji pada SALINAN `.env` bergaya LF dan CRLF (sandi asli tidak diketahui
  pengembang, `.env` asli tidak disentuh): semua penolakan tidak mengubah
  berkas; sukses mengubah hanya baris hash, baris lain identik, tidak ada
  `.tmp` tersisa, sandi lama ditolak dan baru diterima tanpa restart.
- `scripts/buat_hash_sandi.py` tetap ada sebagai jalur pemulihan kalau sandi
  lupa (butuh akses server) - dicatat di PANDUAN.md bagian tanggung jawab IT.

### Pembaruan data dari browser (`/admin/perbarui`)
Alasan: mentor/pengelola adalah petugas PST, tidak nyaman menjalankan .bat.
Bedanya dengan "Terapkan ke data": 2-5 menit, bukan 2 detik - jadi TIDAK
dijalankan di dalam request.

Rancangan (`app/services/pembaruan.py`):
- Satu thread latar (daemon) menjalankan `scripts/perbarui.py` sebagai
  subprocess (`-u`, `PYTHONUTF8=1`) dan menampung tiap baris keluarannya di
  memori proses server. Request hanya MEMBACA tampungan itu. Karena itu
  menutup tab tidak menghentikan apa pun; yang menghentikan hanya mematikan
  server - dan bahkan itu tidak membunuh subprocess-nya (Windows tidak
  mematikan anak proses saat induknya keluar), sementara tiap tahap
  perbarui.py menulis atomik dan aman diulang.
- `GET /admin/perbarui/aliran?dari=N` = streaming response Flask (generator,
  `text/plain`) yang mengeluarkan baris ke-N dan seterusnya sampai proses
  selesai. Waitress meneruskannya tanpa menahan: diukur dengan `curl -N`,
  satu baris tiap ~1,5 detik ("halaman 14/66 ... OK"), bukan sekaligus.
- `pembaruan.js` menarik aliran itu dengan `fetch` + `ReadableStream` dan
  menempelkannya ke `<pre>`; begitu aliran habis -> `location.reload()`
  supaya ringkasan dirender SERVER (satu jalur render untuk JS dan non-JS).
  Tanpa JS: `<noscript><meta http-equiv="refresh" content="5">` di `<head>`.
- Ringkasan akhir dibaca dari `data/pembaruan_terakhir.json` yang DITULIS
  perbarui.py sendiri (status sukses / tidak_ada_baru / gagal + flag
  jaringan), bukan ditebak dari teks log. Ditulis di jalur .bat juga, jadi
  halaman admin tahu hasil run tim IT dari terminal. Berkas ini dan kuncinya
  di-gitignore.

**Pengaman "satu pembaruan pada satu waktu" ada di perbarui.py, bukan hanya
di aplikasi.** Berkas `data/pembaruan.lock` berisi PID; `perbarui.py`
menolak jalan (exit 2) kalau PID di dalamnya masih hidup, kunci basi (PID
mati - sisa proses yang dibunuh/hibernate) ditimpa. Ini yang menjaga jalur
web DAN .bat sekaligus, di arah mana pun. Diuji dengan skenario lapangan
paling mungkin: pengelola mengklik tombol di browser, lalu tim IT
menjalankan `perbarui-data.bat` 6 detik kemudian -> .bat berhenti dalam
1 detik dengan "TIDAK DIJALANKAN: pembaruan lain sedang berjalan", web-run
tetap hidup dan selesai normal. Di dalam aplikasi ada lock kedua (in-memory)
untuk menonaktifkan tombol dan menolak POST kedua.

**Jebakan Windows: `os.kill(pid, 0)` MEMBUNUH proses.** Idiom POSIX
"kirim sinyal 0 untuk memeriksa apakah PID hidup" di Windows diterjemahkan
CPython menjadi `TerminateProcess` untuk sinyal apa pun selain
CTRL_C_EVENT/CTRL_BREAK_EVENT. Memeriksa kunci dengan cara itu akan
mematikan pembaruan yang sedang berjalan. Pemeriksaan PID memakai
`OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` + `GetExitCodeProcess ==
STILL_ACTIVE` lewat ctypes (`_proses_hidup` di perbarui.py, diduplikasi
sebagai `_pid_hidup` di `app/services/pembaruan.py` supaya paket app tidak
mengimpor dari `scripts/`).

**Bukti pengaman #3 dari kejadian nyata, bukan uji terencana:** sesi
pengembangan terputus (batas penggunaan) tepat setelah `POST
/admin/perbarui/mulai` dikirim ke server uji - tidak ada tab, tidak ada
request aliran, tidak ada yang menunggu. Saat sesi berikutnya diperiksa,
pembaruan sudah selesai sendiri: `pembaruan_terakhir.json` berstatus
`tidak_ada_baru` (111 detik), kunci sudah dilepas, `hasil_ekstraksi.json`
tidak tersentuh, dan halaman merender keadaan "selesai" dengan benar.

Verifikasi kesetaraan: run lewat web lalu run lewat .bat pada data yang
sama -> himpunan pub_id, entri per publikasi, dan hitungan DB (75/6.366)
identik di ketiga potret (sebelum / sesudah web / sesudah .bat).

### Server produksi
`run.py` sekarang memakai **waitress** secara bawaan (`threads=4`);
`--dev` untuk server Flask + debugger. `--host`/`--port` bisa diubah.

**Port: argumen > `PORT` di .env > 5000.** Ditambahkan atas pertanyaan tim
IT BPS (port 5000 mungkin sudah dipakai di server). `Config.PORT` disimpan
sebagai TEKS dan divalidasi di `periksa_konfigurasi()` (angka 1-65535, else
SystemExit dengan pesan) - supaya `PORT=abc` ditolak rapi, bukan traceback
`int()`. `run.py --port` default `None` lalu diisi dari `app.config["PORT"]`.
`jalankan-aplikasi.bat` membaca baris `PORT=` dari `.env` sendiri lewat
`for /f "eol=# tokens=1,* delims=="` - harus tahu portnya SEBELUM memanggil
python, karena pemeriksaan port-sibuk dan URL browser ada di .bat. Kedua
pembaca harus sepakat: format yang didukung hanya `PORT=angka` tanpa spasi
di sekitar `=` (python-dotenv menerima lebih longgar, .bat tidak).
Diuji sungguhan di port 5006-5009: argumen run.py, argumen .bat, .env untuk
keduanya, argumen menimpa .env, `PORT=abc` ditolak, port sibuk ditolak.

**Jebakan Windows yang ditemukan saat verifikasi:** waitress memasang
`SO_REUSEADDR`, dan di Windows itu membuat DUA proses bisa mendengarkan
port yang sama TANPA galat - request lalu jatuh ke salah satunya secara acak.
Terbukti terjadi: dua server di 127.0.0.1:5000 bersamaan. Kalau `.bat`
diklik dua kali, ini pasti terjadi. `run.py` sekarang mencoba
`socket.create_connection` ke port itu dulu dan berhenti dengan pesan kalau
sudah ada yang menjawab.

### Berkas .bat (klik dua kali, untuk tim IT)
- `jalankan-aplikasi.bat [port]`: cek venv -> cek .env -> cek koneksi MySQL
  (memakai `create_app()` + `SELECT 1`, jadi sekaligus memicu
  `periksa_konfigurasi`) -> buka browser -> `run.py --port`. Pesan `[GAGAL]`
  dibedakan menurut jenis galat (Can't connect / Access denied / KONFIGURASI
  BELUM LENGKAP).
- `perbarui-data.bat`: cek yang sama, lalu `scripts/perbarui.py %*`, lalu
  `pause` supaya ringkasan terbaca. Diuji sungguhan: menemukan 2 publikasi
  baru yang dirilis BPS (72 -> 74, entri 5.975 -> 6.316, 0 diekstrak ulang,
  179 detik) - jadi angka "72 publikasi / 5.975 entri" di bagian-bagian
  sebelumnya adalah angka SAAT DITULIS; data hidup dan bertambah.
- Ditulis ASCII + CRLF (cmd.exe rewel soal encoding).
- **Kesan pertama itu penting - dua jebakan "terlihat rusak padahal tidak":**
  1. Browser dibuka SEBELUM server siap -> halaman pertama yang dilihat
     penerima aplikasi adalah ERR_CONNECTION_REFUSED. Sekarang browser dibuka
     oleh `run.py --buka-browser` dari thread yang mem-poll URL sampai
     menjawab (batas 30 detik, lalu pesan peringatan tanpa membuka browser),
     bukan oleh `start` di .bat. Thread-nya daemon: kalau `serve()` gagal,
     browser tidak pernah dibuka ke halaman galat.
  2. `perbarui.py` dulu memakai `capture_output=True` sehingga layar DIAM
     ~2 menit di tahap 1 (dan lebih lama di ekstraksi) lalu memuntahkan
     semuanya sekaligus - terlihat macet. Sekarang `Popen` + `-u` +
     `PYTHONUTF8=1`, baris dialirkan begitu muncul.

### Tombol "Terapkan ke data"
Logika `isi_normalisasi.py` dipindah ke `app/services/normalisasi_data.py`
(`jalankan(cetak=...)` mengembalikan dict ringkasan) supaya route admin tidak
perlu mengimpor dari folder `scripts/`. `scripts/isi_normalisasi.py` tinggal
pembungkus yang mencetak laporan rinci; nama `jalankan` dipertahankan karena
`muat_ke_database.py` mengimpornya. Diuji: menambah varian "hotel" ke
kelompok "banyaknya" lalu Terapkan mengubah persis 105 entri (semua yang
memuat token "hotel"); menghapus varian lalu Terapkan lagi mengembalikan
database ke keadaan awal byte-per-byte.

## Catatan lingkungan
- **Masalah DNS kantor (awal Nov 2026, TERATASI 9 Nov 2026).**
  - Gejala: pembaruan data gagal dengan "connection reset" ke WebAPI, padahal
    situs BPS terbuka di browser.
  - Penyebab: DNS internal kantor mengarahkan webapi.bps.go.id ke
    vs.bps.go.id → 10.0.11.232, dan koneksi ke alamat itu ditolak. IP publik
    yang benar 203.123.60.70. WebAPI-nya sendiri tidak diblokir: 7 Nov 2026,
    dari Wi-Fi rumah dengan DNS publik, curl langsung HTTP 200 dalam 0,49
    detik tanpa hosts file.
  - Teratasi: 9 Nov 2026, dari Wi-Fi "BPS - Pegawai", webapi.bps.go.id
    mengarah ke 203.123.60.70; curl dan Python requests sama-sama HTTP 200.
    Kemungkinan diperbaiki tim IT (belum dikonfirmasi). Hosts file tidak
    pernah dipakai.
- Penarikan 13 domain nanti boleh dari jaringan kantor.
- Kalau gejalanya muncul lagi: cek dengan `Resolve-DnsName webapi.bps.go.id`
  (PowerShell). Kalau hasilnya 10.0.11.232, masalah DNS-nya kambuh. Solusi
  sementara: baris hosts file `203.123.60.70 webapi.bps.go.id`. **Jangan ubah
  hosts file tanpa izin pemilik project.** Cara ini dijadwalkan masuk
  `PANDUAN.md` bagian pemecahan masalah (tahap dokumentasi, belum ditulis).
- Catatan lama: dulu tercatat bahwa jaringan "BPS - Pegawai" bisa mengakses
  WebAPI dan "BPS - Tamu" tidak.

## Skema database (ERD rancangan sendiri — bebas disesuaikan dengan temuan data)
- **publikasi**: id (pub_id dari BPS), judul, abstrak, tahun_terbit, tanggal_rilis, url_pdf, url_cover, updated_at
- **kategori**: id, nama (dari `subject_csa`)
- **publikasi_kategori**: publikasi_id, kategori_id (tabel penghubung many-to-many)
- **entri_dokumen**: id, publikasi_id, tipe (isi/tabel/gambar/lampiran), nomor, judul, halaman, teks_ternormalisasi
- **kelompok_sinonim**: id, kata_kanonik
- **varian_sinonim**: id, kelompok_id, kata_varian
- **petugas**: id, nama, username, role (opsional, bisa dilewati untuk MVP)
- **log_pencarian**: id, petugas_id, keyword, keyword_ternormalisasi, jumlah_hasil, skor_tertinggi, waktu_pencarian

Kunci desain: `entri_dokumen` terpisah dari `publikasi` — inilah yang memungkinkan sistem
menjawab "di bagian mana", bukan cuma "di publikasi mana".

Relasi publikasi-kategori **many-to-many** lewat `publikasi_kategori`, bukan kolom
`kategori_id` di tabel `publikasi`. Alasannya data aktual: `subject_csa` berbentuk array
dan satu publikasi bisa punya lebih dari satu subjek (73 penyebutan dari 72 publikasi).

Kategori bersifat **opsional**: 43 dari 72 publikasi tidak punya `subject_csa` sama sekali,
jadi banyak publikasi tidak akan punya baris di `publikasi_kategori`. Ini kondisi normal,
bukan data rusak — jangan perlakukan sebagai error saat impor maupun saat menampilkan hasil.

`log_pencarian` dipakai untuk closed-loop improvement: query dengan skor rendah direview
berkala untuk memperkaya kamus sinonim.

## Timeline (10 minggu)
1. Setup + **spike ekstraksi PDF** (validasi risiko terbesar: apakah format PDF konsisten?)
2. Pipeline pengambilan data WebAPI
3-4. Ekstraksi struktur dokumen (bagian paling kompleks)
5. Preprocessing + kamus sinonim awal
6. Mesin pencarian + scoring
7. Backend API + UI pencarian (titik MVP bisa didemokan)
8. Log pencarian, refinement, polish
9-10. Uji coba petugas PST + dokumentasi/laporan

**Yang boleh dipangkas kalau waktu mepet**: filter tahun/kategori di UI, highlight keyword,
tuning bobot mendalam, embeddings.

**Yang TIDAK boleh dipangkas**: ekstraksi PDF, kamus sinonim dasar, fuzzy matching + skor,
UI yang menunjukkan lokasi spesifik.

## Prinsip kerja
- Prioritaskan **MVP yang berfungsi** di atas pendekatan tercanggih yang setengah jadi.
- Kode harus bisa dijelaskan pemiliknya ke penguji — hindari kompleksitas yang tidak perlu.
- Bahasa Indonesia untuk penamaan domain (publikasi, entri_dokumen, dst.) agar konsisten
  dengan konteks dan mudah dijelaskan di laporan.
