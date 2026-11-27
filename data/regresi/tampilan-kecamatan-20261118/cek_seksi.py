"""Seksi hasil kecamatan di database uji (hanya baca, log mati)."""
import os, re, sys, html
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.path.insert(0, f"{DIR}/tests"); sys.stdout.reconfigure(encoding="utf-8")
from potret_tampilan import konfigurasi
from app import create_app
c = create_app(konfigurasi("uji")).test_client()
for u in ["/hasil?q=jumlah+penduduk+menurut+desa&kec=1", "/hasil?q=penduduk&w=6301&kc=pelaihari",
          "/hasil?q=tanah+laut&kec=1", "/hasil?q=sekolah&w=6301&kec=1&semua_kec=1", "/hasil?q=penduduk&w=6300&kec=1",
          "/hasil?q=xqzv&kec=1", "/hasil?q=penduduk&w=6301"]:
    r = c.get(u); t = r.get_data(as_text=True)
    s = re.search(r'<h2 class="seksi seksi-kecamatan">(.*?)</h2>(.*?)</section>', t, re.S)
    if not s:
        print(u, r.status_code, "| TANPA seksi kecamatan"); continue
    isi = s.group(2)
    ket = re.sub(r"\s+", " ", html.unescape(re.sub("<[^>]+>", "", (re.search(r'<p class="ket-seksi">(.*?)</p>', isi, re.S) or re.search(r"()", "")).group(1)))).strip()
    label = re.findall(r'<span class="label-kecamatan">(.*?)</span>', isi)
    print(u, r.status_code, "|", s.group(1), "|", ket[:110], "| kartu:", isi.count("<article"), "| label:", label[:3],
          "| semua:", "Tampilkan semua" in isi, "| pesan:", "peringatan" in isi)
