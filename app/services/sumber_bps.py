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
# Unduhan PDF bisa putus di tengah ("Response ended prematurely"), dan server
# BPS TIDAK mendukung Range (diuji 9 Nov 2026: permintaan sebagian dijawab 200
# berkas penuh, tanpa Accept-Ranges/Content-Length) - jadi tiap percobaan
# mulai dari nol. Jeda bertahap memberi waktu jaringan pulih.
JEDA_ULANG_UNDUH = (5, 15, 45)          # sebelum percobaan ke-2, ke-3, ke-4
MAKS_PERCOBAAN_UNDUH = len(JEDA_ULANG_UNDUH) + 1
TIMEOUT_DAFTAR = 30
TIMEOUT_UNDUH = (15, 120)     # (connect, read) - berkas bisa sampai 25 MB
UKURAN_CHUNK = 64 * 1024
MINIMAL_WAJAR = 1024    # di bawah ini pasti bukan PDF publikasi utuh
EKOR_DIBACA = 2048      # cukup untuk menemukan %%EOF di ujung berkas

# Berapa tahun terakhir yang diambil, dihitung dari tahun berjalan.
JUMLAH_TAHUN = 2

# Boleh berhenti menarik halaman daftar begitu satu halaman penuh berisi
# publikasi di luar jendela tahun? Hanya kalau daftar API terbukti terurut dari
# rl_date terbaru (bukti per domain: cek_urutan(), dijalankan --hanya-periksa).
# Dibuktikan 9 Nov 2026: 14 domain, 5.246 publikasi, 0 rl_date yang naik dalam
# urutan API, 0 publikasi jendela yang terlewat; pemeriksanya sendiri diuji
# dengan urutan yang sengaja diacak dan menangkapnya. Menghemat ~450 dari ~530
# halaman daftar per pembaruan. --hanya-periksa tetap menarik SEMUA halaman,
# jadi bukti ini terus diperbarui; kalau suatu saat "terlewat" > 0, ubah ke False.
DAFTAR_TERURUT_TERBARU = True


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


def ambil_domain(domain, berhenti_sebelum_tahun=None):
    """Daftar publikasi milik satu domain, utuh atau tidak sama sekali.

    Begitu satu halaman gagal, proses berhenti: daftar yang tidak utuh membuat
    publikasi yang ada terlihat seperti terhapus.

    `berhenti_sebelum_tahun`: kalau diberi, penarikan berhenti begitu SATU
    HALAMAN PENUH berisi publikasi yang seluruhnya dirilis sebelum tahun itu.
    Hanya sah karena daftar API terurut dari rl_date terbaru - dibuktikan
    9 Nov 2026 di 14 domain (lihat cek_urutan() dan --hanya-periksa). Tanpa
    parameter ini semua halaman ditarik (dipakai --hanya-periksa, yang memang
    butuh daftar semua tahun).
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
        if berhenti_sebelum_tahun and daftar and all(
                (tahun_rilis(p.get("rl_date")) or 9999) < berhenti_sebelum_tahun
                for p in daftar):
            print(f"  berhenti di halaman {halaman - 1}/{total_halaman}: seluruh isinya "
                  f"dirilis sebelum {berhenti_sebelum_tahun} (daftar API terurut terbaru)",
                  flush=True)
            return list(semua.values())
        time.sleep(JEDA_DETIK)   # jeda sesuai Term of Use


def cek_urutan(daftar, tahun_min):
    """Bukti urutan daftar API (sesuai urutan halaman) untuk berhenti lebih awal.

    Return dict:
      pelanggaran   - berapa kali rl_date NAIK dibanding item sebelumnya
                      (daftar yang terurut terbaru tidak pernah naik)
      terlewat      - publikasi di jendela tahun yang muncul SESUDAH titik
                      berhenti lebih awal; harus 0 supaya berhenti lebih awal aman
      halaman_dibaca / halaman_total - perkiraan halaman yang ditarik kalau
                      berhenti lebih awal (10 item per halaman)
    """
    tanggal = [str(p.get("rl_date") or "") for p in daftar]
    pelanggaran = sum(1 for a, b in zip(tanggal, tanggal[1:]) if a and b and b > a)
    halaman = [daftar[i:i + 10] for i in range(0, len(daftar), 10)]
    berhenti = len(halaman)
    for i, h in enumerate(halaman):
        if h and all((tahun_rilis(p.get("rl_date")) or 9999) < tahun_min for p in h):
            berhenti = i + 1
            break
    sesudah = [p for h in halaman[berhenti:] for p in h]
    terlewat = sum(1 for p in sesudah if (tahun_rilis(p.get("rl_date")) or 0) >= tahun_min)
    return {"pelanggaran": pelanggaran, "terlewat": terlewat,
            "halaman_dibaca": berhenti, "halaman_total": len(halaman)}


def ukuran_mb(teks):
    """Field `size` API ("14.07 MB") -> MB. Per berkas meleset sampai 167%,
    tapi jumlahnya cocok dengan total sebenarnya - jadi hanya untuk perkiraan
    total, tidak untuk memeriksa keutuhan berkas."""
    cocok = re.match(r"\s*([0-9.,]+)\s*(KB|MB|GB)?", str(teks or ""), re.IGNORECASE)
    if not cocok:
        return 0.0
    nilai = float(cocok.group(1).replace(",", "."))
    satuan = (cocok.group(2) or "MB").upper()
    return nilai / 1024 if satuan == "KB" else nilai * 1024 if satuan == "GB" else nilai


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


def unduh_pdf(url, path_tujuan, statistik=None):
    """Unduh ke berkas .part, periksa, baru ganti berkas lama secara atomik.

    Berkas lama tetap utuh sampai yang baru terbukti PDF yang sah. Server bisa
    mengembalikan halaman HTML galat dengan status 200.

    `statistik` opsional (dict), diisi untuk laporan kecepatan unduhan:
      byte, detik_transfer (percobaan yang berhasil saja), detik_total
      (termasuk percobaan gagal dan jedanya), percobaan, putus (percobaan yang
      gagal sesudah sempat menerima data), url_kedaluwarsa (HTTP 4xx - URL
      PDF di WebAPI bertoken dan berganti; URL dari metadata lama ditolak 400).

    Return None kalau berhasil, atau pesan galat kalau gagal.
    """
    os.makedirs(os.path.dirname(path_tujuan), exist_ok=True)
    sementara = path_tujuan + ".part"
    stat = statistik if statistik is not None else {}
    stat.update(byte=0, detik_transfer=0.0, detik_total=0.0, percobaan=0,
                putus=0, url_kedaluwarsa=False)
    galat = None
    mulai_total = time.perf_counter()

    for percobaan in range(1, MAKS_PERCOBAAN_UNDUH + 1):
        stat["percobaan"] = percobaan
        diterima = 0
        mulai = time.perf_counter()
        try:
            with requests.get(url, stream=True, timeout=TIMEOUT_UNDUH) as r:
                r.raise_for_status()
                with open(sementara, "wb") as f:
                    for chunk in r.iter_content(chunk_size=UKURAN_CHUNK):
                        if chunk:
                            f.write(chunk)
                            diterima += len(chunk)

            if not berkas_pdf_valid(sementara):
                raise ValueError(f"bukan PDF utuh ({os.path.getsize(sementara)} byte)")

            os.replace(sementara, path_tujuan)
            stat.update(byte=diterima, detik_transfer=time.perf_counter() - mulai,
                        detik_total=time.perf_counter() - mulai_total,
                        url_kedaluwarsa=False)
            return None

        except Exception as e:  # noqa: BLE001 - apa pun sebabnya, publikasi ini saja yang gagal
            galat = e
            if diterima:
                stat["putus"] += 1
            respons = getattr(e, "response", None)
            if respons is not None and 400 <= respons.status_code < 500:
                stat["url_kedaluwarsa"] = True
            try:
                os.remove(sementara)
            except OSError:
                pass
            if stat["url_kedaluwarsa"]:
                break           # URL yang sama tidak akan diterima; pakai URL segar
            if percobaan < MAKS_PERCOBAAN_UNDUH:
                jeda = JEDA_ULANG_UNDUH[percobaan - 1]
                print(f"    percobaan {percobaan} gagal sesudah {diterima / 1e6:.1f} MB "
                      f"({samarkan(e)[:80]}), ulangi dari awal dalam {jeda} detik",
                      flush=True)
                time.sleep(jeda)

    stat["detik_total"] = time.perf_counter() - mulai_total
    return samarkan(galat)
