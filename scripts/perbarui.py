"""Perbarui data dari WebAPI BPS sampai siap dicari - satu perintah.

Untuk tiap domain aktif di data/wilayah.json:
  1. ambil metadata   daftar publikasi dari WebAPI, utuh atau tidak sama sekali
  2. tentukan         publikasi yang perlu dikerjakan, dari database
  3. unduh PDF        yang baru, usang, hilang, atau rusak
  4. ekstrak + muat   langsung ke MySQL, satu publikasi per transaksi

Satu domain gagal TIDAK menghentikan domain lain, dan satu publikasi gagal tidak
menghentikan publikasi lain. Yang gagal tetap memakai data lamanya dan dicoba
lagi pada pembaruan berikutnya.

Dipanggil dari tiga tempat: terminal, perbarui-data.bat, dan halaman
/admin/perbarui (yang menjalankannya sebagai subprocess dan mengalirkan
keluarannya ke browser). Berkas kunci data/pembaruan.lock mencegah dua
pembaruan berjalan bersamaan dari jalur mana pun.

Kode keluar: 0 berhasil, 1 gagal, 2 ada pembaruan lain berjalan, 3 sebagian gagal.

Jalankan:  venv/Scripts/python.exe scripts/perbarui.py
           venv/Scripts/python.exe scripts/perbarui.py --hanya-periksa
           venv/Scripts/python.exe scripts/perbarui.py --lokal --paksa
"""

import argparse
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone

DIR_PROYEK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR_PROYEK)

import sqlalchemy as sa
from sqlalchemy.engine import make_url

from app import create_app
from app.config import Config, KonfigurasiUji
from app.models import EntriDokumen, Publikasi, db
from app.services import pipeline_data, sumber_bps, versi_data
from app.services.sumber_bps import GagalAmbil, samarkan
from app.services.wilayah import muat_wilayah, pola_judul_dikecualikan, wilayah_aktif

FILE_RINGKASAN = "data/pembaruan_terakhir.json"   # dibaca /admin/perbarui
FILE_RINGKASAN_UJI = "data/pembaruan_terakhir-uji.json"   # run --db-uji
FILE_KUNCI = "data/pembaruan.lock"                # berisi PID yang sedang jalan
FILE_PEMERIKSAAN = "data/pemeriksaan_domain.json" # hasil --hanya-periksa
# OCR halaman tanpa lapisan teks (app/services/ocr.py). Dimatikan dengan
# --tanpa-ocr: halaman itu lalu dilewati dan dicatat, perilaku sebelum OCR ada.
OCR_AKTIF = True

DIR_LOG = "data/log_pembaruan"                    # salinan keluaran tiap run

TAHAP = ("ambil_metadata", "unduh", "ekstraksi", "muat")

# Laju ekstraksi terukur (pemuatan ulang penuh 9 Nov 2026: 1.294 detik untuk
# 721 MB PDF di laptop pengembang). Hanya untuk perkiraan di --hanya-periksa.
DETIK_EKSTRAKSI_PER_MB = 1.8

KODE_SUKSES, KODE_GAGAL, KODE_TERKUNCI, KODE_SEBAGIAN = 0, 1, 2, 3

PESAN_JARINGAN = """
  WebAPI BPS tidak bisa dihubungi.

  Periksa koneksi internet. Kalau browser bisa membuka situs BPS tetapi
  pembaruan tetap gagal ("connection reset"), cek DNS di PowerShell:
      Resolve-DnsName webapi.bps.go.id
  Hasil 10.0.11.232 berarti DNS jaringan kantor mengarahkan ke alamat yang
  menolak koneksi (pernah terjadi Nov 2026). Pindah jaringan atau hubungi
  tim IT, lalu jalankan ulang perintah ini.
"""

PESAN_SKEMA = """
  Database belum memakai struktur multi-domain. Jalankan sekali:

      venv\\Scripts\\python.exe scripts\\migrasi_multidomain.py

  lalu ulangi perintah ini.
"""


def judul_bagian(teks):
    print()
    print("=" * 74)
    print(teks)
    print("=" * 74)


def tulis_atomik(path, isi):
    sementara = path + ".tmp"
    with open(sementara, "w", encoding="utf-8") as f:
        json.dump(isi, f, ensure_ascii=False, indent=2)
    os.replace(sementara, path)


class Salin:
    """Tulis ke layar DAN ke berkas log sekaligus.

    Pembaruan besar dibiarkan berjalan semalaman; jendela .bat bisa tertutup
    atau isinya tergulung habis. Berkas log di data/log_pembaruan/ tetap ada
    untuk diperiksa besok paginya.
    """

    def __init__(self, asli, berkas):
        self.asli, self.berkas = asli, berkas

    def write(self, teks):
        self.asli.write(teks)
        self.berkas.write(samarkan(teks))
        return len(teks)

    def flush(self):
        self.asli.flush()
        self.berkas.flush()


def info_jaringan():
    """Jaringan yang dipakai run ini, untuk laporan (revisi 3).

    SSID Wi-Fi (Windows, lewat netsh) dan alamat IP webapi.bps.go.id menurut
    DNS yang dipakai - DNS kantor pernah mengarahkannya ke 10.0.11.232 yang
    menolak koneksi (lihat CLAUDE.md, Catatan lingkungan).
    """
    import socket
    import subprocess
    info = {"ssid": None, "webapi_ip": None}
    try:
        keluaran = subprocess.run(["netsh", "wlan", "show", "interfaces"],
                                  capture_output=True, text=True, timeout=10,
                                  errors="replace").stdout
        for baris in keluaran.splitlines():
            kiri, _, kanan = baris.partition(":")
            if kiri.strip() == "SSID":
                info["ssid"] = kanan.strip()
                break
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        info["webapi_ip"] = socket.gethostbyname("webapi.bps.go.id")
    except OSError:
        pass
    return info


def jaga_tetap_bangun(aktif):
    """Cegah Windows tidur selama pembaruan berjalan (tidak mencegah tutup layar
    laptop kalau setelan 'tutup layar = tidur'). Tanpa efek di sistem lain."""
    if os.name != "nt":
        return
    import ctypes
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    bendera = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if aktif else 0)
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(bendera)
    except (AttributeError, OSError):
        pass


def tulis_ringkasan(status, **isi):
    """Catat hasil akhir ke data/pembaruan_terakhir.json.

    Dibaca halaman /admin/perbarui untuk menampilkan ringkasan yang bisa
    dipahami petugas - jauh lebih andal daripada menebak dari teks log.
    Ditulis apa pun jalurnya (.bat maupun browser), jadi halaman admin juga
    tahu kalau pembaruan terakhir dijalankan tim IT dari terminal.
    """
    isi.update(status=status,
               selesai_pada=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    tulis_atomik(FILE_RINGKASAN, isi)


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
    saling menimpa PDF dan entri yang sama. Kunci ini yang mencegahnya, di
    jalur mana pun pembaruan dijalankan.
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


# --------------------------------------------------------------------------
# Pengaman
# --------------------------------------------------------------------------

def pastikan_skema():
    """Buat tabel kalau belum ada, tolak database lama yang belum dimigrasi.

    db.create_all() tidak mengubah tabel yang sudah ada, jadi database lama
    tetap harus lewat scripts/migrasi_multidomain.py.
    """
    db.create_all()
    kolom = {k["name"] for k in sa.inspect(db.engine).get_columns("publikasi")}
    if "domain" not in kolom:
        print(PESAN_SKEMA)
        sys.exit(KODE_GAGAL)
    # Penanda versi untuk korpus pencarian di memori. DDL di sini, SEBELUM
    # transaksi penulis mana pun (CREATE TABLE memaksa commit di MySQL).
    versi_data.pastikan_tabel()
    # Kolom tambahan untuk database lama (publikasi.halaman_ocr, dll.).
    from app.models.skema import pastikan_kolom
    pastikan_kolom()


def domain_terhalang(aktif):
    """Domain aktif yang belum boleh dimuat karena belum lolos --hanya-periksa.

    Primary key publikasi adalah pub_id saja, dengan anggapan pub_id tidak
    bertabrakan antar-domain. Anggapan itu harus dibuktikan dengan data nyata
    SEBELUM domain baru pertama kali dimuat.

    Berlaku hanya kalau domain aktif lebih dari satu dan domain itu belum punya
    baris di database. Dengan satu domain, tabrakan antar-domain tidak mungkin.
    """
    if len(aktif) < 2:
        return {}
    try:
        with open(FILE_PEMERIKSAAN, encoding="utf-8") as f:
            laporan = json.load(f)
    except (OSError, ValueError):
        laporan = {}

    terhalang = {}
    for w in aktif:
        kode = w["kode"]
        if Publikasi.query.filter_by(domain=kode).first() is not None:
            continue
        if kode not in laporan.get("domain_berhasil", []):
            terhalang[kode] = "belum lolos scripts/perbarui.py --hanya-periksa"
        elif laporan.get("tabrakan"):
            terhalang[kode] = (f"--hanya-periksa menemukan {len(laporan['tabrakan'])} "
                               f"tabrakan pub_id, lihat {FILE_PEMERIKSAAN}")
    db.session.commit()
    return terhalang


# --------------------------------------------------------------------------
# --hanya-periksa
# --------------------------------------------------------------------------

def jalankan_pemeriksaan():
    """Tarik metadata SEMUA wilayah di konfigurasi dan cari tabrakan pub_id.

    Tidak menulis apa pun ke database dan tidak mengunduh PDF. Memeriksa daftar
    SEMUA tahun, bukan hanya jendela rilis yang dipakai: jendela itu bergeser
    tiap tahun, jadi tabrakan di publikasi lama pun akhirnya bisa berpengaruh.
    """
    mulai = time.time()
    pemilik = {}        # pub_id -> [(kode, judul)]
    per_domain = []
    wilayah = muat_wilayah()

    for i, w in enumerate(wilayah):
        kode = w["kode"]
        judul_bagian(f"PERIKSA {kode} {w['nama']}")
        try:
            daftar = sumber_bps.ambil_domain(kode)
        except GagalAmbil as e:
            per_domain.append({"kode": kode, "nama": w["nama"], "status": "gagal",
                               "pesan": str(e), "jaringan": e.jaringan})
            continue
        jendela = sumber_bps.tahun_dipakai()
        lolos = sumber_bps.saring_tahun(daftar, jendela)
        lolos, dikecualikan = sumber_bps.saring_judul(lolos, pola_judul_dikecualikan())
        for p in daftar:
            pemilik.setdefault(p["pub_id"], []).append((kode, (p.get("title") or "").strip()))
        urutan = sumber_bps.cek_urutan(daftar, min(jendela))
        sudah = {pid for (pid,) in db.session.query(Publikasi.id).filter(
            Publikasi.id.in_([p["pub_id"] for p in lolos]))} if lolos else set()
        db.session.commit()
        baru = [p for p in lolos if p["pub_id"] not in sudah]
        per_domain.append({"kode": kode, "nama": w["nama"], "status": "berhasil",
                           "publikasi_semua_tahun": len(daftar),
                           "publikasi_lolos_filter": len(lolos),
                           "publikasi_dikecualikan_judul": len(dikecualikan),
                           "judul_dikecualikan": [(p.get("title") or "")[:90] for p in dikecualikan],
                           "sudah_di_database": len(sudah),
                           "perlu_diunduh": len(baru),
                           "perkiraan_mb_perlu_diunduh": round(sum(
                               sumber_bps.ukuran_mb(p.get("size")) for p in baru), 1),
                           "urutan": urutan})
        print(f"  {len(daftar)} publikasi semua tahun, {len(lolos)} lolos filter tahun"
              f" dan judul ({len(dikecualikan)} dikecualikan menurut judul)")
        print(f"  perlu diunduh {len(baru)} (~{per_domain[-1]['perkiraan_mb_perlu_diunduh']} MB);"
              f" urutan rl_date: {urutan['pelanggaran']} pelanggaran, {urutan['terlewat']}"
              f" terlewat bila berhenti di halaman {urutan['halaman_dibaca']}/{urutan['halaman_total']}")
        if i < len(wilayah) - 1:
            time.sleep(sumber_bps.JEDA_DETIK)

    tabrakan = [{"pub_id": pid, "pemilik": [{"domain": k, "judul": j} for k, j in daftar]}
                for pid, daftar in pemilik.items() if len(daftar) > 1]

    # Bandingkan juga dengan database: publikasi yang di API hanya dimiliki satu
    # domain tetap bertabrakan kalau tersimpan sebagai milik domain lain.
    tersimpan = dict(db.session.query(Publikasi.id, Publikasi.domain).all())
    db.session.commit()
    for pid, daftar in pemilik.items():
        if len(daftar) == 1 and tersimpan.get(pid, daftar[0][0]) != daftar[0][0]:
            tabrakan.append({"pub_id": pid, "domain_tersimpan": tersimpan[pid],
                             "pemilik": [{"domain": k, "judul": j} for k, j in daftar]})

    berhasil = [d["kode"] for d in per_domain if d["status"] == "berhasil"]
    gagal = [d for d in per_domain if d["status"] == "gagal"]
    tulis_atomik(FILE_PEMERIKSAAN, {
        "diperiksa_pada": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "domain_berhasil": berhasil,
        "per_domain": per_domain,
        "pub_id_diperiksa": len(pemilik),
        "tabrakan": tabrakan,
    })

    judul_bagian("HASIL PEMERIKSAAN")
    print(f"  Domain berhasil diperiksa : {len(berhasil)} dari {len(wilayah)}")
    for d in gagal:
        print(f"    GAGAL {d['kode']} {d['nama']}: {d['pesan']}")
    print(f"  pub_id diperiksa          : {len(pemilik)}")
    print(f"  Tabrakan antar-domain     : {len(tabrakan)}")
    for t in tabrakan[:20]:
        print(f"    {t['pub_id']}: " + "; ".join(
            f"{p['domain']} {p['judul'][:40]!r}" for p in t["pemilik"]))
    ok = [d for d in per_domain if d["status"] == "berhasil"]
    total_mb = sum(d["perkiraan_mb_perlu_diunduh"] for d in ok)
    print(f"  Perlu diunduh             : {sum(d['perlu_diunduh'] for d in ok)} publikasi, "
          f"~{total_mb:,.0f} MB (field size API, per berkas tidak akurat)")
    print(f"  Perkiraan ekstraksi       : ~{total_mb * DETIK_EKSTRAKSI_PER_MB / 60:,.0f} menit "
          f"({DETIK_EKSTRAKSI_PER_MB} detik/MB, terukur 9 Nov 2026)")
    print(f"  Urutan rl_date            : {sum(d['urutan']['pelanggaran'] for d in ok)} pelanggaran, "
          f"{sum(d['urutan']['terlewat'] for d in ok)} publikasi terlewat bila berhenti lebih awal")
    print(f"  Waktu                     : {time.time() - mulai:.0f} detik")
    print(f"  Laporan                   : {FILE_PEMERIKSAAN}")
    print()
    print("  Database tidak diubah dan tidak ada PDF yang diunduh.")

    if tabrakan or len(gagal) == len(wilayah):
        return KODE_GAGAL
    return KODE_SEBAGIAN if gagal else KODE_SUKSES


# --------------------------------------------------------------------------
# Pembaruan
# --------------------------------------------------------------------------

def proses_tugas(t, durasi, hasil):
    """Unduh (kalau perlu), ekstrak, dan muat satu publikasi."""
    print(f"  {t['judul'][:52]:<52} [{', '.join(t['alasan'])}]", flush=True)

    def gagal(tahap, pesan):
        pesan = samarkan(pesan)
        print(f"      GAGAL di {tahap}: {pesan[:120]}", flush=True)
        hasil["gagal"].append({"pub_id": t["pub_id"], "judul": t["judul"],
                               "tahap": tahap, "pesan": pesan[:300]})

    if t["unduh"]:
        if not t["url_pdf"]:
            gagal("unduh", "publikasi tidak punya URL PDF")
            return
        # Jeda SEBELUM unduhan: unduhan pertama datang tepat setelah halaman
        # daftar terakhir, dan jeda sesudah unduhan tidak menjaga celah itu.
        time.sleep(sumber_bps.JEDA_DETIK)   # jeda sesuai Term of Use
        mulai = time.perf_counter()
        stat = {}
        pesan = sumber_bps.unduh_pdf(t["url_pdf"], t["path"], stat)
        durasi["unduh"] += time.perf_counter() - mulai
        u = hasil["unduhan"]
        u["percobaan_ulang"] += max(0, stat["percobaan"] - 1)
        u["putus"] += stat["putus"]
        if pesan:
            u["gagal"] += 1
            gagal("unduh", pesan)
            return
        u["berkas"] += 1
        u["byte"] += stat["byte"]
        u["detik_transfer"] += stat["detik_transfer"]
        kbps = stat["byte"] / 1024 / max(stat["detik_transfer"], 0.001)
        print(f"      unduh {stat['byte'] / 1e6:.1f} MB, {kbps:,.0f} KB/detik"
              + (f", {stat['percobaan']} percobaan" if stat["percobaan"] > 1 else ""),
              flush=True)
        hasil["diunduh"] += 1

    if not sumber_bps.berkas_pdf_valid(t["path"]):
        gagal("ekstraksi", "berkas PDF lokal hilang atau rusak")
        return

    # Sidik diambil SEBELUM parsing: kalau berkas berubah saat dibaca, sidik
    # lama tersimpan dan run berikutnya mendeteksinya sebagai perubahan.
    sidik = sumber_bps.sidik_pdf(t["path"])
    mulai = time.perf_counter()
    try:
        entri, catatan = pipeline_data.ekstrak_berkas(
            t["path"], t["pub_id"], ocr_aktif=OCR_AKTIF,
            log=lambda baris: print(baris, flush=True))
    except Exception as e:  # noqa: BLE001 - satu PDF rusak tidak boleh menghentikan yang lain
        durasi["ekstraksi"] += time.perf_counter() - mulai
        gagal("ekstraksi", str(e))
        pipeline_data.catat_galat(t["pub_id"], str(e))
        return
    durasi["ekstraksi"] += time.perf_counter() - mulai

    mulai = time.perf_counter()
    try:
        pipeline_data.simpan_entri(
            t["pub_id"], entri, sidik, catatan,
            updt_diproses=t["updt_date_api"] if t["unduh"] else None)
    except Exception as e:  # noqa: BLE001 - transaksinya sudah dibatalkan, data lama utuh
        durasi["muat"] += time.perf_counter() - mulai
        gagal("muat", str(e))
        return
    durasi["muat"] += time.perf_counter() - mulai

    print(f"      {len(entri)} entri", flush=True)
    info_ocr = catatan.get("ocr") or {}
    if info_ocr.get("halaman_tanpa_teks"):
        print(f"      halaman tanpa teks {info_ocr['halaman_tanpa_teks']}: "
              f"cache OCR {info_ocr['dari_cache']}, di-OCR {info_ocr['di_ocr']}, "
              f"dilewati {info_ocr['dilewati']}"
              + (f" ({info_ocr['alasan_dilewati']})" if info_ocr["dilewati"] else ""),
              flush=True)
        hasil.setdefault("ocr", []).append({"pub_id": t["pub_id"], "judul": t["judul"], **info_ocr})
    hasil["diproses"] += 1
    if t["belum_pernah"]:
        hasil["publikasi_baru"].append({"pub_id": t["pub_id"], "judul": t["judul"],
                                        "entri": len(entri)})
    alasan = pipeline_data.perlu_diperiksa(catatan)
    if alasan:
        hasil["perlu_diperiksa"].append({"pub_id": t["pub_id"], "judul": t["judul"],
                                         "alasan": alasan})


JEDA_PUTARAN_ULANG = 60     # detik, sebelum mencoba lagi unduhan yang gagal


def putaran_ulang(kode, tugas, durasi, hasil, opsi):
    """Coba sekali lagi publikasi yang GAGAL DIUNDUH, di akhir domain.

    Unduhan BPS bisa putus acak dan server tidak mendukung Range, jadi
    percobaan ulang di unduh_pdf selalu dari nol. Sesudah semua publikasi lain
    selesai, yang gagal dicoba lagi - dengan URL SEGAR: URL PDF di WebAPI
    bertoken dan berganti (URL dari metadata beberapa hari sebelumnya ditolak
    400), sehingga daftar domain ditarik ulang dulu.
    """
    gagal_unduh = {g["pub_id"] for g in hasil["gagal"] if g["tahap"] == "unduh"}
    ulang = [t for t in tugas if t["pub_id"] in gagal_unduh]
    if not ulang:
        return
    print(f"\n  PUTARAN ULANG: {len(ulang)} unduhan gagal dicoba lagi dalam "
          f"{JEDA_PUTARAN_ULANG} detik, dengan URL segar", flush=True)
    time.sleep(JEDA_PUTARAN_ULANG)
    try:
        jendela = sumber_bps.tahun_dipakai(opsi.tahun_min)
        segar = {p["pub_id"]: p.get("pdf") for p in sumber_bps.ambil_domain(
            kode, berhenti_sebelum_tahun=min(jendela) if sumber_bps.DAFTAR_TERURUT_TERBARU else None)}
    except GagalAmbil as e:
        print(f"  putaran ulang dibatalkan: daftar tidak bisa ditarik ({e})", flush=True)
        return
    # Dihitung ulang dari nol: yang gagal lagi dicatat ulang oleh proses_tugas.
    hasil["unduhan"]["putaran_ulang"] += len(ulang)
    hasil["unduhan"]["gagal"] -= len(ulang)
    hasil["gagal"] = [g for g in hasil["gagal"]
                      if not (g["tahap"] == "unduh" and g["pub_id"] in gagal_unduh)]
    for t in ulang:
        t = dict(t, url_pdf=segar.get(t["pub_id"]) or t["url_pdf"])
        sebelum = hasil["diunduh"]
        proses_tugas(t, durasi, hasil)
        if hasil["diunduh"] > sebelum:
            hasil["unduhan"]["pulih_di_putaran_ulang"] += 1


def proses_domain(w, opsi, terhalang):
    """Kerjakan satu domain. Tidak pernah melempar exception ke pemanggil."""
    kode = w["kode"]
    durasi = dict.fromkeys(TAHAP, 0.0)
    hasil = {
        "kode": kode, "wilayah": w["nama"], "status": None, "pesan": None,
        "jaringan": False, "jumlah_publikasi": 0, "diunduh": 0, "diproses": 0,
        "publikasi_baru": [], "gagal": [], "tabrakan": [], "tidak_di_daftar": [],
        "menunggu_unduhan": [], "perlu_diperiksa": [], "durasi_tahap": durasi,
        "unduhan": {"berkas": 0, "byte": 0, "detik_transfer": 0.0, "gagal": 0,
                    "putus": 0, "percobaan_ulang": 0, "putaran_ulang": 0,
                    "pulih_di_putaran_ulang": 0},
    }
    judul_bagian(f"DOMAIN {kode} {w['nama']}")

    if kode in terhalang:
        print(f"  DILEWATI: {terhalang[kode]}")
        hasil.update(status="gagal", pesan=f"Dilewati: {terhalang[kode]}")
        return hasil

    try:
        di_daftar = None
        if not opsi.lokal:
            mulai = time.perf_counter()
            jendela = sumber_bps.tahun_dipakai(opsi.tahun_min)
            semua = sumber_bps.ambil_domain(
                kode, berhenti_sebelum_tahun=min(jendela) if sumber_bps.DAFTAR_TERURUT_TERBARU else None)
            durasi["ambil_metadata"] = time.perf_counter() - mulai
            lolos = sumber_bps.saring_tahun(semua, jendela)
            # Pengecualian judul (data/wilayah.json, kecualikan_judul) - misalnya
            # "Kecamatan ... Dalam Angka", di luar cakupan atas permintaan tim PST.
            lolos, dikecualikan = sumber_bps.saring_judul(lolos, pola_judul_dikecualikan())
            print(f"  {len(semua)} publikasi dibaca dari daftar, {len(lolos)} lolos filter tahun"
                  f" dan judul ({len(dikecualikan)} dikecualikan menurut judul)")

            # Nol hasil padahal data lama ada hampir pasti kegagalan penarikan,
            # bukan BPS menghapus seluruh publikasinya.
            sudah_ada = Publikasi.query.filter_by(domain=kode).count()
            db.session.commit()
            if not lolos and sudah_ada:
                raise GagalAmbil("0 publikasi lolos filter padahal database berisi "
                                 f"{sudah_ada} publikasi domain ini")

            mulai = time.perf_counter()
            meta = pipeline_data.simpan_metadata(kode, w["nama"], lolos)
            durasi["muat"] += time.perf_counter() - mulai
            hasil["tabrakan"] = meta["tabrakan"]
            hasil["tidak_di_daftar"] = meta["tidak_di_daftar"]
            # Yang bertabrakan bukan milik domain ini, jadi tidak ikut diproses.
            milik_lain = {t["pub_id"] for t in meta["tabrakan"]}
            di_daftar = {p["pub_id"] for p in lolos} - milik_lain
            print(f"  metadata tersimpan: {len(meta['baru'])} baru, "
                  f"{meta['diperbarui']} diperbarui")
            for t in meta["tabrakan"]:
                print(f"  TABRAKAN pub_id {t['pub_id']}: sudah milik domain "
                      f"{t['domain_lain']}, tidak ditimpa")
            for t in meta["tidak_di_daftar"]:
                print(f"  tidak lagi di daftar API (dibiarkan): {t['judul'][:60]}")

        tugas, hasil["menunggu_unduhan"] = pipeline_data.susun_rencana(
            kode, di_daftar, paksa=opsi.paksa)
        hasil["jumlah_publikasi"] = Publikasi.query.filter_by(domain=kode).count()
        db.session.commit()

        print(f"  {len(tugas)} publikasi perlu dikerjakan")
        if hasil["menunggu_unduhan"]:
            print(f"  {len(hasil['menunggu_unduhan'])} publikasi punya versi lebih baru "
                  "di BPS, menunggu pembaruan online")
        for t in tugas:
            proses_tugas(t, durasi, hasil)

        if not opsi.lokal:
            putaran_ulang(kode, tugas, durasi, hasil, opsi)

    except GagalAmbil as e:
        hasil.update(status="gagal", pesan=samarkan(e), jaringan=e.jaringan)
    except Exception as e:  # noqa: BLE001 - satu domain gagal tidak menggagalkan domain lain
        db.session.rollback()
        traceback.print_exc()
        hasil.update(status="gagal", pesan=samarkan(e))

    if hasil["status"] is None:
        if hasil["gagal"] or hasil["tabrakan"]:
            hasil["status"] = "sebagian"
        elif hasil["diproses"]:
            hasil["status"] = "sukses"
        else:
            hasil["status"] = "tidak_ada_baru"
    return hasil


def status_keseluruhan(per_domain):
    status = [d["status"] for d in per_domain]
    if all(s == "gagal" for s in status):
        return "gagal"
    if "gagal" in status or "sebagian" in status:
        return "sebagian"
    return "sukses" if "sukses" in status else "tidak_ada_baru"


def ringkas_unduhan(per_domain):
    """Total statistik unduhan semua domain, dengan kecepatan rata-rata."""
    total = {}
    for d in per_domain:
        for k, v in d["unduhan"].items():
            total[k] = total.get(k, 0) + v
    total["kb_per_detik"] = round(total.get("byte", 0) / 1024 / total["detik_transfer"], 1) \
        if total.get("detik_transfer") else None
    total["mb"] = round(total.get("byte", 0) / 1e6, 1)
    total["detik_transfer"] = round(total.get("detik_transfer", 0), 1)
    return total


def cetak_ringkasan(status, per_domain, entri_sebelum, entri_sesudah, durasi_total, detik,
                    unduhan, jaringan_dipakai):
    judul_bagian("RINGKASAN PEMBARUAN")
    print(f"  Status       : {status}")
    print(f"  Entri dokumen: {entri_sebelum} -> {entri_sesudah} "
          f"({entri_sesudah - entri_sebelum:+d})")
    print(f"  Waktu        : {detik:.0f} detik ({detik / 3600:.1f} jam)")
    print("  Per tahap    : " + ", ".join(f"{t} {durasi_total[t]:.1f} d" for t in TAHAP))
    print(f"  Jaringan     : SSID {jaringan_dipakai.get('ssid')!r}, "
          f"webapi.bps.go.id -> {jaringan_dipakai.get('webapi_ip')}")
    print(f"  Unduhan      : {unduhan['berkas']} berkas, {unduhan['mb']} MB, "
          f"rata-rata {unduhan['kb_per_detik']} KB/detik; putus {unduhan['putus']}x, "
          f"percobaan ulang {unduhan['percobaan_ulang']}x, putaran ulang "
          f"{unduhan['putaran_ulang']} (pulih {unduhan['pulih_di_putaran_ulang']}), "
          f"tetap gagal {unduhan['gagal']}")

    print()
    print(f"  {'domain':<34}{'status':<16}{'publikasi':>9}{'diunduh':>9}"
          f"{'diproses':>9}{'gagal':>7}")
    for d in per_domain:
        print(f"  {d['kode'] + ' ' + d['wilayah']:<34.34}{d['status']:<16}"
              f"{d['jumlah_publikasi']:>9}{d['diunduh']:>9}{d['diproses']:>9}"
              f"{len(d['gagal']):>7}")

    for d in per_domain:
        if d["pesan"]:
            print(f"\n  {d['kode']}: {d['pesan']}")
        for g in d["gagal"]:
            print(f"\n  GAGAL {d['kode']} {g['judul'][:50]} ({g['tahap']}): {g['pesan'][:120]}")

    curiga = [(d["kode"], c) for d in per_domain for c in d["perlu_diperiksa"]]
    if curiga:
        print(f"\n  Perlu diperiksa manual ({len(curiga)}):")
        for kode, c in curiga:
            print(f"    {kode} {c['judul'][:42]:<42} {c['alasan']}")


def jalankan_pembaruan(opsi):
    mulai = time.time()
    aktif = wilayah_aktif()
    if not aktif:
        print("Tidak ada domain aktif di data/wilayah.json.")
        tulis_ringkasan("gagal", tahap="konfigurasi", jaringan=False,
                        pesan="Tidak ada domain aktif", durasi_detik=0)
        return KODE_GAGAL

    entri_sebelum = EntriDokumen.query.count()
    terhalang = {} if opsi.lokal else domain_terhalang(aktif)
    db.session.commit()
    jaringan_dipakai = {} if opsi.lokal else info_jaringan()
    if jaringan_dipakai:
        print(f"Jaringan: SSID {jaringan_dipakai.get('ssid')!r}, "
              f"webapi.bps.go.id -> {jaringan_dipakai.get('webapi_ip')}")

    per_domain = []
    for i, w in enumerate(aktif):
        per_domain.append(proses_domain(w, opsi, terhalang))
        if i < len(aktif) - 1 and not opsi.lokal:
            time.sleep(sumber_bps.JEDA_DETIK)   # jeda sesuai Term of Use

    entri_sesudah = EntriDokumen.query.count()
    jumlah_publikasi = Publikasi.query.count()
    db.session.commit()

    status = status_keseluruhan(per_domain)
    durasi_total = {t: sum(d["durasi_tahap"][t] for d in per_domain) for t in TAHAP}
    for d in per_domain:
        d["durasi_tahap"] = {t: round(v, 1) for t, v in d["durasi_tahap"].items()}

    detik = time.time() - mulai
    unduhan = ringkas_unduhan(per_domain)
    for d in per_domain:
        u = d["unduhan"]
        u["detik_transfer"] = round(u["detik_transfer"], 1)
        u["kb_per_detik"] = round(u["byte"] / 1024 / u["detik_transfer"], 1) \
            if u["detik_transfer"] else None
    cetak_ringkasan(status, per_domain, entri_sebelum, entri_sesudah, durasi_total, detik,
                    unduhan, jaringan_dipakai)

    jaringan = any(d["jaringan"] for d in per_domain)
    if status == "gagal" and jaringan:
        print(PESAN_JARINGAN)

    tulis_ringkasan(
        status,
        jaringan=jaringan,
        mode="lokal" if opsi.lokal else "online",
        ocr="mati (--tanpa-ocr)" if not OCR_AKTIF else "aktif",
        jumlah_publikasi=jumlah_publikasi,
        publikasi_baru=[{**p, "wilayah": d["wilayah"]}
                        for d in per_domain for p in d["publikasi_baru"]],
        diproses=sum(d["diproses"] for d in per_domain),
        diunduh=sum(d["diunduh"] for d in per_domain),
        entri_sebelum=entri_sebelum,
        entri_sesudah=entri_sesudah,
        durasi_tahap={t: round(v, 1) for t, v in durasi_total.items()},
        durasi_detik=round(detik),
        unduhan=unduhan,
        jaringan_dipakai=jaringan_dipakai,
        log=getattr(sys.stdout, "berkas", None) and sys.stdout.berkas.name,
        domain=per_domain,
    )
    return {"gagal": KODE_GAGAL, "sebagian": KODE_SEBAGIAN}.get(status, KODE_SUKSES)


def main():
    arg = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    arg.add_argument("--paksa", action="store_true",
                     help="Ekstrak ulang SEMUA publikasi, bukan hanya yang perlu. "
                          "Pakai setiap kali parser diperbarui.")
    arg.add_argument("--lokal", action="store_true",
                     help="Tanpa jaringan: hanya mengekstrak dari PDF yang sudah "
                          "ada. Metadata tidak diperbarui, tidak ada yang diunduh.")
    arg.add_argument("--hanya-periksa", action="store_true",
                     help="Tarik metadata semua wilayah (aktif maupun tidak) dan "
                          "cari tabrakan pub_id. Tidak mengubah database. WAJIB "
                          "sebelum domain baru pertama kali dimuat.")
    arg.add_argument("--tanpa-ocr", action="store_true",
                     help="Jangan memakai OCR (EasyOCR maupun cache-nya). Halaman "
                          "PDF tanpa lapisan teks dilewati dan dicatat.")
    arg.add_argument("--tahun-min", type=int, default=None,
                     help="Tahun rilis paling awal (default: 2 tahun terakhir).")
    arg.add_argument("--db-uji", action="store_true",
                     help="Tulis ke database UJI (KonfigurasiUji: nama database di "
                          "DATABASE_URL + '_uji'), bukan produksi. Ringkasan ditulis ke "
                          f"{FILE_RINGKASAN_UJI}, bukan ke ringkasan yang dibaca "
                          "/admin/perbarui.")
    opsi = arg.parse_args()
    global OCR_AKTIF, FILE_RINGKASAN
    OCR_AKTIF = not opsi.tanpa_ocr
    konfigurasi = KonfigurasiUji if opsi.db_uji else Config
    if opsi.db_uji:
        FILE_RINGKASAN = FILE_RINGKASAN_UJI

    # Baris dialirkan begitu muncul: kalau layar diam selama penarikan metadata,
    # orang yang menjalankan .bat menyangka macet. errors="replace" karena konsol
    # Windows bisa tidak mengenal karakter di judul publikasi.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    # Baris pdfminer tentang FontBBox membanjiri layar tanpa memberi informasi.
    logging.getLogger("pdfminer").setLevel(logging.ERROR)

    # Baris PERTAMA keluaran: database mana yang akan ditulis. Sandi tidak
    # pernah ikut dicetak. Pengaman nama database uji ada di create_app().
    tujuan = make_url(konfigurasi.SQLALCHEMY_DATABASE_URI)
    baris_tujuan = (f"Database tujuan: {tujuan.database} @ {tujuan.host or '-'}:{tujuan.port or '-'}"
                    f" ({'UJI - bukan produksi' if opsi.db_uji else 'PRODUKSI'})")
    print(baris_tujuan)

    os.chdir(DIR_PROYEK)
    pid_lain = pembaruan_sedang_berjalan()
    if pid_lain or not ambil_kunci():
        print("PEMBARUAN SUDAH BERJALAN di proses lain "
              f"(PID {pid_lain}). Tunggu sampai selesai, jangan jalankan dua kali.")
        sys.exit(KODE_TERKUNCI)

    # Salinan keluaran ke berkas (untuk run semalaman) dan cegah laptop tidur.
    os.makedirs(DIR_LOG, exist_ok=True)
    nama_log = os.path.join(DIR_LOG, datetime.now().strftime("%Y%m%d-%H%M%S")
                            + ("-periksa" if opsi.hanya_periksa else "") + ".log")
    berkas_log = open(nama_log, "w", encoding="utf-8")
    berkas_log.write(baris_tujuan + "\n")       # sudah tercetak di layar, belum di log
    sys.stdout = Salin(sys.stdout, berkas_log)
    print(f"Log run ini: {nama_log}")
    jaga_tetap_bangun(True)

    kode = KODE_GAGAL
    try:
        app = create_app(konfigurasi)
        with app.app_context():
            pastikan_skema()
            kode = jalankan_pemeriksaan() if opsi.hanya_periksa else jalankan_pembaruan(opsi)
    except Exception:  # noqa: BLE001 - pesan disamarkan dulu, traceback bisa memuat URL ber-key
        print(samarkan(traceback.format_exc()))
        tulis_ringkasan("gagal", tahap="tak terduga", jaringan=False)
    finally:
        lepas_kunci()
        jaga_tetap_bangun(False)
        print(f"\nSelesai {datetime.now():%Y-%m-%d %H:%M:%S}, kode keluar {kode}. Log: {nama_log}")
        sys.stdout.flush()
        berkas_log.close()
        sys.stdout = sys.stdout.asli
    sys.exit(kode)


if __name__ == "__main__":
    main()
