#!/usr/bin/env bash
# Padanan Linux untuk jalankan-aplikasi.bat (26 Nov 2026).
#
# Port: argumen baris perintah > baris PORT=... di .env > 5000.
#   contoh sekali jalan :  ./jalankan-aplikasi.sh 8080
#   contoh permanen     :  tulis PORT=8080 di .env
# Format .env yang dibaca sama dengan .bat: PORT=angka, tanpa spasi di
# sekitar "=", baris berawalan # diabaikan.
#
# Untuk layanan systemd, jalankan run.py langsung (PANDUAN, "Memindahkan
# aplikasi ke server"); skrip ini untuk dijalankan dari terminal.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUTF8=1
PY=venv/bin/python

# Jeda seperti "pause" di .bat, hanya kalau ada terminal (bukan di layanan).
jeda() {
    if [ -t 0 ]; then
        read -r -p "Tekan Enter untuk menutup . . . " _ || true
    fi
}

PORT="${1:-}"
if [ -z "$PORT" ] && [ -f .env ]; then
    while IFS= read -r baris || [ -n "$baris" ]; do
        baris="${baris%$'\r'}"
        case "$baris" in '#'*|'') continue ;; esac
        kunci="${baris%%=*}"
        [ "$kunci" = "$baris" ] && continue
        if [ "${kunci,,}" = "port" ]; then
            PORT="${baris#*=}"
        fi
    done < .env
fi
[ -z "$PORT" ] && PORT=5000

echo "=========================================================="
echo "  Pencarian Publikasi BPS Kalsel"
echo "=========================================================="
echo

if [ ! -x "$PY" ]; then
    echo "[GAGAL] Folder venv tidak ditemukan."
    echo
    echo "  Lingkungan Python belum dibuat. Jalankan dulu di folder ini:"
    echo "    python3 -m venv venv"
    echo "    venv/bin/pip install -r requirements.txt"
    echo
    jeda
    exit 1
fi

if [ ! -f .env ]; then
    echo "[GAGAL] Berkas .env tidak ditemukan."
    echo
    echo "  Salin .env.example menjadi .env lalu isi nilainya."
    echo "  Petunjuk lengkap ada di PANDUAN.md."
    echo
    jeda
    exit 1
fi

echo "Memeriksa koneksi MySQL ..."
if ! "$PY" -c "from app import create_app; from app.models import db; import sqlalchemy as sa; app=create_app(); ctx=app.app_context(); ctx.push(); db.session.execute(sa.text('SELECT 1'))"; then
    echo
    echo "[GAGAL] Aplikasi tidak bisa dijalankan."
    echo
    echo "  Kalau pesan di atas menyebut \"Can't connect\" atau \"Connection refused\":"
    echo "    MySQL belum aktif. Jalankan: sudo systemctl start mysql, lalu coba lagi."
    echo "  Kalau menyebut \"Access denied\":"
    echo "    Sandi MySQL di baris DATABASE_URL pada .env tidak cocok."
    echo "  Kalau menyebut \"KONFIGURASI BELUM LENGKAP\":"
    echo "    Ikuti petunjuk di pesan itu, lalu coba lagi."
    echo
    jeda
    exit 1
fi

echo "MySQL aktif."

# Diperiksa DI SINI, sebelum apa pun dijalankan (sama dengan .bat).
# (exit 1 = ada yang menjawab di port itu)
if ! "$PY" -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(0 if s.connect_ex(('127.0.0.1', $PORT)) else 1)"; then
    echo
    echo "[GAGAL] Port $PORT sudah dipakai."
    echo
    echo "  Kemungkinan aplikasi ini SUDAH BERJALAN di jendela lain - pakai saja"
    echo "  yang itu (http://localhost:$PORT/), atau tutup dulu jendela itu."
    echo "  Kalau port dipakai program lain, jalankan dengan port berbeda:"
    echo "    ./jalankan-aplikasi.sh 8080"
    echo
    jeda
    exit 1
fi

# Browser hanya dibuka kalau ada layar grafis (server tanpa layar: tidak).
buka=()
if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    buka=(--buka-browser)
fi

echo
echo "Memuat aplikasi, biasanya 5-10 detik."
if [ ${#buka[@]} -gt 0 ]; then
    echo "Browser akan terbuka otomatis begitu aplikasi siap - tidak perlu membukanya sendiri."
else
    echo "Sesudah tertulis \"Menyiapkan aplikasi\", buka http://localhost:$PORT/ di browser."
fi
echo "Biarkan jendela ini tetap terbuka selama aplikasi dipakai;"
echo "tekan Ctrl+C untuk berhenti."
echo

# Ctrl+C menghentikan run.py; skrip ini tetap mencetak pesan penutup.
trap ':' INT
kode=0
"$PY" run.py --port "$PORT" ${buka[@]+"${buka[@]}"} || kode=$?
trap - INT

echo
if [ "$kode" -eq 0 ] || [ "$kode" -eq 130 ]; then
    echo "Aplikasi berhenti."
else
    echo "[GAGAL] Aplikasi tidak bisa dijalankan - baca pesan di atas."
fi
jeda
exit "$kode"
