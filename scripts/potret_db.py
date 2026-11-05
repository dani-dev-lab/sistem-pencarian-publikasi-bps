"""Potret isi publikasi + entri dari database, dan pembanding antar-potret.

Dipakai sebagai baseline regresi saat pipeline diubah: isi yang sama harus
menghasilkan potret yang IDENTIK, termasuk urutan entrinya.

Potret mengambil langsung dari MySQL, bukan dari berkas perantara, karena yang
dipakai pencarian adalah isi database.

Hanya MEMBACA database. Berkas keluaran ditulis atomik.

Jalankan:  venv/Scripts/python.exe scripts/potret_db.py ekspor data/regresi/potret.json
           venv/Scripts/python.exe scripts/potret_db.py banding A.json B.json
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

KOLOM_ENTRI = ("tipe", "nomor", "judul", "halaman", "halaman_fisik", "sumber")

# Berapa perbedaan yang dicetak per publikasi. Hitungan totalnya tetap utuh.
MAKS_CONTOH = 5


def ekspor(path):
    from app import create_app
    from app.models import EntriDokumen, Publikasi, db

    app = create_app()
    with app.app_context():
        publikasi = {}
        for p in Publikasi.query.order_by(Publikasi.id).all():
            publikasi[p.id] = {
                "pub_id": p.id,
                "judul": p.judul,
                "tanggal_rilis": p.tanggal_rilis.isoformat() if p.tanggal_rilis else None,
                "teks_ternormalisasi": p.teks_ternormalisasi,
                "jumlah_entri": 0,
                "entri": [],
            }

        baris = (
            db.session.query(
                EntriDokumen.publikasi_id,
                *(getattr(EntriDokumen, k) for k in KOLOM_ENTRI),
                EntriDokumen.teks_ternormalisasi,
            )
            # Urutan id = urutan penyisipan = urutan keluaran parser.
            .order_by(EntriDokumen.publikasi_id, EntriDokumen.id)
            .all()
        )
        for pid, *kolom, teks in baris:
            pub = publikasi[pid]
            pub["entri"].append({**dict(zip(KOLOM_ENTRI, kolom)),
                                 "teks_ternormalisasi": teks})
            pub["jumlah_entri"] += 1

    keluaran = {
        "dibuat_pada": datetime.now().isoformat(timespec="seconds"),
        "jumlah_publikasi": len(publikasi),
        "jumlah_entri": sum(p["jumlah_entri"] for p in publikasi.values()),
        "publikasi": list(publikasi.values()),
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    sementara = path + ".tmp"
    with open(sementara, "w", encoding="utf-8", newline="\n") as f:
        json.dump(keluaran, f, ensure_ascii=False, indent=1)
    os.replace(sementara, path)

    with open(path, "rb") as f:
        sidik = hashlib.sha256(f.read()).hexdigest()
    print(f"Potret  : {path}")
    print(f"Isi     : {keluaran['jumlah_publikasi']} publikasi, "
          f"{keluaran['jumlah_entri']} entri")
    print(f"SHA-256 : {sidik}")


def _muat(path):
    with open(path, encoding="utf-8") as f:
        return {p["pub_id"]: p for p in json.load(f)["publikasi"]}


def beda_potret(a, b):
    """Daftar perbedaan antara dua potret ({pub_id: publikasi}).

    Tiap perbedaan berbentuk (pub_id, keterangan). Entri dibandingkan menurut
    posisinya, jadi urutan yang berubah juga terhitung sebagai perbedaan.
    """
    beda = []
    for pid in sorted(set(a) - set(b)):
        beda.append((pid, "publikasi hilang dari potret kedua"))
    for pid in sorted(set(b) - set(a)):
        beda.append((pid, "publikasi tambahan di potret kedua"))

    for pid in sorted(set(a) & set(b)):
        pa, pb = a[pid], b[pid]
        for kolom in ("judul", "tanggal_rilis", "teks_ternormalisasi"):
            if pa.get(kolom) != pb.get(kolom):
                beda.append((pid, f"publikasi.{kolom}: "
                                  f"{str(pa.get(kolom))[:60]!r} -> "
                                  f"{str(pb.get(kolom))[:60]!r}"))

        ea, eb = pa["entri"], pb["entri"]
        if len(ea) != len(eb):
            beda.append((pid, f"jumlah entri: {len(ea)} -> {len(eb)}"))
        for i, (x, y) in enumerate(zip(ea, eb)):
            if x == y:
                continue
            kolom = [k for k in x if x.get(k) != y.get(k)]
            rincian = "; ".join(f"{k}: {str(x.get(k))[:50]!r} -> {str(y.get(k))[:50]!r}"
                                for k in kolom)
            beda.append((pid, f"entri #{i}: {rincian}"))
    return beda


def banding(path_a, path_b):
    a, b = _muat(path_a), _muat(path_b)
    beda = beda_potret(a, b)

    print(f"A: {path_a}  ({len(a)} publikasi, "
          f"{sum(p['jumlah_entri'] for p in a.values())} entri)")
    print(f"B: {path_b}  ({len(b)} publikasi, "
          f"{sum(p['jumlah_entri'] for p in b.values())} entri)")
    print()

    if not beda:
        print("IDENTIK")
        return 0

    per_pub = {}
    for pid, teks in beda:
        per_pub.setdefault(pid, []).append(teks)
    print(f"BERBEDA: {len(beda)} perbedaan pada {len(per_pub)} publikasi")
    for pid, daftar in per_pub.items():
        judul = (a.get(pid) or b.get(pid))["judul"][:60]
        print(f"\n  {pid}  {judul}  ({len(daftar)} perbedaan)")
        for teks in daftar[:MAKS_CONTOH]:
            print(f"    {teks}")
        if len(daftar) > MAKS_CONTOH:
            print(f"    ... dan {len(daftar) - MAKS_CONTOH} lainnya")
    return 1


def main():
    arg = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = arg.add_subparsers(dest="perintah", required=True)
    sub.add_parser("ekspor").add_argument("berkas")
    b = sub.add_parser("banding")
    b.add_argument("a")
    b.add_argument("b")
    opsi = arg.parse_args()

    if opsi.perintah == "ekspor":
        ekspor(opsi.berkas)
    else:
        sys.exit(banding(opsi.a, opsi.b))


if __name__ == "__main__":
    main()
