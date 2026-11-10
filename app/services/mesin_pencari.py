"""Mesin pencari: fuzzy matching + scoring relevansi.

Alur: kueri -> normalisasi -> skor terhadap `entri_dokumen.teks_ternormalisasi`
-> urutkan -> pisahkan menurut ambang.

Normalisasi memakai `preprocessing.normalisasi()` yang SAMA PERSIS dengan yang
mengisi kolom teks_ternormalisasi. Kalau keduanya berbeda, skornya tidak
bermakna.

Keputusan sadar (lihat CLAUDE.md): fuzzy matching, BUKAN semantic embeddings.
"""

import math
import re
import threading
import time
from datetime import date

from rapidfuzz import fuzz

from app.models import EntriDokumen, Publikasi, db
from app.services import versi_data
from app.services.preprocessing import kamus_default, normalisasi, normalisasi_token
from app.services.wilayah import DOMAIN_PROVINSI

BOBOT_SET = 0.5        # token_set_ratio: toleran urutan kata & salah ketik
BOBOT_SORT = 0.2       # token_sort_ratio: menghukum entri yang jauh lebih panjang
BOBOT_COVERAGE = 0.3   # cakupan kata kunci petugas

# Peredam penalti panjang. Bentuk penalti: skor / (1 + ALPHA * ln(1 + rasio)),
# dengan rasio = panjang_entri / panjang_kueri.
#
# Tanpa peredam (ALPHA = 1) penalti terlalu keras: kueri 1 kata terhadap entri
# 11 kata (median korpus) sudah membagi skor dengan 3,5 - kecocokan sempurna
# pun jatuh ke ~29 dan seluruh hasil tenggelam di bawah ambang.
ALPHA_PANJANG = 0.05

# Ambang SEMENTARA, diturunkan dari sebaran skor 8 kueri uji (lihat CLAUDE.md).
# Angka lama 80/40 berasal dari rumus lama yang skornya jenuh di 100; setelah
# rumus diperbaiki, puncak skor turun ke kisaran 87-90 sehingga ambangnya ikut
# digeser. Ditetapkan ulang setelah uji coba petugas PST dan setelah
# log_pencarian terisi kueri sungguhan.
AMBANG_DITEMUKAN = 75     # >= ini: hasil ditemukan
AMBANG_SARAN = 50         # 50-74: "mungkin maksud Anda"; < 50 disembunyikan

BATAS_HASIL = 20

# Bagian "Juga ada di publikasi provinsi" di bawah hasil yang difilter ke satu
# kabupaten/kota. Pelengkap, bukan hasil utama, jadi dibatasi lebih pendek.
BATAS_PROVINSI = 10


def _skor(token_kueri, teks_entri):
    """Tiga sinyal digabung, lalu dibagi penalti panjang. Skala 0-100.

    - token_set_ratio  : jenuh di 100 begitu semua kata kueri terkandung,
                         tak peduli sepanjang apa entrinya
    - token_sort_ratio : membandingkan urutan penuh, jadi entri panjang yang
                         kebetulan memuat kata kunci ikut turun sendirinya
    - coverage         : seberapa banyak kata kunci benar-benar ada

    Penalti panjang menutup celah yang tersisa: dua judul tabel berbeda yang
    tergabung jadi satu entri panjang tidak boleh mengalahkan entri pendek
    yang benar-benar membahas topik itu.
    """
    if not token_kueri or not teks_entri:
        return 0.0, 0.0, 0.0, 0.0

    kueri = " ".join(token_kueri)
    token_entri = teks_entri.split()

    set_ratio = fuzz.token_set_ratio(kueri, teks_entri)
    sort_ratio = fuzz.token_sort_ratio(kueri, teks_entri)

    unik_entri = set(token_entri)
    ada = sum(1 for t in token_kueri if t in unik_entri)
    coverage = ada / len(token_kueri) * 100

    dasar = (BOBOT_SET * set_ratio
             + BOBOT_SORT * sort_ratio
             + BOBOT_COVERAGE * coverage)

    rasio = len(token_entri) / len(token_kueri)
    penalti = 1 + ALPHA_PANJANG * math.log1p(rasio)

    return dasar / penalti, set_ratio, sort_ratio, coverage


def _ambil_publikasi():
    """Publikasi + jumlah entri yang dimilikinya, sekali query."""
    jml = (
        db.session.query(
            EntriDokumen.publikasi_id.label("pid"),
            db.func.count(EntriDokumen.id).label("n"),
        )
        .group_by(EntriDokumen.publikasi_id)
        .subquery()
    )
    return (
        db.session.query(
            Publikasi.id,
            Publikasi.judul,
            Publikasi.abstrak,
            Publikasi.tanggal_rilis,
            Publikasi.url_pdf,
            Publikasi.teks_ternormalisasi,
            db.func.coalesce(jml.c.n, 0),
            Publikasi.domain,
            Publikasi.wilayah,
        )
        .outerjoin(jml, jml.c.pid == Publikasi.id)
        .all()
    )


def _cari_publikasi(token_kueri, ambang_saran, baris_publikasi):
    """Skor tingkat publikasi.

    Skornya diambil dari NILAI TERTINGGI antara dua perhitungan:

      a. terhadap judul saja
      b. terhadap judul + abstrak

    Diuji terhadap 6 kueri: (a) unggul untuk kueri yang menyebut judul
    ("statistik ekspor impor" -> 86,2 vs 68,6) tapi buta terhadap istilah yang
    hanya ada di abstrak ("kpppbc" -> 8,3); (b) sebaliknya, bagus untuk istilah
    abstrak tapi judul tenggelam karena abstrak median 82 token mengencerkan
    sinyal - "perhotelan" malah menempatkan Direktori Akomodasi di atas
    Statistik Perhotelan.

    Mengambil nilai tertinggi membuat keduanya menang di wilayahnya sendiri.
    """
    hasil = []
    kumpulan = set(token_kueri)

    for (pid, judul, abstrak, tanggal_rilis, url_pdf, ternormalisasi,
         jumlah_entri, domain, wilayah, token_gabungan, judul_normal) in baris_publikasi:
        if not ternormalisasi:
            continue
        # Penyaring murah memakai teks gabungan, supaya istilah yang hanya ada
        # di abstrak tetap lolos ke tahap penilaian.
        if kumpulan.isdisjoint(token_gabungan):
            continue

        skor_judul, set_j, sort_j, cov_j = _skor(token_kueri, judul_normal)
        skor_gabungan, set_g, sort_g, cov_g = _skor(token_kueri, ternormalisasi)

        if skor_judul >= skor_gabungan:
            skor, set_r, sort_r, cov = skor_judul, set_j, sort_j, cov_j
            sumber = "judul"
        else:
            skor, set_r, sort_r, cov = skor_gabungan, set_g, sort_g, cov_g
            sumber = "judul+abstrak"

        if skor < ambang_saran:
            continue

        hasil.append({
            "publikasi_id": pid,
            "judul": judul,
            "abstrak": abstrak,
            "tanggal_rilis": tanggal_rilis,
            "url_pdf": url_pdf,
            "jumlah_entri": jumlah_entri,
            "domain": domain,
            "wilayah": wilayah,
            "skor": round(skor, 1),
            "skor_set": round(set_r, 1),
            "skor_sort": round(sort_r, 1),
            "skor_coverage": round(cov, 1),
            "sumber_skor": sumber,
        })

    hasil.sort(key=lambda h: (-h["skor"],
                              -(h["tanggal_rilis"] or date.min).toordinal()))
    return hasil


def _ambil_korpus():
    """Semua entri + metadata publikasinya, sekali query.

    Sengaja mengambil kolom lepas (bukan objek ORM penuh) supaya ringan -
    tidak perlu identity map untuk pekerjaan baca-saja seperti ini.
    """
    return (
        db.session.query(
            EntriDokumen.id,
            EntriDokumen.tipe,
            EntriDokumen.nomor,
            EntriDokumen.judul,
            EntriDokumen.halaman,
            EntriDokumen.halaman_fisik,
            EntriDokumen.teks_ternormalisasi,
            Publikasi.id,
            Publikasi.judul,
            Publikasi.url_pdf,
            Publikasi.tanggal_rilis,
            Publikasi.domain,
            Publikasi.wilayah,
        )
        .join(Publikasi, EntriDokumen.publikasi_id == Publikasi.id)
        .all()
    )


# --------------------------------------------------------------------------
# Korpus di memori proses (10 Nov 2026)
# --------------------------------------------------------------------------
# Sesudah 13 kab/kota masuk (23.461 entri), ±70% waktu tiap pencarian habis
# untuk mengambil SELURUH korpus dari MySQL (308 dari 430 ms). Korpus kini
# dimuat sekali, disimpan di memori proses, dan dimuat ulang hanya kalau
# datanya berubah - ditandai versi_data (dinaikkan setiap penulis data di
# transaksi yang sama: pembaruan lewat .bat/admin dan "Terapkan ke data").
#
# Aman untuk banyak thread (waitress threads=4): korpus baru disiapkan PENUH
# dulu, baru referensi globalnya ditukar (satu penugasan, atomik di CPython).
# Thread yang sedang mencari tetap memakai korpus lamanya sampai selesai;
# objek Korpus tidak pernah diubah setelah dibuat.


class Korpus:
    """Potret baca-saja korpus pencarian. Tidak diubah setelah dibuat."""

    __slots__ = ("versi", "kamus", "entri", "publikasi",
                 "entri_per_domain", "publikasi_per_domain", "detik_muat")

    def __init__(self, versi, kamus, entri, publikasi, detik_muat):
        self.versi = versi
        self.kamus = kamus
        self.entri = entri              # tuple per entri + frozenset token
        self.publikasi = publikasi      # tuple per publikasi + token + judul ternormalisasi
        # Filter wilayah: baris yang sama, dikelompokkan per kode domain
        # dengan urutan aslinya. Pencarian satu wilayah hanya menelusuri
        # baris wilayah itu, dan urutan hasil pada skor sama tetap seperti
        # urutan korpus.
        self.entri_per_domain = _kelompokkan(entri, _KOLOM_DOMAIN_ENTRI)
        self.publikasi_per_domain = _kelompokkan(publikasi, _KOLOM_DOMAIN_PUBLIKASI)
        self.detik_muat = detik_muat


# Posisi kolom domain di baris _ambil_korpus() dan _ambil_publikasi().
_KOLOM_DOMAIN_ENTRI = 11
_KOLOM_DOMAIN_PUBLIKASI = 7


def _kelompokkan(baris, kolom):
    kelompok = {}
    for b in baris:
        kelompok.setdefault(b[kolom], []).append(b)
    return {kode: tuple(isi) for kode, isi in kelompok.items()}


_korpus = None
_kunci_muat = threading.Lock()


def _bangun_korpus(versi, kamus):
    """Ambil seluruh entri dan publikasi dari database, siapkan untuk dicari.

    Urutan baris sama dengan query lama (tanpa ORDER BY, query yang sama),
    sehingga urutan hasil pada skor dan tanggal yang sama ikut sama.
    Token dan judul publikasi ternormalisasi dihitung SEKALI di sini, bukan
    di setiap kueri. Judul dinormalkan dengan kamus yang sama dengan yang
    dipakai kueri (`kamus`); kamus yang diganti lewat halaman admin
    (muat_ulang_kamus) membuat korpus dibangun ulang.
    """
    mulai = time.perf_counter()
    entri = tuple(
        (*baris, frozenset(baris[6].split()) if baris[6] else frozenset())
        for baris in _ambil_korpus())
    publikasi = tuple(
        (*baris,
         frozenset(baris[5].split()) if baris[5] else frozenset(),
         normalisasi(baris[1] or "", kamus))
        for baris in _ambil_publikasi())
    return Korpus(versi, kamus, entri, publikasi, time.perf_counter() - mulai)


def korpus():
    """Korpus yang mutakhir: dimuat ulang kalau versi data atau kamus berubah."""
    global _korpus
    versi = versi_data.baca()
    kamus = kamus_default()
    k = _korpus
    if k is not None and k.versi == versi and k.kamus is kamus:
        return k
    with _kunci_muat:
        k = _korpus     # thread lain mungkin sudah memuatnya selagi menunggu
        if k is not None and k.versi == versi and k.kamus is kamus:
            return k
        k = _bangun_korpus(versi, kamus)
        _korpus = k
        return k


def kata_untuk_sorot(kueri):
    """Kata mentah + hasil normalisasinya, untuk menyorot di hasil pencarian.

    Keduanya diperlukan: petugas mengetik "penghunian" sementara judul memuat
    "Penghunian", tapi kamus juga memetakannya ke "tpk" yang muncul apa adanya
    di sebagian judul. Menyorot dua-duanya membuat alasan kecocokan terlihat.
    """
    mentah = [k for k in re.findall(r"[0-9A-Za-z]+", kueri.lower()) if len(k) > 2]
    ternormalisasi = [t for t in normalisasi_token(kueri) if len(t) > 2]
    return sorted(set(mentah) | set(ternormalisasi), key=len, reverse=True)


def _cari_entri(token_kueri, baris, ambang_saran):
    """Nilai entri di `baris` terhadap kueri. Return (hasil terurut, dinilai)."""
    kumpulan = set(token_kueri)
    hasil = []
    dinilai = 0
    for (eid, tipe, nomor, judul, halaman, halaman_fisik, ternormalisasi,
         pub_id, pub_judul, url_pdf, tanggal_rilis, domain, wilayah,
         token_entri) in baris:
        if not ternormalisasi:
            continue

        # Penyaring murah: entri yang tidak memuat SATU PUN token kueri tidak
        # mungkin melewati ambang, jadi tidak perlu dihitung fuzzy-nya.
        if kumpulan.isdisjoint(token_entri):
            continue

        dinilai += 1
        skor, set_ratio, sort_ratio, coverage = _skor(token_kueri, ternormalisasi)
        if skor < ambang_saran:
            continue

        hasil.append({
            "entri_id": eid,
            "publikasi_id": pub_id,
            "judul_publikasi": pub_judul,
            "tanggal_rilis": tanggal_rilis,
            "url_pdf": url_pdf,
            "domain": domain,
            "wilayah": wilayah,
            "tipe": tipe,
            "nomor": nomor,          # boleh None - entri tipe `isi` tidak bernomor
            "judul": judul,
            "halaman": halaman,      # nomor CETAK dari halaman daftar, boleh None
            "halaman_fisik": halaman_fisik,   # nomor halaman PDF, untuk #page=
            "skor": round(skor, 1),
            "skor_set": round(set_ratio, 1),
            "skor_sort": round(sort_ratio, 1),
            "skor_coverage": round(coverage, 1),
            "panjang_entri": len(ternormalisasi.split()),
        })

    # Skor sama -> edisi terbaru lebih dulu. Judul yang sama memang muncul di
    # beberapa edisi; itu TIDAK digabung, petugas perlu tahu edisi mana.
    hasil.sort(key=lambda h: (-h["skor"], -(h["tanggal_rilis"] or date.min).toordinal()))
    return hasil, dinilai


def cari(kueri, batas=BATAS_HASIL, ambang_saran=AMBANG_SARAN,
         ambang_ditemukan=AMBANG_DITEMUKAN, domain=None, provinsi=False):
    """Cari entri yang relevan dengan kueri petugas.

    Return dict berisi daftar `ditemukan` dan `saran`. Tiap hasil memuat lokasi
    spesifik - publikasi mana DAN bagian mana - plus link PDF-nya.

    Filter wilayah (10 Nov 2026):
      - `domain` = kode domain ("6301"): hanya publikasi dan entri domain itu
        yang dinilai. None = semua wilayah, jalur yang sama persis dengan
        sebelum filter ada.
      - `provinsi=True` (hanya bersama `domain` kab/kota): entri publikasi
        provinsi yang cocok dengan kueri yang sama ikut dikembalikan sebagai
        `provinsi`, dinilai dari korpus yang sama.
    Kueri yang diberikan ke sini sudah TANPA kata wilayah; membuangnya urusan
    pemanggil (app/services/pencarian_wilayah.py).
    """
    mulai = time.perf_counter()
    token_kueri = normalisasi_token(kueri)

    if not token_kueri:
        return {
            "kueri": kueri,
            "kueri_ternormalisasi": "",
            "sorot": [],
            "publikasi": [],
            "ditemukan": [],
            "saran": [],
            "provinsi": [],
            "jumlah_entri": 0,
            "jumlah_dinilai": 0,
            "waktu_ms": (time.perf_counter() - mulai) * 1000,
        }

    # Dua tingkat pencarian menjawab pertanyaan yang berbeda: "publikasi mana"
    # dan "bagian mana di dalamnya". Hasilnya sengaja TIDAK dicampur.
    k = korpus()
    if domain is None:
        baris_publikasi, baris = k.publikasi, k.entri
    else:
        baris_publikasi = k.publikasi_per_domain.get(domain, ())
        baris = k.entri_per_domain.get(domain, ())

    publikasi = _cari_publikasi(token_kueri, ambang_saran, baris_publikasi)[:batas]
    hasil, dinilai = _cari_entri(token_kueri, baris, ambang_saran)

    ditemukan = [h for h in hasil if h["skor"] >= ambang_ditemukan][:batas]
    saran = [h for h in hasil if h["skor"] < ambang_ditemukan][:batas]

    dari_provinsi = []
    if provinsi and domain is not None and domain != DOMAIN_PROVINSI:
        dari_provinsi, _ = _cari_entri(
            token_kueri, k.entri_per_domain.get(DOMAIN_PROVINSI, ()), ambang_saran)
        dari_provinsi = dari_provinsi[:BATAS_PROVINSI]

    return {
        "kueri": kueri,
        "kueri_ternormalisasi": " ".join(token_kueri),
        "sorot": kata_untuk_sorot(kueri),
        "publikasi": publikasi,
        "ditemukan": ditemukan,
        "saran": saran,
        "provinsi": dari_provinsi,
        "jumlah_entri": len(baris),
        "jumlah_dinilai": dinilai,
        "jumlah_publikasi": len(publikasi),
        "waktu_ms": (time.perf_counter() - mulai) * 1000,
    }


def publikasi_wilayah(domain):
    """Semua publikasi satu wilayah, terbaru dulu, untuk kueri yang hanya
    berisi nama wilayah ("tanah laut"). Tanpa skor: tidak ada topik yang
    bisa dinilai, jadi urutannya hanya tanggal rilis."""
    k = korpus()
    hasil = [{
        "publikasi_id": pid, "judul": judul, "abstrak": abstrak,
        "tanggal_rilis": tanggal_rilis, "url_pdf": url_pdf,
        "jumlah_entri": jumlah_entri, "domain": kode, "wilayah": wilayah,
        "skor": None,
    } for (pid, judul, abstrak, tanggal_rilis, url_pdf, _, jumlah_entri,
           kode, wilayah, _, _) in k.publikasi_per_domain.get(domain, ())]
    hasil.sort(key=lambda h: (-(h["tanggal_rilis"] or date.min).toordinal(), h["judul"]))
    return hasil
