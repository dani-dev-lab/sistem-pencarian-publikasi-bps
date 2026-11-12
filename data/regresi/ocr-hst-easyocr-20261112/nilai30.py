"""Bandingkan beberapa keluaran parser-OCR pada 30 tabel acuan yang SAMA.

Acuan (acuan30.json) dibaca manual dari render baris Daftar Tabel HST 2026.
Per tabel, per mesin: entri dicari menurut nomor (tanpa titik akhir); kalau
tidak ada, menurut 40 karakter pertama judul acuan (partial_ratio, hanya
entri yang judulnya >= 40 karakter - partial_ratio mencocokkan string yang
lebih pendek di dalam yang lebih panjang). Keluaran: kartu teks per tabel
untuk dinilai manual + ringkasan otomatis (bukan penilaian akhir).
Pemakaian (venv proyek): python nilai30.py <keluar.txt> nama=berkas.json ...
"""
import json
import re
import sys

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein


def norm(s):
    s = (s or "").replace("–", "-").replace("—", "-").replace("’", "'")
    return re.sub(r"\s+", " ", s.lower()).strip()


def cari(entri, a):
    tab = [e for e in entri if e["tipe"] == "tabel"]
    for e in tab:
        if (e.get("nomor") or "").rstrip(".") == a["nomor"]:
            return e, "nomor"
    jarum = norm(a["judul"])[:40]
    terbaik = max(((fuzz.partial_ratio(jarum, norm(e["judul"])), e) for e in tab
                   if len(norm(e["judul"])) >= len(jarum)), default=(0, None), key=lambda x: x[0])
    return (terbaik[1], f"judul {terbaik[0]:.0f}") if terbaik[0] >= 85 else (None, "-")


def main():
    acuan = json.load(open("acuan30.json", encoding="utf-8"))
    mesin = dict(a.split("=", 1) for a in sys.argv[2:])
    data = {m: json.load(open(f, encoding="utf-8"))["entri"] for m, f in mesin.items()}
    baris, hasil = [], []
    for i, a in enumerate(acuan, 1):
        baris.append(f"=== #{i} [{a['nomor']}] hal={a['halaman']} (Daftar hal.{a['halaman_daftar']})")
        baris.append(f"    ACUAN: {a['judul']}")
        for m, entri in data.items():
            e, cara = cari(entri, a)
            if e is None:
                baris.append(f"    {m:10} TIDAK DITEMUKAN")
                hasil.append({"no": i, "mesin": m, "ada": False})
                continue
            j = norm(e["judul"]); g = norm(a["judul"])
            al = fuzz.partial_ratio_alignment(g, j)
            mirip = Levenshtein.normalized_similarity(g, j[al.dest_start:al.dest_end]) * 100 if len(j) >= len(g) else fuzz.ratio(g, j)
            awalan = j[:al.dest_start].strip() if len(j) >= len(g) else ""
            hasil.append({"no": i, "mesin": m, "ada": True, "cara": cara,
                          "nomor_ok": (e.get("nomor") or "").rstrip(".") == a["nomor"],
                          "hal_ok": None if a["halaman"] is None else str(e.get("halaman")) == a["halaman"],
                          "mirip_judul": round(mirip, 1), "awalan": len(awalan),
                          "halaman": e.get("halaman"), "halaman_fisik": e.get("halaman_fisik")})
            baris.append(f"    {m:10} ({cara}) nomor={e.get('nomor')} hal={e.get('halaman')} fisik={e.get('halaman_fisik')} "
                         f"mirip={mirip:.0f} awalan={len(awalan)}")
            baris.append(f"               {(e.get('judul') or '')[:230]}")
    open(sys.argv[1], "w", encoding="utf-8").write("\n".join(baris))
    json.dump(hasil, open(sys.argv[1].replace(".txt", ".json"), "w", encoding="utf-8"), indent=1)
    for m in mesin:
        h = [x for x in hasil if x["mesin"] == m]
        ada = [x for x in h if x["ada"]]
        print(f"{m:10} ditemukan {len(ada)}/30 | nomor benar {sum(x['nomor_ok'] for x in ada)} | "
              f"halaman benar {sum(1 for x in ada if x['hal_ok'])}/{sum(1 for x in h if acuan[x['no']-1]['halaman'])} | "
              f"judul mirip>=95 {sum(1 for x in ada if x['mirip_judul'] >= 95)} | berawalan {sum(1 for x in ada if x['awalan'] > 0)} | "
              f"fisik terisi {sum(1 for x in ada if x['halaman_fisik'])}")


if __name__ == "__main__":
    main()
