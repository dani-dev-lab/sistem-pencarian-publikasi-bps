"""Gabungkan layar-sebelum/ dan layar-sesudah/ menjadi pasangan berdampingan
(kiri = sebelum, kanan = sesudah), dipotong ke bagian atas halaman, JPEG.
Hasil di layar-banding/ (yang di-commit; PNG penuh di-gitignore).

  venv/Scripts/python.exe gabung_banding.py [SEBELUM SESUDAH KELUAR LABEL_SEBELUM]

Tanpa argumen: layar-sebelum (HEAD 70887dd) vs layar-v1 -> layar-banding.
Revisi 25 Nov sore: layar-v1 layar-v2 layar-banding-v2 "SEBELUM (v1, menu di kop)".
"""
import os
import sys

from PIL import Image, ImageDraw

D = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) > 4:
    A, B, K, LABEL = (f"{D}/{sys.argv[1]}", f"{D}/{sys.argv[2]}", f"{D}/{sys.argv[3]}", sys.argv[4])
else:
    A, B, K, LABEL = f"{D}/layar-sebelum", f"{D}/layar-v1", f"{D}/layar-banding", "SEBELUM (HEAD 70887dd)"
os.makedirs(K, exist_ok=True)
n = 0
for nama in sorted(os.listdir(B)):
    if not nama.endswith(".png") or not os.path.exists(f"{A}/{nama}"):
        continue
    x, y = Image.open(f"{A}/{nama}").convert("RGB"), Image.open(f"{B}/{nama}").convert("RGB")
    batas = 1500 if nama.startswith("1280") else 2200
    x, y = x.crop((0, 0, x.width, min(x.height, batas))), y.crop((0, 0, y.width, min(y.height, batas)))
    jarak, judul = 24, 28
    c = Image.new("RGB", (x.width + y.width + jarak, max(x.height, y.height) + judul), "white")
    c.paste(x, (0, judul))
    c.paste(y, (x.width + jarak, judul))
    g = ImageDraw.Draw(c)
    g.text((8, 6), LABEL, fill=(160, 0, 0))
    g.text((x.width + jarak + 8, 6), "SESUDAH", fill=(0, 110, 0))
    g.line([(x.width + jarak // 2, 0), (x.width + jarak // 2, c.height)], fill=(200, 200, 200), width=2)
    if nama.startswith("1280"):
        c = c.resize((c.width * 2 // 3, c.height * 2 // 3))
    c.save(f"{K}/{nama[:-4]}.jpg", quality=80)
    n += 1
print(n, "pasangan ->", K)
