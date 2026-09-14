@echo off
setlocal
title Pencarian Publikasi BPS Kalsel
cd /d "%~dp0"

rem Port bisa diganti lewat argumen, misalnya:  jalankan-aplikasi.bat 8080
set PORT=%1
if "%PORT%"=="" set PORT=5000

echo ==========================================================
echo   Pencarian Publikasi BPS Kalsel
echo ==========================================================
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
    echo.
    echo   Salin .env.example menjadi .env lalu isi nilainya.
    echo   Petunjuk lengkap ada di PANDUAN.md.
    echo.
    pause
    exit /b 1
)

call "venv\Scripts\activate.bat"

echo Memeriksa koneksi MySQL ...
python -c "from app import create_app; from app.models import db; import sqlalchemy as sa; app=create_app(); ctx=app.app_context(); ctx.push(); db.session.execute(sa.text('SELECT 1'))"
if errorlevel 1 (
    echo.
    echo [GAGAL] Aplikasi tidak bisa dijalankan.
    echo.
    echo   Kalau pesan di atas menyebut "Can't connect" atau "Connection refused":
    echo     MySQL belum aktif. Buka Laragon, klik "Start All", lalu coba lagi.
    echo   Kalau menyebut "Access denied":
    echo     Sandi MySQL di baris DATABASE_URL pada .env tidak cocok.
    echo   Kalau menyebut "KONFIGURASI BELUM LENGKAP":
    echo     Ikuti petunjuk di pesan itu, lalu coba lagi.
    echo.
    pause
    exit /b 1
)

echo MySQL aktif.
echo.
echo Membuka browser ke http://localhost:%PORT%/ ...
echo Biarkan jendela ini tetap terbuka selama aplikasi dipakai.
echo Tekan Ctrl+C atau tutup jendela ini untuk menghentikan aplikasi.
echo.
start "" "http://localhost:%PORT%/"
python run.py --port %PORT%

echo.
echo Aplikasi berhenti.
pause
