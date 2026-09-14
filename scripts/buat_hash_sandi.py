"""Buat hash kata sandi admin untuk ditaruh di .env (ADMIN_PASSWORD_HASH).

Sandi diketik dua kali tanpa tampil di layar, lalu hash-nya dicetak. Yang
disimpan di .env hanya hash - sandi aslinya tidak pernah ditulis ke berkas
mana pun, jadi kalau .env bocor sandi tetap tidak ketahuan.

Dipakai juga untuk MENGGANTI sandi: jalankan lagi, ganti baris
ADMIN_PASSWORD_HASH di .env, lalu jalankan ulang aplikasi.

Jalankan:  venv/Scripts/python.exe scripts/buat_hash_sandi.py
"""

import getpass
import sys

from werkzeug.security import generate_password_hash

PANJANG_MINIMAL = 8


def main():
    print("Membuat hash kata sandi halaman admin.")
    print("Sandi tidak akan tampil saat diketik.")
    print()

    sandi = getpass.getpass("Kata sandi baru      : ")
    if len(sandi) < PANJANG_MINIMAL:
        print(f"Sandi terlalu pendek - minimal {PANJANG_MINIMAL} karakter.")
        sys.exit(1)
    ulang = getpass.getpass("Ketik sekali lagi    : ")
    if sandi != ulang:
        print("Kedua isian tidak sama. Ulangi dari awal.")
        sys.exit(1)

    hash_sandi = generate_password_hash(sandi)

    print()
    print("Salin baris berikut ke berkas .env (ganti baris lama kalau sudah ada):")
    print()
    print(f"ADMIN_PASSWORD_HASH={hash_sandi}")
    print()
    print("Setelah itu jalankan ulang aplikasi supaya sandi baru berlaku.")


if __name__ == "__main__":
    main()
