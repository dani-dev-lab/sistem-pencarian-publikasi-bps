"""Jalankan scripts/perbarui.py dari dalam aplikasi dan simpan keluarannya.

Dipakai halaman /admin/perbarui. Pembaruan butuh 2-5 menit, jadi TIDAK
dijalankan di dalam request: satu thread latar menjalankan subprocess dan
menampung tiap baris keluarannya di memori; request streaming hanya membaca
tampungan itu. Akibatnya menutup tab tidak menghentikan apa pun - proses
tetap jalan, dan halaman bisa dibuka lagi untuk melihat kelanjutannya.

Satu keadaan untuk satu proses server (waitress = satu proses, beberapa
thread), dijaga dengan lock. Kunci antar-PROSES (misalnya .bat berjalan
bersamaan) ditangani perbarui.py sendiri lewat data/pembaruan.lock.
"""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

from app.config import BASE_DIR

FILE_RINGKASAN = BASE_DIR / "data" / "pembaruan_terakhir.json"
# perbarui.py --db-uji menulis ringkasannya ke berkas terpisah (12 Nov 2026).
FILE_RINGKASAN_UJI = BASE_DIR / "data" / "pembaruan_terakhir-uji.json"
FILE_KUNCI = BASE_DIR / "data" / "pembaruan.lock"
SKRIP = BASE_DIR / "scripts" / "perbarui.py"

_kunci = threading.Lock()
_keadaan = {
    "berjalan": False,
    "mulai": None,          # datetime UTC
    "selesai": None,        # datetime UTC
    "kode_keluar": None,
    "baris": [],            # keluaran subprocess, satu string per baris
}


def _pid_hidup(pid):
    """Sama seperti perbarui._proses_hidup - diduplikasi supaya paket app tidak
    perlu mengimpor dari folder scripts/."""
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        kode = wintypes.DWORD()
        return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(kode))) \
            and kode.value == 259                        # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def pid_proses_lain():
    """PID pembaruan yang dijalankan DI LUAR aplikasi ini (.bat/terminal), atau None."""
    try:
        with open(FILE_KUNCI, encoding="utf-8") as f:
            pid = int(f.read().strip() or 0)
    except (OSError, ValueError):
        return None
    return pid if pid and _pid_hidup(pid) else None


def sedang_berjalan():
    with _kunci:
        if _keadaan["berjalan"]:
            return True
    return pid_proses_lain() is not None


def perintah(uji=False):
    """Baris perintah pembaruan.

    Aplikasi dengan KonfigurasiUji (KONFIGURASI_UJI = True) menjalankan
    perbarui.py --db-uji, supaya tombol di halaman admin tidak pernah menulis ke
    produksi selama pengujian (13 Nov 2026). Konfigurasi biasa tetap tanpa
    argumen: pembaruan ke database dari .env, seperti sebelumnya.
    """
    return [sys.executable, "-u", str(SKRIP)] + (["--db-uji"] if uji else [])


def berkas_ringkasan(uji=False):
    return FILE_RINGKASAN_UJI if uji else FILE_RINGKASAN


def _pekerja(argumen):
    lingkungan = {**os.environ, "PYTHONUTF8": "1"}
    try:
        proses = subprocess.Popen(
            argumen,
            cwd=str(BASE_DIR), env=lingkungan,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        for baris in proses.stdout:
            with _kunci:
                _keadaan["baris"].append(baris.rstrip("\r\n"))
        proses.wait()
        kode = proses.returncode
    except Exception as e:  # noqa: BLE001 - apa pun sebabnya, halaman harus tahu
        with _kunci:
            _keadaan["baris"].append(f"GAGAL menjalankan pembaruan: {e}")
        kode = -1
    with _kunci:
        _keadaan["berjalan"] = False
        _keadaan["selesai"] = datetime.now(timezone.utc)
        _keadaan["kode_keluar"] = kode


def mulai(uji=False):
    """Mulai pembaruan di thread latar. Return False kalau sudah ada yang jalan.

    `uji` = current_app.config["KONFIGURASI_UJI"]; lihat perintah().
    """
    with _kunci:
        if _keadaan["berjalan"]:
            return False
        if pid_proses_lain():
            return False
        _keadaan.update(berjalan=True, mulai=datetime.now(timezone.utc),
                        selesai=None, kode_keluar=None, baris=[])
    # daemon: server yang dihentikan tidak menunggu; subprocess-nya sendiri
    # tetap hidup sampai selesai (setiap tahap menulis atomik, aman diulang).
    threading.Thread(target=_pekerja, args=(perintah(uji),), daemon=True,
                     name="pembaruan-data").start()
    return True


def baris_sejak(indeks):
    """(baris baru sejak indeks, masih_berjalan)."""
    with _kunci:
        return _keadaan["baris"][indeks:], _keadaan["berjalan"]


def aliran(indeks=0):
    """Generator baris untuk streaming response; berhenti begitu proses selesai."""
    while True:
        baru, jalan = baris_sejak(indeks)
        for b in baru:
            yield b + "\n"
        indeks += len(baru)
        if not jalan and not baru:
            return
        if not baru:
            time.sleep(0.5)


def keadaan():
    with _kunci:
        return {
            "berjalan": _keadaan["berjalan"],
            "mulai": _keadaan["mulai"],
            "selesai": _keadaan["selesai"],
            "kode_keluar": _keadaan["kode_keluar"],
            "baris": list(_keadaan["baris"]),
        }


def ringkasan_terakhir(uji=False):
    """Isi data/pembaruan_terakhir.json (ditulis perbarui.py), atau None.
    Dengan uji=True: berkas ringkasan run --db-uji."""
    try:
        with open(berkas_ringkasan(uji), encoding="utf-8") as f:
            isi = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    try:
        isi["selesai_pada"] = datetime.fromisoformat(isi["selesai_pada"])
    except (KeyError, ValueError):
        isi["selesai_pada"] = None
    return isi
