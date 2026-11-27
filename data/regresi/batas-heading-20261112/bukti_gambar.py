"""Lembar bukti sampel entri gambar BARU (aturan heading baru), dibaca manual.

Per entri: (1) potongan BARIS DAFTAR GAMBAR aslinya - baris yang diawali nomor
entri dan judulnya cocok, dicari di halaman heading s.d. 12 halaman sesudahnya;
(2) 45% atas halaman_fisik-nya; (3) hasil parser. Skor kecocokan dicetak.
Pemakaian: bukti_gambar.py <kering.json> <n> <seed> <dir_keluar>
"""
import json
import os
import random
import sys

sys.path.insert(0, os.getcwd())
import pdfplumber  # noqa: E402
import pypdfium2 as pdfium  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from rapidfuzz import fuzz  # noqa: E402

from app.services import ekstraksi_pdf as ep  # noqa: E402

S = 1.4


def main():
    hasil = json.load(open(sys.argv[1], encoding="utf-8"))
    n, seed, keluar = int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    os.makedirs(keluar, exist_ok=True)
    ukur = {x["pid"]: x for x in json.load(open("data/regresi/batas-heading-20261110/batas-heading.json", encoding="utf-8"))}
    calon = [(x["pid"], x["domain"], e) for x in hasil for e in x["entri_tambah"]
             if e["tipe"] == "gambar" and e.get("nomor")]
    sampel = random.Random(seed).sample(calon, n)
    catatan = []
    for urut, (pid, domain, e) in enumerate(sampel, 1):
        path = f"data/publikasi_pdf/{domain}/{pid}.pdf"
        awal = next(t["halaman_heading"] for t in ukur[pid]["terlewat"] if t["tipe"] == "gambar")
        jarum = (e["judul"] or "")[:35].lower()
        terbaik = (0, None, None)
        with pdfplumber.open(path) as pdf:
            for p in range(awal, min(awal + 12, len(pdf.pages)) + 1):
                bs = ep._kelompokkan_baris(ep._kata_halaman(pdf.pages[p - 1]))
                ts = [ep._teks_baris(x).strip() for x in bs]
                for j, (b, t) in enumerate(zip(bs, ts)):
                    if not t.split() or t.split()[0].rstrip(".") != e["nomor"].rstrip("."):
                        continue
                    # Nomor bisa berdiri sendiri di kolom kiri, sejajar tengah di
                    # antara dua baris judul: cocokkan dengan baris itu + baris
                    # di atas dan di bawahnya (kesalahan alat putaran pertama).
                    sisa = " ".join([" ".join(t.split()[1:])] + ts[max(0, j - 1):j] + ts[j + 1:j + 2]).lower()
                    skor = fuzz.partial_ratio(jarum, sisa) if len(sisa) >= len(jarum) else fuzz.ratio(jarum, sisa)
                    if skor > terbaik[0]:
                        terbaik = (skor, p, bs[max(0, j - 1)][0]["top"])
        doc = pdfium.PdfDocument(path)
        potongan = []
        skor, p, top = terbaik
        if p:
            img = doc[p - 1].render(scale=S).to_pil().convert("RGB")
            potongan.append((f"Daftar hal.{p} (cocok {skor:.0f})",
                             img.crop((0, max(0, int((top - 14) * S)), img.width, int((top + 56) * S)))))
        if e.get("halaman_fisik"):
            img = doc[e["halaman_fisik"] - 1].render(scale=S * 0.62).to_pil().convert("RGB")
            potongan.append((f"halaman_fisik {e['halaman_fisik']} (penuh)", img))
        teks = (f"#{urut} {pid[:8]} [gambar {e['nomor']}] hal={e.get('halaman')} fisik={e.get('halaman_fisik')}\n"
                f"{(e['judul'] or '')[:200]}")
        lebar = max([im.width for _, im in potongan] + [900])
        tinggi = sum(im.height + 16 for _, im in potongan) + 60
        k = Image.new("RGB", (lebar, tinggi), "white")
        d = ImageDraw.Draw(k)
        y = 0
        for label, im in potongan:
            d.text((4, y), label, fill="red"); y += 14
            k.paste(im, (0, y)); y += im.height + 2
        d.rectangle((0, y, lebar, tinggi), fill=(255, 245, 200))
        d.multiline_text((6, y + 4), teks, fill="black")
        k.save(os.path.join(keluar, f"gambar-{urut:02d}.png"))
        catatan.append({"urut": urut, "pid": pid, **{x: e.get(x) for x in ("nomor", "judul", "halaman", "halaman_fisik")},
                        "daftar_hal": p, "skor_cocok": skor})
    json.dump(catatan, open(os.path.join(keluar, "sampel.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print([(c["urut"], c["daftar_hal"], c["skor_cocok"]) for c in catatan])


if __name__ == "__main__":
    main()
