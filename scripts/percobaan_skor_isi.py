"""Percobaan skor: entri `isi` (judul bab) vs tabel/gambar/lampiran.

PERCOBAAN, bukan kode produksi. Skrip ini TIDAK mengubah mesin_pencari; ia
hanya membaca daftar kandidat lengkap yang dihitung mesin produksi, lalu
menyusun ulang peringkatnya menurut alternatif yang diuji. Keputusan
final menunggu uji coba petugas PST (10 Nov 2026).

Latar: untuk "penduduk tanah laut", 7 hasil teratas adalah judul bab;
tabel pertama baru muncul jauh di bawah.

Varian yang dibandingkan:
  A  sekarang: urut skor, ambang 75 (ditemukan) / 50 (saran)
  B  bobot pengali entri isi (0,9; disapu juga 0,95/0,85/0,8), lalu urut
     ulang dan DIKELOMPOKKAN ULANG dengan ambang yang sama, sehingga
     dampaknya ke ambang 75/50 terlihat
  C  urutan tampil: di dalam tiap kelompok (ditemukan, saran) tabel/
     gambar/lampiran ditampilkan lebih dulu, skor dan ambang tidak berubah

Jalur kueri sama dengan halaman /hasil (pencarian_wilayah): kueri bernama
wilayah memasang filter dan kata wilayah tidak dinilai.

Jalankan:  venv/Scripts/python.exe scripts/percobaan_skor_isi.py
Hasil   :  data/regresi/percobaan-skor-isi-<tanggal>.json (+ ringkasan di layar)
"""

import json
import os
import sys
from datetime import date, datetime

DIR_PROYEK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DIR_PROYEK)

from app import create_app                                  # noqa: E402
from app.config import KonfigurasiUji                       # noqa: E402
from app.services import mesin_pencari, pencarian_wilayah   # noqa: E402
from app.services.preprocessing import normalisasi_token    # noqa: E402

AMBANG_DITEMUKAN = mesin_pencari.AMBANG_DITEMUKAN
AMBANG_SARAN = mesin_pencari.AMBANG_SARAN
BATAS = mesin_pencari.BATAS_HASIL
TOP = 10
BOBOT_UTAMA = 0.9
SAPUAN = (1.0, 0.95, 0.9, 0.85, 0.8)


def _kueri_uji():
    """12 kueri uji yang sama dengan ukur_kinerja.py (dibaca dari sana)."""
    src = open(os.path.join(DIR_PROYEK, "scripts", "ukur_kinerja.py"), encoding="utf-8").read()
    awal = src.index("KUERI = [")
    return eval(src[awal + 8: src.index("]", awal) + 1])  # noqa: S307 - berkas sendiri


KUERI_WILAYAH = [
    "penduduk miskin tala",
    "inflasi bjm",
    "pdrb hss",
    "jumlah sekolah banjar",
    "penduduk kotabaru",
]


def kandidat(kueri):
    """Semua entri yang lolos ambang saran (>= 50), dihitung mesin produksi,
    di cakupan wilayah yang sama dengan halaman hasil."""
    f = pencarian_wilayah.tentukan_filter(kueri)
    token = normalisasi_token(f["kueri_topik"])
    k = mesin_pencari.korpus()
    baris = k.entri if f["kode"] is None else k.entri_per_domain.get(f["kode"], ())
    hasil, _ = mesin_pencari._cari_entri(token, baris, AMBANG_SARAN)
    return f, hasil


def _urut(daftar, kunci_skor):
    return sorted(daftar, key=lambda h: (-kunci_skor(h),
                                         -(h["tanggal_rilis"] or date.min).toordinal()))


def tampilan(hasil, bobot_isi=1.0, tabel_dulu=False):
    """Daftar yang tampil di halaman (ditemukan lalu saran, masing-masing
    maks. 20), plus jumlah per kelompok."""
    def skor(h):
        return round(h["skor"] * (bobot_isi if h["tipe"] == "isi" else 1.0), 1)
    ada = [h for h in hasil if skor(h) >= AMBANG_SARAN]
    urut = _urut(ada, skor)
    ditemukan = [h for h in urut if skor(h) >= AMBANG_DITEMUKAN]
    saran = [h for h in urut if skor(h) < AMBANG_DITEMUKAN]
    if tabel_dulu:
        # sorted() stabil: urutan skor di dalam tiap golongan dipertahankan.
        ditemukan = sorted(ditemukan, key=lambda h: h["tipe"] == "isi")
        saran = sorted(saran, key=lambda h: h["tipe"] == "isi")
    tampil = ditemukan[:BATAS] + saran[:BATAS]
    return {
        "tampil": [(h["entri_id"], h["tipe"], skor(h), h["judul"]) for h in tampil],
        "ditemukan": len(ditemukan),
        "saran": len(saran),
        "tersembunyi": len(hasil) - len(ada),
        "isi_ditemukan": sum(h["tipe"] == "isi" for h in ditemukan),
    }


def ringkas(t):
    top = t["tampil"][:TOP]
    pertama = next((i + 1 for i, x in enumerate(t["tampil"]) if x[1] != "isi"), None)
    return {
        "isi_di_top10": sum(x[1] == "isi" for x in top),
        "nonisi_di_top10": sum(x[1] != "isi" for x in top),
        "peringkat_nonisi_pertama": pertama,
        "ditemukan": t["ditemukan"], "saran": t["saran"], "tersembunyi": t["tersembunyi"],
        "isi_ditemukan": t["isi_ditemukan"],
        "top10": [f"{x[2]:5.1f} {x[1][:3]} {x[3][:70]}" for x in top],
    }


def main():
    app = create_app(KonfigurasiUji)
    semua = list(dict.fromkeys(_kueri_uji() + KUERI_WILAYAH))
    keluaran = {"dijalankan": datetime.now().isoformat(timespec="seconds"),
                "ambang": [AMBANG_DITEMUKAN, AMBANG_SARAN], "kueri": {}}
    with app.app_context():
        for q in semua:
            f, hasil = kandidat(q)
            rek = {
                "filter": f["kode"], "kueri_topik": f["kueri_topik"],
                "kandidat": len(hasil),
                "kandidat_isi": sum(h["tipe"] == "isi" for h in hasil),
                "A_sekarang": ringkas(tampilan(hasil)),
                "B_bobot_isi_0_9": ringkas(tampilan(hasil, bobot_isi=BOBOT_UTAMA)),
                "C_tabel_dulu": ringkas(tampilan(hasil, tabel_dulu=True)),
                # Peringkat tabel/gambar/lampiran PERTAMA di seluruh daftar urut
                # skor (tanpa batas 20), untuk kasus "tabel muncul di ~72".
                "A_peringkat_nonisi_tanpa_batas": next(
                    (i + 1 for i, h in enumerate(hasil) if h["tipe"] != "isi"), None),
                "sapuan": {str(b): ringkas(tampilan(hasil, bobot_isi=b)) | {"top10": None}
                           for b in SAPUAN},
            }
            keluaran["kueri"][q] = rek
            a, b, c = rek["A_sekarang"], rek["B_bobot_isi_0_9"], rek["C_tabel_dulu"]
            print(f"{q[:34]:34} filter={f['kode'] or '-':4} | isi/top10 A={a['isi_di_top10']:2} "
                  f"B={b['isi_di_top10']:2} C={c['isi_di_top10']:2} | non-isi pertama "
                  f"A={a['peringkat_nonisi_pertama']} B={b['peringkat_nonisi_pertama']} "
                  f"C={c['peringkat_nonisi_pertama']} | ditemukan/saran A={a['ditemukan']}/{a['saran']} "
                  f"B={b['ditemukan']}/{b['saran']} (+{b['tersembunyi']} tersembunyi)")

    nama = os.path.join(DIR_PROYEK, "data", "regresi",
                        f"percobaan-skor-isi-{datetime.now():%Y%m%d}.json")
    with open(nama, "w", encoding="utf-8") as f_:
        json.dump(keluaran, f_, ensure_ascii=False, indent=1, default=str)
    print("Hasil ->", os.path.relpath(nama, DIR_PROYEK))


if __name__ == "__main__":
    main()
