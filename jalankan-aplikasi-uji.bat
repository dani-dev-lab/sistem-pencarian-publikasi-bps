@echo off
setlocal
title Pencarian Publikasi BPS Kalsel - DATABASE UJI
cd /d "%~dp0"

rem Menjalankan aplikasi dengan DATABASE UJI (db_pencarian_bps_uji), bukan
rem produksi. Untuk mencoba fitur yang belum dimuat ke produksi, misalnya
rem publikasi Kecamatan Dalam Angka (kotak centang di bawah kotak cari).
rem Log pencarian TIDAK ditulis. Tombol pembaruan di halaman admin hanya
rem memperbarui database uji.
rem
rem Port: argumen baris perintah > 5001. Sengaja TIDAK membaca PORT di .env,
rem supaya bisa berjalan bersamaan dengan jalankan-aplikasi.bat (port 5000).
rem   contoh:  jalankan-aplikasi-uji.bat 5002
set PORT=%1
if "%PORT%"=="" set PORT=5001

echo ==========================================================
echo   Pencarian Publikasi BPS Kalsel - DATABASE UJI
echo   (bukan data produksi; log pencarian tidak ditulis)
echo ==========================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [GAGAL] Folder venv tidak ditemukan. Lihat PANDUAN.md.
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [GAGAL] Berkas .env tidak ditemukan. Lihat PANDUAN.md.
    echo.
    pause
    exit /b 1
)

call "venv\Scripts\activate.bat"

echo Memeriksa koneksi ke database uji ...
python -c "from app import create_app; from app.config import KonfigurasiUji; from app.models import db; import sqlalchemy as sa; app=create_app(KonfigurasiUji); ctx=app.app_context(); ctx.push(); db.session.execute(sa.text('SELECT 1')); print('Database:', db.engine.url.database)"
if errorlevel 1 (
    echo.
    echo [GAGAL] Database uji tidak bisa dibuka.
    echo.
    echo   Kalau pesan di atas menyebut "Can't connect": MySQL belum aktif.
    echo     Buka Laragon, klik "Start All", lalu coba lagi.
    echo   Kalau menyebut "Unknown database": database uji belum dibuat.
    echo     Lihat PANDUAN.md bagian database uji ^(scripts\siapkan_db_uji.py^).
    echo.
    pause
    exit /b 1
)

python -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(0 if s.connect_ex(('127.0.0.1', %PORT%)) else 1)"
if errorlevel 1 (
    echo.
    echo [GAGAL] Port %PORT% sudah dipakai.
    echo.
    echo   Kemungkinan aplikasi uji SUDAH BERJALAN di jendela lain - pakai saja
    echo   yang itu ^(http://localhost:%PORT%/^), atau jalankan dengan port lain:
    echo     jalankan-aplikasi-uji.bat 5002
    echo.
    pause
    exit /b 1
)

echo.
echo Memuat aplikasi. Browser terbuka otomatis begitu siap.
echo Untuk mencoba tampilan layar kecil: di browser tekan F12, lalu
echo Ctrl+Shift+M (mode perangkat), dan pilih ukuran ponsel.
echo Tekan Ctrl+C atau tutup jendela ini untuk berhenti.
echo.
python run.py --db-uji --port %PORT% --buka-browser

echo.
if errorlevel 1 (
    echo [GAGAL] Aplikasi tidak bisa dijalankan - baca pesan di atas.
) else (
    echo Aplikasi berhenti.
)
pause
