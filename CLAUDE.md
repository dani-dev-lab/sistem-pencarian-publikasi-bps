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
- **3 × Master File Desa: 0 entri.** Publikasi ini memang tidak punya halaman
  DAFTAR konvensional, hanya halaman navigasi bergaya grid. Perilaku benar.
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
- Judul publikasi dwibahasa menyimpan teks Indonesia DAN Inggris apa adanya.
  Ini disengaja — petugas bisa saja mencari dengan istilah Inggris, dan fuzzy
  matching yang akan menanganinya. Jangan dibuang saat preprocessing.

## Persiapan serah terima ke tim IT BPS (September 2026)
Bukan fitur baru - pengamanan dan kemudahan operasional supaya aplikasi bisa
dijalankan orang yang tidak pernah melihat kodenya. Dokumen operasionalnya
untuk tim IT ada di `PANDUAN.md` (bahasa awam, tanpa asumsi tahu Python).
Kata sandi admin dan isi `.env` DISERAHKAN TERPISAH - tidak ditulis di
PANDUAN.md maupun di Git.

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
