"""Potret isi DB (HANYA BACA) untuk perbandingan per kunci.

  python potret_kunci.py uji|produksi <keluaran.json>

Entri disimpan per publikasi sebagai tuple lengkap; publikasi dengan medan
yang relevan (tanpa stempel waktu ekstraksi, yang pasti berganti di --paksa).
"""
import json
import sys

sys.path.insert(0, "C:/sistem-pencarian-bps")
import sqlalchemy as sa  # noqa: E402

from app.config import Config, KonfigurasiUji  # noqa: E402

sasaran, keluaran = sys.argv[1], sys.argv[2]
url = {"uji": KonfigurasiUji, "produksi": Config}[sasaran].SQLALCHEMY_DATABASE_URI
mesin = sa.create_engine(url)
with mesin.connect() as k:
    nama = k.execute(sa.text("SELECT DATABASE()")).scalar()
    pub = {}
    for r in k.execute(sa.text(
            "SELECT id, domain, judul, abstrak, halaman_ocr, galat_ekstraksi, catatan_ekstraksi, "
            "teks_ternormalisasi, sidik_ukuran, sidik_mtime, updt_date_diproses FROM publikasi")).mappings():
        pub[r["id"]] = {k2: (str(v) if v is not None and not isinstance(v, (int, str)) else v)
                        for k2, v in r.items() if k2 != "id"}
    entri = {}
    for r in k.execute(sa.text(
            "SELECT publikasi_id, tipe, nomor, judul, halaman, halaman_fisik, sumber, teks_ternormalisasi "
            "FROM entri_dokumen ORDER BY id")):
        entri.setdefault(r[0], []).append(list(r[1:]))
    versi = k.execute(sa.text("SELECT versi FROM versi_data")).scalar()
json.dump({"database": nama, "versi_data": versi, "publikasi": pub, "entri": entri},
          open(keluaran, "w", encoding="utf-8"), ensure_ascii=False)
print(f"{nama}: {len(pub)} publikasi, {sum(map(len, entri.values()))} entri, versi_data {versi} -> {keluaran}")
