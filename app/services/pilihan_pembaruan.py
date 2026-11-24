"""Pilihan penarikan: wilayah, jenis publikasi, tahun rilis (24 Nov 2026).

Satu aturan untuk dua jalan masuk: formulir di /admin/perbarui dan argumen
scripts/perbarui.py (--wilayah, --jenis, --tahun-min, --tahun-maks), yang
juga dipakai perbarui-data.bat. Formulir menerjemahkan pilihannya menjadi
argumen perbarui.py lewat Pilihan.argumen(), sehingga keduanya berjalan di
jalur yang sama.

Tanpa pilihan apa pun = bawaan() = perilaku pembaruan rutin sebelum formulir
ada: semua wilayah aktif, publikasi kabupaten/kota dan Kecamatan Dalam Angka,
rilis tahun lalu sampai tahun ini. Pilihan yang sama dengan bawaan tidak
diterjemahkan menjadi argumen sama sekali, jadi tombol "Mulai pembaruan"
dengan formulir bawaan menjalankan perintah yang persis sama seperti dulu.

Validasi di sini (bukan hanya di browser): kode wilayah harus wilayah aktif
di data/wilayah.json, tahun harus di daftar_tahun(), Dari <= Sampai, minimal
satu wilayah, dan kalau ada kabupaten/kota terpilih, minimal satu jenis.
"""

import json
from dataclasses import dataclass
from datetime import date

from app.config import Config
from app.services.sumber_bps import JUMLAH_TAHUN
from app.services.wilayah import DOMAIN_PROVINSI, kecamatan_dari_judul, wilayah_aktif

JENIS_KABKOTA = "kabkota"
JENIS_KECAMATAN = "kecamatan"
SEMUA_JENIS = (JENIS_KABKOTA, JENIS_KECAMATAN)
NAMA_JENIS = {JENIS_KABKOTA: "Publikasi kabupaten/kota", JENIS_KECAMATAN: "Kecamatan Dalam Angka"}

# Tahun rilis paling awal yang boleh dipilih, kalau `tahun_min_pilihan` tidak
# ada di data/wilayah.json. Nilai di berkas itu yang berlaku (Tim IT boleh
# mengubahnya tanpa mengubah kode).
TAHUN_MIN_PILIHAN_BAWAAN = 2020

# Tahun rilis yang mutu pembacaan PDF-nya sudah diuji (korpus 2025-2026).
# Pilihan "Dari" sebelum tahun ini diberi catatan di formulir dan di hasil cek.
TAHUN_TERUJI = 2025


class PilihanTidakSah(ValueError):
    """Pilihan ditolak. `galat` = daftar pesan untuk ditampilkan apa adanya."""

    def __init__(self, galat):
        super().__init__("; ".join(galat))
        self.galat = list(galat)


def tahun_ini():
    return date.today().year  # noqa: DTZ011 - tahun lokal memang yang dimaksud


def tahun_min_pilihan(path=None):
    """`tahun_min_pilihan` dari data/wilayah.json. Isi yang salah ditolak dengan
    pesan (SystemExit), seperti isi wilayah.json lainnya."""
    path = path or Config.FILE_WILAYAH
    try:
        with open(path, encoding="utf-8") as f:
            nilai = json.load(f).get("tahun_min_pilihan", TAHUN_MIN_PILIHAN_BAWAAN)
    except (OSError, ValueError) as e:
        raise SystemExit(f"{path} tidak bisa dibaca: {e}") from None
    if isinstance(nilai, bool) or not isinstance(nilai, int) or not 1990 <= nilai <= 2100:
        raise SystemExit(f"{path}: tahun_min_pilihan harus tahun (angka), bukan {nilai!r}")
    return nilai


def daftar_tahun(path=None):
    """Tahun rilis yang boleh dipilih: tahun_min_pilihan sampai tahun berjalan.
    Tahun yang belum tiba tidak pernah ada. Tahun bawaan "Dari" selalu ikut,
    walaupun tahun_min_pilihan diisi lebih besar."""
    sekarang = tahun_ini()
    awal = min(tahun_min_pilihan(path), sekarang - (JUMLAH_TAHUN - 1))
    return list(range(awal, sekarang + 1))


def _wilayah_aktif(path=None):
    return [(w["kode"], w["nama"]) for w in wilayah_aktif(path)]


@dataclass(frozen=True)
class Pilihan:
    wilayah: tuple      # kode domain, urut seperti di wilayah.json
    jenis: tuple        # bagian dari SEMUA_JENIS, urut seperti SEMUA_JENIS
    dari: int
    sampai: int

    def tahun(self):
        return set(range(self.dari, self.sampai + 1))

    def wilayah_bawaan(self, path=None):
        return self.wilayah == tuple(k for k, _ in _wilayah_aktif(path))

    def jenis_bawaan(self):
        return self.jenis == SEMUA_JENIS

    def tahun_bawaan(self):
        sekarang = tahun_ini()
        return (self.dari, self.sampai) == (sekarang - (JUMLAH_TAHUN - 1), sekarang)

    def bawaan(self, path=None):
        return self.wilayah_bawaan(path) and self.jenis_bawaan() and self.tahun_bawaan()

    def menyaring_isi(self):
        """True kalau jenis/tahun bukan bawaan: publikasi di database juga harus
        disaring (rencana kerja, sampul, "tidak lagi di daftar"). Dengan bawaan,
        semuanya berjalan persis seperti sebelum ada pilihan."""
        return not (self.jenis_bawaan() and self.tahun_bawaan())

    def argumen(self, path=None):
        """Argumen perbarui.py. Bagian yang sama dengan bawaan tidak ditulis."""
        arg = []
        if not self.wilayah_bawaan(path):
            arg += ["--wilayah", ",".join(self.wilayah)]
        if not self.jenis_bawaan():
            arg += ["--jenis", ",".join(self.jenis)]
        if not self.tahun_bawaan():
            arg += ["--tahun-min", str(self.dari), "--tahun-maks", str(self.sampai)]
        return arg

    def cocok_jenis(self, kode, judul):
        """Publikasi domain `kode` berjudul `judul` termasuk jenis terpilih?
        Provinsi tidak punya publikasi kecamatan: selalu ikut."""
        if kode == DOMAIN_PROVINSI:
            return True
        kecamatan = kecamatan_dari_judul(judul) is not None
        return (JENIS_KECAMATAN if kecamatan else JENIS_KABKOTA) in self.jenis

    def ada_kabkota(self):
        return any(k != DOMAIN_PROVINSI for k in self.wilayah)

    def ke_dict(self, path=None):
        """Untuk ringkasan (pembaruan_terakhir.json) dan hasil cek."""
        nama = dict(_wilayah_aktif(path))
        return {"wilayah": list(self.wilayah),
                "nama_wilayah": [nama.get(k, k) for k in self.wilayah],
                "jenis": list(self.jenis), "tahun_dari": self.dari, "tahun_sampai": self.sampai,
                "bawaan": self.bawaan(path)}


def bawaan(path=None):
    sekarang = tahun_ini()
    return Pilihan(wilayah=tuple(k for k, _ in _wilayah_aktif(path)), jenis=SEMUA_JENIS,
                   dari=sekarang - (JUMLAH_TAHUN - 1), sampai=sekarang)


def _tahun(teks, label, galat):
    try:
        return int(str(teks).strip())
    except (TypeError, ValueError):
        galat.append(f"Tahun \"{label}\" tidak sah: {str(teks)[:20]!r}.")
        return None


def periksa(wilayah=None, jenis=None, dari=None, sampai=None, path=None):
    """Pilihan yang sudah diperiksa, atau PilihanTidakSah dengan semua galatnya.

    Argumen None = bawaan bagian itu. `wilayah`/`jenis` boleh list teks atau
    teks dipisah koma ("6301,6302"). Urutan dan duplikat tidak berpengaruh.
    """
    b = bawaan(path)
    galat = []
    aktif = _wilayah_aktif(path)
    kode_aktif = [k for k, _ in aktif]

    def pecah(nilai):
        if isinstance(nilai, str):
            nilai = [nilai]
        return [x.strip() for v in nilai for x in str(v).split(",") if x.strip()]

    if wilayah is None:
        pilih_wilayah = b.wilayah
    else:
        diminta = pecah(wilayah)
        asing = [k for k in diminta if k not in kode_aktif]
        if asing:
            galat.append("Kode wilayah tidak dikenal atau tidak aktif: "
                         + ", ".join(x[:12] for x in sorted(set(asing))[:5]) + ".")
        pilih_wilayah = tuple(k for k in kode_aktif if k in diminta)
        if not diminta:
            galat.append("Pilih minimal satu wilayah.")

    if jenis is None:
        pilih_jenis = b.jenis
    else:
        diminta = pecah(jenis)
        asing = [j for j in diminta if j not in SEMUA_JENIS]
        if asing:
            galat.append("Jenis publikasi tidak dikenal: " + ", ".join(x[:20] for x in sorted(set(asing))[:5])
                         + f" (yang sah: {', '.join(SEMUA_JENIS)}).")
        pilih_jenis = tuple(j for j in SEMUA_JENIS if j in diminta)

    t_dari = b.dari if dari is None else _tahun(dari, "Dari", galat)
    t_sampai = b.sampai if sampai is None else _tahun(sampai, "Sampai", galat)
    sah = daftar_tahun(path)
    for t, label in ((t_dari, "Dari"), (t_sampai, "Sampai")):
        if t is not None and t not in sah:
            galat.append(f"Tahun \"{label}\" {t} di luar pilihan ({sah[0]}-{sah[-1]}).")
    if t_dari is not None and t_sampai is not None and t_dari > t_sampai:
        galat.append(f"Tahun \"Dari\" ({t_dari}) tidak boleh sesudah \"Sampai\" ({t_sampai}).")

    if any(k != DOMAIN_PROVINSI for k in pilih_wilayah) and not pilih_jenis and not any(
            "Jenis publikasi tidak dikenal" in g for g in galat):
        galat.append("Kabupaten/kota terpilih, tetapi tidak ada jenis publikasi yang dicentang: "
                     "pilih \"Publikasi kabupaten/kota\", \"Kecamatan Dalam Angka\", atau keduanya.")

    if galat:
        raise PilihanTidakSah(galat)
    if not any(k != DOMAIN_PROVINSI for k in pilih_wilayah):
        # Hanya provinsi: jenis tidak berlaku (provinsi tidak punya publikasi
        # kecamatan), jadi tidak ikut menentukan argumen maupun saringan.
        pilih_jenis = SEMUA_JENIS
    return Pilihan(wilayah=pilih_wilayah, jenis=pilih_jenis, dari=t_dari, sampai=t_sampai)


def dari_formulir(form, path=None):
    """Pilihan dari request.form. Formulir lama tanpa penanda `formulir`
    (POST kosong) = bawaan, seperti tombol sebelum ada formulir."""
    if not form.get("formulir"):
        return bawaan(path)
    return periksa(wilayah=form.getlist("wilayah"), jenis=form.getlist("jenis"),
                   dari=form.get("dari", ""), sampai=form.get("sampai", ""), path=path)
