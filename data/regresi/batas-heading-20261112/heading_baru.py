"""Calon aturan baru cari_heading (BELUM dipasang di parser).

Heading Daftar dicari di HALAMAN DEPAN: 25 halaman pertama, ditambah
perpanjangan selama blok halaman Daftar belum putus. Sesudah halaman 25,
sebuah halaman meneruskan blok kalau:
  - halaman Daftar menurut _halaman_daftar (heading DAFTAR di 6 baris
    teratas, atau dot leader > 3 pada lanjutan langsung), ATAU
  - lanjutan langsung yang membawa KOP KOLOM Daftar di 3 baris teratas
    ("Tabel ... Halaman", "Gambar ... Page") - daftar KAK tidak punya dot
    leader sama sekali, yang selalu diulang hanya kop kolomnya, ATAU
  - halaman kosong / hampir kosong (<= 3 baris tanpa dot leader: halaman
    kosong pemisah, folio "xxvi", kop kolom tanpa isi) - tidak memutus blok,
    paling banyak 2 berturut-turut.
Halaman pertama sesudah halaman 25 yang bukan salah satu di atas mengakhiri
pencarian.

Pemeriksaan heading per halaman SAMA PERSIS dengan cari_heading lama; yang
berubah hanya sampai halaman mana pencarian berjalan. setdefault
mempertahankan heading pertama, jadi tipe yang sudah ditemukan di 25
halaman pertama tidak berubah: aturan ini hanya MENAMBAH daftar yang
terlewat.
"""
import re

from app.services import ekstraksi_pdf as ep

RE_KOP_KOLOM = re.compile(
    r"^(tabel|table|tables|gambar|figure|figures|grafik|lampiran|appendix|appendices)\b"
    r".*\b(halaman|hal\.?|page|pages)$", re.IGNORECASE)
MAKS_KOSONG = 2


def _status_depan(teks, lanjutan):
    """'daftar' | 'kosong' | None untuk satu halaman."""
    if ep._halaman_daftar(teks, lanjutan):
        return "daftar"
    if lanjutan and any(RE_KOP_KOLOM.match(t) for t in teks[:3]):
        return "daftar"
    if len(teks) <= 3 and ep._jumlah_dot_leader(" ".join(teks)) == 0:
        return "kosong"
    return None


def cari_heading_baru(pdf, jejak=None):
    ketemu = {}
    lanjutan = False
    kosong = 0
    for i in range(len(pdf.pages)):
        baris = ep._kelompokkan_baris(ep._kata_halaman(pdf.pages[i]))
        teks = [ep._teks_baris(b).strip() for b in baris]
        status = _status_depan(teks, lanjutan)
        if i >= ep.BATAS_HALAMAN_CARI:
            kosong = kosong + 1 if status == "kosong" else 0
            if status is None or kosong > MAKS_KOSONG:
                if jejak is not None:
                    jejak["berhenti_di"] = i + 1
                break
        for b in baris[:6]:
            cocok = ep.RE_HEADING.match(ep._teks_baris(b).strip())
            if cocok:
                for tipe in ep._tipe_dari_heading(cocok.group(1)):
                    ketemu.setdefault(tipe, i)
        if status != "kosong":
            lanjutan = status == "daftar"
    return ketemu
