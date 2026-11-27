"""Analisis regresi penuh (database uji, hanya baca).
  python analisis_regresi.py ringkas <awal.json> <akhir.json> <keluar_berubah.json>
      per kelompok (produksi / kecamatan): publikasi berubah, kunci bernomor hilang/baru, dst.
  python analisis_regresi.py tanpa_rapikan <berubah.json> <awal.json>
      ekstrak ulang publikasi berubah dengan _rapikan_nomor_halaman DIMATIKAN;
      harus identik dengan potret awal -> perubahan hanya berasal dari pola 2/3.
"""
import json, os, sys
from collections import Counter
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.stdout.reconfigure(encoding="utf-8")

def kunci(es):
    return {(e["tipe"], e["nomor"]): e for e in es if e["nomor"]}

def sama(a, b):
    m = ("tipe", "nomor", "judul", "halaman", "halaman_fisik", "halaman_fisik_perkiraan", "sumber")
    norm = lambda e: tuple(str(e[k]) if e[k] is not None else None for k in m)
    return [norm(e) for e in a] == [norm(e) for e in b]

if sys.argv[1] == "ringkas":
    awal = json.load(open(sys.argv[2], encoding="utf-8")); akhir = json.load(open(sys.argv[3], encoding="utf-8"))
    from sqlalchemy import create_engine, text
    from app.config import KonfigurasiUji
    with create_engine(KonfigurasiUji.SQLALCHEMY_DATABASE_URI).connect() as c:
        judul = dict(c.execute(text("select id, judul from publikasi")).fetchall())
    berubah = {}
    for kel in ("produksi", "kecamatan"):
        t = Counter(); contoh = []
        for p in awal:
            if (judul[p].startswith("Kecamatan")) != (kel == "kecamatan"):
                continue
            t["publikasi"] += 1
            a, b = awal[p], akhir.get(p, [])
            t["entri_awal"] += len(a); t["entri_akhir"] += len(b)
            if sama(a, b):
                continue
            t["berubah"] += 1; berubah.setdefault(kel, []).append(p)
            ka, kb = kunci(a), kunci(b)
            hilang = ka.keys() - kb.keys()
            t["kunci_hilang"] += len(hilang); t["kunci_baru"] += len(kb.keys() - ka.keys())
            contoh += [(p[:8], judul[p][:40], k) for k in hilang]
            t["hal_cetak_awal"] += sum(1 for e in a if e["halaman"]); t["hal_cetak_akhir"] += sum(1 for e in b if e["halaman"])
            t["fisik_awal"] += sum(1 for e in a if e["halaman_fisik"]); t["fisik_akhir"] += sum(1 for e in b if e["halaman_fisik"])
        print(kel, dict(t))
        for x in contoh[:30]:
            print("   hilang", x)
        print("   berubah:", [judul[p][:45] for p in berubah.get(kel, [])][:40])
    json.dump(berubah, open(sys.argv[4], "w"), indent=0)

elif sys.argv[1] == "tanpa_rapikan":
    from app.services import ekstraksi_pdf as E, pipeline_data, perkiraan_halaman
    import glob
    E._rapikan_nomor_halaman = lambda b: b
    awal = json.load(open(sys.argv[3], encoding="utf-8"))
    pids = json.load(open(sys.argv[2]))["produksi"]
    beda = 0
    for p in pids:
        f = glob.glob(f"data/publikasi_pdf/*/{p}.pdf")[0]
        entri, cat = pipeline_data.ekstrak_berkas(f, p, ocr_aktif=True, log=lambda *_: None)
        prk = perkiraan_halaman.perkirakan(entri)
        es = [{"tipe": e["tipe"], "nomor": e.get("nomor"), "judul": e["judul"], "halaman": e.get("halaman"),
               "halaman_fisik": e.get("halaman_fisik") or prk.get(j), "halaman_fisik_perkiraan": int(j in prk),
               "sumber": e.get("sumber", "daftar")} for j, e in enumerate(entri)]
        ok = sama(es, awal[p]); beda += not ok
        print(p[:8], "identik dengan awal" if ok else "BEDA", (cat.get("ocr") or {}).get("di_ocr", 0), flush=True)
    print("TIDAK TERJELASKAN:", beda)
