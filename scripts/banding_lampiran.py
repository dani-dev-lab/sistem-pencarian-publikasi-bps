"""Bandingkan hasil ekstraksi terhadap baseline, fokus pada regresi.

Dipakai setelah mengubah parser: memastikan tidak ada publikasi yang KEHILANGAN
entri, dan mengukur pertambahan halaman_fisik.

Jalankan:  venv/Scripts/python.exe scripts/banding_lampiran.py
"""

import json
import os
import sys
from collections import Counter

FILE_BASELINE = "data/baseline_sebelum_lampiran.json"
FILE_BARU = "data/hasil_ekstraksi.json"


def muat(path):
    """Terima format lama (list) maupun baru (dict berpenanda kelengkapan)."""
    if not os.path.exists(path):
        print(f"{path} tidak ada.")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        isi = json.load(f)
    daftar = isi if isinstance(isi, list) else isi.get("hasil", [])
    return {h["publikasi_id"]: h for h in daftar}


def n_fisik(h):
    return sum(1 for e in h["entri"] if e.get("halaman_fisik"))


def main():
    lama, baru = muat(FILE_BASELINE), muat(FILE_BARU)

    tot_lama = sum(h["jumlah_entri"] for h in lama.values())
    tot_baru = sum(h["jumlah_entri"] for h in baru.values())
    fis_lama = sum(n_fisik(h) for h in lama.values())
    fis_baru = sum(n_fisik(h) for h in baru.values())

    print("=" * 74)
    print("AGREGAT")
    print("=" * 74)
    print(f"  {'':<26}{'baseline':>10}{'baru':>10}   selisih")
    print(f"  {'total entri':<26}{tot_lama:>10}{tot_baru:>10}   {tot_baru - tot_lama:+d}")
    print(f"  {'punya halaman_fisik':<26}{fis_lama:>10}{fis_baru:>10}   {fis_baru - fis_lama:+d}")

    src_lama, src_baru = Counter(), Counter()
    tipe_lama, tipe_baru = Counter(), Counter()
    for h in lama.values():
        src_lama.update(e.get("sumber", "daftar") for e in h["entri"])
        tipe_lama.update(e["tipe"] for e in h["entri"])
    for h in baru.values():
        src_baru.update(e.get("sumber", "daftar") for e in h["entri"])
        tipe_baru.update(e["tipe"] for e in h["entri"])

    print()
    print("  per sumber:")
    for s in ("daftar", "badan", "keduanya"):
        print(f"    {s:<24}{src_lama[s]:>10}{src_baru[s]:>10}   "
              f"{src_baru[s] - src_lama[s]:+d}")
    print("  per tipe:")
    for t in ("isi", "tabel", "gambar", "lampiran"):
        print(f"    {t:<24}{tipe_lama[t]:>10}{tipe_baru[t]:>10}   "
              f"{tipe_baru[t] - tipe_lama[t]:+d}")

    # ------------------------- REGRESI: entri berkurang -------------------------
    turun, naik = [], []
    for pid, h in baru.items():
        l = lama.get(pid)
        if l is None:
            continue
        d = h["jumlah_entri"] - l["jumlah_entri"]
        if d < 0:
            turun.append((d, l["jumlah_entri"], h["jumlah_entri"], h["judul"]))
        elif d > 0:
            naik.append((d, l["jumlah_entri"], h["jumlah_entri"], h["judul"]))

    print()
    print("=" * 74)
    print(f"PUBLIKASI YANG ENTRINYA BERKURANG ({len(turun)})  <- tanda regresi")
    print("=" * 74)
    if not turun:
        print("  TIDAK ADA")
    for d, a, b, j in sorted(turun):
        print(f"  {d:+5d}  {a:>4} -> {b:<4}  {j[:52]}")

    print()
    print("=" * 74)
    print(f"PUBLIKASI YANG ENTRINYA BERTAMBAH ({len(naik)})")
    print("=" * 74)
    if not naik:
        print("  tidak ada")
    for d, a, b, j in sorted(naik, reverse=True)[:12]:
        print(f"  {d:+5d}  {a:>4} -> {b:<4}  {j[:52]}")

    # Publikasi yang halaman_fisik-nya bertambah paling banyak.
    delta_fisik = []
    for pid, h in baru.items():
        l = lama.get(pid)
        if l:
            delta_fisik.append((n_fisik(h) - n_fisik(l), n_fisik(l), n_fisik(h),
                                h["judul"]))
    print()
    print("=" * 74)
    print("PERTAMBAHAN halaman_fisik TERBESAR")
    print("=" * 74)
    for d, a, b, j in sorted(delta_fisik, reverse=True)[:10]:
        if d:
            print(f"  {d:+5d}  {a:>4} -> {b:<4}  {j[:52]}")


if __name__ == "__main__":
    main()
