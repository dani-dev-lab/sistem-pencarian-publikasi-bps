"""Isi kolom teks_ternormalisasi untuk entri_dokumen DAN publikasi.

Pembungkus terminal untuk `app.services.normalisasi_data.jalankan()` - logika
sebenarnya ada di sana supaya bisa dipanggil juga oleh tombol "Terapkan ke
data" di /admin/kamus. Dua jalan masuk, satu implementasi.

IDEMPOTEN: menulis ulang nilai, bukan menambah baris. Aman dijalankan lagi
setiap kali `data/kamus_sinonim.json` diperbarui.

Jalankan:  venv/Scripts/python.exe scripts/isi_normalisasi.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.normalisasi_data import jalankan as _jalankan


def jalankan():
    """Versi terminal: laporan rinci dicetak ke layar.

    Tetap bernama `jalankan` karena scripts/muat_ke_database.py mengimpornya
    dengan nama ini di akhir pemuatan.
    """
    return _jalankan(cetak=print)


def main():
    app = create_app()
    with app.app_context():
        jalankan()


if __name__ == "__main__":
    main()
