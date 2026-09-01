"""Bandingkan hasil ekstraksi terhadap baseline untuk mendeteksi regresi.

Dipakai setelah mengubah parser: memastikan publikasi yang tadinya bersih tidak
ikut berubah, dan mutu keseluruhan tidak turun.

Jalankan:  venv/Scripts/python.exe scripts/banding_regresi.py
"""

import json
import os

FILE_BASELINE = "data/baseline_ekstraksi.json"
FILE_BARU = "data/hasil_ekstraksi.json"

# Publikasi yang memang jadi sasaran perubahan; perubahan di sini diharapkan.
SASARAN_KATA_KUNCI = "Dalam Angka"


def muat(path):
    """Terima format lama (list) maupun baru (dict berpenanda kelengkapan)."""
    with open(path, encoding="utf-8") as f:
        isi = json.load(f)
    daftar = isi if isinstance(isi, list) else isi.get("hasil", [])
    return {h["publikasi_id"]: h for h in daftar}


def mutu(h):
    """(jumlah entri, tanpa halaman, non-isi, non-isi bernomor)."""
    non = [e for e in h["entri"] if e["tipe"] != "isi"]
    return (
        h["jumlah_entri"],
        sum(1 for e in h["entri"] if not e["halaman"]),
        len(non),
        sum(1 for e in non if e["nomor"]),
    )


def main():
    for p in (FILE_BASELINE, FILE_BARU):
        if not os.path.exists(p):
            print(f"{p} tidak ada.")
            return

    lama, baru = muat(FILE_BASELINE), muat(FILE_BARU)

    sasaran, berubah, sama = [], [], 0
    for pid in sorted(set(lama) | set(baru)):
        a, b = lama.get(pid), baru.get(pid)
        if not a or not b:
            berubah.append((pid, "hilang/baru", None, None))
            continue
        ma, mb = mutu(a), mutu(b)
        if ma == mb:
            sama += 1
        elif SASARAN_KATA_KUNCI in b["judul"]:
            sasaran.append((pid, b["judul"], ma, mb))
        else:
            berubah.append((pid, b["judul"], ma, mb))

    def agregat(d):
        e = sum(h["jumlah_entri"] for h in d.values())
        th = sum(1 for h in d.values() for x in h["entri"] if not x["halaman"])
        non = [x for h in d.values() for x in h["entri"] if x["tipe"] != "isi"]
        return e, th, len(non), sum(1 for x in non if x["nomor"])

    ea, tha, nona, noma = agregat(lama)
    eb, thb, nonb, nomb = agregat(baru)

    print("=" * 76)
    print("AGREGAT 72 PUBLIKASI")
    print("=" * 76)
    print(f"  {'':<28}{'baseline':>12}{'baru':>12}   selisih")
    print(f"  {'total entri':<28}{ea:>12}{eb:>12}   {eb - ea:+d}")
    print(f"  {'tanpa nomor halaman':<28}{tha:>12}{thb:>12}   {thb - tha:+d}")
    print(f"  {'  (persen)':<28}{tha / ea * 100:>11.1f}%{thb / eb * 100:>11.1f}%"
          f"   {thb / eb * 100 - tha / ea * 100:+.1f} poin")
    print(f"  {'entri non-isi':<28}{nona:>12}{nonb:>12}   {nonb - nona:+d}")
    print(f"  {'  bernomor':<28}{noma:>12}{nomb:>12}   {nomb - noma:+d}")
    print(f"  {'  (persen)':<28}{noma / nona * 100:>11.1f}%{nomb / nonb * 100:>11.1f}%"
          f"   {nomb / nonb * 100 - noma / nona * 100:+.1f} poin")

    print()
    print("=" * 76)
    print(f"PUBLIKASI SASARAN ({len(sasaran)}) - perubahan diharapkan")
    print("=" * 76)
    for pid, judul, ma, mb in sasaran:
        print(f"  {judul[:52]}")
        print(f"      entri {ma[0]} -> {mb[0]}   tanpa halaman {ma[1]} -> {mb[1]}   "
              f"bernomor {ma[3]}/{ma[2]} -> {mb[3]}/{mb[2]}")

    print()
    print("=" * 76)
    print(f"REGRESI - publikasi lain yang ikut berubah ({len(berubah)})")
    print("=" * 76)
    if not berubah:
        print(f"  TIDAK ADA. {sama} publikasi lain identik dengan baseline.")
    for pid, judul, ma, mb in berubah:
        print(f"  {pid}  {str(judul)[:46]}")
        if ma and mb:
            print(f"      entri {ma[0]} -> {mb[0]}   tanpa halaman {ma[1]} -> {mb[1]}   "
                  f"bernomor {ma[3]}/{ma[2]} -> {mb[3]}/{mb[2]}")

    print()
    print(f"Identik dengan baseline: {sama}/{len(baru)} publikasi")


if __name__ == "__main__":
    main()
