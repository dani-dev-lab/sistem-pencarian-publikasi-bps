# Portabilitas Windows + Linux (26 November 2026)

Permintaan pemilik project: aplikasi harus bisa dipasang di Windows DAN
Linux, tanpa mengubah perilaku di Windows. `.env` tidak dibuka. Belum
di-push.

**Ringkasnya:**

- Kode aplikasi sudah hampir portabel sejak awal. Jalur dibangun dengan
  `os.path`/`pathlib`, subprocess memakai `sys.executable`, dan cabang
  Windows (`OpenProcess`, `SetThreadExecutionState`) sudah dijaga
  `os.name`.
- Audit menemukan **satu bug nyata khusus Linux**: cek PID yang
  memperlakukan proses milik pengguna lain sebagai mati.
- Selebihnya berupa pesan bergaya Windows, skrip `.bat` tanpa padanan
  `.sh`, uji yang memanggil program Windows, dan beberapa hal pemasangan
  (collation MySQL 8, akhir baris di Git).
- Semua sudah diperbaiki atau didokumentasikan. **Belum ada yang dijalankan
  di Linux sungguhan**; daftar yang belum bisa dipastikan ada di akhir.

## 1. Audit

Diperiksa: semua `.py` di `app/`, `scripts/`, `tests/`, `run.py`, kelima
`.bat`, `requirements*.txt`, `.gitignore`, dan berkas data yang dibaca kode.

| Berkas / baris | Masalah | Perbaikan |
|---|---|---|
| `scripts/perbarui.py` `_proses_hidup`, `app/services/pembaruan.py` `_pid_hidup`, `scripts/isi_cache_ocr.py` `_proses_hidup` (cabang non-Windows) | **Bug Linux.** `os.kill(pid, 0)` melempar `PermissionError` kalau proses itu milik pengguna lain, dan semua `OSError` dianggap "mati". Contohnya layanan berjalan sebagai `bps` dan tim IT menjalankan `./perbarui-data.sh` sebagai pengguna lain: kunci pembaruan dianggap basi, sehingga dua pembaruan bisa berjalan bersamaan. | `ProcessLookupError` = mati, `PermissionError` = hidup, `OSError` lain = mati. Cabang Windows (`OpenProcess`) tidak disentuh. Uji Y2 (os.kill ditiru, 3 salinan fungsi). |
| `scripts/perbarui.py` `jaga_tetap_bangun`; `scripts/isi_cache_ocr.py` `_jaga_tetap_bangun` | `SetThreadExecutionState` hanya ada di Windows. | Sudah dijaga `os.name`; di Linux tidak melakukan apa-apa. Server tidak tidur; untuk laptop Linux, PANDUAN 7.4 menyarankan `systemd-inhibit`. Docstring dilengkapi. |
| `scripts/perbarui.py` `info_jaringan` | `netsh` tidak ada di Linux. | Dulu `FileNotFoundError` sudah tertangkap. Kini `netsh` hanya dipanggil di Windows; di Linux SSID tetap `None`. |
| `app/config.py` `PESAN_SECRET_KEY`, `PESAN_ADMIN_HASH`, `program_mysql`; `scripts/perbarui.py` `PESAN_SEMUA_TERHALANG`, `PESAN_PAKSA_TANPA_OCR`, `PESAN_SKEMA` + pesan ringkasan; `scripts/isi_cache_ocr.py` pesan EasyOCR; `app/routes/admin.py` flash "Database masih kosong"; `app/services/normalisasi_data.py`; `app/templates/admin/perbarui.html`; `tests/uji_pipeline.py` `LingkunganBelumSiap` | Petunjuk berbentuk Windows (`venv\Scripts\python.exe`, `perbarui-data.bat`, `data\ocr_cache`, `C:/laragon/...`), salah kalau diikuti di Linux. | `config.teks_os(teks)`: di Windows mengembalikan teks **apa adanya**; di Linux `venv/bin/python`, `./perbarui-data.sh`, dan "/". Templat lewat global Jinja `teks_os`. Contoh `MYSQL_BIN` di Linux: `/usr/bin`. Uji Y1: 5 pesan identik byte demi byte di Windows; tiruan Linux tanpa `\`, `.exe`, `.bat`, `Scripts`. |
| `scripts/*.py` docstring "Jalankan: venv\Scripts\python.exe ..." | Dokumentasi berbentuk Windows. | **Tidak diubah**: hanya komentar, tidak tampil ke pengguna. PANDUAN 7.4 memberi padanan Linux. |
| `app/services/pembaruan.py` `perintah()`, `tests/*` | Subprocess Python. | Sudah `sys.executable`; tidak ada yang memanggil `venv\Scripts\python.exe` atau `.bat` dari Python, kecuali uji `.bat` (baris berikut). |
| `tests/uji_pipeline.py` T2 `taskkill /F`; Q1 `cmd /c mklink /J` + `os.rmdir`; pemeriksaan lingkungan `splitdrive`; W2-W6 dan Q7 `cmd /c perbarui-data.bat` | Program Windows: gagal di Linux. Khususnya, `os.rmdir` pada symlink gagal di Linux. | Cabang non-Windows: `p.kill()` (SIGKILL), `os.symlink` + `os.unlink`, `st_dev` sama (di Linux `/tmp` sering tmpfs, sehingga hardlink gagal; pesannya menyarankan `TMPDIR`). Uji `.bat` hanya di Windows (`lewati` di Linux); padanan `.sh` diuji di W7-W14 + Q7b. |
| Lima `.bat` | Tidak ada padanan Linux. | `jalankan-aplikasi.sh`, `perbarui-data.sh`, `jalankan-aplikasi-uji.sh`, `tarik-kecamatan-uji.sh`, `periksa-kecamatan-uji.sh` (bagian 2). |
| `.bat` di Git | Di indeks tersimpan **LF**; CRLF di laptop ini hanya karena `core.autocrlf=true`. Klon di Linux, atau di Windows tanpa autocrlf, memberi `.bat` ber-LF, yang dibaca salah oleh cmd.exe (label/goto). | `.gitattributes`: `*.bat text eol=crlf`, `*.sh text eol=lf`. Indeks tidak berubah (tetap LF), berkas kerja di sini tetap CRLF (`git ls-files --eol`). |
| Nama berkas templat dan static (kepekaan huruf besar-kecil) | Linux membedakan `Hasil.html` dan `hasil.html`. | Diperiksa: semua nama di `render_template`/`extends`/`include`/`import` cocok persis dengan berkas di `app/templates`; semua `url_for('static', filename=...)` cocok dengan `app/static` (0 selisih). Berkas data dan tabel MySQL berhuruf kecil; nama PDF = `pub_id` dari API, dipakai konsisten. |
| `open()` tanpa `encoding` | Bawaan berbeda: cp1252 di Windows, locale di Linux. | 4 tempat (berkas kunci `isi_cache_ocr.py`, 2 di `uji_pipeline.py`) kini `encoding="utf-8"`. Isinya angka/ASCII, jadi hasil di Windows tidak berubah. Semua `open()` teks lain sudah eksplisit. Subprocess `mysql` sudah `encoding="utf-8"`. |
| Locale | Format bergantung locale. | Tidak ada: nama bulan dari daftar sendiri (`BULAN_SINGKAT`), angka ribuan di sisi JavaScript. Skrip `.sh` dan unit systemd memasang `PYTHONUTF8=1`. Python 3.7+ juga memaksa UTF-8 kalau locale-nya C/POSIX. |
| `MYSQL_BIN`, `program_mysql()` | Nama `.exe`. | Sudah mencoba `nama.exe`, lalu `nama`, lalu `PATH` (`shutil.which`), jadi di Linux berjalan tanpa diubah. Hanya contoh di pesannya yang dibuat per sistem. |
| Sidik PDF `(ukuran, int(mtime))` | Portabel, tetapi waktu ubah bisa bergeser saat folder dipindah (ZIP, FAT32/exFAT: ketelitian 2 detik). Akibatnya ekstraksi ulang dan cache OCR dibuang. Tidak ada cara memeriksanya. | `scripts/periksa_sidik.py [--db-uji]` (hanya membaca). Produksi: 622/622 PDF, 34/34 cache OCR cocok, 649 sampul. Uji Y3: +2 detik tertangkap. tar Windows -> GNU tar: 0 selisih (bagian 4). |
| `versi_data` di MySQL | Collation `utf8mb4_0900_ai_ci` hanya ada di MySQL 8; cadangan gagal dipulihkan ke MariaDB. 5 tabel lain `utf8mb4_unicode_ci`. | Didokumentasikan: wajib MySQL 8.0, bukan MariaDB (PANDUAN 7.4). Skema tidak diubah. |
| `requirements.txt` | PyMySQL butuh `cryptography` untuk login MySQL 8 dengan sandi (`caching_sha2_password`). Di laptop ini sandi root kosong, jadi tidak pernah terlihat. | Ternyata sudah terpasang sebagai dependensi `pdfminer.six`. Kini ditulis eksplisit (`cryptography>=42`); versi terpasang 50.0.1, jadi tidak ada yang berubah di Windows. |
| `requirements-ocr.txt` | Komentar hanya menyebut jalur Windows. | Ditambah perintah dan folder model Linux (`~/.EasyOCR`). |
| `run.py --buka-browser` | Di server tanpa layar tidak ada browser. | `.sh` hanya memasang `--buka-browser` kalau `DISPLAY`/`WAYLAND_DISPLAY` ada; selain itu mencetak alamatnya. `run.py` tidak diubah. |
| `run.py` cek port | Komentar SO_REUSEADDR khusus Windows. | Tetap berlaku di kedua sistem (cek sebelum `serve`). Tidak diubah. |
| `os.replace` (tulis atomik) | | Portabel (rename atomik POSIX). Tidak diubah. |
| Direktori kerja | Layanan bisa dimulai dari folder lain. | Aplikasi memakai `BASE_DIR` dan `perbarui.py` melakukan `chdir` ke folder proyek, jadi aman. Unit systemd tetap memakai `WorkingDirectory`. |
| Menghentikan server saat pembaruan berjalan | Windows: anak proses tetap hidup. systemd: `KillMode=control-group` bawaan ikut menghentikan `perbarui.py`. | Didokumentasikan sebagai beda perilaku (PANDUAN 7.4). Aman, karena tiap tahap atomik dan kunci basi ditimpa. |

## 2. Skrip `.sh`

Satu per `.bat`, semuanya:

- bash dengan `#!/usr/bin/env bash` dan `set -euo pipefail`;
- ASCII, LF, mode Git 100755 (`git add --chmod=+x`);
- shellcheck 0.11.0 (venv alat terpisah): **0 temuan**.

| Hal | Sama dengan `.bat` | Beda (sengaja) |
|---|---|---|
| Port | argumen > `PORT=` di `.env` (kunci tak peka huruf, baris `#` diabaikan, CR dibuang) > 5000; `-uji` hanya argumen > 5001 | |
| Pemeriksaan | venv, `.env`, MySQL (`SELECT 1` lewat `create_app`), port terpakai: kalimat sama, kode 1 | petunjuk "Buka Laragon, Start All" menjadi `sudo systemctl start mysql` |
| Pesan penutup `perbarui-data` | lima kalimat persis sama (SELESAI SEBAGIAN / TIDAK DIJALANKAN / GAGAL / CEK SELESAI / SELESAI) | |
| Kode keluar | 1 untuk kegagalan di awal | **akhir = kode `perbarui.py` / `run.py`** (0/1/2/3). Diukur 26 Nov: pola akhir `.bat` (`set KODE`, pipa `find`, `pause`) **selalu berkode 0** di cmd, juga tanpa `pause`; `.bat` sengaja tidak diubah. Kode yang benar dibutuhkan timer systemd. |
| `pause` | | hanya kalau stdin terminal (`[ -t 0 ]`), supaya layanan dan jadwal tidak macet |
| Ctrl+C di `jalankan-aplikasi` | | `trap ':' INT` supaya pesan penutup tetap tercetak; kode 130 dianggap "Aplikasi berhenti." |
| Browser | | hanya kalau ada layar grafis |
| Python | `venv\Scripts\python.exe` + `activate.bat` | `venv/bin/python` langsung, `PYTHONUTF8=1` |

## 3. Pengujian (Windows 11)

- **`uji_pipeline.py`**:
  - W7-W14 dan Q7b menjalankan `.sh` sungguhan dengan bash **Git for
    Windows** (`C:\Program Files\Git\usr\bin\bash.EXE`; `bash.exe` WSL di
    System32/WindowsApps sengaja tidak dipakai). `venv/bin/python` di
    salinan berupa pembungkus `sh` yang memanggil Python uji.
  - Bagian Y = portabilitas.
  - Uji `.bat` (W2-W6, Q7) tetap dan tetap lulus.

| Uji | Isi | Hasil |
|---|---|---|
| W7 | 5 `.sh`: ASCII, LF, 100755 di Git, shebang, `set -euo pipefail`, satu per `.bat`; `.gitattributes` | lulus |
| W8-W12 | `perbarui-data.sh`: sebagian -> kode 3; selesai -> 0 (database uji); jaringan putus -> 1; terkunci -> 2; `--cek-dulu` -> 0 "CEK SELESAI" | lulus |
| W13 | `jalankan-aplikasi.sh`: PORT dari `.env` ber-CRLF dengan baris `#PORT=1`, argumen menimpa, port terpakai -> pesan + kode 1; `jalankan-aplikasi-uji.sh` memeriksa database uji | lulus sesudah perbaikan alat (catatan di bawah) |
| W14 | tiga skrip tanpa venv -> "[GAGAL] Folder venv tidak ditemukan.", kode 1 | lulus |
| Q7b | `perbarui-data.sh --wilayah 6305,6300 --jenis kecamatan --cek-dulu` (pilihan utuh lewat `"$@"`), pilihan tidak sah -> DITOLAK, kode 1 | lulus |
| Y1 | `teks_os`: Windows identik (5 pesan); tiruan Linux benar | lulus |
| Y2 | cek PID non-Windows: ada / ProcessLookupError / **PermissionError = hidup** / OSError | lulus (3 salinan) |
| Y3 | `periksa_sidik.py`: satu PDF (salinan, bukan hardlink) +2 detik -> "PDF berbeda" 1, "selisih waktu +2 detik", kode 1; dikembalikan -> sama dengan awal | lulus |

**W13, catatan alat:** run pertama `--hanya WQY` (`uji-pipeline-WQY.txt`:
51 lulus, 1 gagal) menggagalkan W13.

- Gejala: `jalankan-aplikasi-uji.sh` tidak melihat port terpakai.
- Sebabnya soket pendengar uji memakai `listen(1)`. Dua run sebelumnya
  sudah mengisi antrean koneksinya, yang tidak pernah di-`accept`. Windows
  lalu menolak koneksi berikutnya, sehingga port tampak bebas.
- Dijalankan sendiri di luar uji, dengan port terpakai, skrip yang sama
  benar: kode 1 dan pesan "[GAGAL] Port ... sudah dipakai.".
- Perbaikan: `listen(50)` di uji. Skripnya tidak diubah.
- `--hanya W` sesudahnya: **22 lulus, 0 gagal** (`uji-pipeline-W.txt`).
- **Uji alat W13:** baris pembuang CR (`baris="${baris%$'\r'}"`) dihapus
  dari salinan skrip. Dengan `.env` ber-CRLF, pesannya menjadi "[GAGAL]
  Port 59175" + CR, dan syarat W13 gagal. Skrip asli memberi pesan utuh.
  Jadi W13 memang menguji pembacaan CRLF.

**Run penuh** `uji_pipeline.py` tanpa argumen: **184 lulus, 0 gagal, 0
dilewati, 3.524 detik** (`uji-pipeline-penuh.txt`); Z1 database uji
dipulihkan, Z2 produksi tidak berubah selama run. **CHECKSUM produksi**
sebelum dan sesudah run: 6/6 tabel sama (`checksum-produksi-awal.json` =
`checksum-produksi-akhir.json`).

**Perilaku Windows tidak berubah:**

- Potret HTML 28 URL pencarian (database uji) **IDENTIK 28/28**, halaman
  penuh dan isi `<main>`, dibanding potret pagi ini
  (`banding-html-penuh.txt`, `banding-isi.txt`).
- Pesan `.env`/pembaruan identik byte demi byte (Y1).
- Templat admin tetap merender `perbarui-data.bat`.
- `.bat` tidak diubah sama sekali.

## 4. Persiapan uji Linux

- **Cadangan produksi:** `data/serah_terima/db_pencarian_bps-20261126.sql`.
  - Ukuran 15.972.754 bait; sha256
    `807ce7a3bade11d4f06043edc645b91c4b6632a4a5e0333aa6a0f5d36b363200`.
  - Dibuat dengan perintah dan pilihan PANDUAN bagian 7 (`mysqldump` dari
    `MYSQL_BIN`, kredensial dari konfigurasi tanpa membuka `.env`, sandi
    lewat `MYSQL_PWD`, tidak dicetak).
  - **Uji pulih:** dimuat ke database sementara
    `db_pencarian_bps_serah_uji`. 6/6 tabel sama dengan produksi (jumlah
    baris + `CHECKSUM TABLE`; `uji-pulih-cadangan.json`), lalu database
    sementaranya dihapus.
- **`.gitignore`:** `data/serah_terima/` dan `*.sql`. Dua `.sql` lama yang
  sudah dilacak di `data/regresi/` tetap dilacak (aturan ignore tidak
  melepas berkas yang sudah dilacak).
- **tar lintas implementasi:** `tar` bawaan Windows (bsdtar 3.8.9)
  membungkus `publikasi_pdf/6305`, `ocr_cache/6305`, kamus, dan wilayah
  (434 MB); GNU tar 1.35 (Git Bash) membukanya. Hasil: 1.574 berkas,
  **0 sidik berbeda**. Dibuka di NTFS, bukan ext4.
- **Lingkungan pengembangan** (`portabilitas-20261126/pip-freeze-windows.txt`):
  - Python 3.14.6 (Windows-11-10.0.26300, AMD64), pip 26.1.2, MySQL
    Community 8.0.30 (Laragon).
  - 58 paket, di antaranya: Flask 3.1.3, Flask-SQLAlchemy 3.1.1,
    SQLAlchemy 2.0.52, PyMySQL 1.2.0, cryptography 50.0.1, pdfplumber
    0.11.10, pdfminer.six 20260107, pypdfium2 5.13.0, PySastrawi 1.2.1,
    RapidFuzz 3.14.5, waitress 3.0.2, Werkzeug 3.1.8, python-dotenv 1.2.3,
    requests 2.34.2; OCR: torch 2.15.0+cpu, torchvision 0.29.2+cpu,
    easyocr 1.7.2.
  - Paket yang ada di venv tetapi tidak diminta `requirements*.txt`
    (mysql-connector-python, ruff, Sastrawi, pytest, dsb.) tidak dibutuhkan
    aplikasi.

## 5. PANDUAN

- **7.4 "Memindahkan aplikasi ke server"** berisi:
  - status: Windows teruji, Linux **MENUNGGU UJI**;
  - tabel padanan `.bat`/`.sh`;
  - cara A (tarik ulang) vs cara B (paket serah terima): isi, ukuran, `tar`,
    `periksa_sidik.py`;
  - pemasangan Windows: Task Scheduler/NSSM, tertulis "belum dicoba";
  - pemasangan Linux: paket, pengguna `bps`, venv, MySQL 8 + akun khusus
    (root Ubuntu `auth_socket`), `.env` `chmod 600`, unit systemd aplikasi
    + timer pembaruan, beda `systemctl stop`;
  - jaringan ke `webapi.bps.go.id` dan `JUMLAH_PROXY`.
- **Bagian 2, jalur A:** sampul dan kamus ditambahkan ke daftar serahan,
  ukuran terbaru, dan `periksa_sidik.py` menggantikan kalimat "tidak punya
  perintah untuk memeriksa".
- **Daftar isi:** menyebut 7.4.

## 6. Yang belum bisa dipastikan tanpa menjalankan di Linux

1. **Pemasangan paket di Linux**: wheel untuk Python yang tersedia di
   distribusi (Ubuntu 24.04 = 3.12), khususnya pypdfium2, rapidfuzz,
   cryptography, dan torch `+cpu` dari indeks PyTorch. Versi minimum di
   `requirements.txt` belum diuji di Python 3.12.
2. **MySQL 8 dengan sandi lewat TCP** (PyMySQL + `caching_sha2_password` +
   cryptography). Di laptop ini sandi root kosong. Selain itu, pemulihan
   cadangan ke MySQL 8 Linux, dan bahwa MariaDB memang gagal (collation).
3. **Skrip `.sh` di bash Linux sungguhan.** Yang teruji adalah bash Git for
   Windows (MSYS2), dengan pembungkus `venv/bin/python`. Belum teruji:
   - `-x` pada berkas biasa;
   - sinyal Ctrl+C dan `trap`;
   - `read -p` di terminal;
   - `systemd-inhibit`.
4. **Cabang non-Windows sungguhan**: cek PID dengan dua pengguna Linux
   (`PermissionError`). Y2 hanya meniru `os.kill`; `p.kill()`, symlink, dan
   `st_dev` di `uji_pipeline.py` belum pernah berjalan.
5. **systemd**: unit aplikasi dan timer, `KillMode` saat `systemctl stop`
   di tengah pembaruan, dan pengodean keluaran di journald.
6. **Sistem berkas Linux**: `tar -xf` di ext4/xfs menjaga detik waktu ubah
   (`periksa_sidik.py` harus `SEMUA COCOK`), dan hak akses `data/` antara
   pengguna layanan dan pengguna terminal.
7. **`uji_pipeline.py` penuh di Linux**: hardlink butuh `TMPDIR` di disk
   yang sama, server tiruan, mysqldump/mysql di PATH. Alat Playwright di
   `data/regresi/` juga belum (memakai `channel="chrome"` dan jalur
   `C:/Users/...`).
8. **OCR di Linux** (EasyOCR + torch CPU, unduhan model ke `~/.EasyOCR`) dan
   hasil OCR-nya. Hasil di Windows tidak boleh dianggap sama tanpa
   pembanding: GPU vs CPU sudah terbukti berbeda 6/551 kata.
9. **Kinerja dan memori** (±174 MB, waktu cari, muat ulang korpus) di
   server Linux.
10. **DNS/jaringan server BPS** ke `webapi.bps.go.id` dan reverse proxy +
    `JUMLAH_PROXY` sungguhan (bagian ini juga belum diuji di Windows).
11. **NSSM / Task Scheduler** sebagai layanan Windows (tertulis "belum
    dicoba" di PANDUAN).
