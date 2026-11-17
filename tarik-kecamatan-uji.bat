@echo off
setlocal
title Tarik Kecamatan Dalam Angka - DATABASE UJI
cd /d "%~dp0"

echo ==========================================================
echo   Publikasi "Kecamatan ... Dalam Angka" ke DATABASE UJI
echo   (db_pencarian_bps_uji). Produksi TIDAK disentuh.
echo ==========================================================
echo.
echo   Melanjutkan unduhan yang tersisa, lalu mengekstrak ke database
echo   uji. Aman diulang: PDF utuh tidak diunduh lagi, publikasi yang
echo   sudah diekstrak tidak diekstrak lagi. Kalau gagal, dicoba lagi
echo   otomatis (paling banyak 3 kali, jeda 2 menit).
echo.
echo   Windows dicegah tidur selama perbarui.py berjalan, TETAPI layar
echo   laptop jangan ditutup dan laptop tetap tersambung listrik.
echo   Log: data\log_pembaruan\  -  Kemajuan: periksa-kecamatan-uji.bat
echo.

if not exist "venv\Scripts\python.exe" (
    echo [GAGAL] Folder venv tidak ditemukan.
    pause
    exit /b 1
)

set PERCOBAAN=0
:ulang
set /a PERCOBAAN+=1
echo.
echo ---------- Percobaan %PERCOBAAN% dari 3 ----------
venv\Scripts\python.exe scripts\perbarui.py --db-uji --kecamatan --tanpa-ocr
set KODE=%ERRORLEVEL%
if "%KODE%"=="0" goto selesai
if "%KODE%"=="2" (
    echo [BERHENTI] Pembaruan lain sedang berjalan. Tunggu sampai selesai.
    goto selesai
)
if %PERCOBAAN% GEQ 3 goto selesai
echo Kode keluar %KODE%. Dicoba lagi dalam 2 menit...
timeout /t 120 /nobreak >nul
goto ulang

:selesai
echo.
venv\Scripts\python.exe scripts\kemajuan_kecamatan.py
echo.
echo Selesai. Kode keluar terakhir: %KODE%
pause
