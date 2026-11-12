"""Uji kering aturan heading baru: ekstrak_lengkap dengan cari_heading diganti
cari_heading_baru (monkeypatch, parser tidak diubah), dibandingkan dengan
entri DB per kunci. Tidak menulis ke DB.

Kunci: (tipe, nomor) untuk entri bernomor; (tipe, judul) untuk yang tidak.
Pemakaian: kering_heading.py <daftar_pid.json|semua> <keluaran.json> [proses]
"""
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MEDAN = ("judul", "halaman", "halaman_fisik", "sumber")


def kunci(e):
    return (e["tipe"], e["nomor"]) if e.get("nomor") else (e["tipe"], "#" + (e.get("judul") or ""))


def satu(arg):
    pid, domain, lama = arg
    # Kode parser SEBENARNYA (working tree), jalur yang sama dengan perbarui.py.
    from app.services import pipeline_data
    entri, catatan = pipeline_data.ekstrak_berkas(f"data/publikasi_pdf/{domain}/{pid}.pdf", pid)
    baru = {}
    for e in entri:
        baru.setdefault(kunci(e), []).append(e)
    l = {}
    for e in lama:
        l.setdefault(kunci(e), []).append(e)
    hilang = [k for k in l if k not in baru]
    tambah = [k for k in baru if k not in l]
    berubah = []
    for k in l:
        if k in baru and len(l[k]) == 1 and len(baru[k]) == 1:
            a, b = l[k][0], baru[k][0]
            beda = {m: (a.get(m), b.get(m)) for m in MEDAN if (a.get(m) or None) != (b.get(m) or None)}
            if beda:
                berubah.append({"kunci": list(k), "beda": beda})
    # Kunci kembar (8 kelompok yang sudah tercatat) dilewati pemeriksaan medan
    # di atas; jumlahnya tetap harus sama, kalau tidak itu juga perubahan.
    jumlah_beda = [[list(k), len(l[k]), len(baru[k])] for k in l if k in baru and len(l[k]) != len(baru[k])]
    return {"pid": pid, "domain": domain, "lama": len(lama), "baru": len(entri),
            "heading": catatan.get("heading_ditemukan"), "jumlah_beda": jumlah_beda,
            "hilang": [list(k) for k in hilang], "tambah": [list(k) for k in tambah],
            "berubah": berubah,
            "entri_tambah": [e for k in tambah for e in baru[k]]}


def main():
    from app import create_app
    from app.config import KonfigurasiUji
    from app.models import db
    import sqlalchemy as sa
    app = create_app(KonfigurasiUji)
    with app.app_context():
        pubs = {r.id: r.domain for r in db.session.execute(sa.text("select id, domain from publikasi"))}
        rows = db.session.execute(sa.text(
            "select publikasi_id, tipe, nomor, judul, halaman, halaman_fisik, sumber from entri_dokumen order by id")).mappings().all()
    lama = {}
    for r in rows:
        lama.setdefault(r["publikasi_id"], []).append(dict(r))
    pilih = list(pubs) if sys.argv[1] == "semua" else json.load(open(sys.argv[1]))
    tugas = [(p, pubs[p], lama.get(p, [])) for p in pilih]
    with Pool(int(sys.argv[3]) if len(sys.argv) > 3 else 2) as pool:
        hasil = pool.map(satu, tugas, chunksize=1)
    json.dump(hasil, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(f"publikasi {len(hasil)} | entri lama {sum(h['lama'] for h in hasil)} baru {sum(h['baru'] for h in hasil)} | "
          f"kunci hilang {sum(len(h['hilang']) for h in hasil)} | tambah {sum(len(h['tambah']) for h in hasil)} | "
          f"berubah {sum(len(h['berubah']) for h in hasil)} | jumlah per kunci beda {sum(len(h['jumlah_beda']) for h in hasil)} | publikasi berubah {sum(1 for h in hasil if h['hilang'] or h['tambah'] or h['berubah'])}")


if __name__ == "__main__":
    main()
