"""Preprocessing teks: stemming Bahasa Indonesia + normalisasi sinonim.

SATU fungsi dipakai DUA arah - saat indexing (mengisi
`entri_dokumen.teks_ternormalisasi`) dan saat memproses kueri petugas. Keduanya
WAJIB memakai `normalisasi()` yang sama; kalau perlakuannya berbeda, skor
kemiripan jadi tidak bermakna.

Urutan langkah:
    lowercase -> bersihkan tanda baca -> stemming Sastrawi -> substitusi sinonim

Substitusi sinonim terjadi SETELAH stemming, di level kata dasar. Kamus di
`data/kamus_sinonim.json` boleh ditulis dengan kata sehari-hari ("banyaknya",
"keseluruhan"); modul ini yang men-stem-kan saat memuat, sehingga file kamus
tetap enak dibaca manusia.
"""

import json
import os
import re
from functools import lru_cache

from Sastrawi.Stemmer.StemmerFactory import StemmerFactory

FILE_KAMUS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "kamus_sinonim.json",
)

# Angka ikut dipertahankan: tahun ("2025") sering jadi pembeda antar entri.
RE_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

_stemmer = StemmerFactory().create_stemmer()


@lru_cache(maxsize=100_000)
def stem_kata(kata):
    """Stem satu kata, dengan cache.

    Sastrawi relatif lambat dan korpus punya puluhan ribu token tapi kosakata
    uniknya hanya ribuan, jadi cache menghilangkan sebagian besar pemanggilan.
    """
    return _stemmer.stem(kata)


def tokenkan(teks):
    """lowercase + buang tanda baca -> daftar token."""
    if not teks:
        return []
    return RE_TOKEN.findall(teks.lower())


def stem_token(token):
    return [stem_kata(t) for t in token]


class Kamus:
    """Kamus sinonim kelompok kanonik, siap pakai untuk substitusi.

    Format file:
        {"banyaknya": ["banyaknya", "jumlah", "total", "keseluruhan"]}

    Kunci = bentuk kanonik, nilai = varian yang dipetakan ke kanonik itu.
    Kanonik maupun varian sama-sama di-stem saat dimuat, jadi pencocokan
    terjadi di level kata dasar.
    """

    def __init__(self, kelompok=None):
        self._peta = {}          # tuple token varian -> tuple token kanonik
        self._maks_panjang = 1
        for kanonik, varian in (kelompok or {}).items():
            self.tambah(kanonik, varian)

    def tambah(self, kanonik, varian):
        token_kanonik = tuple(stem_token(tokenkan(kanonik)))
        if not token_kanonik:
            return
        for v in list(varian) + [kanonik]:
            token_varian = tuple(stem_token(tokenkan(v)))
            if not token_varian or token_varian == token_kanonik:
                continue
            self._peta[token_varian] = token_kanonik
            self._maks_panjang = max(self._maks_panjang, len(token_varian))

    def substitusi(self, token, maks_putaran=3):
        """Ganti varian jadi bentuk kanonik. Frasa terpanjang dicoba lebih dulu.

        Frasa penting karena banyak sinonim BPS berupa frasa, bukan satu kata:
        "tingkat huni kamar" -> "tpk".

        Diulang sampai stabil karena sinonim bisa berantai: "rerata lama tamu
        menginap" harus jadi "rata lama tamu inap" DULU sebelum frasa itu bisa
        dikenali sebagai "rlm". Sekali jalan tidak cukup.
        """
        hasil = list(token)
        for _ in range(maks_putaran):
            berikut = self._satu_putaran(hasil)
            if berikut == hasil:
                break
            hasil = berikut
        return hasil

    def _satu_putaran(self, token):
        if not self._peta:
            return list(token)

        hasil = []
        i = 0
        while i < len(token):
            cocok = None
            batas = min(self._maks_panjang, len(token) - i)
            for n in range(batas, 0, -1):
                kunci = tuple(token[i:i + n])
                if kunci in self._peta:
                    cocok = (n, self._peta[kunci])
                    break
            if cocok:
                n, ganti = cocok
                hasil.extend(ganti)
                i += n
            else:
                hasil.append(token[i])
                i += 1

        # Korpus sering menulis "Frasa Lengkap (AKRONIM)" sekaligus, sehingga
        # frasa DAN akronimnya sama-sama tersubstitusi jadi token yang sama.
        # Rapatkan kembaran berurutan supaya cakupan kata kunci tidak melar.
        rapat = []
        for t in hasil:
            if not rapat or rapat[-1] != t:
                rapat.append(t)
        return rapat

    def __len__(self):
        return len(self._peta)


def muat_kamus(path=FILE_KAMUS):
    """Baca kamus dari JSON. File tidak ada / rusak -> kamus kosong, bukan error.

    Sistem tetap harus bisa mencari walau kamus belum disusun.
    """
    if not os.path.exists(path):
        return Kamus()
    try:
        with open(path, encoding="utf-8") as f:
            isi = json.load(f)
    except (OSError, json.JSONDecodeError):
        return Kamus()
    if not isinstance(isi, dict):
        return Kamus()
    return Kamus(isi)


_kamus_default = None


def kamus_default():
    """Kamus bersama, dimuat sekali saat pertama dipakai."""
    global _kamus_default
    if _kamus_default is None:
        _kamus_default = muat_kamus()
    return _kamus_default


def muat_ulang_kamus():
    """Paksa muat ulang - dipakai setelah kamus diedit lewat halaman admin."""
    global _kamus_default
    _kamus_default = None
    return kamus_default()


def normalisasi_token(teks, kamus=None):
    """Pipeline lengkap, hasilnya daftar token."""
    kamus = kamus_default() if kamus is None else kamus
    return kamus.substitusi(stem_token(tokenkan(teks)))


def normalisasi(teks, kamus=None):
    """Pipeline lengkap, hasilnya satu string dipisah spasi.

    Inilah yang disimpan ke `entri_dokumen.teks_ternormalisasi` DAN yang dipakai
    untuk kueri petugas.
    """
    return " ".join(normalisasi_token(teks, kamus))
