"""Sampul publikasi: diunduh SEKALI dari WebAPI BPS, disimpan lokal (19 Nov 2026).

Kolom `cover` di respons WebAPI (publikasi.url_cover) berbentuk
https://webapi.bps.go.id/cover.php?f=<token>. Tokennya bisa kedaluwarsa, sama
seperti URL PDF, jadi sampul diunduh sesaat sesudah metadata ditarik
(perbarui.py) atau, untuk data lama, oleh scripts/isi_sampul.py pada hari
yang sama dengan pembaruan terakhir.

Dua berkas per publikasi di Config.DIR_SAMPUL (data/sampul/, di-gitignore):
  <pub_id>.jpg           sampul resmi dari WebAPI, disimpan apa adanya (JPEG)
  <pub_id>.cadangan.jpg  render halaman 1 PDF lokal, dibuat kalau unduhan gagal
Cadangan dipisah supaya pembaruan berikutnya tetap mencoba sampul resmi;
begitu sampul resmi ada, cadangannya dihapus. Tanpa keduanya, publikasi
tampil tanpa gambar.

Render cadangan memakai pdfplumber (sudah di requirements) beserta
dependensinya sendiri (pypdfium2, Pillow); tidak ada dependensi baru.
Token dan API key tidak pernah ditulis ke keluaran: semua pesan lewat
samarkan_url().
"""

import io
import os
import re
import time

import requests

from app.config import Config
from app.services.sumber_bps import berkas_pdf_valid, samarkan

TIMEOUT = (15, 60)              # (connect, read); sampul ±100 KB
MAKS_BYTE = 5 * 1024 * 1024     # di atas ini pasti bukan sampul
MINIMAL_BYTE = 1024             # di bawah ini pasti bukan gambar utuh
JEDA_ULANG = 5                  # detik, sebelum percobaan kedua
LEBAR_CADANGAN = 500            # = lebar sampul WebAPI (diukur 19 Nov 2026)
MUTU_JPEG = 85

RE_TOKEN = re.compile(r"([?&](?:f|key|token)=)[^&\s'\"]+", re.I)


def samarkan_url(teks):
    """API key (sumber_bps.samarkan) dan nilai parameter f/key/token -> ***."""
    return RE_TOKEN.sub(r"\1***", samarkan(teks))


def path_resmi(pub_id):
    return os.path.join(str(Config.DIR_SAMPUL), f"{pub_id}.jpg")


def path_cadangan(pub_id):
    return os.path.join(str(Config.DIR_SAMPUL), f"{pub_id}.cadangan.jpg")


def berkas(pub_id):
    """Berkas sampul yang ditampilkan: resmi dulu, lalu cadangan; None kalau
    tidak ada keduanya."""
    for path in (path_resmi(pub_id), path_cadangan(pub_id)):
        if os.path.isfile(path):
            return path
    return None


# Ukuran sampul untuk atribut width/height <img> (tata letak tidak bergeser
# saat gambar dimuat). Dibaca dari kepala berkas sekali per (berkas, waktu
# ubah), lalu disimpan di memori proses; dict biasa aman untuk beberapa thread
# waitress karena isinya hanya ditambah/ditimpa utuh.
_UKURAN = {}
RE_PUB_ID = re.compile(r"[0-9A-Za-z]{1,64}")


def info(pub_id):
    """{"lebar", "tinggi", "versi"} sampul yang ditampilkan, atau None kalau
    publikasi tidak punya berkas sampul (kartu lalu tampil tanpa gambar).
    versi = waktu ubah berkas, dipasang di URL supaya cache browser
    tergantikan begitu sampul cadangan diganti sampul resmi."""
    if not pub_id or not RE_PUB_ID.fullmatch(str(pub_id)):
        return None
    path = berkas(pub_id)
    if path is None:
        return None
    try:
        mtime = os.stat(path).st_mtime_ns
    except OSError:
        return None
    kunci = (path, mtime)
    if kunci not in _UKURAN:
        from PIL import Image          # dependensi pdfplumber; hanya membaca kepala berkas
        try:
            with Image.open(path) as img:
                lebar, tinggi = img.size
        except Exception:  # noqa: BLE001 - berkas rusak: tampil tanpa gambar
            return None
        _UKURAN[kunci] = {"lebar": lebar, "tinggi": tinggi, "versi": mtime // 1_000_000_000}
    return _UKURAN[kunci]


def _tulis_atomik(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sementara = path + ".part"
    with open(sementara, "wb") as f:
        f.write(data)
    os.replace(sementara, path)


def _periksa_gambar(data):
    """Gambar utuh? Kembalikan (format, lebar, tinggi); ValueError kalau bukan."""
    from PIL import Image          # dependensi pdfplumber
    if len(data) < MINIMAL_BYTE:
        raise ValueError(f"terlalu kecil ({len(data)} byte)")
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()             # membaca seluruh data: gambar terpotong ketahuan
            return img.format, img.width, img.height
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"bukan gambar utuh ({type(e).__name__})") from None


def _ke_jpeg(data):
    from PIL import Image
    with Image.open(io.BytesIO(data)) as img:
        keluar = io.BytesIO()
        img.convert("RGB").save(keluar, "JPEG", quality=MUTU_JPEG)
        return keluar.getvalue()


def unduh(url, pub_id, statistik=None):
    """Unduh sampul resmi ke <pub_id>.jpg. None kalau berhasil, atau pesan galat
    (sudah disamarkan). Paling banyak 2 percobaan; HTTP 4xx (token kedaluwarsa)
    tidak diulang. JPEG disimpan apa adanya; format lain dikonversi ke JPEG."""
    stat = statistik if statistik is not None else {}
    stat.update(byte=0, detik=0.0, format=None, ukuran=None)
    if not url:
        return "publikasi tidak punya url_cover"
    galat = None
    for percobaan in (1, 2):
        mulai = time.perf_counter()
        try:
            with requests.get(url, timeout=TIMEOUT, stream=True) as r:
                r.raise_for_status()
                data = r.raw.read(MAKS_BYTE + 1, decode_content=True)
            if len(data) > MAKS_BYTE:
                raise ValueError("lebih dari 5 MB, bukan sampul")
            fmt, lebar, tinggi = _periksa_gambar(data)
            if fmt != "JPEG":
                data = _ke_jpeg(data)
            _tulis_atomik(path_resmi(pub_id), data)
            try:
                os.remove(path_cadangan(pub_id))    # sampul resmi menggantikan cadangan
            except OSError:
                pass
            stat.update(byte=len(data), detik=time.perf_counter() - mulai,
                        format=fmt, ukuran=(lebar, tinggi))
            return None
        except Exception as e:  # noqa: BLE001 - sampul gagal tidak boleh menghentikan apa pun
            galat = e
            respons = getattr(e, "response", None)
            if respons is not None and 400 <= respons.status_code < 500:
                break
            if percobaan == 1:
                time.sleep(JEDA_ULANG)
    return samarkan_url(galat)[:200]


def dari_pdf(path_pdf, pub_id):
    """Cadangan: render halaman 1 PDF lokal ke <pub_id>.cadangan.jpg, lebar
    500 px. None kalau berhasil, atau pesan galat."""
    if not path_pdf or not berkas_pdf_valid(path_pdf):
        return "PDF lokal tidak ada atau rusak"
    try:
        import pdfplumber
        with pdfplumber.open(path_pdf) as pdf:
            img = pdf.pages[0].to_image(width=LEBAR_CADANGAN).original.convert("RGB")
        if img.width != LEBAR_CADANGAN:     # pembulatan pdfplumber (bisa 501 px)
            img = img.resize((LEBAR_CADANGAN, round(img.height * LEBAR_CADANGAN / img.width)))
        keluar = io.BytesIO()
        img.save(keluar, "JPEG", quality=MUTU_JPEG)
        _tulis_atomik(path_cadangan(pub_id), keluar.getvalue())
        return None
    except Exception as e:  # noqa: BLE001
        return samarkan_url(f"render halaman 1 gagal: {e}")[:200]


def lengkapi(pub_id, url, path_pdf, online=True):
    """Satu publikasi: coba sampul resmi (kalau online), lalu cadangan PDF.

    Kembalikan dict {hasil, byte, pesan}; hasil = "resmi" | "cadangan" |
    "cadangan_lama" (unduhan gagal, cadangan yang sudah ada dipertahankan) |
    "gagal". Pemanggil yang memberi jeda antar unduhan (Term of Use)."""
    pesan_unduh = None
    if online:
        stat = {}
        pesan_unduh = unduh(url, pub_id, stat)
        if pesan_unduh is None:
            return {"hasil": "resmi", "byte": stat["byte"], "pesan": None}
    if os.path.isfile(path_cadangan(pub_id)):
        return {"hasil": "cadangan_lama", "byte": 0, "pesan": pesan_unduh}
    pesan_pdf = dari_pdf(path_pdf, pub_id)
    if pesan_pdf is None:
        return {"hasil": "cadangan", "byte": 0, "pesan": pesan_unduh}
    return {"hasil": "gagal", "byte": 0,
            "pesan": "; ".join(p for p in (pesan_unduh, pesan_pdf) if p)}
