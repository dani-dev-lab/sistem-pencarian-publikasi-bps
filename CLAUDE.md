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
  infrastruktur BPS diserahkan ke instansi.
- **Platform**: web app, Python + Flask. MySQL (via Laragon) sebagai database.

## Sumber data
- **BPS WebAPI**: `https://webapi.bps.go.id/v1/api/list/model/publication/lang/ind/domain/6300/page/{page}/key/{key}/`
- Domain Kalsel = `6300`. API key disimpan di `.env` sebagai `BPS_API_KEY`.
- Pagination: 10 publikasi per halaman, total ~648 publikasi (~65 halaman) untuk semua tahun.
- Field penting: `pub_id`, `title`, `abstract`, `rl_date`, `pdf` (link unduh), `cover`, `subject_csa`.
- PDF publikasi diunduh dari field `pdf`, lalu diekstrak strukturnya.

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

Empat format daftar yang ditangani satu parser (jangan dipecah jadi parser terpisah):
1. label + nomor satu baris ("Tabel 1 Judul ..... 7")
2. dua kolom, label dan nomor beda baris (PDRB)
3. nomor halaman di baris pertama, judul menyambung ke bawah
4. tanpa kata label, nomor berdiri sendiri di kolom kiri ("Dalam Angka")

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
**0 publikasi berkurang**. Pertahankan sifat superset ini kalau jalur badan
diubah lagi.

Dedup memakai kunci `(tipe, nomor)` per publikasi; kalau judulnya berbeda,
versi dari BADAN yang dipakai karena versi daftar kadang terpotong.

Kolom `sumber` bernilai 'daftar' | 'badan' | 'keduanya'.

`#page=` di tombol PDF memakai `halaman_fisik`, BUKAN `halaman`. Dulu fitur ini
dilewati karena selisih halaman cetak vs fisik terbukti tidak konsisten (5 dari
8 publikasi foliony tidak terbaca, sisanya selisihnya berubah-ubah di dalam satu
publikasi). Sekarang akurat tanpa tebakan karena halaman fisik dicatat langsung
saat ekstraksi.

## Prinsip verifikasi (dipelajari dari dua kesalahan nyata)
**Alat verifikasi juga bisa salah, dan salahnya LEBIH BERBAHAYA daripada bug
biasa - karena kita mempercayainya dan berhenti memeriksa.** Sudah dua kali
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

Aturan yang berlaku:
- **Verifikasi harus menampilkan bukti yang BENAR-BENAR DIPAKAI mengambil
  keputusan**, bukan bukti yang kebetulan ada di sekitarnya.
- **Untuk menilai mutu ekstraksi, baca sampel acak 25-40 entri satu per satu.**
  Heuristik boleh dipakai untuk menyaring kandidat, tidak untuk menyimpulkan.
- Kalau hasil verifikasi mengejutkan (terlalu bagus ATAU terlalu buruk),
  curigai alatnya dulu sebelum menyimpulkan tentang kodenya.

## Keterbatasan yang diketahui (sudah diverifikasi, bukan bug)
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

  Ini mekanisme perawatan kamus sinonim SETELAH masa magang selesai - jangan
  dihapus. Setelah mengubah kamus lewat halaman ini, jalankan
  `scripts/isi_normalisasi.py` supaya berlaku pada data.
- **Tidak ada autentikasi.** `/admin/` terbuka tanpa login. Disengaja:
  aplikasi berjalan lokal di laptop selama masa magang, dan tabel `petugas`
  sengaja dilewati untuk MVP. Tidak ditautkannya halaman itu BUKAN pengamanan
  - siapa pun yang tahu URL-nya bisa masuk. WAJIB ditambahkan autentikasi
  sebelum deploy ke jaringan mana pun.
- **Sekitar 2,5-2,9% entri dari jalur `badan` cacat ringan.** Pemeriksaan manual 40
  entri acak menemukan 1 yang tercampur teks badan ("...di Jawa Barat 8.
  Pemberian atribut"). Diterima apa adanya. Catatan: audit heuristik otomatis
  sempat melaporkan 0% untuk kasus serupa - untuk menilai mutu jalur ini,
  PERIKSA SAMPEL ACAK SECARA MANUAL, jangan hanya mengandalkan heuristik.
- **3 × Master File Desa: 0 entri.** Publikasi ini memang tidak punya halaman
  DAFTAR konvensional, hanya halaman navigasi bergaya grid. Perilaku benar.
- **5 publikasi hanya punya Daftar Isi** (Direktori Perusahaan Akomodasi,
  Direktori Perusahaan Konstruksi, Direktori Perusahaan Industri Manufaktur,
  Statistik Daerah, Buklet Survei Angkatan Kerja). Memang tidak ada daftar
  tabel/gambar/lampiran di dokumennya.
- **15 dari 348 entri "Dalam Angka 2025" tanpa nomor halaman** (edisi 2026 hanya
  4 dari 335). Sisa dari daftar tiga kolom dwibahasa yang paling rumit di korpus.
- Judul publikasi dwibahasa menyimpan teks Indonesia DAN Inggris apa adanya.
  Ini disengaja — petugas bisa saja mencari dengan istilah Inggris, dan fuzzy
  matching yang akan menanganinya. Jangan dibuang saat preprocessing.

## Catatan lingkungan
- WebAPI BPS hanya bisa diakses dari jaringan "BPS - Pegawai".
  Jaringan "BPS - Tamu" memblokir (DNS mengarah ke 10.0.11.232, koneksi ditolak).

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
