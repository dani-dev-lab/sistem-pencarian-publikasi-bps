"""Potret 28 URL (tests/potret_tampilan.py) langsung di PRODUKSI, log pencarian MATI.
  python potret_produksi.py <keluar.json>
Hanya membaca (kolom baru sudah ditambahkan di langkah 2)."""
import os, sys
DIR = "C:/sistem-pencarian-bps"; sys.path.insert(0, f"{DIR}/tests")
import potret_tampilan as P          # mengunci PYTHONHASHSEED=0 (jalan ulang sendiri)
from app.config import Config
P.konfigurasi = lambda _nama: type("KonfigurasiProduksiTanpaLog", (Config,), {"CATAT_LOG_PENCARIAN": False})
P.simpan(sys.argv[1], "produksi")
