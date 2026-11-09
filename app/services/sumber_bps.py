"""Akses ke WebAPI BPS dan berkas PDF-nya: daftar publikasi per domain + unduhan.

Sesuai Term of Use BPS: ada jeda antar request supaya tidak membebani server,
dan API key tidak boleh bocor. Pesan galat `requests` memuat URL lengkap,
termasuk key, jadi semua pesan melewati samarkan() sebelum ditampilkan.
"""

import os
import re
import time
from datetime import date

import requests

from app.config import Config

JEDA_DETIK = 1.0        # Term of Use: jangan membebani server BPS
MAKS_PERCOBAAN = 3
JEDA_ULANG_DAFTAR = 3.0
JEDA_ULANG_UNDUH = 5.0
TIMEOUT_DAFTAR = 30
TIMEOUT_UNDUH = (15, 120)     # (connect, read) - berkas bisa sampai 25 MB
UKURAN_CHUNK = 64 * 1024
MINIMAL_WAJAR = 1024    # di bawah ini pasti bukan PDF publikasi utuh
EKOR_DIBACA = 2048      # cukup untuk menemukan %%EOF di ujung berkas

# Berapa tahun terakhir yang diambil, dihitung dari tahun berjalan.
JUMLAH_TAHUN = 2


class GagalAmbil(Exception):
    """Daftar publikasi satu domain tidak bisa diambil utuh."""

    def __init__(self, pesan, jaringan=False):
        super().__init__(pesan)
        self.jaringan = jaringan


def samarkan(teks):
    """Hilangkan API key dari teks yang akan ditampilkan atau disimpan.

    Keluaran pembaruan tampil di jendela .bat dan halaman admin, sehingga key
    yang ikut tercetak bisa terbaca siapa pun yang melihat layar.
    """
    teks = str(teks)
    kunci = (Config.BPS_API_KEY or "").strip()
    return teks.replace(kunci, "***") if kunci else teks


def tahun_dipakai(tahun_min=None):
    """Jendela tahun rilis, relatif terhadap hari ini.

    Dihitung dari tahun berjalan supaya tidak perlu diubah tiap tahun: angka
    mati akan diam-diam menolak publikasi baru begitu tahun berganti.
    """
    sekarang = date.today().year  # noqa: DTZ011 - tahun lokal memang yang dimaksud
    if tahun_min is None:
        tahun_min = sekarang - (JUMLAH_TAHUN - 1)
    return set(range(int(tahun_min), sekarang + 1))


def tahun_rilis(rl_date):
    """Tahun dari rl_date. Return int atau None kalau tidak terbaca."""
    if not rl_date:
        return None
    cocok = re.search(r"(19|20)[0-9]{2}", str(rl_date))
    return int(cocok.group(0)) if cocok else None


def saring_tahun(daftar, tahun):
    return [p for p in daftar if tahun_rilis(p.get("rl_date")) in tahun]


def saring_judul(daftar, pola):
    """Buang publikasi yang judulnya cocok salah satu pola pengecualian.

    `pola`: keluaran wilayah.pola_judul_dikecualikan(). Return (lolos, dikecualikan).
    """
    lolos, dikecualikan = [], []
    for p in daftar:
        judul = (p.get("title") or "").strip()
        (dikecualikan if any(r.search(judul) for r, _ in pola) else lolos).append(p)
    return lolos, dikecualikan


def _url_halaman(domain, halaman):
    dasar = Config.BPS_API_BASE_URL.rstrip("/")
    kunci = (Config.BPS_API_KEY or "").strip()
    return (f"{dasar}/list/model/publication/lang/ind/domain/{domain}"
            f"/page/{halaman}/key/{kunci}/")


def _ambil_halaman(domain, halaman):
    """Satu halaman daftar, dengan retry ringan. Return (pagination, daftar)."""
    galat = None
    for percobaan in range(1, MAKS_PERCOBAAN + 1):
        try:
            r = requests.get(_url_halaman(domain, halaman), timeout=TIMEOUT_DAFTAR)
            r.raise_for_status()
            body = r.json()
            if body.get("status") != "OK":
                raise ValueError(f"status API = {body.get('status')}, "
                                 f"data-availability = {body.get('data-availability')}")

            data = body.get("data")
            # Bentuk khas WebAPI BPS: data = [ {info pagination}, [ ...publikasi... ] ]
            if isinstance(data, list) and len(data) == 2:
                pagination = data[0] if isinstance(data[0], dict) else {}
                daftar = data[1] if isinstance(data[1], list) else []
            else:
                pagination, daftar = {}, (data if isinstance(data, list) else [])
            return pagination, daftar

        except Exception as e:  # noqa: BLE001 - JSON rusak, HTTP 5xx, jaringan: sama-sama diulang
            galat = e
            if percobaan < MAKS_PERCOBAAN:
                print(f"    percobaan {percobaan} gagal ({samarkan(e)}), "
                      f"ulangi dalam {JEDA_ULANG_DAFTAR:.0f} detik", flush=True)
                time.sleep(JEDA_ULANG_DAFTAR)

    jaringan = isinstance(galat, (requests.ConnectionError, requests.Timeout))
    raise GagalAmbil(f"halaman {halaman}: {samarkan(galat)}", jaringan=jaringan) from None


def ambil_domain(domain):
    """Daftar publikasi SEMUA tahun milik satu domain, utuh atau tidak sama sekali.

    Semua halaman discan sampai habis - hasil API TIDAK diasumsikan terurut
    rl_date. Begitu satu halaman gagal, proses berhenti: daftar yang tidak utuh
    membuat publikasi yang ada terlihat seperti terhapus.
    """
    semua = {}
    halaman = 1
    total_halaman = None

    while True:
        label = f"{halaman}/{total_halaman}" if total_halaman else f"{halaman}/?"
        print(f"  halaman {label} ...", end=" ", flush=True)
        try:
            pagination, daftar = _ambil_halaman(domain, halaman)
        except GagalAmbil as e:
            print(f"GAGAL ({e})", flush=True)
            raise

        if total_halaman is None:
            total_halaman = pagination.get("pages") or 1
        print(f"OK ({len(daftar)} item)", flush=True)

        # Kunci pub_id: API bisa mengulang publikasi yang sama di dua halaman
        # kalau ada rilis baru tepat saat halaman-halaman itu ditarik.
        for p in daftar:
            if p.get("pub_id"):
                semua.setdefault(p["pub_id"], p)

        halaman += 1
        if halaman > total_halaman:
            return list(semua.values())
        time.sleep(JEDA_DETIK)   # jeda sesuai Term of Use


# --------------------------------------------------------------------------
# Berkas PDF
# --------------------------------------------------------------------------

def path_pdf(domain, pub_id):
    """data/publikasi_pdf/<domain>/<pub_id>.pdf

    pub_id dipakai sebagai nama berkas: stabil, dan judul mengandung karakter
    yang bermasalah untuk nama berkas.
    """
    return os.path.join(str(Config.DIR_PUBLIKASI_PDF), domain, f"{pub_id}.pdf")


def sidik_pdf(path):
    """Penanda ringkas isi berkas: (ukuran, waktu ubah).

    Cukup untuk mendeteksi PDF yang diunduh ulang atau diganti, tanpa membaca
    ratusan MB hanya untuk memutuskan apakah perlu diproses.
    """
    st = os.stat(path)
    return st.st_size, int(st.st_mtime)


def berkas_pdf_valid(path):
    """Cek murah: ukuran wajar, diawali %PDF, dan diakhiri %%EOF.

    %%EOF adalah penanda akhir dokumen PDF. Unduhan yang terputus tetap diawali
    %PDF tapi kehilangan penanda ini. Field `size` dari API sengaja tidak
    dipakai: nilainya terbukti meleset sampai 167%.
    """
    try:
        ukuran = os.path.getsize(path)
        if ukuran < MINIMAL_WAJAR:
            return False
        with open(path, "rb") as f:
            if f.read(4) != b"%PDF":
                return False
            f.seek(max(0, ukuran - EKOR_DIBACA))
            return b"%%EOF" in f.read()
    except OSError:
        return False


def unduh_pdf(url, path_tujuan):
    """Unduh ke berkas .part, periksa, baru ganti berkas lama secara atomik.

    Berkas lama tetap utuh sampai yang baru terbukti PDF yang sah. Server bisa
    mengembalikan halaman HTML galat dengan status 200.

    Return None kalau berhasil, atau pesan galat kalau gagal.
    """
    os.makedirs(os.path.dirname(path_tujuan), exist_ok=True)
    sementara = path_tujuan + ".part"
    galat = None

    for percobaan in range(1, MAKS_PERCOBAAN + 1):
        try:
            with requests.get(url, stream=True, timeout=TIMEOUT_UNDUH) as r:
                r.raise_for_status()
                with open(sementara, "wb") as f:
                    for chunk in r.iter_content(chunk_size=UKURAN_CHUNK):
                        if chunk:
                            f.write(chunk)

            if not berkas_pdf_valid(sementara):
                raise ValueError(f"bukan PDF utuh ({os.path.getsize(sementara)} byte)")

            os.replace(sementara, path_tujuan)
            return None

        except Exception as e:  # noqa: BLE001 - apa pun sebabnya, publikasi ini saja yang gagal
            galat = e
            try:
                os.remove(sementara)
            except OSError:
                pass
            if percobaan < MAKS_PERCOBAAN:
                print(f"    percobaan {percobaan} gagal ({samarkan(e)}), "
                      f"ulangi dalam {JEDA_ULANG_UNDUH:.0f} detik", flush=True)
                time.sleep(JEDA_ULANG_UNDUH)

    return samarkan(galat)
