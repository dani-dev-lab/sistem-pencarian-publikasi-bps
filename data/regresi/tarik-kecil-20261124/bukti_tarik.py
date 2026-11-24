"""HANYA MEMBACA database uji: apa yang ditambahkan tarik kecil 6301/2024."""
import sys
sys.path.insert(0, r"c:\sistem-pencarian-bps")
import sqlalchemy as sa
from app.config import KonfigurasiUji

m = sa.create_engine(KonfigurasiUji.SQLALCHEMY_DATABASE_URI)
q = lambda s: m.connect().execute(sa.text(s)).fetchall()  # noqa: E731
BARU = "p.domain='6301' AND YEAR(p.tanggal_rilis)=2024"
print("publikasi total", q("SELECT COUNT(*) FROM publikasi")[0][0])
print("baru (6301 rilis 2024)", q(f"SELECT COUNT(*) FROM publikasi p WHERE {BARU}")[0][0])
print("rilis selain 2025-2026 di luar 6301/2024",
      q(f"SELECT COUNT(*) FROM publikasi p WHERE YEAR(p.tanggal_rilis) NOT IN (2025,2026) AND NOT ({BARU})")[0][0])
print("entri publikasi baru", q(f"SELECT COUNT(*) FROM entri_dokumen e JOIN publikasi p ON p.id=e.publikasi_id WHERE {BARU}")[0][0])
print("entri publikasi lain", q(f"SELECT COUNT(*) FROM entri_dokumen e JOIN publikasi p ON p.id=e.publikasi_id WHERE NOT ({BARU})")[0][0])
print("publikasi lain diekstrak hari ini", q(f"SELECT COUNT(*) FROM publikasi p WHERE NOT ({BARU}) AND p.diekstrak_pada >= '2026-11-24 13:57'")[0][0])
print("publikasi lain metadata diubah hari ini", q(f"SELECT COUNT(*) FROM publikasi p WHERE NOT ({BARU}) AND p.updated_at >= '2026-11-24 13:57'")[0][0])
print("OCR baru", q(f"SELECT COUNT(*), COALESCE(SUM(halaman_ocr),0) FROM publikasi p WHERE {BARU} AND halaman_ocr>0")[0])
print("versi_data", q("SELECT * FROM versi_data")[0])
print("\nper publikasi: kec | entri | tabel/gambar/lampiran/isi | bernomor(non-isi) | hal cetak | hal PDF asli | perkiraan")
for r in q(f"""SELECT p.id, p.judul, p.kecamatan, COUNT(e.id),
  SUM(e.tipe='tabel'), SUM(e.tipe='gambar'), SUM(e.tipe='lampiran'), SUM(e.tipe='isi'),
  SUM(e.tipe<>'isi' AND e.nomor IS NOT NULL AND e.nomor<>''), SUM(e.tipe<>'isi'),
  SUM(e.halaman IS NOT NULL AND e.halaman<>''), SUM(e.halaman_fisik IS NOT NULL AND NOT e.halaman_fisik_perkiraan),
  SUM(e.halaman_fisik_perkiraan)
  FROM publikasi p LEFT JOIN entri_dokumen e ON e.publikasi_id=p.id WHERE {BARU} GROUP BY p.id ORDER BY p.judul"""):
    print(f"{r[0][:8]} {r[1][:62]:62} {'K' if r[2] else '-'} {r[3]:4} {r[4]}/{r[5]}/{r[6]}/{r[7]} "
          f"nomor {r[8]}/{r[9]} hal {r[10]} fisik {r[11]} perk {r[12]}")


def mutu(syarat, nama):
    r = q(f"""SELECT COUNT(DISTINCT p.id), COUNT(e.id),
      SUM(e.tipe<>'isi'), SUM(e.tipe<>'isi' AND e.nomor IS NOT NULL AND e.nomor<>''),
      SUM(e.halaman IS NOT NULL AND e.halaman<>''), SUM(e.halaman_fisik IS NOT NULL),
      SUM(e.halaman_fisik IS NOT NULL AND NOT e.halaman_fisik_perkiraan),
      SUM((e.halaman IS NULL OR e.halaman='') AND e.halaman_fisik IS NULL)
      FROM publikasi p JOIN entri_dokumen e ON e.publikasi_id=p.id WHERE {syarat}""")[0]
    pub, n, non, nom, hal, fis, asli, tanpa = (int(x or 0) for x in r)
    print(f"{nama:38} pub {pub:3} entri {n:5} ({n/pub:.0f}/pub) | non-isi bernomor {nom/non:.1%} | "
          f"hal cetak {hal/n:.1%} | hal PDF {fis/n:.1%} (asli {asli/n:.1%}) | tanpa keduanya {tanpa/n:.1%}")


print()
mutu(BARU + " AND p.kecamatan IS NULL", "6301 rilis 2024, kab/kota")
mutu("p.domain='6301' AND YEAR(p.tanggal_rilis) IN (2025,2026) AND p.kecamatan IS NULL", "6301 rilis 2025-2026, kab/kota")
mutu(BARU + " AND p.kecamatan IS NOT NULL", "6301 rilis 2024, kecamatan")
mutu("p.domain='6301' AND YEAR(p.tanggal_rilis) IN (2025,2026) AND p.kecamatan IS NOT NULL", "6301 rilis 2025-2026, kecamatan")
