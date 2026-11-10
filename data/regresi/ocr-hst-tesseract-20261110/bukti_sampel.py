"""Lembar bukti sampel acak entri hasil parser-OCR, untuk dibaca manual.

Jalankan dengan venv PROYEK dari folder proyek:
  venv/Scripts/python.exe C:/Users/Dani/alat-ocr/bukti_sampel.py <hasil_parser.json> <mesin> <n> <seed> <dir_keluar>

Per entri: cari baris di halaman OCR yang paling mirip dengan judul entri
(di SEMUA halaman), potong pita gambar di sekitar baris itu dari render PDF
asli (bukan teks OCR), lalu tulis hasil parser di bawahnya. Skor kemiripan
pencarian dicetak, supaya potongan yang salah tempat langsung terlihat.
Juga dicetak halaman fisik entri (kalau ada) sebagai potongan kedua.
"""
import json
import os
import random
import sys

import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from rapidfuzz import fuzz

DPI = 110
S = DPI / 72


import re
RE_SAMPAH = re.compile(r"^[a-z.,]{8,}$")


def judul_bersih(judul):
    """Bagian judul sesudah token sampah titik pemandu TERAKHIR. Judul yang
    diawali ekor entri sebelumnya + sampah tidak boleh dicari dengan
    awalannya: sampah cocok dengan sampah di baris lain (kesalahan alat yang
    terjadi pada putaran pertama)."""
    token = judul.split()
    akhir = max((i for i, t in enumerate(token)
                 if RE_SAMPAH.match(t) and sum(c in "aesuvcnorw.," for c in t) / len(t) > .8), default=-1)
    return " ".join(token[akhir + 1:]) or judul


def baris_ocr(data):
    per = {}
    for k in data["kata"]:
        per.setdefault(tuple(k["baris"]), []).append(k)
    out = []
    for ks in per.values():
        ks.sort(key=lambda k: k["x0"])
        out.append((" ".join(k["text"] for k in ks), min(k["top"] for k in ks), max(k["bottom"] for k in ks)))
    return out


def main():
    hasil = json.load(open(sys.argv[1], encoding="utf-8"))
    mesin, n, seed, keluar = sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    os.makedirs(keluar, exist_ok=True)
    path = hasil["ringkasan"]["pdf"]
    domain = os.path.basename(os.path.dirname(path)); pid = os.path.splitext(os.path.basename(path))[0]
    cache = os.path.join("data", "ocr_cache", domain, pid)
    halaman = {}
    for f in sorted(os.listdir(cache)):
        if f.endswith(f"-{mesin}.json"):
            halaman[int(f[:4])] = baris_ocr(json.load(open(os.path.join(cache, f), encoding="utf-8")))
    pdf = pdfium.PdfDocument(path)
    entri = hasil["entri"]
    sampel = random.Random(seed).sample(range(len(entri)), min(n, len(entri)))
    catatan = []
    for urut, i in enumerate(sampel, 1):
        e = entri[i]
        judul = judul_bersih(e["judul"] or "")
        # pita sumber: halaman Daftar untuk sumber daftar/keduanya, halaman fisik untuk badan
        # partial_ratio mencocokkan string yang LEBIH PENDEK di dalam yang lebih
        # panjang. Jarum = 40 karakter pertama judul bersih, dan hanya baris
        # OCR yang minimal sepanjang itu yang dibandingkan - kalau tidak, baris
        # pendek ("Sungai Tengah, 2025") cocok 100 di mana-mana (kesalahan alat
        # putaran kedua).
        jarum = judul[:40].lower()
        terbaik = max(((fuzz.partial_ratio(jarum, t.lower()), p, top, bot)
                       for p, bs in halaman.items() for t, top, bot in bs
                       if len(t) >= len(jarum) and
                       ((e.get("sumber") == "badan" and p == e.get("halaman_fisik"))
                       or (e.get("sumber") != "badan" and 9 <= p <= 31))), default=(0, None, 0, 0))
        skor, p, top, bot = terbaik
        potongan = []
        if p:
            img = pdf[p - 1].render(scale=S).to_pil()
            potongan.append((f"hal.{p} (cocok {skor:.0f})", img.crop((0, max(0, int((top - 30) * S)), img.width, int((bot + 62) * S)))))
        if e.get("halaman_fisik") and e.get("halaman_fisik") != p:
            img = pdf[e["halaman_fisik"] - 1].render(scale=S).to_pil()
            potongan.append((f"halaman_fisik {e['halaman_fisik']}", img.crop((0, 0, img.width, int(img.height * 0.42)))))
        teks = f"#{urut} [{e['tipe']} {e.get('nomor')}] hal={e.get('halaman')} fisik={e.get('halaman_fisik')} sumber={e.get('sumber')}\n{(e['judul'] or '')[:190]}"
        lebar = max([im.width for _, im in potongan] + [900])
        tinggi = sum(im.height + 16 for _, im in potongan) + 70
        kanvas = Image.new("RGB", (lebar, tinggi), "white")
        d = ImageDraw.Draw(kanvas); y = 0
        for label, im in potongan:
            d.text((4, y), label, fill="red"); y += 14
            kanvas.paste(im, (0, y)); y += im.height + 2
        d.rectangle((0, y, lebar, tinggi), fill=(255, 245, 200))
        d.multiline_text((6, y + 6), teks, fill="black")
        kanvas.save(os.path.join(keluar, f"sampel-{urut:02d}.png"))
        catatan.append({"urut": urut, "indeks": i, **{k: e.get(k) for k in ("tipe", "nomor", "judul", "halaman", "halaman_fisik", "sumber")},
                        "pita_halaman": p, "skor_cocok": skor})
    json.dump(catatan, open(os.path.join(keluar, "sampel.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(catatan), "sampel ->", keluar)


if __name__ == "__main__":
    main()
