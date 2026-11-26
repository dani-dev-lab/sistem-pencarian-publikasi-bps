#!/usr/bin/env bash
# Padanan Linux untuk perbarui-data.bat (26 Nov 2026).
#
# Argumen diteruskan ke scripts/perbarui.py, sama dengan .bat, misalnya:
#   ./perbarui-data.sh
#   ./perbarui-data.sh --wilayah 6301 --tahun-min 2025 --cek-dulu
#
# Kode keluar = kode keluar perbarui.py: 0 selesai, 1 gagal, 2 tidak
# dijalankan (pembaruan lain berjalan), 3 selesai sebagian. Berguna untuk
# jadwal systemd/cron. (.bat selalu berakhir dengan kode 0 sesudah "pause";
# lihat data/regresi/portabilitas-20261126.md.)
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
echo "  Perbarui data publikasi dari WebAPI BPS"
echo "=========================================================="
echo
echo "  Butuh koneksi internet ke webapi.bps.go.id."
echo
echo "  Pembaruan rutin 14 wilayah: sekitar 2 menit (diukur 16 Nov 2026:"
echo "  107 detik dengan 1 publikasi baru). Daftar tiap wilayah diperiksa"
echo "  dengan jeda 1 detik per halaman. Tiap publikasi yang perlu diproses"
echo "  menambah beberapa detik sampai beberapa menit, tergantung ukuran"
echo "  PDF-nya (unduh + membaca strukturnya). Penarikan wilayah baru bisa"
echo "  berjam-jam: biarkan terminal ini terbuka (atau jalankan lewat"
echo "  systemd/tmux), dan komputer jangan tidur."
echo
echo "  Seluruh keluaran juga disimpan ke data/log_pembaruan/ (nama berkas"
echo "  tercetak di baris pertama), dan ringkasannya ke data/pembaruan_terakhir.json."
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
    echo "  Salin .env.example menjadi .env lalu isi nilainya. Lihat PANDUAN.md."
    echo
    jeda
    exit 1
fi

echo "Memeriksa koneksi MySQL ..."
# --db-uji: periksa database uji (KonfigurasiUji), bukan produksi.
if ! "$PY" -c "import sys; from app import create_app; from app.config import Config, KonfigurasiUji; from app.models import db; import sqlalchemy as sa; app=create_app(KonfigurasiUji if '--db-uji' in sys.argv[1:] else Config); ctx=app.app_context(); ctx.push(); db.session.execute(sa.text('SELECT 1')); print('  database:', db.engine.url.database)" "$@"; then
    echo
    echo "[GAGAL] Tidak bisa melanjutkan."
    echo
    echo "  Kalau pesan di atas menyebut \"Can't connect\" atau \"Connection refused\":"
    echo "    MySQL belum aktif. Jalankan: sudo systemctl start mysql, lalu coba lagi."
    echo "  Kalau menyebut \"KONFIGURASI BELUM LENGKAP\":"
    echo "    Ikuti petunjuk di pesan itu, lalu coba lagi."
    echo
    jeda
    exit 1
fi
echo "MySQL aktif."
echo
echo "Memulai. Tiap wilayah diawali pemeriksaan halaman daftar publikasi di"
echo "WebAPI dengan jeda 1 detik per halaman - baris \"halaman 3/24 ... OK\""
echo "muncul satu per satu. Itu normal, bukan macet."
echo

KODE=0
"$PY" scripts/perbarui.py "$@" || KODE=$?
CEK=""
for a in "$@"; do
    case "${a,,}" in *--cek-dulu*) CEK=1 ;; esac
done

echo
if [ "$KODE" -ge 3 ]; then
    echo "=========================================================="
    echo "  PEMBARUAN SELESAI SEBAGIAN - sebagian wilayah/publikasi gagal."
    echo "=========================================================="
    echo "  Yang berhasil sudah bisa dicari. Yang gagal tetap memakai data"
    echo "  lamanya dan dicoba lagi pada pembaruan berikutnya. Baca rincian di atas."
elif [ "$KODE" -eq 2 ]; then
    echo "=========================================================="
    echo "  TIDAK DIJALANKAN: pembaruan lain sedang berjalan."
    echo "=========================================================="
    echo "  Kemungkinan pengelola sedang menjalankannya dari halaman admin"
    echo "  di browser. Tunggu sampai selesai, lalu coba lagi kalau perlu."
elif [ "$KODE" -eq 1 ]; then
    echo "=========================================================="
    echo "  PEMBARUAN GAGAL - baca pesan di atas."
    echo "=========================================================="
elif [ -n "$CEK" ]; then
    echo "=========================================================="
    echo "  CEK SELESAI - tidak ada PDF yang diunduh, database tidak diubah."
    echo "=========================================================="
    echo "  Kalau angkanya sesuai, jalankan lagi dengan pilihan yang sama"
    echo "  TANPA --cek-dulu untuk memulai penarikan."
else
    echo "=========================================================="
    echo "  PEMBARUAN SELESAI."
    echo "=========================================================="
    echo "  Kalau aplikasi sedang berjalan, tidak perlu di-restart:"
    echo "  data baru langsung bisa dicari."
fi
echo
jeda
exit "$KODE"
