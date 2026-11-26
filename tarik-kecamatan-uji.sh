#!/usr/bin/env bash
# Padanan Linux untuk tarik-kecamatan-uji.bat (26 Nov 2026).
#
# Publikasi "Kecamatan ... Dalam Angka" ke DATABASE UJI. Sejak 19 Nov 2026
# kecamatan sudah dimuat ke produksi dan kecualikan_judul tidak aktif, jadi
# skrip ini hanya untuk mengulang percobaan di database uji.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUTF8=1
PY=venv/bin/python

jeda() {
    if [ -t 0 ]; then
        read -r -p "Tekan Enter untuk menutup . . . " _ || true
    fi
}

echo "=========================================================="
echo "  Publikasi \"Kecamatan ... Dalam Angka\" ke DATABASE UJI"
echo "  (db_pencarian_bps_uji). Produksi TIDAK disentuh."
echo "=========================================================="
echo
echo "  Melanjutkan unduhan yang tersisa, lalu mengekstrak ke database"
echo "  uji. Aman diulang: PDF utuh tidak diunduh lagi, publikasi yang"
echo "  sudah diekstrak tidak diekstrak lagi. Kalau gagal, dicoba lagi"
echo "  otomatis (paling banyak 3 kali, jeda 2 menit)."
echo
echo "  Di Linux komputer tidak dicegah tidur oleh perbarui.py. Di laptop,"
echo "  jalankan lewat: systemd-inhibit ./tarik-kecamatan-uji.sh"
echo "  Log: data/log_pembaruan/  -  Kemajuan: ./periksa-kecamatan-uji.sh"
echo

if [ ! -x "$PY" ]; then
    echo "[GAGAL] Folder venv tidak ditemukan."
    jeda
    exit 1
fi

PERCOBAAN=0
KODE=0
while :; do
    PERCOBAAN=$((PERCOBAAN + 1))
    echo
    echo "---------- Percobaan $PERCOBAAN dari 3 ----------"
    KODE=0
    "$PY" scripts/perbarui.py --db-uji --kecamatan --tanpa-ocr || KODE=$?
    if [ "$KODE" -eq 0 ]; then break; fi
    if [ "$KODE" -eq 2 ]; then
        echo "[BERHENTI] Pembaruan lain sedang berjalan. Tunggu sampai selesai."
        break
    fi
    if [ "$PERCOBAAN" -ge 3 ]; then break; fi
    echo "Kode keluar $KODE. Dicoba lagi dalam 2 menit..."
    sleep 120
done

echo
"$PY" scripts/kemajuan_kecamatan.py || true
echo
echo "Selesai. Kode keluar terakhir: $KODE"
jeda
exit "$KODE"
