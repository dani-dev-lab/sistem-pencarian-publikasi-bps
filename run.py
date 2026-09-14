"""Entry point aplikasi Flask.

Dua mode:
  produksi (bawaan) : venv/Scripts/python.exe run.py
      Dilayani waitress - server WSGI yang stabil di Windows, tanpa auto-reload
      dan tanpa debugger. Ini yang dipakai jalankan-aplikasi.bat.
  pengembangan      : venv/Scripts/python.exe run.py --dev
      Server bawaan Flask dengan debugger dan auto-reload. JANGAN dipakai di
      jaringan kantor: debugger-nya bisa menjalankan kode dari browser.

Alamat dan port bisa diubah lewat --host / --port.
"""

import argparse
import socket
import sys

from app import create_app

app = create_app()


def _port_terpakai(host, port):
    """True kalau sudah ada yang menerima koneksi di host:port."""
    tujuan = "127.0.0.1" if host == "0.0.0.0" else host
    try:
        with socket.create_connection((tujuan, port), timeout=1):
            return True
    except OSError:
        return False


def main():
    arg = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    arg.add_argument("--dev", action="store_true",
                     help="Mode pengembangan: server Flask dengan debugger dan "
                          "auto-reload.")
    arg.add_argument("--host", default="127.0.0.1",
                     help="Alamat yang didengarkan (default 127.0.0.1 = hanya "
                          "komputer ini; pakai 0.0.0.0 agar bisa diakses dari "
                          "komputer lain di jaringan).")
    arg.add_argument("--port", type=int, default=5000)
    opsi = arg.parse_args()

    if opsi.dev:
        app.run(host=opsi.host, port=opsi.port, debug=True)
        return

    from waitress import serve

    # waitress memasang SO_REUSEADDR, dan di Windows itu berarti DUA server
    # bisa mendengarkan port yang sama tanpa galat - request lalu jatuh ke
    # salah satunya secara acak. Terjadi kalau .bat diklik dua kali. Periksa
    # dulu supaya kejadian itu gagal dengan pesan, bukan diam-diam.
    if _port_terpakai(opsi.host, opsi.port):
        sys.exit(f"Port {opsi.port} sudah dipakai - kemungkinan aplikasi ini "
                 "sudah berjalan di jendela lain.\n"
                 "Pakai yang sudah berjalan, tutup dulu jendela itu, atau "
                 "jalankan dengan port lain: run.py --port 8080")

    print(f"Aplikasi berjalan di http://{opsi.host}:{opsi.port}/  "
          "(tekan Ctrl+C untuk berhenti)", flush=True)
    serve(app, host=opsi.host, port=opsi.port, threads=4)


if __name__ == "__main__":
    main()
