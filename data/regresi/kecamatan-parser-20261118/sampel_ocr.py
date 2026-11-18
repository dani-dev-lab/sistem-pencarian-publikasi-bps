"""Sampel acak entri publikasi OCR kecamatan + gambar bukti (PDF tanpa teks, jadi bukti = render halaman).
  python sampel_ocr.py <potret.json> <folder_gambar> [n] [seed]
Per entri satu PNG: (atas) potongan baris Daftar tempat nomor entri terbaca di cache OCR,
(bawah) 40% atas halaman yang dituju tombol PDF. Bukti dibaca dari GAMBAR, bukan dari teks OCR."""
import glob, json, os, random, sys
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.stdout.reconfigure(encoding="utf-8")
import pypdfium2 as pdfium
from PIL import Image
potret = json.load(open(sys.argv[1], encoding="utf-8")); keluar = sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 10; seed = int(sys.argv[4]) if len(sys.argv) > 4 else 20261118
target = [l.split()[0] for l in open("data/ocr_target_kecamatan.txt", encoding="utf-8") if l.strip() and not l.startswith("#")]
populasi = [(p, e) for p in target for e in potret.get(p, [])]
print(f"populasi {len(populasi)} entri di {len(target)} publikasi OCR; seed {seed}")
SK = 2.0
for k, (p, e) in enumerate(random.Random(seed).sample(populasi, n), 1):
    f = glob.glob(f"data/publikasi_pdf/*/{p}.pdf")[0]; dom = f.split(os.sep)[-2] if os.sep in f else f.split("/")[-2]
    doc = pdfium.PdfDocument(f); potong = []
    if e["nomor"]:
        for h in range(1, 31):
            c = glob.glob(f"data/ocr_cache/*/{p}/{h:04d}-easyocr.json")
            if not c or h == e["halaman_fisik"]: continue
            kata = json.load(open(c[0], encoding="utf-8"))["kata"]
            hit = [w for w in kata if w["text"].strip(".") == e["nomor"] and w["x0"] < 150]
            if hit:
                img = doc[h - 1].render(scale=SK).to_pil()
                y = hit[0]["top"]; potong.append(img.crop((0, max(0, (y - 12) * SK), img.width, (y + 40) * SK)))
                break
    if e["halaman_fisik"]:
        img = doc[int(e["halaman_fisik"]) - 1].render(scale=SK).to_pil()
        potong.append(img.crop((0, 0, img.width, int(img.height * 0.4))))
        bawah = img.crop((0, int(img.height * 0.93), img.width, img.height)); potong.append(bawah)
    doc.close()
    if potong:
        w = max(i.width for i in potong); gb = Image.new("RGB", (w, sum(i.height for i in potong) + 8 * len(potong)), "white")
        y = 0
        for i in potong:
            gb.paste(i, (0, y)); y += i.height + 8
        gb.thumbnail((900, 2000)); gb.save(os.path.join(keluar, f"{k:02d}.png"))
    print(f"#{k} [{p[:8]}] {e['tipe']} {e['nomor']} | hal {e['halaman']} | fisik {e['halaman_fisik']}"
          f"{' (perkiraan)' if e['halaman_fisik_perkiraan'] else ''} | {e['sumber']} | {e['judul'][:150]}")
