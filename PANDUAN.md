# Panduan Pengoperasian — Sistem Pencarian Publikasi BPS Kalsel

Panduan ini ditujukan untuk tim IT BPS Provinsi Kalimantan Selatan yang
menerima serah terima aplikasi. Tidak perlu tahu Python atau Flask untuk
mengikuti panduan ini; cukup terbiasa dengan komputer Windows, folder, dan
berkas teks.

Kata sandi admin dan isi berkas `.env` (yang memuat API key dan sandi
database) **diserahkan terpisah** — tidak ditulis di panduan ini dan tidak
disimpan di Git.

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

1. Daftar publikasi BPS Kalsel diambil dari WebAPI BPS (hanya publikasi
   yang **dirilis dalam 2 tahun terakhir**).
2. Berkas PDF tiap publikasi diunduh dan dibaca strukturnya: Daftar Isi,
   Daftar Tabel, Daftar Gambar, Daftar Lampiran, serta keterangan
   tabel/gambar di badan dokumen.
3. Hasilnya disimpan di database MySQL. Pencarian berjalan terhadap
   database ini — **tidak** menghubungi BPS setiap kali petugas mencari,
   jadi pencarian berjalan tanpa internet.

Yang butuh internet (khususnya jaringan **"BPS - Pegawai"**) hanya langkah
pembaruan data (bagian 4).

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

---

## 2. Yang harus tersedia di komputer

- **Windows** (dikembangkan dan diuji di Windows 11).
- **Python 3.12 atau lebih baru** (dikembangkan dengan 3.14). Saat
  memasang Python, centang *"Add Python to PATH"*.
- **MySQL 8** — selama pengembangan dipakai lewat **Laragon**. Database
  bernama `db_pencarian_bps` harus sudah dibuat (kosong pun tidak apa-apa;
  tabelnya dibuat otomatis saat data dimuat pertama kali).
- Folder proyek ini (`sistem-pencarian-bps`) beserta subfolder
  `data/publikasi_pdf/` yang berisi PDF publikasi (~650 MB). Kalau folder
  PDF-nya kosong, langkah pembaruan data (bagian 4) akan mengunduh semuanya
  — butuh waktu sekitar 30-40 menit di jaringan kantor.

### Pemasangan pertama kali (sekali saja)

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
| `DATABASE_URL` | `mysql+pymysql://root:SANDI@localhost:3306/db_pencarian_bps` — ganti `SANDI` dengan sandi root MySQL |
| `PORT` | Opsional. Port server; kosong = 5000. Isi kalau 5000 sudah dipakai program lain (bagian 3). |

Aplikasi **menolak berjalan** kalau `SECRET_KEY` atau `ADMIN_PASSWORD_HASH`
kosong, dan menampilkan pesan yang menjelaskan cara mengisinya. Ini
disengaja: lebih baik tidak jalan daripada jalan tanpa pengaman.

Setelah `.env` terisi, jalankan `perbarui-data.bat` sekali (bagian 4) untuk
mengisi database pertama kali, lalu `jalankan-aplikasi.bat` (bagian 3).
Pembaruan berikutnya bisa dilakukan pengelola dari browser.

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
| `Folder venv tidak ditemukan` | Python belum disiapkan | Ikuti "Pemasangan pertama kali" di bagian 2 |
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
Rincian untuk pemasangan di server ada di bagian 7.

Server yang dipakai adalah **waitress** (server produksi). Jangan
menjalankan `run.py --dev` di jaringan kantor — mode itu menyalakan debugger
yang bisa menjalankan kode dari browser; hanya untuk pengembangan.

---

## 4. Memperbarui data saat ada publikasi baru

BPS Kalsel merilis publikasi baru secara berkala. Publikasi baru **tidak
otomatis** masuk ke aplikasi; jalankan pembaruan secara manual, misalnya
seminggu sekali atau setiap ada rilis.

### Cara utama: dari halaman admin di browser

1. Pastikan komputer yang menjalankan aplikasi tersambung ke jaringan
   **"BPS - Pegawai"**. Jaringan "BPS - Tamu" **memblokir** WebAPI BPS.
2. Buka `http://localhost:5000/admin/`, masuk, klik kartu **Perbarui Data**
   (atau buka `/admin/perbarui`).
3. Baca penjelasan singkatnya, lalu klik **Mulai pembaruan**.
4. Kemajuan proses tampil langsung di halaman, baris demi baris — di tahap
   pertama muncul `halaman 12/66 ... OK` kira-kira satu baris per detik. Itu
   tanda proses berjalan normal.
5. Begitu selesai, halaman menampilkan ringkasannya: berapa publikasi baru
   dan berapa bagian terindeks, atau "Tidak ada publikasi baru".

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
- Kalau gagal, halaman menjelaskan sebabnya dengan bahasa biasa. Yang paling
  sering: tidak tersambung ke "BPS - Pegawai". Data lama tetap utuh, tinggal
  coba lagi setelah jaringan beres.
- Halaman ini tetap berfungsi tanpa JavaScript: halamannya memuat ulang
  sendiri tiap 5 detik sampai ringkasan tampil.

### Cara cadangan untuk tim IT: `perbarui-data.bat`

Melakukan hal yang persis sama dari jendela Command Prompt — berguna kalau
aplikasi sedang tidak berjalan atau halaman admin bermasalah. Pastikan MySQL
aktif, klik dua kali `perbarui-data.bat`, tunggu `PEMBARUAN SELESAI`, tekan
sembarang tombol untuk menutup. Kalau muncul `TIDAK DIJALANKAN: pembaruan
lain sedang berjalan`, berarti pengelola sedang menjalankannya dari browser —
tunggu saja. Hasil run lewat `.bat` juga tampil di halaman admin sebagai
"Pembaruan terakhir".

### Berapa lama

- **Tidak ada publikasi baru:** sekitar 2 menit (memeriksa 65+ halaman
  daftar di WebAPI, dengan jeda 1 detik per halaman sesuai ketentuan BPS).
- **Ada publikasi baru:** ditambah sekitar 20-90 detik per publikasi
  (unduh PDF + membaca strukturnya). Hanya publikasi baru yang diproses;
  yang lama tidak dibaca ulang.

Aplikasi **tidak perlu di-restart** setelah pembaruan — data baru langsung
bisa dicari, dan pencarian tetap bisa dipakai selama pembaruan berjalan.

Kalau pembaruan gagal di tengah jalan, tidak ada yang rusak: proses berhenti
dengan pesan, data lama tetap utuh, dan bisa diulang begitu penyebabnya
diperbaiki.

Catatan: pembaruan mengambil publikasi yang dirilis **2 tahun terakhir**
(tahun berjalan dan tahun sebelumnya), dihitung otomatis dari tanggal
komputer. Publikasi yang lebih lama tidak pernah masuk dan tidak dihapus
kalau sudah terlanjur ada.

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
   ini, perubahan kamus **belum berpengaruh** pada pencarian. Prosesnya
   sekitar 2 detik dan hasilnya dilaporkan di halaman (berapa entri yang
   berubah).

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
| **Port** | Lihat "Mengganti port di server" di bawah tabel ini. |
| **HTTPS** | Aplikasi melayani HTTP polos. Kata sandi admin dikirim saat login, jadi di jaringan bersama harus lewat HTTPS — pasang *reverse proxy* (IIS, nginx, Caddy) di depannya dengan sertifikat internal. |
| **Firewall / pembatasan akses** | Batasi port aplikasi hanya ke subnet PST. Idealnya `/admin/` dibatasi lebih ketat lagi (mis. hanya dari alamat tertentu) di proxy. |
| **Pencadangan database** | Database `db_pencarian_bps` bisa dibangun ulang dari WebAPI dan PDF (bagian 4), kecuali tabel `log_pencarian` (riwayat pencarian petugas) yang tidak bisa dipulihkan. Cadangkan berkala dengan `mysqldump`. Cadangkan juga `data/kamus_sinonim.json` dan `.env`. |
| **Menjalankan sebagai layanan** | Sekarang aplikasi berjalan di jendela Command Prompt yang harus dibiarkan terbuka. Untuk berjalan otomatis saat komputer menyala, daftarkan `jalankan-aplikasi.bat` di Task Scheduler (*At startup*) atau bungkus dengan NSSM sebagai Windows Service. |
| **Pembaruan berkala** | Pengelola bisa memperbarui dari halaman admin (bagian 4). Kalau ingin otomatis, `perbarui-data.bat` bisa dijadwalkan lewat Task Scheduler, mis. tiap Senin pagi, di komputer yang tersambung "BPS - Pegawai" — pengaman "satu pembaruan pada satu waktu" tetap berlaku antara jadwal dan tombol di browser. |
| **Kerahasiaan `.env`** | Berisi API key BPS dan sandi database. Jangan disalin ke tempat bersama; batasi hak baca berkasnya. Perhatikan: halaman Ganti Kata Sandi **menulis ulang** baris `ADMIN_PASSWORD_HASH` di berkas ini, jadi akun yang menjalankan aplikasi harus punya hak tulis ke `.env`. |
| **OCR untuk PDF tanpa teks (opsional)** | Beberapa PDF BPS tidak punya lapisan teks: hurufnya berupa gambar atau kurva. Halaman seperti itu dibaca dengan OCR (EasyOCR). OCR **tidak wajib**: tanpa paketnya, aplikasi dan pembaruan tetap jalan, dan halaman tanpa teks hanya dilewati dan dicatat. Memasangnya: `venv\Scripts\python.exe -m pip install -r requirements-ocr.txt` (±1,1 GB; model ±94 MB diunduh otomatis saat pertama dipakai ke `%USERPROFILE%\.EasyOCR`). OCR lambat (±15 detik per halaman), jadi hasilnya disimpan di `data/ocr_cache/` dan hanya dikerjakan sekali per halaman. Untuk mematikan OCR pada satu pembaruan: `perbarui-data.bat --tanpa-ocr`. Server web tidak pernah memuat OCR, jadi kebutuhan memorinya tidak berubah. |
| **Pemulihan kata sandi admin** | Kalau pengelola lupa sandi, hanya bisa disetel ulang dari server: buka Command Prompt di folder proyek, jalankan `venv\Scripts\python.exe scripts\buat_hash_sandi.py`, ketik sandi baru dua kali (tidak tampil di layar, minimal 8 karakter), lalu salin baris `ADMIN_PASSWORD_HASH=...` yang dicetak ke `.env` menggantikan baris lama. Hentikan dan jalankan ulang aplikasi — jalur ini tidak membaca ulang `.env` secara otomatis. Prosedur yang sama dipakai saat pemasangan pertama (bagian 2). |

### Mengganti port di server

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

---

### Hal terbuka yang perlu dikonfirmasi saat serah terima

- **Lisensi berkas model OCR.** EasyOCR mengunduh dua berkas model:
  `craft_mlt_25k.pth` (deteksi teks, dari proyek CRAFT milik NAVER) dan
  `latin_g2.pth` (pengenalan huruf). **Lisensi kedua berkas itu tidak
  dinyatakan di mana pun** (diperiksa 12 Nov 2026):
  - kode CRAFT berlisensi MIT, dan bobotnya hanya dibagikan lewat tautan
    Google Drive tanpa keterangan lisensi;
  - kode EasyOCR berlisensi Apache-2.0, dan halaman model hub JaidedAI tidak
    menyebut lisensi untuk berkas modelnya;
  - halaman *Terms* JaidedAI yang menyebut "non-commercial" mengatur layanan
    web mereka, bukan berkas model.

  Pemakaian internal BPS kemungkinan besar aman, tetapi itu kesimpulan,
  bukan pernyataan lisensi. **Perlu konfirmasi tim IT/mentor** sebelum OCR
  dipakai di server BPS. Kalau tidak disetujui, cukup jangan pasang
  `requirements-ocr.txt`: aplikasi tetap berjalan tanpa OCR.

## 8. Keterbatasan yang diketahui

Semua ini sudah diperiksa dan **bukan bug** yang bisa diperbaiki dengan
mengulang pembaruan:

- **Sekitar 2,5-3% entri dari badan dokumen sedikit cacat** — misalnya
  judul tabel tercampur sepotong teks di sekitarnya. Judul yang tampil di
  hasil pencarian mungkin sedikit "kotor", tapi lokasinya benar.
- **Beberapa entri tidak punya nomor halaman** (paling banyak di "Kalimantan
  Selatan Dalam Angka", 15 dari 348 entri edisi 2025). Tombol PDF-nya tetap
  membuka publikasinya, hanya tidak melompat ke halaman.
- **Publikasi "Master File Desa" tidak punya entri sama sekali.** Publikasi
  itu memang tidak punya Daftar Isi/Tabel konvensional. Ia tetap muncul di
  pencarian sebagai publikasi (dicocokkan lewat judul dan abstrak), tanpa
  rincian bagian.
- **Lima publikasi hanya punya Daftar Isi** (direktori perusahaan, Statistik
  Daerah, Buklet Sakernas) — memang tidak ada daftar tabel di dokumennya.
- **Ada entri yang terlalu panjang** karena beberapa judul tabel tergabung
  jadi satu saat dibaca dari PDF. Akibatnya kadang muncul hasil yang
  "mengandung semua kata kunci" tapi sebenarnya bukan tabel yang dicari.
- **Ambang relevansi (75% "ditemukan", 50-74% "mungkin Anda cari") masih
  angka sementara**, ditetapkan dari sedikit kueri uji. Kalau setelah
  dipakai petugas terasa terlalu ketat/longgar, angkanya ada di
  `app/services/mesin_pencari.py` (`AMBANG_DITEMUKAN`, `AMBANG_SARAN`).
- **Pencarian tidak membaca isi sel tabel**, hanya judul tabel/gambar/
  lampiran/bab. Angka di dalam tabel tidak bisa dicari.
- **Hanya publikasi yang dirilis 2 tahun terakhir** (lihat bagian 4).
- **Satu kata sandi admin untuk semua** — tidak ada akun per orang, jadi
  tidak bisa dilacak siapa yang mengubah kamus.

Rincian teknis yang lebih dalam (cara kerja parser PDF, rumus skor, riwayat
keputusan) ada di `CLAUDE.md` di folder yang sama — ditulis untuk
pengembang, bukan untuk operasional.
