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
| `ADMIN_PASSWORD_HASH` | Hash kata sandi admin. Buat dengan `venv\Scripts\python.exe scripts\buat_hash_sandi.py` (lihat bagian 6) |
| `BPS_API_KEY` | API key WebAPI BPS, dari https://webapi.bps.go.id/developer/ |
| `DATABASE_URL` | `mysql+pymysql://root:SANDI@localhost:3306/db_pencarian_bps` — ganti `SANDI` dengan sandi root MySQL |

Aplikasi **menolak berjalan** kalau `SECRET_KEY` atau `ADMIN_PASSWORD_HASH`
kosong, dan menampilkan pesan yang menjelaskan cara mengisinya. Ini
disengaja: lebih baik tidak jalan daripada jalan tanpa pengaman.

Setelah `.env` terisi, jalankan `perbarui-data.bat` sekali (bagian 4) untuk
mengisi database, lalu `jalankan-aplikasi.bat` (bagian 3).

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
| `Port 5000 sudah dipakai` | Aplikasi sudah jalan di jendela lain | Pakai yang sudah jalan, atau tutup dulu jendela itu |
| `Server belum menjawab setelah 30 detik` | Server hidup tapi tidak merespons | Tutup jendela, jalankan lagi; kalau terulang, laporkan ke pengembang |

Port bawaan 5000. Kalau bentrok dengan aplikasi lain, jalankan dengan port
lain: `jalankan-aplikasi.bat 8080`.

Server yang dipakai adalah **waitress** (server produksi). Jangan
menjalankan `run.py --dev` di jaringan kantor — mode itu menyalakan debugger
yang bisa menjalankan kode dari browser; hanya untuk pengembangan.

---

## 4. Memperbarui data saat ada publikasi baru

BPS Kalsel merilis publikasi baru secara berkala. Publikasi baru **tidak
otomatis** masuk ke aplikasi; jalankan pembaruan secara manual, misalnya
seminggu sekali atau setiap ada rilis.

1. Pastikan komputer tersambung ke jaringan **"BPS - Pegawai"**. Jaringan
   "BPS - Tamu" **memblokir** WebAPI BPS — pembaruan akan gagal dengan pesan
   soal jaringan.
2. Pastikan MySQL aktif (Laragon → Start All).
3. Klik dua kali `perbarui-data.bat`.
4. Tunggu sampai muncul `PEMBARUAN SELESAI`. Jendela tetap terbuka supaya
   ringkasannya bisa dibaca; tekan sembarang tombol untuk menutup.

Selama berjalan, layar terus menampilkan kemajuan: di tahap pertama baris
`halaman 12/65 ... OK` muncul satu per satu (sekitar satu baris per detik),
di tahap ekstraksi muncul nama publikasi yang sedang dibaca. Kalau layar
diam lebih dari satu menit tanpa baris baru, barulah patut dicurigai.

Berapa lama:

- **Tidak ada publikasi baru:** sekitar 2 menit (memeriksa 65+ halaman
  daftar di WebAPI, dengan jeda 1 detik per halaman sesuai ketentuan BPS).
- **Ada publikasi baru:** ditambah sekitar 20-90 detik per publikasi
  (unduh PDF + membaca strukturnya). Hanya publikasi baru yang diproses;
  yang lama tidak dibaca ulang.

Aplikasi **tidak perlu di-restart** setelah pembaruan — data baru langsung
bisa dicari. Aplikasi juga boleh tetap berjalan selama pembaruan.

Kalau pembaruan gagal di tengah jalan, tidak ada yang rusak: proses berhenti
dengan pesan, data lama tetap utuh, dan bisa diulang begitu penyebabnya
diperbaiki. Penyebab paling umum adalah jaringan.

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
sandinya satu untuk bersama. Tombol **Keluar** ada di pojok kanan atas.

---

## 6. Mengganti kata sandi admin

Sandi tidak disimpan di mana pun dalam bentuk asli — yang disimpan di `.env`
hanya **hash**-nya. Mengganti sandi berarti membuat hash baru:

1. Buka Command Prompt di folder proyek.
2. Jalankan `venv\Scripts\python.exe scripts\buat_hash_sandi.py`.
3. Ketik sandi baru dua kali (tidak tampil di layar; minimal 8 karakter).
4. Script mencetak satu baris `ADMIN_PASSWORD_HASH=...`. Salin baris itu ke
   `.env`, menggantikan baris lama.
5. Hentikan dan jalankan ulang aplikasi (`.env` hanya dibaca saat mulai).

Semua yang sedang login otomatis diminta masuk lagi begitu aplikasi
dijalankan ulang.

Kalau sandi lupa, tidak ada cara memulihkannya — langsung buat yang baru
dengan langkah di atas.

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
| **HTTPS** | Aplikasi melayani HTTP polos. Kata sandi admin dikirim saat login, jadi di jaringan bersama harus lewat HTTPS — pasang *reverse proxy* (IIS, nginx, Caddy) di depannya dengan sertifikat internal. |
| **Firewall / pembatasan akses** | Batasi port aplikasi hanya ke subnet PST. Idealnya `/admin/` dibatasi lebih ketat lagi (mis. hanya dari alamat tertentu) di proxy. |
| **Pencadangan database** | Database `db_pencarian_bps` bisa dibangun ulang dari WebAPI dan PDF (bagian 4), kecuali tabel `log_pencarian` (riwayat pencarian petugas) yang tidak bisa dipulihkan. Cadangkan berkala dengan `mysqldump`. Cadangkan juga `data/kamus_sinonim.json` dan `.env`. |
| **Menjalankan sebagai layanan** | Sekarang aplikasi berjalan di jendela Command Prompt yang harus dibiarkan terbuka. Untuk berjalan otomatis saat komputer menyala, daftarkan `jalankan-aplikasi.bat` di Task Scheduler (*At startup*) atau bungkus dengan NSSM sebagai Windows Service. |
| **Pembaruan berkala** | `perbarui-data.bat` bisa dijadwalkan lewat Task Scheduler, mis. tiap Senin pagi, di komputer yang tersambung "BPS - Pegawai". |
| **Kerahasiaan `.env`** | Berisi API key BPS dan sandi database. Jangan disalin ke tempat bersama; batasi hak baca berkasnya. |

---

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
