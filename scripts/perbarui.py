"""Perbarui data dari WebAPI BPS sampai siap dicari - satu perintah.

Menjalankan empat tahap berurutan:
  1. ambil metadata publikasi   (scripts/ambil_publikasi.py)
  2. unduh PDF yang belum ada   (scripts/unduh_pdf.py)
  3. ekstrak struktur dokumen   (scripts/ekstrak_semua.py, inkremental)
  4. muat ke database           (scripts/muat_ke_database.py, + normalisasi)

Kalau satu tahap gagal, proses BERHENTI di situ. Melanjutkan dengan data
setengah jadi jauh lebih berbahaya daripada berhenti dengan pesan jelas -
misalnya memuat metadata baru tanpa PDF-nya akan membuat entri hilang dari
pencarian tanpa ada yang menyadari.

Dipanggil dari tiga tempat: terminal, perbarui-data.bat, dan halaman
/admin/perbarui (yang menjalankannya sebagai subprocess dan mengalirkan
keluarannya ke browser). Berkas kunci data/pembaruan.lock mencegah dua
pembaruan berjalan bersamaan dari jalur mana pun.

Jalankan:  venv/Scripts/python.exe scripts/perbarui.py
           venv/Scripts/python.exe scripts/perbarui.py --paksa
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

DIR_PROYEK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR_PROYEK)

FILE_META = "data/publikasi_2025_2026.json"
FILE_EKSTRAKSI = "data/hasil_ekstraksi.json"
DIR_PDF = "data/publikasi_pdf"
FILE_RINGKASAN = "data/pembaruan_terakhir.json"   # dibaca /admin/perbarui
FILE_KUNCI = "data/pembaruan.lock"                # berisi PID yang sedang jalan

PESAN_JARINGAN = """
  WebAPI BPS tidak bisa dihubungi.

  Penyebab paling umum: laptop tidak tersambung ke jaringan "BPS - Pegawai".
  Jaringan "BPS - Tamu" MEMBLOKIR akses ke webapi.bps.go.id.

  Periksa koneksi lalu jalankan ulang perintah ini.
"""

# Penanda kegagalan jaringan pada keluaran tahap pengambilan data.
JEJAK_JARINGAN = (
    "connection", "timed out", "timeout", "getaddrinfo", "name resolution",
    "max retries", "connectionerror", "unreachable", "refused",
)


def baca_json(path, bawaan=None):
    if not os.path.exists(path):
        return bawaan
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return bawaan


def daftar_pub(meta):
    return (meta or {}).get("publikasi", [])


def entri_per_pub(hasil):
    """{pub_id: jumlah_entri} dari berkas hasil ekstraksi, format apa pun."""
    if not hasil:
        return {}
    daftar = hasil if isinstance(hasil, list) else hasil.get("hasil", [])
    return {h["publikasi_id"]: h["jumlah_entri"] for h in daftar}


def jalankan(nama_tahap, perintah):
    """Jalankan satu tahap. Return (sukses, keluaran)."""
    print()
    print("=" * 74)
    print(f"TAHAP: {nama_tahap}")
    print("=" * 74)

    # Keluaran DIALIRKAN baris per baris, bukan ditahan sampai tahap selesai.
    # Tahap 1 saja butuh ~2 menit (65+ halaman WebAPI, jeda 1 detik); kalau
    # layar diam selama itu, orang yang menjalankan .bat menyangka macet.
    # -u dan PYTHONUTF8 supaya anak proses tidak menahan keluarannya di
    # buffer dan tidak tersandung encoding konsol Windows.
    lingkungan = {**os.environ, "PYTHONUTF8": "1"}
    proses = subprocess.Popen(
        [sys.executable, "-u", *perintah],
        cwd=DIR_PROYEK, env=lingkungan,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    tampung = []
    for baris in proses.stdout:
        tampung.append(baris)
        # Baris pdfminer tentang FontBBox membanjiri layar tanpa memberi informasi.
        if "FontBBox" in baris or "CropBox" in baris or "MediaBox" in baris:
            continue
        print(baris, end="", flush=True)
    proses.wait()

    return proses.returncode == 0, "".join(tampung)


def tulis_ringkasan(status, **isi):
    """Catat hasil akhir ke data/pembaruan_terakhir.json.

    Dibaca halaman /admin/perbarui untuk menampilkan ringkasan yang bisa
    dipahami petugas - jauh lebih andal daripada menebak dari teks log.
    Ditulis apa pun jalurnya (.bat maupun browser), jadi halaman admin juga
    tahu kalau pembaruan terakhir dijalankan tim IT dari terminal.
    """
    isi.update(status=status,
               selesai_pada=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    sementara = FILE_RINGKASAN + ".tmp"
    with open(sementara, "w", encoding="utf-8") as f:
        json.dump(isi, f, ensure_ascii=False, indent=2)
    os.replace(sementara, FILE_RINGKASAN)


def gagal(nama_tahap, keluaran, mulai):
    print()
    print("=" * 74)
    print(f"GAGAL di tahap: {nama_tahap}")
    print("=" * 74)

    jaringan = any(j in keluaran.lower() for j in JEJAK_JARINGAN)
    if jaringan:
        print(PESAN_JARINGAN)
    else:
        print("  Proses dihentikan supaya database tidak terisi data setengah jadi.")
        print("  Perbaiki penyebabnya di atas, lalu jalankan ulang perintah ini.")
    tulis_ringkasan("gagal", tahap=nama_tahap, jaringan=jaringan,
                    durasi_detik=round(time.time() - mulai))
    sys.exit(1)


# --------------------------------------------------------------------------
# Kunci: satu pembaruan pada satu waktu
# --------------------------------------------------------------------------

def _proses_hidup(pid):
    """Apakah proses dengan PID ini masih berjalan.

    Di Windows JANGAN memakai os.kill(pid, 0): sinyal selain CTRL_C/CTRL_BREAK
    diterjemahkan menjadi TerminateProcess - "memeriksa" berarti MEMBUNUH.
    """
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        kode = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(kode)):
            return False
        return kode.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def pembaruan_sedang_berjalan():
    """PID pembaruan yang sedang berjalan, atau None.

    Kunci yang PID-nya sudah mati dianggap basi (sisa proses yang dibunuh
    atau laptop di-hibernate) dan boleh ditimpa.
    """
    try:
        with open(FILE_KUNCI, encoding="utf-8") as f:
            pid = int(f.read().strip() or 0)
    except (OSError, ValueError):
        return None
    return pid if pid and _proses_hidup(pid) else None


def ambil_kunci():
    """Buat berkas kunci berisi PID proses ini. False kalau sudah ada yang jalan.

    Dua pembaruan bersamaan - misalnya .bat dan tombol di browser - akan
    saling menimpa berkas metadata dan hasil ekstraksi. Kunci ini yang
    mencegahnya, di jalur mana pun pembaruan dijalankan.
    """
    if pembaruan_sedang_berjalan():
        return False
    with open(FILE_KUNCI, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    return True


def lepas_kunci():
    try:
        os.remove(FILE_KUNCI)
    except OSError:
        pass


def main():
    arg = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    arg.add_argument("--paksa", action="store_true",
                     help="Ekstrak ulang SEMUA publikasi, bukan hanya yang baru. "
                          "Pakai setiap kali parser diperbarui.")
    arg.add_argument("--tahun-min", type=int, default=None,
                     help="Tahun rilis paling awal (default: 2 tahun terakhir).")
    opsi = arg.parse_args()

    os.chdir(DIR_PROYEK)
    pid_lain = pembaruan_sedang_berjalan()
    if pid_lain or not ambil_kunci():
        print("PEMBARUAN SUDAH BERJALAN di proses lain "
              f"(PID {pid_lain}). Tunggu sampai selesai, jangan jalankan dua kali.")
        sys.exit(2)
    try:
        _jalankan_semua(opsi)
    finally:
        lepas_kunci()


def _jalankan_semua(opsi):
    mulai = time.time()

    # Keadaan awal, untuk membandingkan di akhir.
    meta_lama = baca_json(FILE_META)
    id_lama = {p["pub_id"] for p in daftar_pub(meta_lama)}
    entri_lama = entri_per_pub(baca_json(FILE_EKSTRAKSI))
    pdf_lama = len([n for n in os.listdir(DIR_PDF)
                    if n.lower().endswith(".pdf")]) if os.path.isdir(DIR_PDF) else 0

    # ---------------------------- 1. metadata ----------------------------
    perintah = ["scripts/ambil_publikasi.py"]
    if opsi.tahun_min is not None:
        perintah += ["--tahun-min", str(opsi.tahun_min)]
    ok, keluaran = jalankan("1/4 Ambil metadata publikasi", perintah)
    if not ok:
        gagal("1/4 Ambil metadata publikasi", keluaran, mulai)

    meta_baru = baca_json(FILE_META)
    id_baru = {p["pub_id"] for p in daftar_pub(meta_baru)}
    publikasi_baru = id_baru - id_lama

    # Halaman yang gagal ditarik berarti daftar publikasinya belum utuh.
    # Melanjutkan bisa membuat publikasi yang ada terlihat seperti terhapus.
    if (meta_baru or {}).get("halaman_gagal"):
        print()
        print(f"  {len(meta_baru['halaman_gagal'])} halaman WebAPI gagal ditarik.")
        gagal("1/4 Ambil metadata publikasi", "connection", mulai)

    # Tidak ada yang baru DAN tidak dipaksa -> tidak ada yang perlu dikerjakan.
    if not publikasi_baru and not opsi.paksa:
        print()
        print("=" * 74)
        print("TIDAK ADA PUBLIKASI BARU")
        print("=" * 74)
        print(f"  {len(id_baru)} publikasi di daftar, semuanya sudah diproses.")
        print(f"  Selesai dalam {time.time() - mulai:.0f} detik.")
        print()
        print("  Pakai --paksa kalau ingin mengekstrak ulang setelah parser diubah.")
        tulis_ringkasan("tidak_ada_baru", jumlah_publikasi=len(id_baru),
                        durasi_detik=round(time.time() - mulai))
        return

    if publikasi_baru:
        print()
        print(f"  {len(publikasi_baru)} publikasi baru terdeteksi.")

    # ---------------------------- 2. unduh PDF ----------------------------
    ok, keluaran = jalankan("2/4 Unduh PDF baru", ["scripts/unduh_pdf.py"])
    if not ok:
        gagal("2/4 Unduh PDF baru", keluaran, mulai)

    # --------------------------- 3. ekstraksi ---------------------------
    perintah = ["scripts/ekstrak_semua.py"]
    if opsi.paksa:
        perintah.append("--paksa")
    ok, keluaran = jalankan("3/4 Ekstrak struktur dokumen", perintah)
    if not ok:
        gagal("3/4 Ekstrak struktur dokumen", keluaran, mulai)

    # --------------------------- 4. muat ke DB ---------------------------
    ok, keluaran = jalankan("4/4 Muat ke database", ["scripts/muat_ke_database.py"])
    if not ok:
        gagal("4/4 Muat ke database", keluaran, mulai)

    # ----------------------------- ringkasan -----------------------------
    entri_baru = entri_per_pub(baca_json(FILE_EKSTRAKSI))
    pdf_baru = len([n for n in os.listdir(DIR_PDF) if n.lower().endswith(".pdf")])

    tambah = sum(entri_baru.values()) - sum(entri_lama.values())
    berubah = [pid for pid, n in entri_baru.items()
               if entri_lama.get(pid) is not None and entri_lama[pid] != n]

    print()
    print("=" * 74)
    print("RINGKASAN PEMBARUAN")
    print("=" * 74)
    print(f"  Publikasi di daftar : {len(id_lama)} -> {len(id_baru)} "
          f"({len(publikasi_baru)} baru)")
    print(f"  Berkas PDF          : {pdf_lama} -> {pdf_baru}")
    print(f"  Entri dokumen       : {sum(entri_lama.values())} -> "
          f"{sum(entri_baru.values())} ({tambah:+d})")
    print(f"  Publikasi diekstrak ulang: {len(berubah)}")
    print(f"  Waktu               : {time.time() - mulai:.0f} detik")

    judul = {p["pub_id"]: p.get("title", "") for p in daftar_pub(meta_baru)}
    if publikasi_baru:
        print()
        print("  Publikasi baru:")
        for pid in sorted(publikasi_baru):
            print(f"    {entri_baru.get(pid, 0):>4} entri  {judul.get(pid, pid)[:56]}")

    tulis_ringkasan(
        "sukses",
        jumlah_publikasi=len(id_baru),
        publikasi_baru=[{"pub_id": pid, "judul": judul.get(pid, pid),
                         "entri": entri_baru.get(pid, 0)}
                        for pid in sorted(publikasi_baru)],
        entri_sebelum=sum(entri_lama.values()),
        entri_sesudah=sum(entri_baru.values()),
        diekstrak_ulang=len(berubah),
        durasi_detik=round(time.time() - mulai),
    )


if __name__ == "__main__":
    main()
