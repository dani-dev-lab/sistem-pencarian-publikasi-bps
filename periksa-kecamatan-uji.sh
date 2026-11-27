#!/usr/bin/env bash
# Padanan Linux untuk periksa-kecamatan-uji.bat (26 Nov 2026): kemajuan
# publikasi kecamatan di DATABASE UJI (hanya membaca).
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUTF8=1
kode=0
venv/bin/python scripts/kemajuan_kecamatan.py || kode=$?
if [ -t 0 ]; then
    read -r -p "Tekan Enter untuk menutup . . . " _ || true
fi
exit "$kode"
