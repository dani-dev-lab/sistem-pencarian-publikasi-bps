"""Uji kering parser pada publikasi terpilih (database UJI hanya dibaca).

  python uji_kering.py daftar <keluar.json>       -> daftar 38 publikasi terdampak
  python uji_kering.py ekstrak <daftar.json> <hasil.json>
  python uji_kering.py banding <lama> <baru> [--rinci N]
     <lama>/<baru> = hasil.json, atau "db" = isi database uji sekarang

Entri dipasangkan menurut kunci (tipe, nomor), BUKAN posisi (prinsip
verifikasi 3). Entri tanpa nomor dihitung per tipe. Perkiraan halaman dihitung
dengan perkiraan_halaman.perkirakan, sama dengan simpan_entri.
"""
import json, os, sys
from collections import Counter, defaultdict
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR)
sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy import create_engine, text
from app.config import KonfigurasiUji

def mesin():
    return create_engine(KonfigurasiUji.SQLALCHEMY_DATABASE_URI)

KOLOM = ("tipe", "nomor", "judul", "halaman", "halaman_fisik", "halaman_fisik_perkiraan", "sumber")

def dari_db(pids):
    hasil = defaultdict(list)
    with mesin().connect() as c:
        for r in c.execute(text("select publikasi_id, tipe, nomor, judul, halaman, halaman_fisik, "
                                "halaman_fisik_perkiraan, sumber from entri_dokumen where publikasi_id in :p "
                                "order by id").bindparams(__import__("sqlalchemy").bindparam("p", expanding=True)),
                           {"p": list(pids)}):
            hasil[r[0]].append(dict(zip(KOLOM, r[1:])))
    return hasil

def muat(sumber, pids=None):
    if sumber == "db":
        return dari_db(pids)
    return json.load(open(sumber, encoding="utf-8"))

def ringkas(daftar):
    kunci = {}
    tanpa = Counter()
    for e in daftar:
        if e["nomor"]:
            kunci.setdefault((e["tipe"], e["nomor"]), e)
        else:
            tanpa[e["tipe"]] += 1
    return kunci, tanpa

if sys.argv[1] == "daftar":
    target = {l.split()[0] for l in open("data/ocr_target_kecamatan.txt", encoding="utf-8") if l.strip() and not l.startswith("#")}
    with mesin().connect() as c:
        rows = c.execute(text("select id, domain, judul from publikasi where judul like 'Kecamatan%' and "
                              "((domain='6301' and judul like '%2025') or (domain='6303' and judul like '%2026') "
                              "or (domain='6311' and judul like '%2025')) order by domain, judul")).fetchall()
    pids = [r[0] for r in rows if r[0] not in target]
    json.dump(pids, open(sys.argv[2], "w"), indent=0)
    print(len(pids), "publikasi")

elif sys.argv[1] == "ekstrak":
    from app.services import pipeline_data, perkiraan_halaman
    pids = json.load(open(sys.argv[2]))
    with mesin().connect() as c:
        dom = dict(c.execute(text("select id, domain from publikasi")).fetchall())
    hasil = {}
    for i, p in enumerate(pids, 1):
        entri, _ = pipeline_data.ekstrak_berkas(f"data/publikasi_pdf/{dom[p]}/{p}.pdf", p, ocr_aktif=False, log=lambda *_: None)
        prk = perkiraan_halaman.perkirakan(entri)
        hasil[p] = [{"tipe": e["tipe"], "nomor": e.get("nomor"), "judul": e["judul"], "halaman": e.get("halaman"),
                     "halaman_fisik": e.get("halaman_fisik") or prk.get(j), "halaman_fisik_perkiraan": int(j in prk),
                     "sumber": e.get("sumber", "daftar")} for j, e in enumerate(entri)]
        print(f"{i}/{len(pids)} {p} {len(entri)}", flush=True)
    json.dump(hasil, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False)

elif sys.argv[1] == "banding":
    baru = muat(sys.argv[3]) if sys.argv[3] != "db" else None
    lama = muat(sys.argv[2], list(baru) if baru else None)
    if baru is None:
        baru = muat("db", list(lama))
    rinci = int(sys.argv[sys.argv.index("--rinci") + 1]) if "--rinci" in sys.argv else 0
    tot = Counter(); contoh = defaultdict(list)
    for p in sorted(set(lama) | set(baru)):
        kl, tl = ringkas(lama.get(p, [])); kb, tb = ringkas(baru.get(p, []))
        tot["entri_lama"] += len(lama.get(p, [])); tot["entri_baru"] += len(baru.get(p, []))
        tot["tanpa_nomor_lama"] += sum(tl.values()); tot["tanpa_nomor_baru"] += sum(tb.values())
        tot["hal_cetak_lama"] += sum(1 for e in lama.get(p, []) if e["halaman"])
        tot["hal_cetak_baru"] += sum(1 for e in baru.get(p, []) if e["halaman"])
        for k in kl.keys() - kb.keys():
            tot["kunci_hilang"] += 1; contoh["hilang"].append((p[:8], k, kl[k]["judul"][:70]))
        for k in kb.keys() - kl.keys():
            tot["kunci_baru"] += 1; contoh["baru"].append((p[:8], k, kb[k]["judul"][:70], kb[k]["halaman"], kb[k]["halaman_fisik"]))
        for k in kl.keys() & kb.keys():
            a, b = kl[k], kb[k]
            for m in ("judul", "halaman", "halaman_fisik", "sumber"):
                if a[m] != b[m]:
                    tot[f"ubah_{m}"] += 1; contoh[m].append((p[:8], k, a[m] if m != "judul" else a[m][-50:], b[m] if m != "judul" else b[m][-50:]))
        if lama.get(p) != baru.get(p):
            tot["publikasi_berubah"] += 1
    for k in sorted(tot):
        print(f"{k:22s} {tot[k]}")
    for jenis, xs in contoh.items():
        print(f"\n-- {jenis} ({len(xs)}), {min(rinci, len(xs))} contoh")
        for x in xs[:rinci]:
            print("  ", x)

elif sys.argv[1] == "potret":
    # Seluruh entri database uji per publikasi -> json (pembanding regresi penuh).
    with mesin().connect() as c:
        pids = [r[0] for r in c.execute(text("select id from publikasi"))]
    json.dump(dari_db(pids), open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, default=str)
    print(len(pids), "publikasi")
