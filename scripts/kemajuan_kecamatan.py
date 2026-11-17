"""Kemajuan penarikan publikasi kecamatan ke DATABASE UJI (hanya membaca).

    venv\\Scripts\\python.exe scripts\\kemajuan_kecamatan.py

Mencetak per wilayah: publikasi kecamatan di database uji, PDF yang sudah ada
di disk, yang sudah diekstrak, dan jumlah entrinya; lalu 15 baris terakhir log
run terbaru di data/log_pembaruan/. Tidak menulis apa pun, tidak menyentuh
produksi. "Kecamatan" = judul cocok dengan pola kecualikan_judul yang aktif.
"""
import glob
import os
import sys

DIR_PROYEK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR_PROYEK)
os.chdir(DIR_PROYEK)

from sqlalchemy import func  # noqa: E402

from app import create_app  # noqa: E402
from app.config import KonfigurasiUji  # noqa: E402
from app.models import EntriDokumen, Publikasi, db  # noqa: E402
from app.services.sumber_bps import berkas_pdf_valid, path_pdf  # noqa: E402
from app.services.wilayah import pola_judul_dikecualikan  # noqa: E402


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pola = pola_judul_dikecualikan()
    app = create_app(KonfigurasiUji)
    with app.app_context():
        entri = dict(db.session.query(EntriDokumen.publikasi_id, func.count())
                     .group_by(EntriDokumen.publikasi_id).all())
        per = {}
        for p in Publikasi.query.order_by(Publikasi.domain).all():
            if not any(r.search((p.judul or "").strip()) for r, _ in pola):
                continue
            d = per.setdefault(p.domain, [0, 0, 0, 0, 0])
            d[0] += 1
            d[1] += berkas_pdf_valid(path_pdf(p.domain, p.id))
            d[2] += p.diekstrak_pada is not None
            d[3] += entri.get(p.id, 0)
            d[4] += p.diekstrak_pada is not None and not entri.get(p.id)
        db.session.commit()

    print("Database UJI - publikasi kecamatan")
    print(f"{'wilayah':<8}{'publikasi':>10}{'PDF ada':>9}{'diekstrak':>11}{'entri':>9}{'0 entri':>9}")
    total = [0] * 5
    for kode, d in sorted(per.items()):
        print(f"{kode:<8}{d[0]:>10}{d[1]:>9}{d[2]:>11}{d[3]:>9}{d[4]:>9}")
        total = [a + b for a, b in zip(total, d)]
    print(f"{'TOTAL':<8}{total[0]:>10}{total[1]:>9}{total[2]:>11}{total[3]:>9}{total[4]:>9}")

    logs = sorted(glob.glob(os.path.join("data", "log_pembaruan", "*.log")))
    if logs:
        print(f"\nLog terbaru: {logs[-1]}")
        with open(logs[-1], encoding="utf-8", errors="replace") as f:
            for baris in f.readlines()[-15:]:
                print("  " + baris.rstrip())
    kunci = os.path.join("data", "pembaruan.lock")
    print("\nPembaruan SEDANG BERJALAN (data/pembaruan.lock ada)." if os.path.exists(kunci)
          else "\nTidak ada pembaruan yang berjalan.")


if __name__ == "__main__":
    main()
