"""Uji modul app/services/sampul.py dengan server HTTP lokal; tanpa BPS, folder sementara."""
import io, os, sys, threading, http.server, shutil, tempfile
DIR = sys.argv[1]
os.environ["DIR_SAMPUL"] = tempfile.mkdtemp(prefix="sampul-uji-")
sys.path.insert(0, DIR); os.chdir(DIR)
from PIL import Image
from app.config import Config
from app.services import sampul
sampul.JEDA_ULANG = 0
assert str(Config.DIR_SAMPUL) == os.environ["DIR_SAMPUL"], "override DIR_SAMPUL tidak berlaku"

def gambar(fmt):
    b = io.BytesIO(); Image.new("RGB", (500, 709), (10, 60, 120)).save(b, fmt); return b.getvalue()
JPG, PNG = gambar("JPEG"), gambar("PNG")
hit = {}
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        jalur = self.path.split("?")[0]; hit[jalur] = hit.get(jalur, 0) + 1
        jawab = {"/jpg": (200, "image/jpeg", JPG), "/png": (200, "image/png", PNG),
                 "/html": (200, "text/html", b"<html>galat</html>" * 100),
                 "/potong": (200, "image/jpeg", JPG[: len(JPG) // 2]),
                 "/400": (400, "text/plain", b"x"), "/500": (500, "text/plain", b"x")}[jalur]
        self.send_response(jawab[0]); self.send_header("Content-Type", jawab[1]); self.end_headers()
        self.wfile.write(jawab[2])
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
U = f"http://127.0.0.1:{srv.server_port}"
TOKEN = "AQADrahasiaTOKENpanjang1234567890"
PDF = "data/publikasi_pdf/6301/62b7bddfd59c974bf4a39e16.pdf"
hasil = []
def cek(nama, syarat, rinci=""):
    hasil.append(bool(syarat)); print(f"  [{'LULUS' if syarat else 'GAGAL'}] {nama} {rinci}")

r = sampul.lengkapi("a1", f"{U}/jpg?f={TOKEN}", PDF)
cek("JPEG 200 -> resmi, byte identik", r["hasil"] == "resmi" and open(sampul.path_resmi("a1"), "rb").read() == JPG, r)
r = sampul.lengkapi("a2", f"{U}/png?f={TOKEN}", PDF)
cek("PNG 200 -> resmi, dikonversi JPEG", r["hasil"] == "resmi" and Image.open(sampul.path_resmi("a2")).format == "JPEG", r["hasil"])
for jalur, n_harap in (("/400", 1), ("/500", 2), ("/html", 2), ("/potong", 2)):
    hit.clear(); pid = "b" + jalur[1:]
    r = sampul.lengkapi(pid, f"{U}{jalur}?f={TOKEN}", PDF)
    ok = r["hasil"] == "cadangan" and os.path.isfile(sampul.path_cadangan(pid)) and not os.path.exists(sampul.path_resmi(pid))
    cek(f"{jalur} -> cadangan PDF, permintaan {hit.get(jalur)} (harap {n_harap}), token tidak di pesan",
        ok and hit.get(jalur) == n_harap and r["pesan"] and TOKEN not in r["pesan"], r["pesan"])
with Image.open(sampul.path_cadangan("b400")) as im:
    cek("cadangan = JPEG lebar 500, rasio halaman", im.format == "JPEG" and im.width == 500 and abs(im.height / im.width - 595 / 420) < 0.01, im.size)
r = sampul.lengkapi("c1", None, "tidak/ada.pdf")
cek("tanpa url + tanpa PDF -> gagal, tanpa berkas", r["hasil"] == "gagal" and sampul.berkas("c1") is None, r["pesan"])
r = sampul.lengkapi("b400", f"{U}/400?f={TOKEN}", PDF)
cek("cadangan sudah ada + unduh gagal -> cadangan_lama (tidak dirender ulang)", r["hasil"] == "cadangan_lama", r["hasil"])
r = sampul.lengkapi("b400", f"{U}/jpg?f={TOKEN}", PDF)
cek("sampul resmi menggantikan cadangan", r["hasil"] == "resmi" and not os.path.exists(sampul.path_cadangan("b400")) and sampul.berkas("b400") == sampul.path_resmi("b400"))
r = sampul.lengkapi("d1", None, PDF, online=False)
cek("online=False -> langsung cadangan", r["hasil"] == "cadangan", r["hasil"])
cek("tidak ada .part tersisa", not [f for f in os.listdir(Config.DIR_SAMPUL) if f.endswith(".part")], sorted(os.listdir(Config.DIR_SAMPUL)))
print(f"{sum(hasil)}/{len(hasil)} lulus"); shutil.rmtree(Config.DIR_SAMPUL); srv.shutdown()
sys.exit(0 if all(hasil) else 1)
