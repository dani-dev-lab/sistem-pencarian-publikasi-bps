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

from app import create_app
from app.models import EntriDokumen, Publikasi, db
from app.services import pipeline_data, sumber_bps
from app.services.sumber_bps import GagalAmbil, samarkan
from app.services.wilayah import muat_wilayah, wilayah_aktif

FILE_RINGKASAN = "data/pembaruan_terakhir.json"   # dibaca /admin/perbarui
FILE_KUNCI = "data/pembaruan.lock"                # berisi PID yang sedang jalan
FILE_PEMERIKSAAN = "data/pemeriksaan_domain.json" # hasil --hanya-periksa

TAHAP = ("ambil_metadata", "unduh", "ekstraksi", "muat")

KODE_SUKSES, KODE_GAGAL, KODE_TERKUNCI, KODE_SEBAGIAN = 0, 1, 2, 3

PESAN_JARINGAN = """
  WebAPI BPS tidak bisa dihubungi.

  Penyebab paling umum: laptop tidak tersambung ke jaringan "BPS - Pegawai".
  Jaringan "BPS - Tamu" MEMBLOKIR akses ke webapi.bps.go.id.

  Periksa koneksi lalu jalankan ulang perintah ini.
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
        lolos = sumber_bps.saring_tahun(daftar, sumber_bps.tahun_dipakai())
        for p in daftar:
            pemilik.setdefault(p["pub_id"], []).append((kode, (p.get("title") or "").strip()))
        per_domain.append({"kode": kode, "nama": w["nama"], "status": "berhasil",
                           "publikasi_semua_tahun": len(daftar),
                           "publikasi_lolos_filter": len(lolos)})
        print(f"  {len(daftar)} publikasi semua tahun, {len(lolos)} lolos filter tahun")
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
        pesan = sumber_bps.unduh_pdf(t["url_pdf"], t["path"])
        durasi["unduh"] += time.perf_counter() - mulai
        if pesan:
            gagal("unduh", pesan)
            return
        hasil["diunduh"] += 1

    if not sumber_bps.berkas_pdf_valid(t["path"]):
        gagal("ekstraksi", "berkas PDF lokal hilang atau rusak")
        return

    # Sidik diambil SEBELUM parsing: kalau berkas berubah saat dibaca, sidik
    # lama tersimpan dan run berikutnya mendeteksinya sebagai perubahan.
    sidik = sumber_bps.sidik_pdf(t["path"])
    mulai = time.perf_counter()
    try:
        entri, catatan = pipeline_data.ekstrak_berkas(t["path"], t["pub_id"])
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
    hasil["diproses"] += 1
    if t["belum_pernah"]:
        hasil["publikasi_baru"].append({"pub_id": t["pub_id"], "judul": t["judul"],
                                        "entri": len(entri)})
    alasan = pipeline_data.perlu_diperiksa(catatan)
    if alasan:
        hasil["perlu_diperiksa"].append({"pub_id": t["pub_id"], "judul": t["judul"],
                                         "alasan": alasan})


def proses_domain(w, opsi, terhalang):
    """Kerjakan satu domain. Tidak pernah melempar exception ke pemanggil."""
    kode = w["kode"]
    durasi = dict.fromkeys(TAHAP, 0.0)
    hasil = {
        "kode": kode, "wilayah": w["nama"], "status": None, "pesan": None,
        "jaringan": False, "jumlah_publikasi": 0, "diunduh": 0, "diproses": 0,
        "publikasi_baru": [], "gagal": [], "tabrakan": [], "tidak_di_daftar": [],
        "menunggu_unduhan": [], "perlu_diperiksa": [], "durasi_tahap": durasi,
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
            semua = sumber_bps.ambil_domain(kode)
            durasi["ambil_metadata"] = time.perf_counter() - mulai
            lolos = sumber_bps.saring_tahun(
                semua, sumber_bps.tahun_dipakai(opsi.tahun_min))
            print(f"  {len(semua)} publikasi semua tahun, {len(lolos)} lolos filter tahun")

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


def cetak_ringkasan(status, per_domain, entri_sebelum, entri_sesudah, durasi_total, detik):
    judul_bagian("RINGKASAN PEMBARUAN")
    print(f"  Status       : {status}")
    print(f"  Entri dokumen: {entri_sebelum} -> {entri_sesudah} "
          f"({entri_sesudah - entri_sebelum:+d})")
    print(f"  Waktu        : {detik:.0f} detik")
    print("  Per tahap    : " + ", ".join(f"{t} {durasi_total[t]:.1f} d" for t in TAHAP))

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
    cetak_ringkasan(status, per_domain, entri_sebelum, entri_sesudah, durasi_total, detik)

    jaringan = any(d["jaringan"] for d in per_domain)
    if status == "gagal" and jaringan:
        print(PESAN_JARINGAN)

    tulis_ringkasan(
        status,
        jaringan=jaringan,
        mode="lokal" if opsi.lokal else "online",
        jumlah_publikasi=jumlah_publikasi,
        publikasi_baru=[{**p, "wilayah": d["wilayah"]}
                        for d in per_domain for p in d["publikasi_baru"]],
        diproses=sum(d["diproses"] for d in per_domain),
        diunduh=sum(d["diunduh"] for d in per_domain),
        entri_sebelum=entri_sebelum,
        entri_sesudah=entri_sesudah,
        durasi_tahap={t: round(v, 1) for t, v in durasi_total.items()},
        durasi_detik=round(detik),
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
    arg.add_argument("--tahun-min", type=int, default=None,
                     help="Tahun rilis paling awal (default: 2 tahun terakhir).")
    opsi = arg.parse_args()

    # Baris dialirkan begitu muncul: kalau layar diam selama penarikan metadata,
    # orang yang menjalankan .bat menyangka macet. errors="replace" karena konsol
    # Windows bisa tidak mengenal karakter di judul publikasi.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    # Baris pdfminer tentang FontBBox membanjiri layar tanpa memberi informasi.
    logging.getLogger("pdfminer").setLevel(logging.ERROR)

    os.chdir(DIR_PROYEK)
    pid_lain = pembaruan_sedang_berjalan()
    if pid_lain or not ambil_kunci():
        print("PEMBARUAN SUDAH BERJALAN di proses lain "
              f"(PID {pid_lain}). Tunggu sampai selesai, jangan jalankan dua kali.")
        sys.exit(KODE_TERKUNCI)

    kode = KODE_GAGAL
    try:
        app = create_app()
        with app.app_context():
            pastikan_skema()
            kode = jalankan_pemeriksaan() if opsi.hanya_periksa else jalankan_pembaruan(opsi)
    except Exception:  # noqa: BLE001 - pesan disamarkan dulu, traceback bisa memuat URL ber-key
        print(samarkan(traceback.format_exc()))
        tulis_ringkasan("gagal", tahap="tak terduga", jaringan=False)
    finally:
        lepas_kunci()
    sys.exit(kode)


if __name__ == "__main__":
    main()
