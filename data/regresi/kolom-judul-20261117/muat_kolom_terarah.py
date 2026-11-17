"""Muat ulang entri HANYA untuk publikasi yang berubah oleh perbaikan kolom judul (17 Nov 2026).

  python muat_kolom_terarah.py --sasaran produksi --coba
  python muat_kolom_terarah.py --sasaran produksi --produksi-disetujui

Salinan muat_parser_terarah.py (16 Nov). Daftar publikasi: publikasi-berubah.txt
(1: Tabalong DA 2025, dari potret sebelum/sesudah regresi penuh di database uji).
Publikasi lain tidak disentuh, tidak menarik metadata, tidak mengunduh.

Tambahan 17 Nov: produksi punya publikasi yang tidak ada di database uji (IPM HSU,
masuk lewat pembaruan 16 Nov 15.20). Publikasi seperti itu tidak bisa
dibandingkan dengan database uji; sebagai gantinya diekstrak kering dengan kode
sekarang dan harus = isi produksi per kunci (perbaikan ini tidak mengubahnya).

Tiap publikasi memakai fungsi yang sama dengan perbarui.py:
ekstrak_berkas lalu simpan_entri (perkiraan halaman ikut dihitung ulang), satu
transaksi per publikasi.

Pemeriksaan (selalu, juga dengan --coba; tidak menulis apa pun):
  - publikasi ada di database tujuan, PDF utuh, dan sidik PDF (ukuran, mtime)
    sama dengan yang tercatat di database tujuan DAN database uji;
  - publikasi OCR: cache SETIAP halaman tanpa teks sudah ada (tidak boleh
    memicu OCR baru);
  - entri publikasi target di database tujuan = potret sebelum regresi (per
    kunci): keadaan awalnya seperti yang diharapkan;
  - publikasi BUKAN target: database tujuan = database uji per kunci, jadi
    sesudah pemuatan seluruh tujuan harus = database uji.

Muat (tanpa --coba): tiap publikasi diekstrak, lalu dibandingkan per kunci
dengan database uji SEBELUM ditulis. Satu beda -> berhenti; publikasi yang
sudah dimuat tetap utuh, karena satu transaksi per publikasi.
"""
import argparse
import csv
import importlib.util
import os
import re
import sys
import time
from collections import Counter

DIR_PROYEK = "C:/sistem-pencarian-bps"
DIR_INI = os.path.dirname(os.path.abspath(__file__))
os.chdir(DIR_PROYEK)                     # FILE_KUNCI perbarui.py relatif ke proyek
sys.path.insert(0, DIR_PROYEK)

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app import create_app  # noqa: E402
from app.config import Config, KonfigurasiUji  # noqa: E402
from app.models import Publikasi, db  # noqa: E402
from app.services import ocr, pipeline_data, sumber_bps, versi_data  # noqa: E402

spec = importlib.util.spec_from_file_location("perbarui", os.path.join(DIR_PROYEK, "scripts", "perbarui.py"))
perbarui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(perbarui)        # hanya untuk ambil_kunci / lepas_kunci / pastikan_skema

arg = argparse.ArgumentParser()
arg.add_argument("--sasaran", choices=["uji", "produksi"], required=True)
arg.add_argument("--produksi-disetujui", action="store_true")
arg.add_argument("--coba", action="store_true")
opsi = arg.parse_args()

konfigurasi = KonfigurasiUji if opsi.sasaran == "uji" else Config
url = make_url(konfigurasi.SQLALCHEMY_DATABASE_URI)
print(f"Database tujuan: {url.database} @ {url.host}:{url.port} "
      f"({'UJI - bukan produksi' if opsi.sasaran == 'uji' else 'PRODUKSI'})"
      f"{' [--coba: tidak menulis]' if opsi.coba else ''}", flush=True)
if opsi.sasaran == "produksi" and not opsi.coba and not opsi.produksi_disetujui:
    raise SystemExit("Produksi butuh --produksi-disetujui. Tidak dijalankan.")

TARGET = [l.strip() for l in open(os.path.join(DIR_INI, "publikasi-berubah.txt")) if l.strip()]
MESIN_UJI = sa.create_engine(KonfigurasiUji.SQLALCHEMY_DATABASE_URI)


def kunci_entri(baris):
    """Multiset per publikasi: (tipe, nomor, judul, halaman, fisik asli, sumber)."""
    return Counter((t, n or "", j, h or "", "" if perk else str(f or ""), s)
                   for t, n, j, h, f, perk, s in baris)


def kunci_lengkap(baris):
    """Sama, ditambah halaman fisik perkiraan + penandanya (untuk bukti sesudah muat)."""
    return Counter((t, n or "", j, h or "", str(f or ""), int(perk), s) for t, n, j, h, f, perk, s in baris)


Q_ENTRI = ("SELECT tipe, nomor, judul, halaman, halaman_fisik, halaman_fisik_perkiraan, sumber "
           "FROM entri_dokumen WHERE publikasi_id=:p")


def entri_uji(p):
    with MESIN_UJI.connect() as k:
        return list(k.execute(sa.text(Q_ENTRI), {"p": p}))


def entri_tujuan(p):
    return list(db.session.execute(sa.text(Q_ENTRI), {"p": p}))


def _batch(teks):
    """Balikkan escape `mysql --batch` di berkas potret: \\\\ \\t \\n \\0.

    Ditemukan saat --coba ke produksi (16 Nov 2026): judul "PAG E \\*" di
    potret tertulis "PAG E \\\\*", sehingga publikasinya disangka berbeda.
    """
    return re.sub(r"\\(.)", lambda m: {"t": "\t", "n": "\n", "0": "\0"}.get(m.group(1), m.group(1)), teks)


def potret_sebelum():
    hasil = {}
    for pid, dom, t, no, j, h, f, perk, s in list(csv.reader(
            open(os.path.join(DIR_INI, "potret-sebelum.tsv"), encoding="utf-8"), delimiter="\t"))[1:]:
        hasil.setdefault(pid, []).append((t, no, _batch(j), h, f, int(perk), s))
    return hasil


app = create_app(konfigurasi)
if not perbarui.ambil_kunci():
    raise SystemExit("TIDAK DIJALANKAN: pembaruan lain sedang berjalan.")
try:
    with app.app_context():
        perbarui.pastikan_skema()        # DDL sebelum transaksi penulis
        t0 = time.time()
        sebelum = potret_sebelum()
        masalah = []
        rencana = []
        with MESIN_UJI.connect() as k:
            sidik_uji = {r[0]: (r[1], r[2]) for r in k.execute(sa.text(
                "SELECT id, sidik_ukuran, sidik_mtime FROM publikasi"))}
        for p in TARGET:
            pub = db.session.get(Publikasi, p)
            if pub is None:
                masalah.append(f"{p}: tidak ada di database tujuan"); continue
            path = sumber_bps.path_pdf(pub.domain, p)
            if not sumber_bps.berkas_pdf_valid(path):
                masalah.append(f"{p}: PDF hilang/rusak"); continue
            sidik = sumber_bps.sidik_pdf(path)
            if sidik != (pub.sidik_ukuran, pub.sidik_mtime) or sidik != sidik_uji.get(p):
                masalah.append(f"{p}: sidik PDF {sidik} != tujuan {(pub.sidik_ukuran, pub.sidik_mtime)} / uji {sidik_uji.get(p)}")
            if pub.halaman_ocr:
                halaman, _, _ = ocr.halaman_tanpa_teks(path)
                kurang = [h for h in halaman if not os.path.exists(ocr.berkas_cache(path, h))]
                if kurang:
                    masalah.append(f"{p}: cache OCR kurang {len(kurang)} halaman")
            if kunci_lengkap(entri_tujuan(p)) != kunci_lengkap(sebelum.get(p, [])):
                masalah.append(f"{p}: entri tujuan saat ini != potret sebelum regresi")
            rencana.append((p, pub.judul, path, sidik))
        with MESIN_UJI.connect() as k:
            id_uji = {r[0] for r in k.execute(sa.text("SELECT id FROM publikasi"))}
        semua = [r[0] for r in db.session.execute(sa.text("SELECT id FROM publikasi")) if r[0] not in set(TARGET)]
        bukan_target = [p for p in semua if p in id_uji]
        hanya_tujuan = [p for p in semua if p not in id_uji]
        for p in hanya_tujuan:
            pub = db.session.get(Publikasi, p)
            path = sumber_bps.path_pdf(pub.domain, p)
            entri, catatan = pipeline_data.ekstrak_berkas(path, p, ocr_aktif=False, log=lambda *a, **k: None)
            kering = kunci_entri([(e["tipe"], e.get("nomor"), e["judul"], e.get("halaman"),
                                   e.get("halaman_fisik"), 0, e.get("sumber", "daftar")) for e in entri])
            sama = kering == kunci_entri(entri_tujuan(p))
            print(f"  hanya di tujuan: {p} {pub.judul[:50]} - ekstraksi kering = tujuan: {sama}", flush=True)
            if not sama:
                masalah.append(f"{p}: hanya di tujuan, dan ekstraksi kode sekarang berbeda dengan isinya")
        beda_lain = [p for p in bukan_target if kunci_lengkap(entri_tujuan(p)) != kunci_lengkap(entri_uji(p))]
        if beda_lain:
            masalah.append(f"{len(beda_lain)} publikasi BUKAN target berbeda dengan database uji: {beda_lain[:5]}")
        db.session.rollback()
        print(f"Pemeriksaan: {len(TARGET)} target, {len(bukan_target)} bukan target "
              f"(= database uji per kunci: {len(bukan_target) - len(beda_lain)}), "
              f"{time.time() - t0:.0f} d", flush=True)
        if masalah:
            for m in masalah:
                print("  MASALAH:", m)
            raise SystemExit("Pemeriksaan GAGAL. Tidak ada yang ditulis.")
        print("Pemeriksaan LULUS.", flush=True)
        if opsi.coba:
            raise SystemExit(0)

        # Muat: bandingkan dengan database uji SEBELUM menulis, satu transaksi per publikasi.
        for n, (p, judul, path, sidik) in enumerate(rencana, 1):
            t1 = time.time()
            entri, catatan = pipeline_data.ekstrak_berkas(path, p, ocr_aktif=True, log=lambda *a, **k: None)
            if (catatan.get("ocr") or {}).get("di_ocr", 0):
                raise SystemExit(f"{p}: ekstraksi menjalankan OCR baru - dihentikan sebelum disimpan.")
            baru = kunci_entri([(e["tipe"], e.get("nomor"), e["judul"], e.get("halaman"),
                                 e.get("halaman_fisik"), 0, e.get("sumber", "daftar")) for e in entri])
            harap = kunci_entri(entri_uji(p))
            if baru != harap:
                raise SystemExit(f"{p}: hasil ekstraksi != database uji ({sum((baru - harap).values())} baris "
                                 f"lebih, {sum((harap - baru).values())} kurang) - dihentikan SEBELUM disimpan.")
            pipeline_data.simpan_entri(p, entri, sidik, catatan)
            print(f"  [{n:>3}/{len(rencana)}] muat {p}  {len(entri)} entri  {time.time() - t1:4.0f} d  {judul[:55]}",
                  flush=True)
        print(f"Selesai: {len(rencana)} publikasi, {time.time() - t0:.0f} d.", flush=True)
finally:
    perbarui.lepas_kunci()
