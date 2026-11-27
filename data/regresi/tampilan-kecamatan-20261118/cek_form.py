"""Form kecamatan di database uji: beranda, /hasil dengan/ tanpa centang (hanya menampilkan potongan form)."""
import os, re, sys
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.path.insert(0, f"{DIR}/tests"); sys.stdout.reconfigure(encoding="utf-8")
from potret_tampilan import konfigurasi
from app import create_app
c = create_app(konfigurasi("uji")).test_client()
for u in ["/", "/?w=6301", "/hasil?q=penduduk&w=6301", "/hasil?q=penduduk+tanah+laut&kec=1&kc=pelaihari", "/hasil?q=penduduk&w=6300&kec=1"]:
    t = c.get(u).get_data(as_text=True)
    f = re.search(r'<form action="/hasil".*?</form>', t, re.S).group(0)
    kc = re.search(r'<select name="kc".*?>', f)
    print(u, "| kc:", kc.group(0) if kc else None, "| opsi:", f.count('<option value="') - 15,
          "| terpilih:", re.findall(r'<option value="([a-z]+)" selected', f), "| centang:", 'name="kec" value="1" checked' in f,
          "| json:", 'id="data-kecamatan"' in f)
