"""Isi cache OCR untuk publikasi tanpa lapisan teks - TANPA menyentuh database.

Memisahkan pekerjaan berat (EasyOCR, +-15 detik/halaman CPU) dari pemuatan:
perintah ini hanya menulis data/ocr_cache/<domain>/<pub_id>/. Pemuatan ke
database tetap lewat perbarui.py, yang lalu membaca cache ini.

Sifat:
- tidak membuka koneksi MySQL; PDF dicari di data/publikasi_pdf/*/<pub_id>.pdf
- bisa dilanjutkan: halaman yang cache-nya sudah ada dilewati, deteksi
  halaman tanpa teks disimpan di _meta.json
- log ke data/log_ocr/<waktu>.log, kemajuan ringkas ke data/log_ocr/kemajuan.txt
- mencegah Windows tidur selama berjalan; menolak jalan dua kali bersamaan

Jalankan (dari folder proyek):
  venv\\Scripts\\python.exe scripts\\isi_cache_ocr.py data\\ocr_target.txt
  venv\\Scripts\\python.exe scripts\\isi_cache_ocr.py data\\ocr_target.txt --batas-halaman 15   (uji)
Kemajuan:
  type data\\log_ocr\\kemajuan.txt
"""

import argparse
import glob
import os
import sys
import time
from datetime import datetime

DIR_PROYEK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR_PROYEK)

DIR_LOG = os.path.join(DIR_PROYEK, "data", "log_ocr")
KUNCI = os.path.join(DIR_LOG, "isi_cache.lock")
KEMAJUAN = os.path.join(DIR_LOG, "kemajuan.txt")


def _proses_hidup(pid):
    """Sama dengan perbarui._proses_hidup: di Windows JANGAN os.kill(pid, 0)."""
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import ctypes
    from ctypes import wintypes
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    try:
        kode = wintypes.DWORD()
        return bool(k.GetExitCodeProcess(h, ctypes.byref(kode))) and kode.value == 259
    finally:
        k.CloseHandle(h)


def _jaga_tetap_bangun(aktif):
    if os.name == "nt":
        import ctypes
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | (0x00000001 if aktif else 0))
        except (AttributeError, OSError):
            pass


def baca_target(path):
    """Satu pub_id per baris; teks sesudah '#' diabaikan."""
    hasil = []
    for baris in open(path, encoding="utf-8"):
        pid = baris.split("#", 1)[0].strip()
        if pid:
            hasil.append(pid)
    return hasil


def main():
    arg = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    arg.add_argument("target", help="berkas daftar pub_id (mis. data/ocr_target.txt)")
    arg.add_argument("--batas-halaman", type=int, default=None,
                     help="UJI: OCR paling banyak N halaman per publikasi")
    opsi = arg.parse_args()
    os.chdir(DIR_PROYEK)
    os.makedirs(DIR_LOG, exist_ok=True)

    if os.path.exists(KUNCI):
        try:
            pid_lain = int(open(KUNCI).read().strip() or 0)
        except ValueError:
            pid_lain = 0
        if pid_lain and _proses_hidup(pid_lain):
            raise SystemExit(f"TIDAK DIJALANKAN: isi_cache_ocr sudah berjalan (PID {pid_lain}).")
    open(KUNCI, "w").write(str(os.getpid()))

    berkas_log = open(os.path.join(DIR_LOG, f"{datetime.now():%Y%m%d-%H%M%S}.log"), "a", encoding="utf-8")

    def log(teks):
        baris = f"{datetime.now():%H:%M:%S} {teks}"
        print(baris, flush=True)
        berkas_log.write(baris + "\n")
        berkas_log.flush()

    def kemajuan(teks):
        with open(KEMAJUAN, "w", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {teks}\n")

    _jaga_tetap_bangun(True)
    try:
        from app.services import ocr
        if not ocr.tersedia():
            raise SystemExit("EasyOCR tidak terpasang: venv\\Scripts\\python.exe -m pip install -r requirements-ocr.txt")
        target = baca_target(opsi.target)
        log(f"mulai: {len(target)} publikasi, batas halaman {opsi.batas_halaman or '-'}")
        mulai_semua = time.perf_counter()
        total_ocr = 0
        for i, pid in enumerate(target, 1):
            cocok = glob.glob(os.path.join("data", "publikasi_pdf", "*", f"{pid}.pdf"))
            if not cocok:
                log(f"[{i}/{len(target)}] {pid}: PDF tidak ditemukan, dilewati")
                continue
            path = cocok[0]
            kemajuan(f"publikasi {i}/{len(target)} {pid}: mendeteksi halaman tanpa teks")
            t0 = time.perf_counter()
            halaman, n_tanpa_teks, jumlah = ocr.halaman_tanpa_teks(path)
            if not halaman:
                log(f"[{i}/{len(target)}] {pid}: BUKAN publikasi tanpa teks "
                    f"({n_tanpa_teks}/{jumlah} halaman < {ocr.AMBANG_PUBLIKASI:.0%}), dilewati")
                continue
            sudah = [n for n in halaman if os.path.exists(ocr.berkas_cache(path, n))]
            belum = [n for n in halaman if n not in set(sudah)]
            if opsi.batas_halaman is not None:
                belum = belum[:opsi.batas_halaman]
            log(f"[{i}/{len(target)}] {pid}: {len(halaman)} halaman tanpa teks "
                f"(deteksi {time.perf_counter() - t0:.0f} s), cache sudah {len(sudah)}, akan di-OCR {len(belum)}")

            def log_hal(teks, i=i, pid=pid, belum=belum):
                log(teks)
                kemajuan(f"publikasi {i}/{len(target)} {pid}: {teks.strip()} | total di-OCR malam ini {total_ocr + 1}")

            n = ocr.isi_cache(path, belum, log=log_hal)
            total_ocr += n
            log(f"[{i}/{len(target)}] {pid}: selesai, {n} halaman di-OCR")
        menit = (time.perf_counter() - mulai_semua) / 60
        log(f"SELESAI: {total_ocr} halaman di-OCR dalam {menit:.0f} menit")
        kemajuan(f"SELESAI: {total_ocr} halaman di-OCR dalam {menit:.0f} menit")
    finally:
        _jaga_tetap_bangun(False)
        berkas_log.close()
        try:
            os.remove(KUNCI)
        except OSError:
            pass


if __name__ == "__main__":
    main()
