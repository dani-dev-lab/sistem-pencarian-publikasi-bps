"""Sampel manual 30 entri hasil OCR + potongan render PDF sebagai bukti.

  python sampel_ocr.py <bertambah.tsv> <folder_keluaran>

Pool: entri yang BERTAMBAH sesudah OCR (untuk 5 publikasi 0-entri = semua
entrinya). Komposisi: 2 per publikasi + 14 acak dari sisa pool, seed 20261113.

Bukti = render halaman PDF ASLI (pypdfium2), bukan teks OCR. Teks OCR hanya
dipakai untuk MENCARI baris mana yang dipotong:
  - D (daftar): halaman OCR dengan kecocokan token judul terbanyak + nomor;
    dipotong selebar halaman di sekitar baris itu (nomor halaman ikut terlihat).
  - F (fisik):  halaman_fisik; dipotong di sekitar baris yang memuat nomor,
    atau seluruh halaman beresolusi rendah kalau barisnya tidak ditemukan.
"""
import csv
import glob
import json
import os
import random
import re
import sys

sys.path.insert(0, "C:/sistem-pencarian-bps")
import pypdfium2 as pdfium  # noqa: E402

pool_path, keluar = sys.argv[1], sys.argv[2]
os.makedirs(keluar, exist_ok=True)
pool = list(csv.DictReader(open(pool_path, encoding="utf-8"), delimiter="\t"))
rng = random.Random(20261113)
per_pub = {}
for r in pool:
    per_pub.setdefault(r["pub_id"], []).append(r)
pilih = []
for pid in sorted(per_pub):
    pilih += rng.sample(per_pub[pid], min(2, len(per_pub[pid])))
sisa = [r for r in pool if r not in pilih]
pilih += rng.sample(sisa, 30 - len(pilih))


def token(s):
    return [t for t in re.findall(r"[a-z0-9]+", s.lower()) if len(t) > 2]


def halaman_ocr(pid):
    d = glob.glob(f"C:/sistem-pencarian-bps/data/ocr_cache/*/{pid}")[0]
    hasil = {}
    for f in glob.glob(d + "/*-easyocr.json"):
        n = int(os.path.basename(f)[:4])
        hasil[n] = json.load(open(f, encoding="utf-8"))
    return hasil


def potong(pdf, n_hal, top, bottom, nama, dpi=150, pad=28):
    hal = pdf[n_hal - 1]
    lebar, tinggi = hal.get_size()
    skala = dpi / 72
    img = hal.render(scale=skala).to_pil()
    if top is None:
        img = hal.render(scale=90 / 72).to_pil()
    else:
        img = img.crop((0, max(0, (top - pad) * skala), lebar * skala, min(tinggi, bottom + pad) * skala))
    img.save(nama)


cache = {}
ringkas = []
for i, r in enumerate(pilih, 1):
    pid = r["pub_id"]
    cache.setdefault(pid, halaman_ocr(pid))
    pdf = pdfium.PdfDocument(glob.glob(f"C:/sistem-pencarian-bps/data/publikasi_pdf/*/{pid}.pdf")[0])
    tj = token(r["judul"])[:8]
    bukti = []
    if r["sumber"] in ("daftar", "keduanya"):
        terbaik = None
        for n, data in cache[pid].items():
            teks = " ".join(k["text"] for k in data["kata"]).lower()
            skor = sum(t in teks for t in tj) + (3 if r["nomor"] and r["nomor"] in teks else 0) \
                + (2 if "daftar" in teks else 0)
            if not terbaik or skor > terbaik[0]:
                terbaik = (skor, n)
        n = terbaik[1]
        kata = cache[pid][n]["kata"]
        # baris: kata yang memuat token judul pertama (atau nomor)
        cocok = [k for k in kata if tj and tj[0] in k["text"].lower()] or \
                [k for k in kata if r["nomor"] and r["nomor"] in k["text"]]
        if cocok:
            top = min(k["top"] for k in cocok[:1]); bottom = max(k["bottom"] for k in cocok[:1]) + 20
        else:
            top = bottom = None
        f = os.path.join(keluar, f"{i:02d}-D-hal{n}.png")
        potong(pdf, n, top, bottom, f)
        bukti.append(f"D hal.fisik {n}")
    if r["halaman_fisik"]:
        n = int(r["halaman_fisik"])
        kata = cache[pid].get(n, {}).get("kata", [])
        cocok = [k for k in kata if r["nomor"] and re.search(rf"(?<![\d.]){re.escape(r['nomor'])}(?![\d])", k["text"])]
        top = cocok[0]["top"] if cocok else None
        bottom = (cocok[0]["bottom"] + 30) if cocok else None
        f = os.path.join(keluar, f"{i:02d}-F-hal{n}.png")
        potong(pdf, n, top, bottom, f, pad=40)
        bukti.append(f"F hal.fisik {n}{'' if cocok else ' (halaman penuh)'}")
    pdf.close()
    ringkas.append({"no": i, **{k: r[k] for k in ("publikasi", "tipe", "nomor", "judul", "halaman",
                                                  "halaman_fisik", "sumber")}, "bukti": bukti})
    print(f"{i:02d} {r['publikasi'][:22]:<22} {r['tipe']:<8} {r['nomor']:<7} hal {r['halaman']:<4} "
          f"fis {r['halaman_fisik']:<4} {r['sumber']:<8} {r['judul'][:70]}  | {'; '.join(bukti)}")
json.dump(ringkas, open(os.path.join(keluar, "sampel.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
