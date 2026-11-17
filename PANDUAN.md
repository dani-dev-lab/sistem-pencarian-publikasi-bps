# Panduan Pengoperasian — Sistem Pencarian Publikasi BPS Kalsel

Panduan ini ditujukan untuk tim IT BPS Provinsi Kalimantan Selatan yang
menerima serah terima aplikasi. Tidak perlu tahu Python atau Flask untuk
mengikuti panduan ini; cukup terbiasa dengan komputer Windows, folder, dan
berkas teks.

Kata sandi admin dan isi berkas `.env` (yang memuat API key dan sandi
database) **diserahkan terpisah** — tidak ditulis di panduan ini dan tidak
disimpan di Git.

Angka di panduan ini (jumlah publikasi, lama proses) adalah hasil pengukuran
pada tanggal yang disebut di sampingnya, di laptop pengembang. Yang belum
pernah diukur ditulis "belum diukur".

Isi panduan:

1. Apa yang dilakukan aplikasi ini
2. Yang harus tersedia di komputer, dan pemasangan pertama kali
3. Menjalankan dan menghentikan aplikasi
4. Memperbarui data saat ada publikasi baru
5. Menambah istilah pendek / sinonim lewat halaman admin
6. Mengganti kata sandi admin
7. Yang perlu disiapkan tim IT untuk pemasangan di jaringan kantor
8. Mengelola daftar wilayah
9. Database uji dan cara menguji aplikasi
10. Pemecahan masalah
11. Keterbatasan yang diketahui dan utang teknis

---

## 1. Apa yang dilakukan aplikasi ini

Petugas Pelayanan Statistik Terpadu (PST) sering ditanya "data X ada di
publikasi mana?" — dan harus membuka publikasi satu per satu untuk
menjawabnya. Aplikasi ini menjawab pertanyaan itu dengan satu kotak
pencarian: petugas mengetik kata kunci, aplikasi menunjukkan **publikasi
mana** dan **bagian mana** (tabel, gambar, lampiran, bab) yang memuat data
tersebut, lengkap dengan nomor halaman dan tombol untuk membuka PDF-nya
langsung di halaman itu.

Cara kerjanya secara garis besar:

1. Daftar publikasi diambil dari WebAPI BPS untuk **14 wilayah**: Provinsi
   Kalimantan Selatan dan 13 kabupaten/kota. Hanya publikasi yang **dirilis
   dalam 2 tahun terakhir** yang diambil. Publikasi "Kecamatan … Dalam
   Angka" sengaja tidak diambil, atas permintaan tim PST (bagian 8).
2. Berkas PDF tiap publikasi diunduh dan dibaca strukturnya: Daftar Isi,
   Daftar Tabel, Daftar Gambar, Daftar Lampiran, serta keterangan
   tabel/gambar di badan dokumen.
3. Hasilnya disimpan di database MySQL. Pencarian berjalan terhadap
   database ini — **tidak** menghubungi BPS setiap kali petugas mencari,
   jadi pencarian berjalan tanpa internet.

Keadaan data pada 17 November 2026: **307 publikasi, 24.532 bagian
terindeks**. 86% bagian itu bisa dibuka langsung di halaman PDF-nya
(rinciannya di bagian 11).

Yang butuh internet hanya langkah pembaruan data (bagian 4).

Ada dua jenis halaman:

| Halaman | Alamat | Siapa | Login? |
|---|---|---|---|
| Pencarian | `http://localhost:5000/` | Petugas PST | Tidak |
| Admin | `http://localhost:5000/admin/` | Pengelola kamus | Ya, kata sandi bersama |

Halaman admin sengaja **tidak ditautkan** dari halaman pencarian. Alamatnya
diketik langsung di browser.

Angka `5000` di alamat itu adalah **port** bawaan. Kalau port diganti (bagian
3 dan 7), semua alamat di panduan ini ikut berubah — misalnya port 8080
berarti `http://localhost:8080/` dan `http://localhost:8080/admin/`.

### Mencari menurut wilayah

Di samping kotak pencarian ada pilihan wilayah. Bawaannya **Semua wilayah**.

- **Memilih sendiri:** petugas memilih satu wilayah, lalu hasil hanya berasal
  dari publikasi wilayah itu.
- **Dipasang otomatis:** kalau kata kunci menyebut nama kabupaten/kota,
  misalnya "penduduk tanah laut", aplikasi memasang filter wilayah itu
  sendiri. Di atas hasil muncul pita **Dipasang otomatis** dengan tautan
  **Batalkan**. Batalkan berarti kata kunci yang sama dicari di semua
  wilayah.
- Nama wilayah yang menjadi filter tidak ikut dicocokkan ke judul tabel.
  Jadi "penduduk tanah laut" dan memilih Tanah Laut lalu mengetik "penduduk"
  memberi hasil yang sama.
- Kalau kata kunci menyebut **lebih dari satu** wilayah, filter tidak
  dipasang, dan petugas diminta memilih sendiri.
- Kalau kata kunci **hanya** nama wilayah ("tanah laut"), yang tampil adalah
  seluruh publikasi wilayah itu, terbaru di atas.
- Saat filter kabupaten/kota aktif, di bawah hasil ada seksi **Juga ada di
  publikasi provinsi** (paling banyak 10). Alasannya: tabel provinsi sering
  dirinci per kabupaten/kota.
- Provinsi tidak dikenali dari kata kunci; hanya bisa dipilih dari daftar.

### Tombol Buka PDF: "hal. N" dan "±hal. N"

Tiap bagian di hasil pencarian punya tombol untuk membuka PDF-nya. Tulisan
pada tombol itu ada tiga macam:

| Tombol | Artinya |
|---|---|
| **Buka PDF hal. 57** | Aplikasi menemukan sendiri tabel/gambar itu di halaman 57 berkas PDF. PDF langsung terbuka di halaman itu. |
| **Buka PDF ±hal. 38** | **Perkiraan.** Letak bagian itu di PDF tidak terbaca langsung, jadi halamannya dihitung dari nomor halaman di Daftar Tabel atau Daftar Isi dan letak tabel-tabel di sekitarnya. Biasanya tepat; kalau tabel atau judul subbabnya tidak ada di halaman itu, gulir **satu-tiga halaman** ke depan atau ke belakang. Arahkan tetikus ke tombol untuk melihat keterangannya. |
| **Buka PDF** | Letaknya tidak diketahui. PDF terbuka di halaman pertama; pakai nomor "Halaman" yang tertulis di kartu untuk mencarinya. |

Nomor **"Halaman"** di kartu adalah nomor yang **tercetak** di publikasi
(seperti di Daftar Tabel). Nomor itu sering berbeda dengan nomor halaman
berkas PDF, karena sampul dan halaman beromawi ikut terhitung di PDF.

Pada uji 16 November 2026, tombol "±hal." diperiksa satu per satu:

- **Tabel/gambar/lampiran:** 56 dari 60 langsung menuju bagian yang benar.
  Tiga meleset 2–3 halaman, dan satu menunjuk tabel yang ternyata tidak
  dicetak di publikasinya. Penyebab utamanya: nomor halaman di Daftar Tabel
  publikasi itu sendiri keliru.
- **Bab dan subbab** (misalnya "3.7 Perkembangan Net Ekspor" di PDRB Menurut
  Pengeluaran): 48 dari 50 langsung menuju judul subbabnya; dua meleset 1–2
  halaman. Untuk **bab**, halaman yang dibuka biasanya **sampul bab**. Isi
  babnya mulai di halaman sesudahnya.

---

## 2. Yang harus tersedia di komputer, dan pemasangan pertama kali

- **Windows** (dikembangkan dan diuji di Windows 11).
- **Python 3.12 atau lebih baru** (dikembangkan dengan 3.14). Saat
  memasang Python, centang *"Add Python to PATH"*.
- **MySQL 8** — selama pengembangan dipakai lewat **Laragon**.
- Folder proyek ini (`sistem-pencarian-bps`).
- **Ruang disk ±3,5 GB** untuk data: folder PDF `data/publikasi_pdf/` berisi
  307 PDF, 3.048 MB (17 November 2026), dalam satu subfolder per kode
  wilayah (`6300`, `6301`, …). PDF ini dipakai dua kali: dibaca saat
  pembaruan, dan dibuka oleh tombol **Buka PDF** di hasil pencarian.
  OCR, kalau dipasang, menambah ±1,1 GB (bagian 7.2).

### Memasang program (sekali saja)

Buka **Command Prompt** di folder proyek, lalu jalankan berurutan:

```
python -m venv venv
venv\Scripts\pip.exe install -r requirements.txt
copy .env.example .env
```

Kemudian buka berkas `.env` dengan Notepad dan isi nilainya. Isinya
diserahkan terpisah oleh pengembang; kalau harus membuat dari awal:

| Variabel | Isi |
|---|---|
| `SECRET_KEY` | Teks acak. Buat dengan `venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_PASSWORD_HASH` | Hash kata sandi admin. Buat dengan `venv\Scripts\python.exe scripts\buat_hash_sandi.py` (rincian di bagian 7, "Pemulihan kata sandi admin"). Setelah itu sandi bisa diganti dari browser (bagian 6). |
| `BPS_API_KEY` | API key WebAPI BPS, dari https://webapi.bps.go.id/developer/ |
| `BPS_API_BASE_URL` | Biarkan seperti di `.env.example`. |
| `DATABASE_URL` | `mysql+pymysql://root:SANDI@localhost:3306/db_pencarian_bps` — ganti `SANDI` dengan sandi root MySQL |
| `PORT` | Opsional. Port server; kosong = 5000. Isi kalau 5000 sudah dipakai program lain (bagian 3). |
| `MYSQL_BIN` | Opsional. Folder tempat program `mysql.exe` dan `mysqldump.exe`, misalnya `C:/laragon/bin/mysql/mysql-8.0.30-winx64/bin`. Hanya dipakai untuk membuat database uji dan menjalankan uji (bagian 9). Kosongkan kalau `mysql` sudah bisa dipanggil dari Command Prompt. Tulis dengan garis miring `/`, tanpa spasi di sekitar `=`. |

Aplikasi **menolak berjalan** kalau `SECRET_KEY` atau `ADMIN_PASSWORD_HASH`
kosong, dan menampilkan pesan yang menjelaskan cara mengisinya. Ini
disengaja: lebih baik tidak jalan daripada jalan tanpa pengaman.

### Mengisi data pertama kali

Ada dua jalur. **Jalur A disarankan**: selesai dalam hitungan menit dan
tidak butuh internet. Jalur B mengunduh semuanya dari BPS dan memakan
beberapa jam.

#### Jalur A (disarankan): dari berkas serah terima

Pengembang menyerahkan empat hal, selain `.env` dan kata sandi admin yang
diserahkan terpisah:

| Yang diserahkan | Ditaruh di |
|---|---|
| Cadangan database (satu berkas `.sql`, dibuat dengan perintah `mysqldump` di bagian 7, pada hari yang sama dengan salinan folder PDF) | dipulihkan ke MySQL, langkah 1–3 |
| Folder PDF `publikasi_pdf` (±3 GB) | `data\publikasi_pdf\` |
| Folder cache OCR `ocr_cache` (±22 MB) | `data\ocr_cache\` |
| Berkas `wilayah.json` | `data\wilayah.json` (sudah ikut di Git; pakai yang diserahkan kalau isinya berbeda) |

Langkahnya, di **Command Prompt** (bukan PowerShell, karena tanda `<` di
langkah 3 tidak dikenal PowerShell), dari folder tempat berkas cadangan
berada:

1. Supaya perintah `mysql` dikenali, tambahkan dulu folder program MySQL ke
   PATH jendela ini. Foldernya sama dengan `MYSQL_BIN` (tabel di atas);
   sesuaikan dengan versi MySQL yang terpasang:
   ```
   set PATH=C:\laragon\bin\mysql\mysql-8.0.30-winx64\bin;%PATH%
   ```
   Tanpa langkah ini Command Prompt tidak mengenali perintah `mysql`
   (begitulah keadaannya di laptop pengembang).
2. Buat database kosong:
   ```
   mysql -u root -p -e "CREATE DATABASE db_pencarian_bps CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
   ```
3. Pulihkan cadangan ke database itu (ganti `cadangan.sql` dengan nama
   berkasnya):
   ```
   mysql -u root -p --default-character-set=utf8mb4 db_pencarian_bps < cadangan.sql
   ```
4. Salin folder `publikasi_pdf` dan `ocr_cache` ke dalam folder `data\`.
5. Jalankan `jalankan-aplikasi.bat` (bagian 3). Data langsung bisa dicari.

Di langkah 2 dan 3, `-p` membuat MySQL **meminta sandi root diketik**.
Kalau sandi root kosong (bawaan Laragon), tekan Enter saja, atau hapus `-p`
dari perintahnya.

Langkah 1–3 diuji 14 November 2026 dengan database sementara: cadangan yang
dibuat dengan perintah `mysqldump` di bagian 7 dipulihkan dalam ±1,5 detik,
dan keenam tabelnya sama dengan database asal (jumlah baris dan `CHECKSUM
TABLE`). Pengujian itu memakai perintah tanpa `-p`, karena sandi root di
laptop pengembang kosong. Untuk langkah 4, cara menyalinnya sudah diuji di
laptop pengembang (tabel di bawah), tetapi menyalin ke komputer lain belum
pernah dicoba.

**Penting saat menyalin folder PDF: tanggal ubah berkas ("Date modified")
harus tetap sama.** Aplikasi mengenali PDF dari ukuran dan tanggal ubahnya.
Kalau tanggal itu berubah, pembaruan berikutnya menganggap semua PDF
berganti, lalu:

- membaca ulang seluruh 307 PDF (±75–95 menit; diukur 4.470 detik pada 10
  November dan 5.541 detik pada 17 November 2026), dan
- membuang cache OCR 8 publikasi, yang hanya bisa dibuat ulang dengan OCR
  (bagian 7.2; 1.192 halaman × ±15 detik ≈ 5 jam). Kalau OCR tidak
  dipasang, kedelapan publikasi itu kehilangan rincian tabelnya.

Aplikasi tidak punya perintah untuk memeriksa hal ini saja: pembaruan
pertama langsung membaca ulang PDF yang tanggalnya berubah. Karena itu
periksa sendiri sesudah menyalin (butir "Sesudah menyalin" di bawah tabel).

Diuji 17 November 2026 di laptop pengembang, antarfolder di drive NTFS yang
sama (5 PDF + 100 berkas cache OCR, dibandingkan sampai ke detik):

| Cara menyalin | Tanggal ubah | Boleh dipakai? |
|---|---|---|
| File Explorer (salin–tempel folder) | tetap | **ya** |
| `robocopy <asal> <tujuan> /E` | tetap | **ya** |
| `Copy-Item -Recurse` (PowerShell) | tetap | **ya** |
| Arsip `tar` bawaan Windows (`tar -cf arsip.tar -C <asal> .`, lalu `tar -xf arsip.tar -C <tujuan>`) | tetap | **ya**, kalau perlu satu berkas arsip |
| ZIP lewat File Explorer ("Send to → Compressed folder", lalu "Extract All") | **bergeser 1–2 detik** pada semua berkas | **tidak** |
| ZIP lewat PowerShell (`Compress-Archive` / `Expand-Archive`) | **bergeser 1 detik** pada sebagian berkas | **tidak** |

Format ZIP hanya mencatat waktu dengan ketelitian 2 detik, jadi pergeseran
itu pasti terjadi, bukan kebetulan.

- **Tidak diuji:** penyimpanan awan, flashdisk atau disk eksternal (FAT32,
  exFAT), dan menyalin lewat folder bersama di jaringan. FAT32 juga hanya
  mencatat waktu per 2 detik, jadi jangan menyalin berkas lepas ke flashdisk
  FAT32. Kalau medianya flashdisk, bungkus dulu dengan arsip `tar` (tabel di
  atas): tanggal ubah tersimpan di dalam arsip. Cara ini juga belum diuji di
  flashdisk, jadi tetap periksa hasilnya.
- Sesudah menyalin, bandingkan "Date modified" beberapa PDF dengan aslinya
  sampai ke detik (kolom "Date modified" di File Explorer hanya menampilkan
  menit; lihat lewat Properties).
- Simpan media serah terima sampai pembaruan pertama selesai dengan baik.

Jalur A tidak memerlukan `--hanya-periksa` (lihat jalur B): wilayah yang
sudah punya data di database langsung boleh diperbarui.

#### Jalur B: dari nol, mengunduh dari BPS

Dipakai kalau berkas serah terima tidak ada. Butuh internet yang bisa
menjangkau WebAPI BPS (bagian 10 kalau gagal terhubung).

**Jalur ini belum diuji dari nol** (dari database kosong sampai selesai),
karena butuh jaringan ke BPS dan berjam-jam unduhan. Yang sudah terbukti
adalah bagian-bagiannya: pemeriksaan 14 wilayah (9 November 2026), penarikan
13 kabupaten/kota ke database yang sudah berisi provinsi (9–10 November
2026), dan berhentinya pembaruan dengan pesan kalau langkah 2 dilewati (14
November 2026).

1. Buat database kosong (langkah 1–2 jalur A). Tabelnya dibuat otomatis.
2. Jalankan pemeriksaan wilayah, **wajib sebelum pembaruan pertama**:
   ```
   venv\Scripts\python.exe scripts\perbarui.py --hanya-periksa
   ```
   Perintah ini menarik daftar publikasi semua wilayah dan memastikan tidak
   ada nomor publikasi yang sama di dua wilayah. Ia tidak mengubah database
   dan tidak mengunduh PDF. Lamanya 927 detik (±15 menit) pada 9 November
   2026. Hasil yang benar: `Tabrakan antar-domain : 0`.
3. Jalankan `perbarui-data.bat`. Ini mengunduh ±3 GB PDF dan membaca
   semuanya. Penarikan 13 kabupaten/kota pada 9–10 November 2026 memakan
   **5,0 jam**. Mulailah **sesudah pukul 01:00**: pada malam itu kecepatan
   unduh pukul 20:30–00:00 hanya 38–75 KB/detik per berkas, dan sesudah
   01:00 naik menjadi 7–10 MB/detik. Biarkan jendela terbuka, laptop
   tersambung listrik, dan layar laptop jangan ditutup.
4. Jalankan `jalankan-aplikasi.bat`.

Kalau langkah 2 dilewati, `perbarui-data.bat` berhenti dalam beberapa detik
dengan pesan `TIDAK ADA YANG DIKERJAKAN: semua wilayah aktif … belum boleh
dimuat` dan menunjuk ke perintah di langkah 2. Tidak ada yang rusak; jalankan
langkah 2 lalu ulangi.

Delapan publikasi tidak punya lapisan teks dan hanya terbaca dengan OCR
(bagian 7.2). Di jalur B:

- kalau OCR **sudah dipasang** sebelum langkah 3, kedelapan publikasi itu
  di-OCR saat pembaruan, dan menambah ±5 jam (1.192 halaman × ±15 detik);
- kalau OCR **belum dipasang**, halaman tanpa teks dilewati dan
  publikasinya tercatat "perlu diperiksa". Publikasinya tetap ditemukan
  lewat judul dan abstrak, tanpa rincian tabel. Untuk mengisinya kemudian:
  pasang OCR, lalu jalankan `perbarui-data.bat --lokal --paksa` (membaca
  ulang semua PDF tanpa internet).

---

## 3. Menjalankan dan menghentikan aplikasi

**Menjalankan:** klik dua kali `jalankan-aplikasi.bat` di folder proyek.

Berkas ini akan:

1. memeriksa bahwa `venv` dan `.env` ada,
2. memeriksa bahwa MySQL bisa dihubungi dan port 5000 belum dipakai,
3. menjalankan server aplikasi di jendela hitam (Command Prompt) — tampil
   "Memuat aplikasi, biasanya 5-10 detik",
4. **membuka browser otomatis** ke `http://localhost:5000/` begitu server
   benar-benar siap menjawab. Tidak perlu membuka browser sendiri; kalau
   dibuka lebih dulu, yang tampil adalah halaman "tidak dapat dihubungi"
   karena server belum selesai memuat.

**Biarkan jendela hitam itu tetap terbuka** selama aplikasi dipakai.
Menutupnya = menghentikan aplikasi.

**Menghentikan:** tekan `Ctrl+C` di jendela hitam itu, atau tutup jendelanya.

Kalau muncul pesan `[GAGAL]`, bacalah — pesannya menyebut penyebab yang
paling umum:

| Pesan | Artinya | Yang dilakukan |
|---|---|---|
| `Folder venv tidak ditemukan` | Python belum disiapkan | Ikuti "Memasang program" di bagian 2 |
| `Berkas .env tidak ditemukan` | Konfigurasi belum ada | Salin `.env.example` ke `.env`, isi nilainya |
| `Can't connect` / `Connection refused` | MySQL belum jalan | Buka Laragon, klik **Start All**, coba lagi |
| `Access denied` | Sandi MySQL di `.env` salah | Periksa baris `DATABASE_URL` |
| `KONFIGURASI BELUM LENGKAP` | `SECRET_KEY` / `ADMIN_PASSWORD_HASH` kosong | Ikuti petunjuk yang tampil di pesan itu |
| `Port 5000 sudah dipakai` | Ada yang sudah memakai port itu — aplikasi ini di jendela lain, atau program lain | Pakai yang sudah jalan / tutup dulu jendela itu; kalau program lain, ganti port (di bawah) |
| `PORT di .env tidak valid` | Baris `PORT=` di `.env` bukan angka 1-65535 | Perbaiki atau kosongkan baris itu |
| `Server belum menjawab setelah 30 detik` | Server hidup tapi tidak merespons | Tutup jendela, jalankan lagi; kalau terulang, laporkan ke pengembang |

### Mengganti port

Port bawaan **5000**. Kalau port itu sudah dipakai program lain, ada dua
cara — keduanya sudah diuji:

- **Sekali jalan:** buka Command Prompt di folder proyek, ketik
  `jalankan-aplikasi.bat 8080` (ganti 8080 dengan port yang diinginkan).
- **Permanen:** tulis baris `PORT=8080` di berkas `.env`. Setelah itu klik
  dua kali `jalankan-aplikasi.bat` seperti biasa — tidak perlu argumen lagi.
  Argumen di baris perintah tetap menang kalau keduanya ada.

Setelah port diganti, **alamat di browser ikut berubah**: pencarian di
`http://localhost:8080/`, admin di `http://localhost:8080/admin/`. Browser
yang dibuka otomatis sudah mengarah ke alamat yang benar; yang perlu
diperbarui adalah bookmark atau alamat yang sudah dibagikan ke petugas.
Rincian untuk pemasangan di server ada di bagian 7.1.

Server yang dipakai adalah **waitress** (server produksi). Jangan
menjalankan `run.py --dev` di jaringan kantor — mode itu menyalakan debugger
yang bisa menjalankan kode dari browser; hanya untuk pengembangan.

---

## 4. Memperbarui data saat ada publikasi baru

BPS merilis publikasi baru secara berkala. Publikasi baru **tidak otomatis**
masuk ke aplikasi; jalankan pembaruan secara manual, misalnya seminggu
sekali atau setiap ada rilis.

Pembaruan memeriksa ke-14 wilayah satu per satu. Yang dikerjakan hanya:

- publikasi **baru**,
- publikasi yang **diperbarui BPS** (berkasnya diunduh ulang),
- publikasi yang PDF-nya **hilang atau rusak** di komputer ini.

Publikasi yang tidak berubah tidak dibaca ulang.

### Cara utama: dari halaman admin di browser

1. Pastikan komputer yang menjalankan aplikasi tersambung ke internet dan
   bisa menjangkau WebAPI BPS (`webapi.bps.go.id`).
2. Buka `http://localhost:5000/admin/`, masuk, klik kartu **Perbarui Data**
   (atau buka `/admin/perbarui`).
3. Baca penjelasan singkatnya, lalu klik **Mulai pembaruan**.
4. Kemajuan proses tampil langsung di halaman, baris demi baris. Tiap
   wilayah diawali baris seperti `halaman 3/24 ... OK`, kira-kira satu baris
   per detik. Itu tanda proses berjalan normal.
5. Begitu selesai, halaman menampilkan ringkasannya: tabel per wilayah
   (Diperbarui / Tidak ada yang baru / Sebagian gagal / Gagal), publikasi
   baru, dan jumlah bagian terindeks.

Yang perlu diketahui:

- **Menutup halaman tidak menghentikan pembaruan.** Prosesnya berjalan di
  server, bukan di browser. Halaman bisa dibuka lagi kapan saja untuk melihat
  kelanjutannya; kalau sudah selesai, ringkasannya yang tampil. Yang
  menghentikan pembaruan hanya mematikan aplikasinya (menutup jendela hitam).
- **Tidak bisa dijalankan dua kali bersamaan.** Selama pembaruan berjalan,
  tombolnya nonaktif dan halaman menampilkan "Pembaruan sedang berjalan" —
  termasuk kalau yang menjalankannya adalah tim IT lewat `perbarui-data.bat`
  di komputer yang sama. Dua pembaruan bersamaan bisa saling menimpa data,
  jadi aplikasi menolaknya di kedua arah.
- **Satu wilayah atau satu publikasi gagal tidak menghentikan yang lain.**
  Hasilnya "Pembaruan selesai sebagian": yang berhasil sudah bisa dicari,
  yang gagal tetap memakai data lamanya dan dicoba lagi pada pembaruan
  berikutnya.
- Kalau gagal seluruhnya, halaman menjelaskan sebabnya. Yang paling sering:
  WebAPI BPS tidak terjangkau (bagian 10). Data lama tetap utuh.
- Halaman ini tetap berfungsi tanpa JavaScript: halamannya memuat ulang
  sendiri tiap 5 detik sampai ringkasan tampil.

### Cara cadangan untuk tim IT: `perbarui-data.bat`

Melakukan hal yang persis sama dari jendela Command Prompt — berguna kalau
aplikasi sedang tidak berjalan atau halaman admin bermasalah. Pastikan MySQL
aktif, klik dua kali `perbarui-data.bat`, tunggu sampai selesai, tekan
sembarang tombol untuk menutup. Hasil run lewat `.bat` juga tampil di halaman
admin sebagai "Pembaruan terakhir".

Kalimat penutupnya ada empat macam:

| Tertulis | Artinya |
|---|---|
| `PEMBARUAN SELESAI.` | Semua wilayah beres. |
| `PEMBARUAN SELESAI SEBAGIAN` | Sebagian wilayah atau publikasi gagal. Yang berhasil sudah bisa dicari; baca rincian di atasnya, lalu ulangi lain waktu. |
| `PEMBARUAN GAGAL` | Tidak ada yang berhasil. Baca pesan di atasnya; biasanya jaringan (bagian 10). |
| `TIDAK DIJALANKAN: pembaruan lain sedang berjalan` | Pengelola sedang menjalankannya dari browser. Tunggu saja. |

Seluruh keluaran tiap run juga disimpan di `data\log_pembaruan\` (nama
berkasnya tercetak di baris kedua), dan ringkasannya di
`data\pembaruan_terakhir.json`.

### Berapa lama

- **Pembaruan rutin 14 wilayah: sekitar 2 menit.** Diukur 16 November 2026
  dari jaringan kantor ("BPS - Pegawai"): **107 detik**, dengan 1 publikasi
  baru.
  - Hampir seluruhnya (89 detik) adalah memeriksa daftar publikasi tiap
    wilayah, dengan jeda 1 detik per halaman sesuai ketentuan BPS.
  - Pemeriksaan tiap wilayah berhenti di halaman 4–7, begitu sampai ke
    publikasi yang lebih tua dari 2 tahun.
- **Tiap publikasi yang dikerjakan:** beberapa detik untuk PDF kecil.
  Contohnya publikasi baru 16 November 2026 (1,5 MB): unduh, baca, dan
  simpan ±4 detik. PDF besar lebih lama, karena membaca strukturnya butuh
  ±1,8 detik per MB (diukur saat memuat ulang semua PDF, 9 November 2026).
- **Publikasi tanpa lapisan teks**, kalau OCR dipasang: ±15 detik per
  halaman (bagian 7.2).
- **Penarikan besar** (wilayah baru, atau mengisi dari nol): berjam-jam.
  Lihat jalur B di bagian 2, dan jadwalkan sesudah pukul 01:00.

Unduhan PDF dari BPS kadang putus di tengah. Aplikasi mengulangnya sendiri
sampai 4 kali dengan jeda, lalu sekali lagi di akhir tiap wilayah. Unduhan
sengaja satu per satu, tidak paralel, supaya tidak membebani server BPS.

Selama pembaruan berjalan, Windows dicegah tidur. Ini **tidak** berlaku kalau
layar laptop ditutup: untuk run yang panjang, biarkan layar terbuka dan
laptop tersambung listrik.

Aplikasi **tidak perlu di-restart** setelah pembaruan — data baru langsung
bisa dicari, dan pencarian tetap bisa dipakai selama pembaruan berjalan.
Pencarian **pertama** sesudah pembaruan sedikit lebih lambat (kurang dari
satu detik di laptop pengembang), karena aplikasi memuat ulang data
pencarian ke memori. Itu normal.

Kalau pembaruan gagal di tengah jalan, tidak ada yang rusak: proses berhenti
dengan pesan, data lama tetap utuh, dan bisa diulang begitu penyebabnya
diperbaiki.

Catatan: pembaruan mengambil publikasi yang dirilis **2 tahun terakhir**
(tahun berjalan dan tahun sebelumnya), dihitung otomatis dari tanggal
komputer. Publikasi yang lebih lama tidak pernah masuk dan tidak dihapus
kalau sudah terlanjur ada.

### Pilihan tambahan untuk tim IT

Ditulis sesudah nama berkasnya di Command Prompt, misalnya
`perbarui-data.bat --lokal --paksa`. Tanpa pilihan apa pun = pembaruan biasa.

| Pilihan | Gunanya |
|---|---|
| `--lokal` | Tanpa internet. Hanya membaca PDF yang sudah ada di komputer; tidak ada yang diunduh. |
| `--paksa` | Membaca ulang **semua** publikasi, bukan hanya yang berubah. Dipakai sesudah program pembaca PDF diperbarui. `--lokal --paksa` untuk 306 PDF memakan 4.470 detik (±75 menit) pada 10 November 2026 dan 5.541 detik (±92 menit) pada 17 November 2026. |
| `--tanpa-ocr` | Tidak memakai OCR maupun cache-nya. Halaman tanpa teks dilewati dan dicatat. **Aplikasi menolak gabungan `--paksa --tanpa-ocr`** selama ada publikasi hasil OCR di wilayah aktif. Gabungan itu akan membaca ulang delapan publikasi OCR tanpa OCR, sehingga rincian tabelnya hilang dari database. Pembaruan berhenti sebelum database diubah, dengan pesan `TIDAK DIJALANKAN: --paksa dan --tanpa-ocr tidak boleh dipakai bersamaan` yang menyebut publikasinya. Untuk membaca ulang semua PDF, pakai `--paksa` saja: hasil OCR diambil dari cache, dan EasyOCR tidak perlu terpasang. |
| `--hanya-periksa` | Hanya memeriksa daftar semua wilayah; tidak mengubah database, tidak mengunduh. Wajib sebelum wilayah baru pertama kali dimuat (bagian 2 jalur B, bagian 8). |
| `--tahun-min 2024` | Mengambil publikasi yang dirilis sejak tahun itu, bukan hanya 2 tahun terakhir. |
| `--db-uji` | Menulis ke database uji, bukan database utama (bagian 9). |

Baris pertama keluaran selalu menyebut database yang akan ditulis, misalnya
`Database tujuan: db_pencarian_bps … (PRODUKSI)`.

### Halaman PDF perkiraan (`isi_perkiraan_halaman.py`)

Arti tombol "±hal. N" untuk petugas dijelaskan di bagian 1.

**Pembaruan biasa sudah mengisi perkiraan sendiri.** Setiap publikasi yang
dimuat lewat `perbarui-data.bat` atau tombol di halaman admin langsung
mendapat perkiraannya. Tidak ada langkah tambahan.

Skrip terpisah ini hanya untuk data yang sudah ada di database **sebelum**
fitur ini dipasang (16 November 2026), atau kalau perkiraannya perlu
dihitung ulang. Aman diulang kapan saja; run kedua tidak mengubah apa pun.

```bat
cd C:\sistem-pencarian-bps
venv\Scripts\python.exe scripts\isi_perkiraan_halaman.py --produksi --coba
venv\Scripts\python.exe scripts\isi_perkiraan_halaman.py --produksi
```

- **Database wajib disebut:**
  - `--produksi` untuk database utama;
  - `--db-uji` untuk database uji (bagian 9);
  - tanpa salah satunya, skrip menolak jalan.
- **`--coba`:** hanya menghitung dan melaporkan, tanpa menulis.
- **Yang ditulis:** hanya bagian yang punya nomor halaman cetak (angka)
  tetapi belum punya halaman PDF. Halaman PDF hasil pembacaan PDF tidak
  pernah diubah.
  - **Tabel/gambar/lampiran** diperkirakan dari tabel/gambar/lampiran di
    sekitarnya.
  - **Bab/subbab** diperkirakan HANYA dari tabel/gambar/lampiran. Tanpa itu,
    bab dibiarkan kosong (misalnya Booklet Sakernas), karena perkiraan dari
    bab lain terbukti sering meleset 1–2 halaman.
- **Penanda:** kolom `entri_dokumen.halaman_fisik_perkiraan`, yang
  ditambahkan otomatis.
- **Kalau pembaruan sedang berjalan,** skrip berhenti dengan "TIDAK
  DIJALANKAN" (kode keluar 2).
- **Lama:** beberapa detik untuk seluruh publikasi. Pencarian pertama sesudahnya
  sedikit lebih lambat, karena data dimuat ulang.

---

## 5. Menambah istilah pendek / sinonim lewat halaman admin

Petugas sering mengetik istilah singkat ("TPK", "PDRB") atau kata sehari-hari
("warga") yang tidak sama dengan istilah di judul tabel ("Tingkat Penghunian
Kamar", "penduduk"). Aplikasi punya **kamus sinonim** untuk menjembatani ini:
tiap kelompok punya satu **bentuk kanonik** dan beberapa **varian**; saat
mencari, varian diganti ke bentuk kanoniknya.

Cara menambah:

1. Buka `http://localhost:5000/admin/`, masukkan kata sandi admin.
2. Klik **Kamus Sinonim**.
3. Cari dulu dengan kotak "Cari kata di kamus" — mungkin kelompoknya sudah
   ada. Kalau ada, ketik varian baru di kotak "tambah varian" pada kelompok
   itu dan klik **Tambah**. Kalau belum ada, buka "Tambah kelompok baru",
   isi bentuk kanonik dan varian-variannya (dipisah koma).
4. **Klik tombol "Terapkan ke data"** di bagian atas halaman. Tanpa langkah
   ini, perubahan kamus **belum berpengaruh** pada pencarian. Hasilnya
   dilaporkan di halaman (berapa entri yang berubah). Lamanya, diukur 14
   November 2026 dengan 24.373 entri: **±2 detik** kalau tidak ada entri
   yang berubah, dan **±9 detik** kalau seluruh entri harus ditulis ulang.
   Perubahan kamus biasa jatuh di antara keduanya.

Untuk menghapus varian, klik tanda `×` di sebelah katanya, lalu Terapkan ke
data lagi.

Dari mana tahu istilah apa yang perlu ditambah? Menu **Review Log
Pencarian** di admin menampilkan kata kunci yang sering dicari petugas tapi
hasilnya kosong atau lemah. Itulah kandidat sinonim berikutnya. Menu
**Periksa** (`/admin/log/periksa?q=...`) memperlihatkan bagaimana sebuah
kata kunci diolah aplikasi — berguna untuk menebak kenapa ia tidak ketemu.

Dua aturan dari pengalaman:

- Jangan memetakan akronim yang bermakna ganda (mis. "PK" bisa banyak hal).
- Jangan memetakan kata penghubung Inggris (*of, and, by, in*) — merusak
  judul dwibahasa.

Kamus tersimpan di `data/kamus_sinonim.json`. Berkas ini ikut di Git, jadi
sebaiknya di-*commit* setelah diubah supaya tidak hilang.

Halaman admin juga bisa dipakai lebih dari satu orang bergantian —
sandinya satu untuk bersama, dan bisa diganti dari kartu **Ganti Kata Sandi**
(bagian 6). Tombol **Keluar** ada di pojok kanan atas.

---

## 6. Mengganti kata sandi admin

Cukup lewat browser, tidak perlu akses ke server:

1. Masuk ke `http://localhost:5000/admin/` dengan kata sandi yang berlaku.
2. Klik kartu **Ganti Kata Sandi** (atau buka `/admin/sandi`).
3. Isi kata sandi lama, kata sandi baru (minimal 8 karakter), dan ulangi
   kata sandi baru. Klik **Ganti kata sandi**.
4. Anda langsung dikeluarkan dan diminta masuk lagi. Masuk dengan sandi
   **baru** — kalau berhasil, berarti sandi baru sudah benar-benar berlaku.

Sandi baru berlaku seketika untuk semua orang; aplikasi **tidak perlu**
dijalankan ulang. Yang disimpan di `.env` hanya **hash**-nya, bukan sandi
aslinya, jadi tidak ada yang bisa "membaca" sandi dari berkas mana pun.

Kalau ditolak, pesannya menyebut sebabnya: sandi lama salah, kedua isian
sandi baru tidak sama, terlalu pendek, atau sama dengan sandi lama. Dalam
semua kasus itu tidak ada yang berubah.

**Kalau sandi lama lupa**, halaman ini tidak bisa dipakai (ia mensyaratkan
sandi lama). Jalur pemulihannya butuh akses ke server — lihat butir
"Pemulihan kata sandi admin" di bagian 7.

---

## 7. Yang perlu disiapkan tim IT untuk pemasangan di jaringan kantor

Aplikasi ini dikembangkan untuk berjalan di **satu komputer**, diakses dari
komputer itu sendiri (`localhost`). Ia **tidak** menyediakan HTTPS,
pembatasan alamat, atau pencadangan — itu di luar cakupan aplikasi dan
menjadi tanggung jawab infrastruktur. Kalau akan diakses dari komputer lain
di jaringan kantor, hal-hal berikut perlu disiapkan oleh tim IT:

| Kebutuhan | Keterangan |
|---|---|
| **Mendengarkan di jaringan** | Bawaan hanya `127.0.0.1`. Untuk diakses komputer lain, jalankan `venv\Scripts\python.exe run.py --host 0.0.0.0` (atau ubah `.bat`). Lakukan **hanya** setelah butir di bawah terpenuhi. |
| **Port** | Lihat 7.1. |
| **HTTPS** | Aplikasi melayani HTTP polos. Kata sandi admin dikirim saat login, jadi di jaringan bersama harus lewat HTTPS — pasang *reverse proxy* (IIS, nginx, Caddy) di depannya dengan sertifikat internal. |
| **Firewall / pembatasan akses** | Batasi port aplikasi hanya ke subnet PST. Idealnya `/admin/` dibatasi lebih ketat lagi (mis. hanya dari alamat tertentu) di proxy. |
| **Akses keluar ke BPS** | Hanya untuk pembaruan data: komputer ini harus bisa menjangkau `webapi.bps.go.id` lewat HTTPS, dan DNS jaringan harus mengarahkannya ke alamat yang benar (bagian 10). |
| **Memori** | Server aplikasi memakai ±174 MB (diukur 12 November 2026 dengan 306 publikasi). Data pencarian disimpan di memori server dan dimuat ulang sendiri sesudah pembaruan. |
| **Pencadangan** | Yang **tidak bisa dibuat ulang**: tabel `log_pencarian` (riwayat pencarian petugas), `data/kamus_sinonim.json`, `data/wilayah.json`, dan `.env`. Yang bisa dibuat ulang tetapi **mahal**: folder PDF `data/publikasi_pdf/` (±3 GB; mengunduh ulang 5,0 jam pada 9–10 November 2026) dan `data/ocr_cache/` (±22 MB; membuat ulang ±5 jam OCR). Cadangkan database berkala dengan `mysqldump`, contoh di bawah tabel ini. |
| **Menjalankan sebagai layanan** | Sekarang aplikasi berjalan di jendela Command Prompt yang harus dibiarkan terbuka. Untuk berjalan otomatis saat komputer menyala, daftarkan `jalankan-aplikasi.bat` di Task Scheduler (*At startup*) atau bungkus dengan NSSM sebagai Windows Service. |
| **Pembaruan berkala** | Pengelola bisa memperbarui dari halaman admin (bagian 4). Kalau ingin otomatis, `perbarui-data.bat` bisa dijadwalkan lewat Task Scheduler, mis. tiap Senin dini hari — pengaman "satu pembaruan pada satu waktu" tetap berlaku antara jadwal dan tombol di browser. Penarikan besar sebaiknya sesudah pukul 01:00 (bagian 2, jalur B). |
| **Kerahasiaan `.env`** | Berisi API key BPS dan sandi database. Jangan disalin ke tempat bersama; batasi hak baca berkasnya. Perhatikan: halaman Ganti Kata Sandi **menulis ulang** baris `ADMIN_PASSWORD_HASH` di berkas ini, jadi akun yang menjalankan aplikasi harus punya hak tulis ke `.env`. |
| **OCR (opsional)** | Lihat 7.2 dan 7.3. |
| **Pemulihan kata sandi admin** | Kalau pengelola lupa sandi, hanya bisa disetel ulang dari server: buka Command Prompt di folder proyek, jalankan `venv\Scripts\python.exe scripts\buat_hash_sandi.py`, ketik sandi baru dua kali (tidak tampil di layar, minimal 8 karakter), lalu salin baris `ADMIN_PASSWORD_HASH=...` yang dicetak ke `.env` menggantikan baris lama. Hentikan dan jalankan ulang aplikasi — jalur ini tidak membaca ulang `.env` secara otomatis. Prosedur yang sama dipakai saat pemasangan pertama (bagian 2). |

Contoh mencadangkan database, di Command Prompt. Tambahkan dulu folder
program MySQL ke PATH (langkah 1 jalur A di bagian 2); `-p` meminta sandi
root. Berkas hasilnya dipulihkan dengan langkah 2–3 jalur A:

```
mysqldump -u root -p --default-character-set=utf8mb4 --single-transaction --routines --triggers --events --hex-blob --no-tablespaces --result-file=cadangan.sql db_pencarian_bps
```

### 7.1 Mengganti port di server

Urutan prioritas port, dari yang paling kuat:

1. **Argumen baris perintah** — `run.py --port 8080` atau
   `jalankan-aplikasi.bat 8080`. Berlaku untuk sekali jalan itu saja.
2. **Baris `PORT=8080` di `.env`** — berlaku permanen, dibaca oleh `run.py`
   maupun `jalankan-aplikasi.bat`. Cocok untuk pemasangan di server: sekali
   ditulis, `.bat` dan Task Scheduler tidak perlu argumen.
3. **5000** kalau keduanya kosong.

Yang diperiksa sebelum server dinyalakan: kalau port sudah ada yang memakai,
aplikasi berhenti dengan pesan `Port 8080 sudah dipakai - kemungkinan
aplikasi ini sudah berjalan di jendela lain` (dan `[GAGAL] Port 8080 sudah
dipakai` dari `.bat`). Ini disengaja: di Windows dua server bisa mendengarkan
port yang sama tanpa galat, lalu permintaan jatuh ke salah satunya secara
acak — jadi aplikasi menolak berbagi port, dengan aplikasi lain maupun dengan
salinan dirinya sendiri. Nilai `PORT` yang bukan angka 1-65535 juga ditolak
saat mulai, dengan pesan `PORT di .env tidak valid`.

Setelah port diganti:

- Alamat di browser berubah menjadi `http://localhost:<port>/` — perbarui
  bookmark/alamat yang dibagikan ke petugas. `jalankan-aplikasi.bat` membuka
  browser ke alamat yang benar secara otomatis.
- Sesuaikan aturan firewall dan konfigurasi *reverse proxy* (butir HTTPS di
  atas) ke port yang baru.
- `perbarui-data.bat` tidak terpengaruh — ia tidak memakai port.

Diuji: port 5006-5009 lewat argumen `run.py`, argumen `.bat`, `PORT` di
`.env` untuk keduanya, dan argumen yang menimpa `.env`; serta penolakan
`PORT=abc` dan port yang sedang dipakai.

### 7.2 OCR untuk PDF tanpa lapisan teks (opsional)

Beberapa PDF BPS tidak punya lapisan teks: hurufnya berupa gambar atau kurva,
jadi tidak bisa dibaca seperti PDF biasa. Halaman seperti itu dibaca dengan
OCR (program EasyOCR). Pada 17 November 2026 ada **8 publikasi** hasil OCR di
database, seluruhnya 1.192 halaman.

- **OCR tidak wajib.** Tanpa paketnya, aplikasi dan pembaruan tetap jalan.
  Halaman tanpa teks dilewati dan dicatat; publikasinya masuk daftar "perlu
  diperiksa" di ringkasan pembaruan.
- **Hasil OCR yang sudah ada tetap terpakai tanpa memasang OCR**, selama
  folder `data/ocr_cache/` ikut dipindahkan dan PDF-nya tidak berganti
  (bagian 2, jalur A). OCR baru diperlukan untuk publikasi tanpa teks yang
  **baru** dirilis.
- **Memasang:** `venv\Scripts\python.exe -m pip install -r requirements-ocr.txt`
  (±1,1 GB; model ±94 MB diunduh otomatis saat pertama dipakai ke
  `%USERPROFILE%\.EasyOCR`).
- **Kapan dipakai:** hanya untuk publikasi yang **separuh atau lebih**
  halamannya tanpa teks. Halaman kosong atau sampul di PDF biasa tidak
  di-OCR.
- **Lambat:** ±15 detik per halaman tanpa kartu grafis (78 menit untuk 320
  halaman, 12 November 2026). Hasilnya disimpan di `data/ocr_cache/` dan
  tiap halaman hanya dikerjakan sekali.
- **Mematikan pada satu pembaruan:** `perbarui-data.bat --tanpa-ocr`.
- **Memisahkan pekerjaan berat:** `scripts\isi_cache_ocr.py` meng-OCR
  daftar publikasi tanpa menyentuh database dan bisa dilanjutkan kalau
  terputus. Cara pakainya tertulis di awal berkas itu.
- Server aplikasi tidak pernah memuat OCR, jadi kebutuhan memorinya tidak
  berubah.

Mutu hasil OCR lebih rendah daripada PDF bertekst; lihat bagian 11.

### 7.3 Hal terbuka: lisensi berkas model OCR

**Perlu dikonfirmasi saat serah terima, sebelum OCR dipakai di server BPS.**

EasyOCR mengunduh dua berkas model: `craft_mlt_25k.pth` (deteksi teks, dari
proyek CRAFT milik NAVER) dan `latin_g2.pth` (pengenalan huruf). **Lisensi
kedua berkas itu tidak dinyatakan di mana pun** (diperiksa 12 November
2026):

- kode CRAFT berlisensi MIT, dan bobotnya hanya dibagikan lewat tautan
  Google Drive tanpa keterangan lisensi;
- kode EasyOCR berlisensi Apache-2.0, dan halaman model hub JaidedAI tidak
  menyebut lisensi untuk berkas modelnya;
- halaman *Terms* JaidedAI yang menyebut "non-commercial" mengatur layanan
  web mereka, bukan berkas model.

Pemakaian internal BPS kemungkinan besar aman, tetapi itu kesimpulan
pengembang, bukan pernyataan lisensi. Kalau tidak disetujui, cukup jangan
pasang `requirements-ocr.txt`: aplikasi tetap berjalan tanpa OCR, dan hasil
OCR yang sudah ada di database tetap bisa dicari.

---

## 8. Mengelola daftar wilayah

Daftar wilayah ada di `data/wilayah.json`, berkas teks yang bisa dibuka
dengan Notepad. Perubahannya berlaku pada pembaruan berikutnya; tidak ada
kode yang perlu diubah.

- **Menghentikan pembaruan satu wilayah:** ubah `"aktif": true` menjadi
  `"aktif": false` pada baris wilayah itu. Publikasi yang sudah ada di
  database tidak dihapus.
- **Mengaktifkan wilayah yang belum punya data:** ubah menjadi
  `"aktif": true`, jalankan
  `venv\Scripts\python.exe scripts\perbarui.py --hanya-periksa`, pastikan
  hasilnya 0 tabrakan, baru jalankan pembaruan. Tanpa pemeriksaan itu,
  wilayah baru **dilewati** dan pembaruan berakhir "selesai sebagian".
  Pemeriksaan ini ada karena nomor publikasi BPS dianggap unik di semua
  wilayah, dan anggapan itu harus dibuktikan dulu untuk wilayah baru.
- **Publikasi yang sengaja tidak diambil:** daftar `kecualikan_judul`.
  Sekarang isinya satu pola, "Kecamatan … Dalam Angka", atas permintaan tim
  PST (9 November 2026): cakupan aplikasi sampai kabupaten/kota, tidak sampai
  kecamatan. Untuk mengambilnya lagi, ubah `"aktif"` pada pola itu menjadi
  `false`. Publikasi yang sudah ada di database tidak dihapus oleh
  pengecualian ini.
- **Singkatan wilayah** (`tala`, `batola`, `hss`, `hst`, `hsu`, `tanbu`,
  `bjm`, `bjb`) dipakai untuk mengenali wilayah dari kata kunci.
  - Daftar ini sudah dikonfirmasi tim IT BPS Kalimantan Selatan (16 November
    2026).
  - Kabupaten/kota yang tidak punya singkatan memang tidak punya singkatan
    resmi.
  - Kalau nanti diperlukan, singkatan baru bisa ditambahkan ke kolom
    `singkatan` wilayah itu di `data/wilayah.json`; aplikasi memakainya tanpa
    perlu dijalankan ulang.

### Membuka publikasi "Kecamatan … Dalam Angka" (kalau nanti diperlukan)

Sekarang publikasi ini sengaja tidak diambil (lihat di atas). Kalau tim PST
kelak membutuhkannya, ini perkiraan dan langkahnya.

**Perkiraan**, diukur 17 November 2026 dari daftar WebAPI BPS, belum
diunduh:

| | |
|---|---|
| Jumlah | **312 publikasi**: 156 rilis 2025 dan 156 rilis 2026, dari 13 kabupaten/kota. Paling banyak Kotabaru (44), Banjar (40), dan Barito Kuala (34); Banjarmasin dan Banjarbaru masing-masing 10. Provinsi tidak punya. |
| Ukuran | **±3,2 GB** menurut daftar BPS (per berkas angkanya bisa meleset, totalnya cukup akurat). Folder PDF sekarang ±3,0 GB, jadi kira-kira dua kali lipat. |
| Waktu unduh | Tergantung jaringan. Pada 9–10 November 2026, sebelum pukul 01:00 hanya 38–75 KB/detik per berkas (pada kecepatan itu 3,2 GB butuh lebih dari 12 jam); sesudah 01:00, 7–10 MB/detik (±10 menit). |
| Waktu membaca PDF | ±1,8 detik per MB, jadi **±1,5 jam** untuk 3,2 GB. PDF tanpa lapisan teks butuh OCR (±15 detik per halaman, bagian 7.2); jumlahnya belum diketahui. |
| Jumlah bagian terindeks | Belum diukur. |

**Langkah:**

1. **Cadangkan database** (bagian 7).
2. **Uji dulu di database uji** (bagian 9), jangan langsung di database
   utama:
   - di `data/wilayah.json`, pada pola "Kecamatan … Dalam Angka" di daftar
     `kecualikan_judul`, ubah `"aktif": true` menjadi `"aktif": false`;
   - jalankan `venv\Scripts\python.exe scripts\perbarui.py --db-uji`,
     sebaiknya mulai sesudah pukul 01:00.

   PDF yang terunduh disimpan di folder PDF yang sama, jadi langkah 4 nanti
   tidak mengunduh ulang.

   **Penting:** `data/wilayah.json` dipakai database uji DAN database utama.
   Selama polanya `false`, pembaruan biasa (tombol di halaman admin atau
   `perbarui-data.bat`) ikut menarik publikasi kecamatan ke database utama.
   Jangan jalankan pembaruan biasa sampai keputusan di langkah 4 atau 5
   diambil.
3. **Periksa mutunya di database uji** sebelum dibuka untuk petugas:
   - **Mutu pembacaan Daftar.** Format daftarnya sudah dikenali pembaca
     PDF, tetapi diketahui masih ada cacat (judul seksi di akhir halaman
     bisa menempel ke entri berikutnya). Buka 30 bagian acak dan cocokkan
     judul serta nomor halamannya dengan PDF-nya.
   - **Mutu hasil pencarian.** Tabel per kecamatan berjudul mirip (misalnya
     "Luas Wilayah Menurut Desa"), sehingga hasil pencarian kabupaten/kota
     bisa dipenuhi tabel kecamatan. Nama kecamatan juga tidak dikenali
     sebagai filter wilayah. Coba beberapa kata kunci yang biasa dipakai
     petugas.
4. **Kalau mutunya diterima,** jalankan `perbarui-data.bat` untuk database
   utama. Karena PDF-nya sudah ada, yang tersisa hanya membaca strukturnya
   (±1,5 jam).
5. **Kalau tidak jadi,** kembalikan `"aktif": true`. Pengecualian tidak
   menghapus publikasi yang sudah masuk database. Karena itu langkah 2
   dilakukan di database uji, yang bisa dihapus lalu dibuat ulang dari
   database utama (bagian 9).

---

## 9. Database uji dan cara menguji aplikasi

Segala percobaan yang bisa mengubah data dilakukan di **database uji**,
salinan terpisah bernama `db_pencarian_bps_uji` di server MySQL yang sama.
Database utama tidak disentuh.

Keduanya butuh program `mysql` dan `mysqldump`: isi `MYSQL_BIN` di `.env`
(bagian 2) kalau belum bisa dipanggil dari Command Prompt.

**Membuat database uji** (sekali; menyalin isi database utama):

```
venv\Scripts\python.exe scripts\siapkan_db_uji.py
```

Skrip ini hanya membaca database utama, dan tidak pernah menimpa: kalau
database uji sudah ada, ia berhenti. Salinan itu tidak ikut diperbarui. Untuk
menyegarkannya, hapus dulu database ujinya secara manual, lalu jalankan
lagi.

**Mencoba pembaruan tanpa menyentuh database utama:**
`perbarui-data.bat --db-uji`. Baris pertama keluarannya menyebut
`(UJI - bukan produksi)`.

**Menjalankan uji menyeluruh**, misalnya sesudah memperbarui Python, paket,
atau kode:

```
venv\Scripts\python.exe -u tests\uji_pipeline.py > uji_log.txt 2>&1
```

- Lamanya ±37 menit. Run penuh terakhir, 16 November 2026: 88 uji lulus,
  0 gagal, 0 dilewati, 2.235 detik.
- Hasilnya dibaca dari baris terakhir `uji_log.txt` dan dari kode keluar:

  | Kode keluar | Artinya |
  |---|---|
  | 0 | Semua uji lulus. |
  | 1 | Ada uji yang gagal; lihat baris `GAGAL:` di akhir `uji_log.txt`. |
  | 2 | Lingkungan belum siap; tidak ada yang dijalankan. Pesannya menyebut yang kurang. |

- Uji ini **tidak menghubungi BPS** (memakai server tiruan di komputer
  sendiri) dan **tidak mengubah database utama**. Database uji dikembalikan
  ke keadaan semula di akhir, dan keduanya dibuktikan di bagian `Z` keluaran.
- Syaratnya: MySQL aktif, database uji sudah dibuat, dan PDF Kabupaten Tapin
  ada di `data\publikasi_pdf\6305\`.
- Jangan menjalankan pembaruan selama uji berjalan.

---

## 10. Pemecahan masalah

### Pembaruan gagal terhubung, padahal situs BPS terbuka di browser

Gejalanya pesan `WebAPI BPS tidak bisa dihubungi` atau "connection reset".
Ini pernah terjadi di jaringan kantor pada awal November 2026. Penyebabnya
**DNS**, bukan jenis Wi-Fi: DNS internal mengarahkan `webapi.bps.go.id` ke
alamat dalam (`10.0.11.232`) yang menolak koneksi. Sejak 9 November 2026
gejala itu tidak muncul lagi.

Cara memeriksanya, di **PowerShell**:

```
Resolve-DnsName webapi.bps.go.id
```

- Hasil `203.123.60.70` (alamat yang benar pada 9 November 2026): DNS
  beres; periksa koneksi internetnya.
- Hasil `10.0.11.232`: DNS mengarah ke alamat yang salah. Perbaikannya di
  DNS jaringan.

Jalan sementara, **hanya oleh tim IT**: menambahkan baris
`203.123.60.70 webapi.bps.go.id` ke berkas hosts Windows, lalu menghapusnya
lagi sesudah DNS diperbaiki. Alamat itu bisa berubah. Cara ini belum pernah
dipakai selama pengembangan.

Tiap run pembaruan mencatat nama Wi-Fi dan alamat `webapi.bps.go.id` yang
dipakai, di baris `Jaringan:` pada keluarannya.

### Masalah lain

| Gejala | Sebab dan yang dilakukan |
|---|---|
| `TIDAK ADA YANG DIKERJAKAN: semua wilayah aktif … belum boleh dimuat` | Database masih kosong dan pemeriksaan wilayah belum dijalankan. Ikuti jalur B di bagian 2 (atau pulihkan cadangan, jalur A). |
| Satu wilayah `DILEWATI: belum lolos … --hanya-periksa` | Wilayah baru diaktifkan tanpa pemeriksaan. Lihat bagian 8. |
| `Response ended prematurely`, unduhan gagal | Unduhan dari BPS putus. Sudah diulang otomatis; yang tetap gagal dicoba lagi pada pembaruan berikutnya. Kalau sering, jalankan sesudah pukul 01:00. |
| Unduhan sangat lambat pada malam hari | Terukur 38–75 KB/detik pukul 20:30–00:00 (9 November 2026). Jadwalkan sesudah 01:00. |
| Ringkasan menulis "336/336 entri tanpa nomor halaman" untuk Master File Desa | Peringatan yang boleh diabaikan: publikasi itu tidak punya nomor halaman cetak, tetapi tombol PDF-nya tetap menuju halaman yang tepat. |
| Ringkasan menulis publikasi "perlu diperiksa" karena halaman tanpa teks | OCR tidak terpasang atau dimatikan. Lihat 7.2. |
| `Database belum memakai struktur multi-domain` | Database berasal dari versi lama aplikasi. Jalankan perintah yang tertulis di pesan itu, sekali. |
| `Program mysql tidak ada di MYSQL_BIN` | Baris `MYSQL_BIN` di `.env` menunjuk folder yang salah. Lihat tabel di bagian 2. |
| Pencarian pertama sesudah pembaruan terasa lambat | Normal; data pencarian dimuat ulang ke memori. Pencarian berikutnya cepat lagi. |
| Kata kunci "penduduk suku banjar" memasang filter Kab. Banjar | "Banjar" juga nama suku. Petugas mengklik **Batalkan** di pita. |
| Pembaruan macet karena komputer tidur | Layar laptop ditutup. Jalankan lagi; yang sudah selesai tidak diulang. |

---

## 11. Keterbatasan yang diketahui dan utang teknis

Semua ini sudah diperiksa dan **bukan bug** yang bisa diperbaiki dengan
mengulang pembaruan. Sebagian bisa diperbaiki dengan mengubah program; itu
didaftar di akhir bagian ini ("Utang teknis"). Angka tanpa tanggal lain
dihitung dari database pada 17 November 2026 (307 publikasi, 24.532 bagian).

**Cakupan**

- **Hanya publikasi yang dirilis 2 tahun terakhir** (bagian 4), dari 14
  wilayah. "Kecamatan … Dalam Angka" tidak diambil (bagian 8).
- **Pencarian tidak membaca isi sel tabel**, hanya judul tabel/gambar/
  lampiran/bab. Angka di dalam tabel tidak bisa dicari.
- **18 dari 307 publikasi hanya punya Daftar Isi** (misalnya direktori
  perusahaan dan buklet) — memang tidak ada daftar tabel di dokumennya.

**Nomor halaman dan tombol PDF**

- **21.187 dari 24.532 bagian (86,4%) punya nomor halaman PDF:**
  - **18.318 (74,7%) dibaca langsung dari PDF**; tombolnya **Buka PDF hal. N**.
  - **2.869 (11,7%) perkiraan**; tombolnya **Buka PDF ±hal. N** (bagian 1):
    - 1.040 tabel/gambar/lampiran. Dari 60 yang diperiksa (16 November
      2026), 56 tepat, 3 meleset 2–3 halaman, dan 1 menunjuk tabel yang
      tidak dicetak di publikasinya.
    - 1.829 bab/subbab. Dari 50 yang diperiksa (16 November 2026), 48 tepat
      dan 2 meleset 1–2 halaman.
- **3.345 bagian tanpa nomor halaman PDF** membuka PDF dari halaman pertama.
  Nomor halaman cetaknya, kalau ada, tetap ditampilkan.
  - **1.252 tabel/gambar/lampiran.** Perkiraan tidak dibuat untuk mereka,
    karena tidak ada tabel tetangga yang cukup dekat dan konsisten, atau
    tidak ada nomor halaman cetaknya. Contohnya semua publikasi Keadaan
    Angkatan Kerja.
  - **2.093 bab/subbab:**
    - 930 di halaman depan bernomor romawi (Kata Pengantar, Daftar Isi);
    - sisanya di publikasi tanpa tabel di dekatnya, misalnya Booklet
      Sakernas.
- **Pembacaan Daftar Isi/Tabel diperbaiki 16 November 2026.** Contohnya:
  - Balangan PDRB Pengeluaran "2.6 Ekspor dan Impor" kini "Halaman 35";
    dulu "Halaman vii".
  - Judul seperti "Inventory 3.7 Perkembangan Ekspor" (PDRB Kotabaru, Tanah
    Bumbu) kini bersih.
  - Entri sampah berjudul "Halaman" sudah dibuang.
  - Daftar Isi Gambaran Ekonomi Makro tidak lagi tergabung menjadi beberapa
    gumpalan.
  - Daftar Tabel Kabupaten Tabalong Dalam Angka 2025 kini terbaca seluruhnya
    (17 November 2026): dari 25 menjadi 100 tabel.
- **Sisa yang diketahui:**
  - Di Gambaran Ekonomi Makro, beberapa entri halaman depan masih tergabung
    ("Kata Pengantar v Daftar Isi").
  - Sebagian judul masih berekor nomor halaman romawi ("… 2025 xiv").
  - Di Tabalong Dalam Angka 2025, 6 tabel masih tergabung ke tabel
    sebelumnya, karena nomor halamannya dicetak miring (lihat "Utang
    teknis").
- **200 bagian (0,8%) tidak punya nomor halaman sama sekali.**
- **Nomor halaman di Daftar Tabel kadang keliru di publikasinya sendiri.**
  Contohnya Daftar Lampiran PDRB Kotabaru menurut Lapangan Usaha menulis
  121–127, padahal tabelnya di halaman cetak 123–129. Perkiraan "±hal." untuk
  bagian seperti itu ikut meleset.
- Nomor halaman cetak dan nomor halaman PDF sering berbeda. Itu sebabnya
  keduanya ditampilkan dengan label berbeda ("Halaman" dan "Halaman PDF").
- **Master File Desa** tidak punya nomor halaman cetak sama sekali (tiap
  edisi 334–336 bagian), tetapi semuanya punya nomor halaman PDF.

**Mutu pembacaan PDF**

- **Publikasi provinsi:** sekitar 2,5–3% entri dari badan dokumen sedikit
  cacat — misalnya judul tabel tercampur sepotong teks di sekitarnya.
  Lokasinya tetap benar.
- **Publikasi kabupaten/kota:** dari 40 entri yang diperiksa acak pada 10
  November 2026, 33 benar.
- **Publikasi hasil OCR (8 publikasi):** dari 30 entri yang diperiksa acak
  pada 13 November 2026, 25 dapat ditemukan dengan benar; sisanya nomor
  tabelnya hilang, judulnya tercampur, atau halamannya meleset. Di PDRB
  Tabalong dan PDRB Banjarbaru menurut Lapangan Usaha, sebagian besar tabel
  tidak punya nomor.
- **Ada entri yang terlalu panjang** karena beberapa judul tabel tergabung
  jadi satu saat dibaca dari PDF. Akibatnya kadang muncul hasil yang
  "mengandung semua kata kunci" tapi sebenarnya bukan tabel yang dicari.
- **Sebagian entri berupa potongan baris**, misalnya potongan judul bahasa
  Inggris tanpa nomor, terutama di "Dalam Angka".
- **Kesalahan di PDF sumbernya sendiri** ikut terbawa. Contoh: Daftar Tabel
  Kotabaru Dalam Angka 2026 mencetak nomor halaman yang tidak berurutan, dan
  tiga "Dalam Angka" mencetak nomor gambar yang sama dua kali.

**Pencarian**

- **Ambang relevansi (75% "ditemukan", 50-74% "mungkin Anda cari") masih
  angka sementara**, ditetapkan dari sedikit kueri uji. Kalau setelah
  dipakai petugas terasa terlalu ketat/longgar, angkanya ada di
  `app/services/mesin_pencari.py` (`AMBANG_DITEMUKAN`, `AMBANG_SARAN`).
- **"Banjar" juga nama suku**, jadi kata kunci yang memuatnya memasang
  filter Kab. Banjar; petugas membatalkannya lewat pita.
- **Provinsi tidak dikenali dari kata kunci**, hanya bisa dipilih dari
  daftar wilayah.

**Pengelolaan**

- **Satu kata sandi admin untuk semua** — tidak ada akun per orang, jadi
  tidak bisa dilacak siapa yang mengubah kamus.
- **Lisensi berkas model OCR belum jelas** (7.3).

**Hal yang masih terbuka saat serah terima**

- **Lisensi berkas model OCR** perlu dikonfirmasi sebelum OCR dipasang di
  server BPS (7.3).
- **Ambang relevansi 75/50 belum diuji dengan kata kunci asli petugas.**
  Pemeriksaan 17 November 2026 memakai 18 kata kunci uji dan tidak
  menemukan alasan kuat untuk mengubahnya. Kata kunci petugas terkumpul di
  **Review Log Pencarian** (bagian 5) begitu aplikasi dipakai.
- **Jalur B** (mengisi data dari nol) belum diuji ujung ke ujung (bagian 2).
- **Menyalin folder PDF dan cache OCR ke komputer lain** belum dicoba. Cara
  menyalinnya sudah diuji di satu laptop (bagian 2, jalur A).

**Utang teknis**

Perbaikan yang sudah diketahui tetapi sengaja belum dikerjakan. Kecuali
kamus sinonim, semuanya menyangkut program pembaca PDF atau penilaian skor,
jadi perlu pengembang.
Rinciannya ada di laporan `data/regresi/` yang disebut, dan di `CLAUDE.md`.

| Hal | Akibat bagi petugas | Laporan |
|---|---|---|
| Beberapa judul tabel kadang terbaca sebagai satu bagian | Hasil yang memuat semua kata kunci tetapi bukan tabel yang dicari | `CLAUDE.md`, "Utang teknis: 764 entri terlalu panjang" |
| Kamus sinonim belum memuat beberapa istilah: "konsumsi listrik" (judulnya "listrik terjual"/"kWh"), "menginap hotel" (judulnya "wisatawan"/"tamu"); "rawat inap" ikut cocok dengan "menginap" | Tabel yang relevan berskor rendah atau tidak tampil. Dua istilah pertama bisa ditambah pengelola lewat halaman admin (bagian 5); "inap" perlu pengembang, karena kata dasarnya sama | `validasi-ambang-20261117.md` |
| Judul menulis "P 1" terpisah, sehingga kata kunci "p1" lemah | Hanya 10 dari 57 tabel P1 yang tampil | `validasi-ambang-20261117.md` |
| Judul tabel yang panjang dan lengkap kalah dari judul bab yang pendek | Tabel TPK dan luas panen jatuh ke skor 70–75 | `validasi-ambang-20261117.md` |
| Teks miring dibuang bersama watermark | Di Tabalong Dalam Angka 2025, 6 tabel tergabung ke tabel sebelumnya. Perbaikannya dicoba 17 November 2026, lalu dibatalkan karena memperburuk publikasi lain; usulan perbaikannya tersimpan | `saringan-miring-20261117.md` |
| Saat versi Daftar dan versi badan sebuah judul berbeda, yang lebih panjang dipakai | 4 judul membawa sampah, padahal versi bersihnya ada | `perbaikan-daftar-20261107.md` |
| Sisa pembacaan Daftar: entri halaman depan Gambaran Ekonomi Makro dan IPM tergabung, folio romawi di baris sendiri menempel ke judul, lanjutan judul di halaman Daftar berikutnya, Indikator Pekerjaan Layak Provinsi 2025 | Judul bercampur; lokasinya tetap benar | `parser-daftar-isi-20261116.md` |
| KAK Agustus 2024: awal judul 5 tabel menempel ke tabel sebelumnya | Judul terpotong di depan | `C2-nomor-sebaris-20261109.md` |
| Luas Panen dan Produksi Padi Provinsi (dua edisi): nomor dan halaman lampiran di Daftar tertukar | ±140 lampiran bernomor salah | `perkiraan-halaman-20261116.md` |
| Grafik bertumpuk di badan "Dalam Angka" belum dibaca sebagai bagian baru | Grafik yang tidak tercantum di Daftar Gambar tidak bisa dicari. Sejak 12 November 2026 Daftar Gambar Dalam Angka terbaca, jadi sisanya sedikit | `C1b-perkiraan-20261109.md` |
| Daftar Gambar yang baru terbaca membawa 23 potongan tanpa nomor; 3 nomor gambar dicetak dua kali di sumbernya | Bagian sampah di hasil; gambar kembar kedua menunjuk halaman gambar pertama | `batas-heading-20261112.md` |
| Hasil OCR: sebagian besar tabel PDRB Tabalong dan PDRB Banjarbaru menurut Lapangan Usaha tanpa nomor | Tabel ditemukan lewat judul, tetapi nomornya tidak tampil | `ocr-pemuatan-20261113.md` |
| Heading Daftar yang terbelah dua baris (Statistik Daerah 2025) tidak dibaca dari Daftar | Gambarnya tetap masuk lewat badan dokumen | `halaman-daftar-dan-isi-20261107.md` |
| Belum ada uji otomatis per fungsi; yang ada `tests\uji_pipeline.py` (bagian 9) | Perubahan program perlu diperiksa ulang manual, seperti di laporan-laporan di atas | `CLAUDE.md`, "Tidak ada pengujian otomatis" |

Rincian teknis yang lebih dalam (cara kerja pembaca PDF, rumus skor, riwayat
keputusan) ada di `CLAUDE.md` di folder yang sama, dan laporan tiap
pemeriksaan ada di `data/regresi/` — ditulis untuk pengembang, bukan untuk
operasional.
