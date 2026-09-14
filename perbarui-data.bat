@echo off
setlocal
title Perbarui Data - Pencarian Publikasi BPS Kalsel
cd /d "%~dp0"

echo ==========================================================
echo   Perbarui data publikasi dari WebAPI BPS
echo ==========================================================
echo.
echo   Butuh koneksi ke jaringan "BPS - Pegawai".
echo   Jaringan "BPS - Tamu" memblokir WebAPI BPS.
echo.
echo   Kalau tidak ada publikasi baru, proses selesai dalam ~2 menit.
echo   Kalau ada publikasi baru, tiap publikasi butuh ~20-60 detik
echo   (unduh PDF + membaca strukturnya).
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

python scripts\perbarui.py %*

echo.
if errorlevel 1 (
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
