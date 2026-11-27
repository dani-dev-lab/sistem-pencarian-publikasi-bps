"""isi_sampul.py --db-uji dengan requests.get PALSU (tanpa jaringan), folder sampul sementara.
  python uji_isi.py <dir proyek> <folder sampul> <berhenti_setelah|0>"""
import io, os, sys
DIR, FOLDER, BERHENTI = sys.argv[1], sys.argv[2], int(sys.argv[3])
os.environ["DIR_SAMPUL"] = FOLDER
sys.path.insert(0, DIR); sys.path.insert(0, os.path.join(DIR, "scripts")); os.chdir(DIR)
import requests
from PIL import Image
b = io.BytesIO(); Image.new("RGB", (500, 709), (0, 43, 106)).save(b, "JPEG"); JPG = b.getvalue()
GAGAL_400 = {"6f8054b90a3847648109f293", "ac101cb3ecf77273005c324d", "62b7bddfd59c974bf4a39e16", "c0ffee"}
TANPA_PDF = "ac101cb3ecf77273005c324d"        # unduh 400 + PDF "hilang" -> gagal
n = {"get": 0}
class Mentah:                     # meniru urllib3 response.raw.read(n, decode_content=...)
    def __init__(self, data): self.b = io.BytesIO(data)
    def read(self, n=-1, decode_content=False): return self.b.read(n)
class Palsu:
    def __init__(self, kode): self.status_code = kode; self.raw = Mentah(JPG)
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def raise_for_status(self):
        if self.status_code >= 400:
            e = requests.HTTPError(f"{self.status_code} Client Error for url: {self.url}"); e.response = self; raise e
def get_palsu(url, **kw):
    n["get"] += 1
    if BERHENTI and n["get"] > BERHENTI:
        raise KeyboardInterrupt("simulasi terputus")
    r = Palsu(400 if any(g in url for g in ()) else 200); r.url = url
    return r
import app.services.sampul as sampul
from app.services import sumber_bps
asli_lengkapi = sampul.lengkapi
def lengkapi(pid, url, path_pdf, online=True):
    if pid in GAGAL_400:
        url = "http://x/cover.php?f=" + "AQADPALSU" + pid           # dijawab 400
    if pid == TANPA_PDF:
        path_pdf = "tidak/ada.pdf"
    return asli_lengkapi(pid, url, path_pdf, online)
def get(url, **kw):
    if "AQADPALSU" in url:
        n["get"] += 1; r = Palsu(400); r.url = url; return r
    return get_palsu(url, **kw)
requests.get = get
sampul.lengkapi = lengkapi
sumber_bps.JEDA_DETIK = 0
import isi_sampul
sys.argv = ["isi_sampul.py", "--db-uji"]
try:
    isi_sampul.main()
except KeyboardInterrupt as e:
    sys.stdout = sys.__stdout__
    print(f"TERPUTUS (disimulasikan) sesudah {n['get'] - 1} permintaan")
