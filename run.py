"""Entry point aplikasi Flask.

Dua mode:
  produksi (bawaan) : venv/Scripts/python.exe run.py
      Dilayani waitress - server WSGI yang stabil di Windows, tanpa auto-reload
      dan tanpa debugger. Ini yang dipakai jalankan-aplikasi.bat.
  pengembangan      : venv/Scripts/python.exe run.py --dev
      Server bawaan Flask dengan debugger dan auto-reload. JANGAN dipakai di
      jaringan kantor: debugger-nya bisa menjalankan kode dari browser.

Alamat dan port bisa diubah lewat --host / --port. --buka-browser (dipakai
.bat) membuka browser SETELAH server benar-benar menjawab, bukan sebelumnya.
"""

import argparse
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from app import create_app

app = create_app()


# Batas tunggu server siap sebelum menyerah membuka browser.
BATAS_SIAP_DETIK = 30


def _buka_browser_saat_siap(url):
    """Poll URL sampai menjawab, baru buka browser. Dijalankan di thread.

    Membuka browser SEBELUM server siap membuat halaman pertama yang dilihat
    orang adalah "ERR_CONNECTION_REFUSED" - terlihat seperti aplikasi rusak
    padahal hanya belum selesai memuat. Jadi tunggu jawaban HTTP dulu.
    """
    mulai = time.time()
    while time.time() - mulai < BATAS_SIAP_DETIK:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status < 500:
                    print(f"Aplikasi siap - membuka browser ke {url}")
                    print("Tekan Ctrl+C untuk berhenti.", flush=True)
                    webbrowser.open(url)
                    return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    print(f"[PERINGATAN] Server belum menjawab setelah {BATAS_SIAP_DETIK} detik. "
          f"Browser tidak dibuka; coba buka {url} secara manual.", flush=True)


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
    arg.add_argument("--buka-browser", action="store_true",
                     help="Buka browser ke alamat aplikasi begitu server siap.")
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

    tujuan = "localhost" if opsi.host in ("127.0.0.1", "0.0.0.0") else opsi.host
    url = f"http://{tujuan}:{opsi.port}/"
    print(f"Menyiapkan aplikasi di {url} ...", flush=True)
    if opsi.buka_browser:
        # daemon: kalau serve() gagal dan proses keluar, thread ini ikut mati
        # tanpa membuka browser ke halaman galat.
        threading.Thread(target=_buka_browser_saat_siap, args=(url,),
                         daemon=True).start()
    else:
        print("Tekan Ctrl+C untuk berhenti.", flush=True)
    serve(app, host=opsi.host, port=opsi.port, threads=4)


if __name__ == "__main__":
    main()
