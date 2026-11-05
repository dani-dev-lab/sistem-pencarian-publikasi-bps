"""Daftar domain BPS yang dikelola aplikasi, dibaca dari data/wilayah.json.

Berkas, bukan tabel database: daftar ini nyaris tidak pernah berubah, dan
mengaktifkan satu domain cukup dengan mengubah satu nilai tanpa antarmuka baru.
Berisi kode, nama tampil, dan status aktif tiap domain.
"""

import json
import re

from app.config import Config


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
