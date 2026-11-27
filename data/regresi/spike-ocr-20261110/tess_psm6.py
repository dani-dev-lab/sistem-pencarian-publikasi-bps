import glob, os, sys, time, json
import pytesseract
from PIL import Image
D = os.path.dirname(os.path.abspath(__file__))
pytesseract.pytesseract.tesseract_cmd = os.path.join(D, "tesseract", "tesseract.exe")
os.environ["TESSDATA_PREFIX"] = os.path.join(D, "tesseract", "tessdata")
waktu = {}
for f in sorted(glob.glob(os.path.join(D, "hasil", "*-p*.png"))):
    nama = os.path.basename(f)[:-4]
    if nama.startswith(("baca-", "potong-")): continue
    img = Image.open(f)
    t = time.perf_counter()
    teks = pytesseract.image_to_string(img, lang="ind+eng", config="--psm 6")
    waktu[nama] = round(time.perf_counter() - t, 2)
    open(os.path.join(D, "hasil-psm6", nama + ".tess.txt"), "w", encoding="utf-8").write(teks)
    # EasyOCR tidak dijalankan ulang: salin hasilnya supaya penilai bisa membaca keduanya
    import shutil; shutil.copy(os.path.join(D, "hasil", nama + ".easy.txt"), os.path.join(D, "hasil-psm6", nama + ".easy.txt"))
json.dump(waktu, open(os.path.join(D, "hasil-psm6", "waktu.json"), "w"), indent=1)
print(waktu)
