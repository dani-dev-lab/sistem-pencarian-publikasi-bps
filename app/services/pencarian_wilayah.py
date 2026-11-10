"""Filter wilayah di pencarian: dropdown + deteksi nama wilayah dari kueri.

Aturan (keputusan pemilik project, 10 Nov 2026):

1. Petugas memilih wilayah lewat dropdown (`w`), ATAU nama/singkatan wilayah
   di kueri ("penduduk tanah laut", "tala", "hss") memasang filter itu secara
   otomatis. Filter otomatis ditandai pita "dipasang otomatis" dan bisa
   dibatalkan.
2. Kata wilayah yang terdeteksi TIDAK ikut dinilai terhadap judul entri.
   Tabel kab/kota jarang menyebut nama wilayahnya sendiri ("Jumlah Penduduk
   Menurut Kecamatan"), sehingga kata itu hanya menurunkan skor entri yang
   benar dan menaikkan entri provinsi yang kebetulan menyebutnya.
3. Entri publikasi provinsi yang cocok dengan kueri tanpa kata wilayah
   ditampilkan terpisah ("Juga ada di publikasi provinsi").
4. "Semua wilayah" + kueri tanpa nama wilayah = pencarian yang sama persis
   dengan sebelum filter ada.

Parameter URL (semua berfungsi tanpa JavaScript):
  w        kode wilayah dari dropdown; kosong = Semua wilayah
  wo       kode yang DIPASANG OTOMATIS di halaman sebelumnya. Dropdown di
           halaman hasil menampilkan wilayah otomatis itu, sehingga form
           mengirim w=wo walaupun petugas tidak memilihnya. w == wo berarti
           "tidak dipilih petugas", jadi deteksi diulang terhadap kueri baru.
  abaikan  kode wilayah yang deteksi otomatisnya dibatalkan petugas
"""

import time

from app.services import mesin_pencari
from app.services.preprocessing import normalisasi_token, tokenkan
from app.services.wilayah import DOMAIN_PROVINSI, deteksi, wilayah_aktif


def _kode_valid(kode):
    return kode if kode in {w["kode"] for w in wilayah_aktif()} else None


def tentukan_filter(kueri, w=None, wo=None, abaikan=None):
    """Putuskan wilayah filter untuk satu kueri. Tidak menyentuh database.

    Return dict:
      kode         wilayah yang aktif, None = semua wilayah
      nama         nama tampilnya
      sumber       "pilihan" (dropdown) | "otomatis" (dari kueri) | None
      teks         kata wilayah di kueri yang memasang/menyertai filter
      kueri_topik  kueri yang dinilai; tanpa kata wilayah filter aktif
      terdeteksi   semua temuan deteksi (untuk catatan "lebih dari satu")
      abaikan      kode yang deteksinya dibatalkan (diteruskan ke form)
    """
    pilihan = _kode_valid(w)
    if pilihan is not None and pilihan == wo:
        pilihan = None          # sisa wilayah otomatis, bukan pilihan petugas
    abaikan = _kode_valid(abaikan)

    token = tokenkan(kueri)
    temuan = deteksi(token)
    kode_terdeteksi = list(dict.fromkeys(t["kode"] for t in temuan))

    sumber = None
    kode = pilihan
    if pilihan is not None:
        sumber = "pilihan"
    elif len(kode_terdeteksi) == 1 and kode_terdeteksi[0] != abaikan:
        kode = kode_terdeteksi[0]
        sumber = "otomatis"

    # Kata wilayah dibuang HANYA kalau wilayahnya sama dengan filter aktif.
    # Tanpa filter (Semua wilayah, atau deteksi dibatalkan) kueri dinilai
    # apa adanya - sama dengan perilaku sebelum filter ada.
    buang = [t for t in temuan if t["kode"] == kode]
    if buang:
        dibuang = set()
        for t in buang:
            dibuang.update(range(t["awal"], t["akhir"]))
        kueri_topik = " ".join(x for i, x in enumerate(token) if i not in dibuang)
    else:
        kueri_topik = kueri

    nama = next((w_["nama"] for w_ in wilayah_aktif() if w_["kode"] == kode), None)
    return {
        "kode": kode,
        "nama": nama,
        "sumber": sumber,
        "teks": ", ".join(t["teks"] for t in buang),
        "kueri_topik": kueri_topik,
        "terdeteksi": temuan,
        "lebih_dari_satu": len(kode_terdeteksi) > 1,
        "abaikan": abaikan,
    }


def cari(kueri, w=None, wo=None, abaikan=None):
    """Pencarian lengkap dengan filter wilayah. Return dict hasil cari()
    ditambah `filter` dan `hanya_wilayah`."""
    mulai = time.perf_counter()
    f = tentukan_filter(kueri, w, wo, abaikan)

    if f["kode"] is None:
        hasil = mesin_pencari.cari(kueri)
        hanya_wilayah = False
    elif not normalisasi_token(f["kueri_topik"]):
        # Kueri hanya berisi nama wilayah ("tanah laut"): tidak ada topik
        # untuk dinilai, jadi tampilkan publikasi wilayah itu, terbaru dulu.
        hasil = mesin_pencari.cari("")
        hasil["publikasi"] = mesin_pencari.publikasi_wilayah(f["kode"])
        hasil["jumlah_publikasi"] = len(hasil["publikasi"])
        hasil["sorot"] = mesin_pencari.kata_untuk_sorot(kueri)
        hasil["waktu_ms"] = (time.perf_counter() - mulai) * 1000
        hanya_wilayah = True
    else:
        hasil = mesin_pencari.cari(
            f["kueri_topik"], domain=f["kode"],
            provinsi=f["kode"] != DOMAIN_PROVINSI)
        hanya_wilayah = False

    hasil["kueri"] = kueri          # yang diketik petugas, untuk tampilan dan log
    hasil["filter"] = f
    hasil["hanya_wilayah"] = hanya_wilayah
    return hasil
