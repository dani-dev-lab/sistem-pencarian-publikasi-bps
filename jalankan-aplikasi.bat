@echo off
setlocal
title Pencarian Publikasi BPS Kalsel
cd /d "%~dp0"

rem Port: argumen baris perintah > baris PORT=... di .env > 5000.
rem   contoh sekali jalan :  jalankan-aplikasi.bat 8080
rem   contoh permanen     :  tulis PORT=8080 di .env
set PORT=%1
if "%PORT%"=="" if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do (
        if /i "%%a"=="PORT" set PORT=%%b
    )
)
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

rem Diperiksa DI SINI, sebelum apa pun dijalankan: di Windows dua server bisa
rem mendengarkan port yang sama tanpa galat (lihat run.py). Kalau ketahuan
rem lebih awal, browser tidak jadi dibuka ke server milik jendela lain.
rem (exit 1 = ada yang menjawab di port itu)
python -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(0 if s.connect_ex(('127.0.0.1', %PORT%)) else 1)"
if errorlevel 1 (
    echo.
    echo [GAGAL] Port %PORT% sudah dipakai.
    echo.
    echo   Kemungkinan aplikasi ini SUDAH BERJALAN di jendela lain - pakai saja
    echo   yang itu ^(http://localhost:%PORT%/^), atau tutup dulu jendela itu.
    echo   Kalau port dipakai program lain, jalankan dengan port berbeda:
    echo     jalankan-aplikasi.bat 8080
    echo.
    pause
    exit /b 1
)

echo.
echo Memuat aplikasi, biasanya 5-10 detik. Browser akan terbuka
echo otomatis begitu aplikasi siap - tidak perlu membukanya sendiri.
echo Biarkan jendela ini tetap terbuka selama aplikasi dipakai;
echo tekan Ctrl+C atau tutup jendela untuk berhenti.
echo.
python run.py --port %PORT% --buka-browser

echo.
if errorlevel 1 (
    echo [GAGAL] Aplikasi tidak bisa dijalankan - baca pesan di atas.
) else (
    echo Aplikasi berhenti.
)
pause
