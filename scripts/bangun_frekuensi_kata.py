"""Analisis frekuensi kata korpus untuk menyusun kamus sinonim.

Korpus diambil dari database: judul entri_dokumen + judul & abstrak publikasi.

Tiga keluaran:
  1. Akronim otomatis dari pola "Frasa Lengkap (AKRONIM)" - satu-satunya bagian
     yang bisa otomatis penuh, langsung jadi pasangan sinonim.
  2. Frekuensi unigram dan bigram setelah stemming Sastrawi. Kata sambung
     SENGAJA tidak dibuang: "menurut", "berdasarkan", "per" justru kandidat
     sinonim satu sama lain.
  3. Istilah Inggris yang sering muncul, dilaporkan terpisah - korpus memuat
     judul dwibahasa yang sengaja dipertahankan.

Jalankan:  venv/Scripts/python.exe scripts/bangun_frekuensi_kata.py
Output  :  data/frekuensi_kata.json
"""

import json
import os
import re
import sys
from collections import Counter
from itertools import pairwise

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Sastrawi.Stemmer.StemmerFactory import StemmerFactory

from app import create_app
from app.models import EntriDokumen, Publikasi

FILE_HASIL = "data/frekuensi_kata.json"

TOP_UNIGRAM = 100
TOP_BIGRAM = 50

# Akronim dalam kurung: 2-10 huruf kapital, boleh berangka ("IHK", "PDRB", "TPK").
RE_AKRONIM = re.compile(r"\(([A-Z][A-Z0-9]{1,9})\)")

# Kata sambung yang biasanya dilewati saat membentuk akronim.
SAMBUNG = {"dan", "di", "ke", "yang", "per", "untuk", "pada", "dengan",
           "atas", "dari", "the", "of", "and", "in", "by"}

# Penanda baris berbahasa Inggris. Dipakai untuk MEMISAHKAN korpus, bukan untuk
# membuang - petugas bisa saja mencari dengan istilah Inggris.
PENANDA_INGGRIS = {"of", "the", "and", "by", "in", "for", "with", "to", "from",
                   "number", "total", "according", "based", "province"}

RE_TOKEN = re.compile(r"[a-z]+(?:-[a-z]+)*")


class Stemmer:
    """Pembungkus Sastrawi dengan cache.

    Korpus punya puluhan ribu token tapi kosakata uniknya jauh lebih kecil,
    jadi cache menghemat sebagian besar pemanggilan.
    """

    def __init__(self):
        self._stemmer = StemmerFactory().create_stemmer()
        self._cache = {}
        self.panggilan = 0
        self.lolos_cache = 0

    def stem(self, kata):
        self.panggilan += 1
        if kata in self._cache:
            self.lolos_cache += 1
            return self._cache[kata]
        hasil = self._stemmer.stem(kata)
        self._cache[kata] = hasil
        return hasil


def _inisial(frasa):
    """Huruf awal kata isi (kata sambung dilewati)."""
    isi = [w for w in frasa if w.lower() not in SAMBUNG]
    return "".join(w[0] for w in isi if w[:1].isalpha()).upper()


def _suburutan_pas(akronim, inisial):
    """Apakah `akronim` suburutan dari `inisial`, dengan ujung-ujung terkunci?

    Sebagian akronim BPS melewati kata: "Rata-Rata Lama Tamu Menginap (RLM)"
    -> inisialnya RLTM, "Tamu" tidak diwakili. Pencocokan longgar tetap
    mengunci huruf pertama dan terakhir supaya tidak asal cocok.
    """
    if len(akronim) < 2 or len(inisial) <= len(akronim):
        return False
    if akronim[0] != inisial[0] or akronim[-1] != inisial[-1]:
        return False
    i = 0
    for huruf in inisial:
        if i < len(akronim) and huruf == akronim[i]:
            i += 1
    return i == len(akronim)


def cari_akronim(teks):
    """Temukan pasangan (frasa lengkap, akronim) dari pola 'Frasa (AKRONIM)'.

    Panjang frasa tidak ditebak dari jumlah huruf saja - dicoba beberapa
    panjang, lalu dipilih yang inisial kata isinya cocok. Cocok persis
    diutamakan; kalau tidak ada, dicoba pencocokan suburutan.
    """
    hasil = []
    for m in RE_AKRONIM.finditer(teks):
        akronim = m.group(1)
        sebelum = re.sub(r"[^\w\s-]", " ", teks[:m.start()]).split()
        if not sebelum:
            continue

        cadangan = None
        ketemu = False
        for n in range(len(akronim), len(akronim) + 4):
            if n > len(sebelum):
                break
            frasa = sebelum[-n:]
            inisial = _inisial(frasa)
            if inisial == akronim:
                hasil.append((" ".join(frasa), akronim))
                ketemu = True
                break
            if cadangan is None and _suburutan_pas(akronim, inisial):
                cadangan = frasa

        if not ketemu and cadangan:
            hasil.append((" ".join(cadangan), akronim))
    return hasil


def tokenkan(teks):
    return RE_TOKEN.findall(teks.lower())


def baris_inggris(teks):
    """Baris dianggap Inggris kalau memuat minimal 2 kata penanda."""
    token = set(tokenkan(teks))
    return len(token & PENANDA_INGGRIS) >= 2


def main():
    app = create_app()
    with app.app_context():
        judul_entri = [j for (j,) in EntriDokumen.query.with_entities(
            EntriDokumen.judul).all() if j]
        judul_pub = [j for (j,) in Publikasi.query.with_entities(
            Publikasi.judul).all() if j]
        abstrak = [a for (a,) in Publikasi.query.with_entities(
            Publikasi.abstrak).all() if a]

    korpus = judul_entri + judul_pub + abstrak
    print(f"Korpus: {len(judul_entri)} judul entri + {len(judul_pub)} judul "
          f"publikasi + {len(abstrak)} abstrak = {len(korpus)} baris")

    # ---------------------------- 1. Akronim ----------------------------
    pasangan = Counter()
    for teks in korpus:
        for frasa, akr in cari_akronim(teks):
            pasangan[(frasa.lower(), akr)] += 1

    # Satu akronim bisa punya beberapa variasi penulisan frasa; ambil yang
    # paling sering muncul sebagai bentuk kanonik.
    per_akronim = {}
    for (frasa, akr), n in pasangan.most_common():
        per_akronim.setdefault(akr, []).append({"frasa": frasa, "jumlah": n})

    # ------------------- 2. Frekuensi unigram + bigram -------------------
    stemmer = Stemmer()
    unigram = Counter()
    bigram = Counter()
    korpus_id, korpus_en = [], []

    for teks in korpus:
        (korpus_en if baris_inggris(teks) else korpus_id).append(teks)
        token = [stemmer.stem(t) for t in tokenkan(teks)]
        unigram.update(token)
        bigram.update(" ".join(p) for p in pairwise(token))

    # -------------------- 3. Istilah Inggris terpisah --------------------
    unigram_en = Counter()
    for teks in korpus_en:
        unigram_en.update(tokenkan(teks))   # tanpa stemming, ini bukan Indonesia

    # ------------------------------ Cetak ------------------------------
    print(f"Token diproses: {stemmer.panggilan} "
          f"({stemmer.lolos_cache} dilayani cache, "
          f"{len(stemmer._cache)} kata unik)")

    print()
    print("=" * 74)
    print(f"AKRONIM DITEMUKAN ({len(per_akronim)})")
    print("=" * 74)
    for akr in sorted(per_akronim):
        for v in per_akronim[akr][:2]:
            print(f"  {akr:<8} = {v['frasa'][:58]:<58} ({v['jumlah']}x)")

    print()
    print("=" * 74)
    print(f"TOP {TOP_UNIGRAM} UNIGRAM (setelah stemming)")
    print("=" * 74)
    for i, (kata, n) in enumerate(unigram.most_common(TOP_UNIGRAM), 1):
        print(f"  {i:>3}. {kata:<24} {n:>6}", end="\n" if i % 2 == 0 else "")
    if TOP_UNIGRAM % 2:
        print()

    print()
    print("=" * 74)
    print(f"TOP {TOP_BIGRAM} BIGRAM")
    print("=" * 74)
    for i, (frasa, n) in enumerate(bigram.most_common(TOP_BIGRAM), 1):
        print(f"  {i:>3}. {frasa:<40} {n:>6}")

    print()
    print("=" * 74)
    print(f"ISTILAH INGGRIS ({len(korpus_en)} baris dwibahasa terdeteksi)")
    print("=" * 74)
    if not korpus_en:
        print("  tidak ada")
    for kata, n in unigram_en.most_common(30):
        print(f"  {kata:<24} {n:>6}")

    # ------------------------------ Simpan ------------------------------
    keluaran = {
        "ukuran_korpus": {
            "judul_entri": len(judul_entri),
            "judul_publikasi": len(judul_pub),
            "abstrak": len(abstrak),
            "baris_dwibahasa": len(korpus_en),
        },
        "akronim": {
            akr: v for akr, v in sorted(per_akronim.items())
        },
        "unigram": [{"kata": k, "jumlah": n}
                    for k, n in unigram.most_common(500)],
        "bigram": [{"frasa": k, "jumlah": n}
                   for k, n in bigram.most_common(200)],
        "istilah_inggris": [{"kata": k, "jumlah": n}
                            for k, n in unigram_en.most_common(100)],
    }
    with open(FILE_HASIL, "w", encoding="utf-8") as f:
        json.dump(keluaran, f, ensure_ascii=False, indent=2)
    print()
    print(f"Hasil -> {FILE_HASIL}")


if __name__ == "__main__":
    main()
