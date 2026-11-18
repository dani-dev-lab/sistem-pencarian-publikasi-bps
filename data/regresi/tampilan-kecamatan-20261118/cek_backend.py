"""Bagian 4 (backend kecamatan) di database uji: kunci lama identik dengan/tanpa kec, isi bagian kecamatan masuk akal."""
import os, sys
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.path.insert(0, f"{DIR}/tests"); sys.stdout.reconfigure(encoding="utf-8")
from potret_tampilan import konfigurasi
from app import create_app
from app.services import mesin_pencari as M, pencarian_wilayah as P
with create_app(konfigurasi("uji")).app_context():
    print("daftar 6301:", M.daftar_kecamatan("6301")[:4], "...", len(M.daftar_kecamatan("6301")))
    print("daftar 6372:", M.daftar_kecamatan("6372"))
    for q, w, kc in [("jumlah penduduk menurut desa", "", None), ("penduduk", "6301", None), ("penduduk", "6301", "pelaihari"),
                     ("tanah laut", "", None), ("penduduk", "6300", None), ("penduduk", "6302", "pelaihari"), ("sekolah", "", "x")]:
        a = P.cari(q, w=w); b = P.cari(q, w=w, kec=True, kc=kc)
        lama_sama = all(a[x] == b[x] for x in a if x not in ("waktu_ms", "kecamatan"))
        kb = b["kecamatan"]
        print(f"{q!r} w={w or '-'} kc={kc}: kunci lama identik={lama_sama}, kec None tanpa centang={a['kecamatan'] is None}, "
              f"filter={b['filter']['kode']}, kc_sah={kb['kc']}, jumlah={kb['jumlah']}, tampil={len(kb['hasil'])}, pub={len(kb['publikasi'])}, "
              f"pesan={kb['pesan']}, {kb['waktu_ms']:.0f} ms")
        for h in (kb["hasil"] or kb["publikasi"])[:2]:
            print("     ", h["kecamatan"], "|", h.get("wilayah"), "|", h["judul"][:70], "|", h.get("skor"))
