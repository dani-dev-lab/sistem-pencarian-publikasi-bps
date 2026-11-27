#!/usr/bin/env bash
# Padanan Linux untuk jalankan-aplikasi-uji.bat (26 Nov 2026).
#
# Menjalankan aplikasi dengan DATABASE UJI (db_pencarian_bps_uji), bukan
# produksi. Log pencarian TIDAK ditulis. Tombol pembaruan di halaman admin
# hanya memperbarui database uji.
#
# Port: argumen baris perintah > 5001. Sengaja TIDAK membaca PORT di .env,
# supaya bisa berjalan bersamaan dengan jalankan-aplikasi.sh (port 5000).
#   contoh:  ./jalankan-aplikasi-uji.sh 5002
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUTF8=1
PY=venv/bin/python

jeda() {
    if [ -t 0 ]; then
        read -r -p "Tekan Enter untuk menutup . . . " _ || true
    fi
}

PORT="${1:-}"
[ -z "$PORT" ] && PORT=5001

echo "=========================================================="
echo "  Pencarian Publikasi BPS Kalsel - DATABASE UJI"
echo "  (bukan data produksi; log pencarian tidak ditulis)"
echo "=========================================================="
echo

if [ ! -x "$PY" ]; then
    echo "[GAGAL] Folder venv tidak ditemukan. Lihat PANDUAN.md."
    echo
    jeda
    exit 1
fi

if [ ! -f .env ]; then
    echo "[GAGAL] Berkas .env tidak ditemukan. Lihat PANDUAN.md."
    echo
    jeda
    exit 1
fi

echo "Memeriksa koneksi ke database uji ..."
if ! "$PY" -c "from app import create_app; from app.config import KonfigurasiUji; from app.models import db; import sqlalchemy as sa; app=create_app(KonfigurasiUji); ctx=app.app_context(); ctx.push(); db.session.execute(sa.text('SELECT 1')); print('Database:', db.engine.url.database)"; then
    echo
    echo "[GAGAL] Database uji tidak bisa dibuka."
    echo
    echo "  Kalau pesan di atas menyebut \"Can't connect\": MySQL belum aktif."
    echo "    Jalankan: sudo systemctl start mysql, lalu coba lagi."
    echo "  Kalau menyebut \"Unknown database\": database uji belum dibuat."
    echo "    Lihat PANDUAN.md bagian database uji (scripts/siapkan_db_uji.py)."
    echo
    jeda
    exit 1
fi

if ! "$PY" -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(0 if s.connect_ex(('127.0.0.1', $PORT)) else 1)"; then
    echo
    echo "[GAGAL] Port $PORT sudah dipakai."
    echo
    echo "  Kemungkinan aplikasi uji SUDAH BERJALAN di jendela lain - pakai saja"
    echo "  yang itu (http://localhost:$PORT/), atau jalankan dengan port lain:"
    echo "    ./jalankan-aplikasi-uji.sh 5002"
    echo
    jeda
    exit 1
fi

buka=()
if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    buka=(--buka-browser)
fi

echo
if [ ${#buka[@]} -gt 0 ]; then
    echo "Memuat aplikasi. Browser terbuka otomatis begitu siap."
else
    echo "Memuat aplikasi. Sesudah siap, buka http://localhost:$PORT/ di browser."
fi
echo "Untuk mencoba tampilan layar kecil: di browser tekan F12, lalu"
echo "Ctrl+Shift+M (mode perangkat), dan pilih ukuran ponsel."
echo "Tekan Ctrl+C untuk berhenti."
echo

trap ':' INT
kode=0
"$PY" run.py --db-uji --port "$PORT" ${buka[@]+"${buka[@]}"} || kode=$?
trap - INT

echo
if [ "$kode" -eq 0 ] || [ "$kode" -eq 130 ]; then
    echo "Aplikasi berhenti."
else
    echo "[GAGAL] Aplikasi tidak bisa dijalankan - baca pesan di atas."
fi
jeda
exit "$kode"
