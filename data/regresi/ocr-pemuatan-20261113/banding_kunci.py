"""Bandingkan dua potret_kunci.py per KUNCI, bukan per posisi.

  python banding_kunci.py <sebelum.json> <sesudah.json> [<keluaran.tsv>]

Kunci entri: (tipe, nomor) untuk entri bernomor, (tipe, judul) untuk yang
tanpa nomor. Kunci kembar ditangani sebagai multiset (Counter).
"""
import json
import sys
from collections import Counter, defaultdict

TARGET = {
    "aafda0cff288ddb041cfa024": "HST Dalam Angka 2026",
    "f338cd99104699dbbd49256a": "PDRB Tapin Pengeluaran",
    "47c94280220a99e5d2045881": "Profil TK Tapin Agt 2024",
    "8db55ef62f0d2083f60d1b31": "Statistik Daerah Banjarbaru 2025",
    "a818fdde814d5bbc2820d135": "PDRB Banjarbaru LU",
    "182e2e58be59ddf2d26a7a44": "PDRB Tapin LU 2020-2024",
    "25f039221e44a34843043419": "PDRB Tapin LU 2021-2025",
    "786645b667871d033771a8b9": "PDRB Tabalong LU 2020-2024",
}
MEDAN_PUB = ["judul", "abstrak", "teks_ternormalisasi", "galat_ekstraksi", "halaman_ocr",
             "sidik_ukuran", "sidik_mtime", "domain"]


def kunci(e):
    tipe, nomor, judul = e[0], e[1], e[2]
    return (tipe, nomor) if nomor else (tipe, "~" + judul)


def kelompok(daftar):
    g = defaultdict(list)
    for e in daftar:
        g[kunci(e)].append(tuple(e))
    return g


def banding_pub(lama, baru):
    """Return dict: tetap, berubah, hilang, bertambah (per entri lama/baru)."""
    gl, gb = kelompok(lama), kelompok(baru)
    hasil = {"tetap": 0, "berubah": [], "hilang": [], "bertambah": []}
    for k, el in gl.items():
        eb = Counter(gb.get(k, []))
        sisa = []
        for e in el:
            if eb[e] > 0:
                eb[e] -= 1
                hasil["tetap"] += 1
            else:
                sisa.append(e)
        sisa_baru = list(eb.elements())
        for e in sisa:
            if sisa_baru:
                hasil["berubah"].append((e, sisa_baru.pop(0)))
            else:
                hasil["hilang"].append(e)
        hasil["bertambah"].extend(sisa_baru)
    for k, eb in gb.items():
        if k not in gl:
            hasil["bertambah"].extend(eb)
    # Entri TANPA nomor berkunci judul: judul yang berubah akan tampak sebagai
    # hilang + bertambah. Pasangkan lagi menurut (tipe, halaman, halaman_fisik).
    for e in list(hasil["hilang"]):
        if e[1]:
            continue
        for b in hasil["bertambah"]:
            if not b[1] and (b[0], b[3], b[4]) == (e[0], e[3], e[4]):
                hasil["hilang"].remove(e)
                hasil["bertambah"].remove(b)
                hasil["berubah"].append((e, b))
                break
    return hasil


a = json.load(open(sys.argv[1], encoding="utf-8"))
b = json.load(open(sys.argv[2], encoding="utf-8"))
print(f"sebelum: {a['database']} versi {a['versi_data']} | sesudah: {b['database']} versi {b['versi_data']}")
print(f"publikasi {len(a['publikasi'])} -> {len(b['publikasi'])}; "
      f"entri {sum(map(len, a['entri'].values()))} -> {sum(map(len, b['entri'].values()))}")
print("publikasi hilang:", sorted(set(a["publikasi"]) - set(b["publikasi"])),
      "| baru:", sorted(set(b["publikasi"]) - set(a["publikasi"])))

berubah_entri, berubah_medan = [], defaultdict(list)
for pid in sorted(set(a["publikasi"]) | set(b["publikasi"])):
    la, lb = a["entri"].get(pid, []), b["entri"].get(pid, [])
    if Counter(map(tuple, la)) != Counter(map(tuple, lb)):
        berubah_entri.append(pid)
    pa, pb = a["publikasi"].get(pid, {}), b["publikasi"].get(pid, {})
    for m in MEDAN_PUB:
        if pa.get(m) != pb.get(m):
            berubah_medan[m].append(pid)

luar = [p for p in berubah_entri if p not in TARGET]
print(f"\nPublikasi dengan entri berubah: {len(berubah_entri)} "
      f"(target {len([p for p in berubah_entri if p in TARGET])}/8, DI LUAR TARGET {len(luar)})")
for p in luar:
    print("   DI LUAR TARGET:", p, b["publikasi"].get(p, a["publikasi"].get(p))["judul"][:60])
print("Medan publikasi berubah:")
for m in MEDAN_PUB:
    d = berubah_medan.get(m, [])
    print(f"   {m:<22} {len(d):>4}  di luar target: {len([p for p in d if p not in TARGET])}")

print(f"\n{'publikasi':<34}{'sebelum':>8}{'sesudah':>8}{'tetap':>7}{'berubah':>8}{'hilang':>7}{'tambah':>7}"
      f"{'hal.OCR':>8}  per tipe sesudah")
baris_tsv = []
for pid, nama in TARGET.items():
    la, lb = a["entri"].get(pid, []), b["entri"].get(pid, [])
    h = banding_pub(la, lb)
    tipe = Counter(e[0] for e in lb)
    print(f"{nama:<34}{len(la):>8}{len(lb):>8}{h['tetap']:>7}{len(h['berubah']):>8}{len(h['hilang']):>7}"
          f"{len(h['bertambah']):>7}{str(b['publikasi'][pid]['halaman_ocr']):>8}  {dict(tipe)}")
    for lama, baru in h["berubah"]:
        print(f"     BERUBAH {lama[:6]}\n          -> {baru[:6]}")
    for e in h["hilang"]:
        print(f"     HILANG  {e[:6]}")
    for e in h["bertambah"]:
        baris_tsv.append([pid, nama] + ["" if x is None else str(x) for x in e[:6]])
if len(sys.argv) > 3:
    with open(sys.argv[3], "w", encoding="utf-8") as f:
        f.write("pub_id\tpublikasi\ttipe\tnomor\tjudul\thalaman\thalaman_fisik\tsumber\n")
        for r in baris_tsv:
            f.write("\t".join(x.replace("\t", " ") for x in r) + "\n")
    print(f"\n{len(baris_tsv)} entri bertambah -> {sys.argv[3]}")
