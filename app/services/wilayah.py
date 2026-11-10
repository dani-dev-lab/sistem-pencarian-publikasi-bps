"""Daftar domain BPS yang dikelola aplikasi, dibaca dari data/wilayah.json.

Berkas, bukan tabel database: daftar ini nyaris tidak pernah berubah, dan
mengaktifkan satu domain cukup dengan mengubah satu nilai tanpa antarmuka baru.
Berisi kode, nama tampil, dan status aktif tiap domain.
"""

import json
import os
import re
from functools import lru_cache

from app.config import Config

# Domain provinsi. Publikasinya mencakup seluruh 13 kabupaten/kota, jadi di
# hasil pencarian yang difilter ke satu kabupaten/kota, entri provinsi
# ditampilkan di bagian tersendiri ("Juga ada di publikasi provinsi").
DOMAIN_PROVINSI = "6300"

# Kata yang mendahului nama wilayah ("kabupaten tanah laut", "kota
# banjarmasin"). Ikut dibuang bersama nama wilayahnya, karena tanpa nama
# wilayah kata ini hanya menyisakan "kabupaten" yang cocok dengan ribuan
# judul "... menurut Kabupaten/Kota".
AWALAN_WILAYAH = frozenset({"kab", "kabupaten", "kota", "kotamadya", "kodya"})

RE_AWALAN_NAMA = re.compile(r"^(?:kab\.?|kabupaten|kota|provinsi)\s+", re.IGNORECASE)


def muat_wilayah(path=None):
    """Seluruh wilayah di konfigurasi, aktif maupun tidak.

    Isi yang salah ditolak dengan pesan, bukan dibiarkan: kode domain yang
    keliru akan menarik data wilayah lain tanpa ada yang menyadari.
    """
    path = path or Config.FILE_WILAYAH
    try:
        with open(path, encoding="utf-8") as f:
            daftar = json.load(f)["wilayah"]
    except (OSError, ValueError, KeyError) as e:
        raise SystemExit(f"{path} tidak bisa dibaca: {e}") from None

    terlihat = set()
    for w in daftar:
        kode = str(w.get("kode", ""))
        if not re.fullmatch(r"[0-9]{4}", kode):
            raise SystemExit(f"{path}: kode domain tidak valid: {kode!r}")
        if kode in terlihat:
            raise SystemExit(f"{path}: kode domain ganda: {kode}")
        if not w.get("nama"):
            raise SystemExit(f"{path}: domain {kode} tidak punya nama")
        terlihat.add(kode)
    return daftar


def wilayah_aktif(path=None):
    return [w for w in muat_wilayah(path) if w.get("aktif")]


def pola_judul_dikecualikan(path=None):
    """Pola judul publikasi yang TIDAK ditarik, dari `kecualikan_judul`.

    Pengaturan, bukan aturan di kode: cakupan publikasi diputuskan tim PST
    dan bisa berubah. Return list (regex terkompilasi, teks pola), hanya yang
    aktif. Pola yang tidak valid ditolak dengan pesan - pola rusak yang
    diam-diam diabaikan berarti publikasi yang seharusnya dikecualikan ikut
    ditarik.
    """
    path = path or Config.FILE_WILAYAH
    try:
        with open(path, encoding="utf-8") as f:
            daftar = json.load(f).get("kecualikan_judul", [])
    except (OSError, ValueError) as e:
        raise SystemExit(f"{path} tidak bisa dibaca: {e}") from None

    hasil = []
    for p in daftar:
        if not p.get("aktif"):
            continue
        teks = p.get("pola") or ""
        try:
            hasil.append((re.compile(teks, re.IGNORECASE), teks))
        except re.error as e:
            raise SystemExit(f"{path}: pola kecualikan_judul tidak valid {teks!r}: {e}") from None
    return hasil


@lru_cache(maxsize=4)
def _pola_deteksi(path, _mtime):
    """Bentuk kata yang dikenali per wilayah, terpanjang lebih dulu.

    Sumbernya `nama` tanpa awalan Kab./Kota, `nama_lain` (ejaan API:
    "Kota Baru", "Banjar Baru"), dan `singkatan`. Provinsi tidak dideteksi:
    "kalsel" dan "kalimantan selatan" ada di judul publikasi kab/kota juga,
    dan provinsi bukan penyempit pencarian.

    Di-cache menurut waktu ubah berkas: wilayah.json yang diedit langsung
    berlaku tanpa restart.
    """
    pola = []
    for w in muat_wilayah(path):
        if not w.get("aktif") or w["kode"] == DOMAIN_PROVINSI:
            continue
        bentuk = [RE_AWALAN_NAMA.sub("", w["nama"])]
        bentuk += w.get("nama_lain") or []
        bentuk += w.get("singkatan") or []
        for b in bentuk:
            kata = tuple(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", b.lower()))
            if kata:
                pola.append((kata, w["kode"], w["nama"]))
    # Terpanjang dulu: "banjar baru" (Banjarbaru) harus menang atas "banjar".
    pola.sort(key=lambda p: -len(p[0]))
    return tuple(pola)


def deteksi(token, path=None):
    """Nama/singkatan wilayah di dalam token kueri, dicocokkan per KATA UTUH.

    `token` = hasil preprocessing.tokenkan(kueri) - tokenisasi yang sama
    dengan normalisasi, sehingga kueri tanpa kata wilayah bisa disusun ulang
    dari token yang tersisa.

    Kata utuh, bukan substring: "banjar" tidak cocok dengan "banjarmasin"
    atau "banjarbaru", dan sebaliknya.

    Return list dict {kode, nama, teks, awal, akhir}; `awal`/`akhir` indeks
    token (akhir eksklusif), sudah termasuk awalan "kabupaten"/"kota" yang
    langsung mendahuluinya.
    """
    path = path or Config.FILE_WILAYAH
    pola = _pola_deteksi(str(path), os.path.getmtime(path))
    temuan = []
    i = 0
    while i < len(token):
        for kata, kode, nama in pola:
            n = len(kata)
            if tuple(token[i:i + n]) != kata:
                continue
            awal = i
            batas_kiri = temuan[-1]["akhir"] if temuan else 0
            if i > batas_kiri and token[i - 1] in AWALAN_WILAYAH:
                awal = i - 1
            temuan.append({"kode": kode, "nama": nama,
                           "teks": " ".join(token[awal:i + n]),
                           "awal": awal, "akhir": i + n})
            i += n
            break
        else:
            i += 1
    return temuan
