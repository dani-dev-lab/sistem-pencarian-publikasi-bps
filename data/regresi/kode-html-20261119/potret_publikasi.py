"""Simpan seluruh baris publikasi + sidik entri (per id) dari PRODUKSI ke JSON; banding dua potret.
  python potret_publikasi.py simpan <keluar.json>
  python potret_publikasi.py banding <a.json> <b.json>"""
import json, os, sys
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR); sys.stdout.reconfigure(encoding="utf-8")
if sys.argv[1] == "simpan":
    from sqlalchemy import create_engine, text
    from app.config import Config
    with create_engine(Config.SQLALCHEMY_DATABASE_URI).connect() as k:
        pub = {r[0]: [str(x) for x in r] for r in k.execute(text("SELECT * FROM publikasi"))}
        kol = list(k.execute(text("SELECT * FROM publikasi LIMIT 0")).keys())
        ent = k.execute(text("SELECT COUNT(*), BIT_XOR(CRC32(CONCAT_WS('|', id, publikasi_id, tipe, IFNULL(nomor,'~'), judul, "
                             "IFNULL(halaman,'~'), IFNULL(halaman_fisik,'~'), halaman_fisik_perkiraan, sumber, "
                             "IFNULL(teks_ternormalisasi,'~')))), SUM(CRC32(CONCAT_WS('|', id, judul, IFNULL(teks_ternormalisasi,'~')))) "
                             "FROM entri_dokumen")).one()
        lain = {t: k.execute(text(f"CHECKSUM TABLE {t}")).one()[1] for t in ("log_pencarian", "kategori", "publikasi_kategori")}
        versi = k.execute(text("SELECT versi FROM versi_data")).scalar()
    json.dump({"kolom": kol, "publikasi": pub, "entri": [str(x) for x in ent], "lain": lain, "versi": versi},
              open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(pub)} publikasi, entri {ent[0]}, versi {versi}")
else:
    a, b = json.load(open(sys.argv[2], encoding="utf-8")), json.load(open(sys.argv[3], encoding="utf-8"))
    kol = a["kolom"]; beda = {}
    for pid in set(a["publikasi"]) | set(b["publikasi"]):
        x, y = a["publikasi"].get(pid), b["publikasi"].get(pid)
        if x != y:
            beda[pid] = sorted(kol[i] for i in range(len(kol)) if not x or not y or x[i] != y[i])
    from collections import Counter
    print(f"publikasi berubah: {len(beda)}; kolom: {dict(Counter(tuple(v) for v in beda.values()))}")
    print(f"entri sama: {a['entri'] == b['entri']}; tabel lain sama: {a['lain'] == b['lain']}; versi {a['versi']} -> {b['versi']}")
    open(sys.argv[3] + ".berubah.txt", "w").write("\n".join(sorted(beda)))
