"""Nilai keluaran OCR terhadap acuan yang dibaca manual (acuan.json).

Per butir acuan:
  kemiripan  : kemiripan karakter (Levenshtein ternormalisasi) antara teks acuan
               dan potongan teks OCR yang paling cocok (penjajaran fuzzy)
  kata       : persen kata acuan yang ada di sekitar potongan itu (urutan bebas)
  nomor_ok   : nomor ada sebagai token utuh di baris potongan itu atau baris
               tepat sebelum/sesudahnya (syarat parser memasangkan nomor-judul)
  hal_ok     : halaman ada sebagai token utuh di baris potongan s.d. 3 baris
               sesudahnya
Pemakaian: python nilai_ocr.py <dir_hasil> <acuan.json> <keluaran.json>
"""
import json
import re
import sys
from collections import Counter

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

GANTI = {"–": "-", "—": "-", "−": "-", "‘": "'", "’": "'",
         "“": '"', "”": '"', "…": "..."}


def norm(s):
    for a, b in GANTI.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s.lower()).strip()


def kata(s):
    return re.findall(r"[0-9a-z]+", norm(s))


def ratakan(teks):
    """Teks OCR -> satu string + indeks baris tiap karakter."""
    datar, baris_ke = [], []
    for i, b in enumerate(l for l in teks.splitlines() if l.strip()):
        b = norm(b) + " "
        datar.append(b)
        baris_ke.extend([i] * len(b))
    return "".join(datar), baris_ke, [norm(l) for l in teks.splitlines() if l.strip()]


def ada_token(token, baris):
    t = re.escape(norm(token).rstrip("."))
    return any(re.search(rf"(?<![0-9a-z.]){t}\.?(?![0-9a-z])", b) for b in baris)


def nilai_butir(b, datar, baris_ke, baris):
    gt = norm(b["teks"])
    al = fuzz.partial_ratio_alignment(gt, datar)
    potong = datar[al.dest_start:al.dest_end]
    kemiripan = Levenshtein.normalized_similarity(gt, potong) * 100 if potong else 0.0
    lebar = int(len(gt) * 0.3)
    sekitar = Counter(kata(datar[max(0, al.dest_start - lebar):al.dest_end + lebar]))
    k = Counter(kata(gt))
    kata_ok = sum(min(n, sekitar[w]) for w, n in k.items()) / max(1, sum(k.values())) * 100
    l0 = baris_ke[min(al.dest_start, len(baris_ke) - 1)] if baris_ke else 0
    l1 = baris_ke[min(max(al.dest_end - 1, 0), len(baris_ke) - 1)] if baris_ke else 0
    # Tanpa urutan: kata/nomor/halaman terbaca benar DI MANA PUN di halaman.
    # Ukuran ini yang relevan kalau OCR dipasang ke parser berbasis koordinat
    # kata (posisi diambil dari kotak kata, bukan dari urutan teks polos).
    semua = Counter(kata(datar))
    kata_hal = sum(min(n, semua[w]) for w, n in k.items()) / max(1, sum(k.values())) * 100
    hasil = {"kemiripan": round(kemiripan, 1), "kata": round(kata_ok, 1), "kata_hal": round(kata_hal, 1)}
    if b.get("nomor"):
        hasil["nomor_ok"] = ada_token(b["nomor"], baris[max(0, l0 - 1):l1 + 2])
        hasil["nomor_ada"] = ada_token(b["nomor"], baris)
    if b.get("hal"):
        hasil["hal_ok"] = ada_token(b["hal"], baris[l0:l1 + 4])
        hasil["hal_ada"] = ada_token(b["hal"], baris)
    return hasil


def main():
    d, acuan, keluar = sys.argv[1], json.load(open(sys.argv[2], encoding="utf-8")), sys.argv[3]
    semua = {}
    for hal, butir in acuan.items():
        if hal.startswith("_"):
            continue
        for mesin in ("tess", "easy"):
            datar, baris_ke, baris = ratakan(open(f"{d}/{hal}.{mesin}.txt", encoding="utf-8").read())
            for i, b in enumerate(butir):
                semua.setdefault(f"{hal}#{i}", {"halaman": hal, **b})[mesin] = nilai_butir(b, datar, baris_ke, baris)
    json.dump(semua, open(keluar, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def ringkas(butir, label):
        n = len(butir)
        if not n:
            return
        out = [f"{label:28} n={n:3}"]
        for m in ("tess", "easy"):
            km = sum(x[m]["kemiripan"] for x in butir) / n
            kt = sum(x[m]["kata"] for x in butir) / n
            g90 = sum(x[m]["kemiripan"] >= 90 for x in butir)
            kh = sum(x[m]["kata_hal"] for x in butir) / n
            nom = [x[m]["nomor_ok"] for x in butir if "nomor_ok" in x[m]]
            noma = [x[m]["nomor_ada"] for x in butir if "nomor_ada" in x[m]]
            hl = [x[m]["hal_ok"] for x in butir if "hal_ok" in x[m]]
            hla = [x[m]["hal_ada"] for x in butir if "hal_ada" in x[m]]
            out.append(f"{m}: mirip {km:5.1f} kata-hal {kh:5.1f} >=90:{g90:2}/{n}"
                       + (f" nomor dekat {sum(nom)}/{len(nom)} ada {sum(noma)}/{len(noma)}" if nom else "")
                       + (f" hal dekat {sum(hl)}/{len(hl)} ada {sum(hla)}/{len(hla)}" if hl else ""))
        print(" | ".join(out))

    nilai = list(semua.values())
    ringkas(nilai, "SEMUA")
    for j in ("entri", "keterangan", "judul", "sel", "prosa"):
        ringkas([x for x in nilai if x["jenis"] == j], f"jenis {j}")
    for hal in dict.fromkeys(x["halaman"] for x in nilai):
        ringkas([x for x in nilai if x["halaman"] == hal], f"halaman {hal}")
    ringkas([x for x in nilai if x["halaman"].startswith("aafda0cf")], "HST Dalam Angka 2026")


if __name__ == "__main__":
    main()
