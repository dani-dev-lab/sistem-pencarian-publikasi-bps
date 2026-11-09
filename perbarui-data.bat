@echo off
setlocal
title Perbarui Data - Pencarian Publikasi BPS Kalsel
cd /d "%~dp0"

echo ==========================================================
echo   Perbarui data publikasi dari WebAPI BPS
echo ==========================================================
echo.
echo   Butuh koneksi internet ke webapi.bps.go.id.
echo.
echo   Kalau tidak ada publikasi baru, proses selesai dalam ~2 menit per wilayah.
echo   Tiap publikasi yang perlu diproses butuh ~20-90 detik
echo   (unduh PDF + membaca strukturnya). Penarikan wilayah baru bisa
echo   berjam-jam: biarkan jendela ini terbuka, laptop tersambung listrik,
echo   dan layar laptop jangan ditutup.
echo.
echo   Seluruh keluaran juga disimpan ke data\log_pembaruan\ (nama berkas
echo   tercetak di baris pertama), dan ringkasannya ke data\pembaruan_terakhir.json.
echo.

if not exist "venv\Scripts\python.exe" (
    echo [GAGAL] Folder venv tidak ditemukan.
    echo.
    echo   Lingkungan Python belum dibuat. Jalankan dulu di folder ini:
    echo     python -m venv venv
    echo     venv\Scripts\pip.exe install -r requirements.txt
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [GAGAL] Berkas .env tidak ditemukan.
    echo   Salin .env.example menjadi .env lalu isi nilainya. Lihat PANDUAN.md.
    echo.
    pause
    exit /b 1
)

call "venv\Scripts\activate.bat"

echo Memeriksa koneksi MySQL ...
python -c "from app import create_app; from app.models import db; import sqlalchemy as sa; app=create_app(); ctx=app.app_context(); ctx.push(); db.session.execute(sa.text('SELECT 1'))"
if errorlevel 1 (
    echo.
    echo [GAGAL] Tidak bisa melanjutkan.
    echo.
    echo   Kalau pesan di atas menyebut "Can't connect" atau "Connection refused":
    echo     MySQL belum aktif. Buka Laragon, klik "Start All", lalu coba lagi.
    echo   Kalau menyebut "KONFIGURASI BELUM LENGKAP":
    echo     Ikuti petunjuk di pesan itu, lalu coba lagi.
    echo.
    pause
    exit /b 1
)
echo MySQL aktif.
echo.
echo Memulai. Tiap wilayah diawali pemeriksaan seluruh halaman daftar publikasi
echo di WebAPI dengan jeda 1 detik per halaman - baris "halaman N/65 ... OK"
echo muncul satu per satu. Itu normal, bukan macet.
echo.

python scripts\perbarui.py %*

echo.
if errorlevel 3 (
    echo ==========================================================
    echo   PEMBARUAN SELESAI SEBAGIAN - sebagian wilayah/publikasi gagal.
    echo ==========================================================
    echo   Yang berhasil sudah bisa dicari. Yang gagal tetap memakai data
    echo   lamanya dan dicoba lagi pada pembaruan berikutnya. Baca rincian di atas.
) else if errorlevel 2 (
    echo ==========================================================
    echo   TIDAK DIJALANKAN: pembaruan lain sedang berjalan.
    echo ==========================================================
    echo   Kemungkinan pengelola sedang menjalankannya dari halaman admin
    echo   di browser. Tunggu sampai selesai, lalu coba lagi kalau perlu.
) else if errorlevel 1 (
    echo ==========================================================
    echo   PEMBARUAN GAGAL - baca pesan di atas.
    echo ==========================================================
) else (
    echo ==========================================================
    echo   PEMBARUAN SELESAI.
    echo ==========================================================
    echo   Kalau aplikasi sedang berjalan, tidak perlu di-restart:
    echo   data baru langsung bisa dicari.
)
echo.
pause
