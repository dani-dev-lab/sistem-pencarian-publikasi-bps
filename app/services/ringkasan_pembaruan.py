"""Ringkasan hasil "Cek dulu" dan hasil pembaruan untuk pembaca non-IT (25 Nov 2026).

Halaman /admin/perbarui menampilkan kartu ringkasan: empat angka besar,
status berwarna dengan satu kalimat, dan satu kalimat bahasa sehari-hari.
Aturannya ada di sini, di fungsi murni, supaya bisa diuji tanpa browser:

- format_ukuran / format_durasi: satuan otomatis (MB/GB satu desimal dengan
  koma; detik/menit/jam).
- ringkas_cek: status hasil cek. Urutan pemeriksaannya:
    abu-abu "Semua sudah terbaru"  : 0 publikasi yang akan diproses;
    merah   "Ruang disk tidak cukup": unduhan + cadangan > sisa ruang disk
                                      (tombol Mulai pembaruan dinonaktifkan);
    kuning  "Penarikan besar"       : perkiraan > besar_menit ATAU unduhan > besar_gb;
    hijau   "Siap ditarik"          : selain itu.
- ringkas_pembaruan: ringkasan SESUDAH pembaruan, dengan gaya yang sama.

Ambang dibaca dari data/wilayah.json (kunci ambang_penarikan), bukan ditulis
di kode, supaya bisa diubah tim IT. scripts/perbarui.py --cek-dulu memakai
ambang yang sama untuk peringatan "Penarikan besar" di terminal.

Satuan ukuran mengikuti sumber_bps.ukuran_mb: 1 GB = 1024 MB.
"""

import json
import os
import shutil

from app.config import Config

KUNCI_AMBANG = "ambang_penarikan"
MB_PER_GB = 1024

STATUS_TERBARU, STATUS_DISK, STATUS_BESAR, STATUS_SIAP = "terbaru", "disk", "besar", "siap"
JUDUL_STATUS = {
    STATUS_SIAP: "Siap ditarik",
    STATUS_BESAR: "Penarikan besar, sebaiknya jalankan malam hari",
    STATUS_DISK: "Ruang disk tidak cukup",
    STATUS_TERBARU: "Semua sudah terbaru",
}
# Kelas CSS warna kartu: hijau / kuning / merah / abu-abu.
WARNA = {STATUS_SIAP: "hijau", STATUS_BESAR: "kuning", STATUS_DISK: "merah", STATUS_TERBARU: "abu"}


# --------------------------------------------------------------------------
# Ambang dari wilayah.json
# --------------------------------------------------------------------------

def ambang(path=None):
    """{besar_menit, besar_gb, cadangan_disk_persen} dari data/wilayah.json.

    Tidak ada nilai cadangan di kode: kunci yang hilang atau salah ditolak
    dengan pesan (SystemExit), seperti isi wilayah.json lainnya.
    """
    path = path or Config.FILE_WILAYAH
    try:
        with open(path, encoding="utf-8") as f:
            isi = json.load(f).get(KUNCI_AMBANG)
    except (OSError, ValueError) as e:
        raise SystemExit(f"{path} tidak bisa dibaca: {e}") from None
    if not isinstance(isi, dict):
        raise SystemExit(f"{path}: {KUNCI_AMBANG} belum diisi, contoh "
                         '{"besar_menit": 30, "besar_gb": 1, "cadangan_disk_persen": 20}')
    hasil = {}
    for kunci in ("besar_menit", "besar_gb", "cadangan_disk_persen"):
        nilai = isi.get(kunci)
        if isinstance(nilai, bool) or not isinstance(nilai, (int, float)) or nilai < 0:
            raise SystemExit(f"{path}: {KUNCI_AMBANG}.{kunci} harus angka >= 0, bukan {nilai!r}")
        hasil[kunci] = nilai
    return hasil


def penarikan_besar(detik_total, mb_unduh, a):
    """Alasan "penarikan besar" (daftar kalimat; kosong = bukan penarikan besar)."""
    alasan = []
    if detik_total > a["besar_menit"] * 60:
        alasan.append(f"Perkiraan waktu {format_durasi(detik_total, kira=True)}, lebih dari "
                      f"{_angka(a['besar_menit'])} menit.")
    if mb_unduh > a["besar_gb"] * MB_PER_GB:
        alasan.append(f"Unduhan sekitar {format_ukuran(mb_unduh)}, lebih dari {_angka(a['besar_gb'])} GB.")
    return alasan


# --------------------------------------------------------------------------
# Satuan
# --------------------------------------------------------------------------

def _angka(x, desimal=0):
    """Format Indonesia: titik ribuan, koma desimal."""
    teks = f"{x:,.{desimal}f}"
    return teks.replace(",", "_").replace(".", ",").replace("_", ".")


def format_ukuran(mb):
    """MB -> "0 MB" / "211,5 MB" / "1,2 GB" (1 GB = 1024 MB, satu desimal)."""
    if mb is None:
        return "tidak diketahui"
    if mb <= 0:
        return "0 MB"
    if mb < 0.05:
        return "< 0,1 MB"
    if mb < MB_PER_GB:
        return f"{_angka(mb, 1)} MB"
    return f"{_angka(mb / MB_PER_GB, 1)} GB"


def format_durasi(detik, kira=False):
    """Detik -> "45 detik" / "12 menit" / "2,5 jam". kira=True menambah "±"."""
    s = max(0, round(detik or 0))
    if s < 60:
        teks = f"{s} detik"
    elif round(s / 60) < 60:
        teks = f"{round(s / 60)} menit"
    else:
        teks = f"{_angka(s / 3600, 1)} jam"
    return ("±" if kira else "") + teks


def sisa_ruang_mb(path=None):
    """Sisa ruang drive folder data (tempat PDF diunduh), dalam MB. None kalau
    tidak bisa dibaca."""
    path = str(path or Config.DIR_PUBLIKASI_PDF)
    while path and not os.path.exists(path):
        induk = os.path.dirname(path)
        if induk == path:
            break
        path = induk
    try:
        return shutil.disk_usage(path).free / 1024 / 1024
    except OSError:
        return None


def nama_drive(path=None):
    """"C:" untuk ditampilkan di samping sisa ruang disk."""
    return os.path.splitdrive(os.path.abspath(str(path or Config.DIR_PUBLIKASI_PDF)))[0] or "/"


def _daftar_nama(nama):
    """["A"] -> "A"; ["A", "B"] -> "A dan B"; ["A", "B", "C"] -> "A, B, dan C"."""
    if len(nama) <= 1:
        return "".join(nama)
    if len(nama) == 2:
        return f"{nama[0]} dan {nama[1]}"
    return ", ".join(nama[:-1]) + f", dan {nama[-1]}"


def _dari_wilayah(nama):
    """Wilayah disebut kalau 3 atau kurang, selain itu "dari N wilayah"."""
    return f"dari {_daftar_nama(nama)}" if len(nama) <= 3 else f"dari {len(nama)} wilayah"


# --------------------------------------------------------------------------
# Ringkasan hasil cek
# --------------------------------------------------------------------------

def ringkas_cek(cek, sisa_mb, a, drive=""):
    """Kartu ringkasan hasil --cek-dulu (data/cek_pembaruan(-uji).json).

    sisa_mb: sisa ruang disk saat halaman dibuka (None = tidak diketahui; status
    merah tidak dipakai). Mengembalikan dict untuk template: status, warna,
    judul, kalimat, angka (4 kotak), boleh_mulai, alasan_tidak_boleh, perlu_mb.
    """
    t = cek["total"]
    pk = cek["perkiraan"]
    detik = pk["detik"]["total"]
    kerja = pk["publikasi_diproses"]
    mb = t["mb_unduh"] or 0
    perlu_mb = mb * (1 + a["cadangan_disk_persen"] / 100)
    ok = [d for d in cek["domain"] if d["status"] != "gagal"]
    gagal = [d for d in cek["domain"] if d["status"] == "gagal"]
    alasan_besar = penarikan_besar(detik, mb, a)

    if kerja == 0:
        status = STATUS_TERBARU
    elif sisa_mb is not None and perlu_mb > sisa_mb:
        status = STATUS_DISK
    elif alasan_besar:
        status = STATUS_BESAR
    else:
        status = STATUS_SIAP

    kalimat = []
    if kerja:
        bagian = []
        if t["baru"]:
            bagian.append(f"{t['baru']} publikasi baru")
        if t["direvisi"]:
            bagian.append(f"{t['direvisi']} publikasi yang direvisi BPS")
        if t["baca_ulang"]:
            bagian.append(f"{t['baca_ulang']} publikasi yang perlu dibaca ulang")
        wilayah = [d["wilayah"] for d in ok if d["baru"] + d["direvisi"] + d["baca_ulang"]]
        kalimat.append(f"Ada {_daftar_nama(bagian)} {_dari_wilayah(wilayah)}.")
        if t["tetap"]:
            kalimat.append(f"{_angka(t['tetap'])} publikasi lain tidak berubah.")
    else:
        kalimat.append("Tidak ada publikasi baru atau yang direvisi BPS."
                       + (f" {_angka(t['tetap'])} publikasi sesuai pilihan sudah terbaru."
                          if t["tetap"] else ""))
    if gagal:
        kalimat.append(f"Cek gagal untuk {_daftar_nama([d['wilayah'] for d in gagal])}; "
                       "wilayah itu belum dihitung.")
    if status == STATUS_SIAP:
        kalimat.append("Klik Mulai pembaruan untuk menariknya.")
    elif status == STATUS_BESAR:
        kalimat.append("Klik Mulai pembaruan pada malam hari (sesudah pukul 01.00), dari jaringan "
                       "kantor, laptop tersambung listrik.")
    elif status == STATUS_DISK:
        kalimat.append(f"Perlu sekitar {format_ukuran(perlu_mb)} (unduhan + cadangan "
                       f"{_angka(a['cadangan_disk_persen'])}%), sisa ruang hanya {format_ukuran(sisa_mb)}.")

    angka = [
        {"label": "Akan diproses", "nilai": _angka(kerja), "satuan": "publikasi",
         "ket": f"baru {t['baru']}, direvisi {t['direvisi']}"
                + (f", baca ulang {t['baca_ulang']}" if t["baca_ulang"] else "")},
        {"label": "Ukuran unduhan", "nilai": format_ukuran(mb), "satuan": "",
         "ket": f"{t['unduh']} PDF"},
        {"label": "Perkiraan waktu", "nilai": format_durasi(detik, kira=True), "satuan": "",
         "ket": "belum termasuk OCR"},
        {"label": "Sisa ruang disk", "nilai": format_ukuran(sisa_mb), "satuan": "",
         "ket": f"drive {drive}" if drive else ""},
    ]
    alasan_tidak_boleh = None
    if status == STATUS_DISK:
        alasan_tidak_boleh = (f"Mulai pembaruan dinonaktifkan: unduhan {format_ukuran(mb)} ditambah "
                              f"cadangan {_angka(a['cadangan_disk_persen'])}% "
                              f"({format_ukuran(perlu_mb)}) lebih besar dari sisa ruang disk "
                              f"{format_ukuran(sisa_mb)}. Kosongkan ruang disk, atau perkecil "
                              "pilihan, lalu klik Cek dulu lagi.")
    return {"status": status, "warna": WARNA[status], "judul": JUDUL_STATUS[status],
            "kalimat": " ".join(kalimat), "angka": angka, "alasan_besar": alasan_besar,
            "boleh_mulai": status != STATUS_DISK, "alasan_tidak_boleh": alasan_tidak_boleh,
            "perlu_mb": perlu_mb}


# --------------------------------------------------------------------------
# Ringkasan sesudah pembaruan
# --------------------------------------------------------------------------

def ringkas_pembaruan(r):
    """Kartu ringkasan data/pembaruan_terakhir(-uji).json, gaya sama dengan cek.

    Ringkasan format lama (sebelum multi-domain, tanpa domain/unduhan) tetap
    bisa dirender; angka yang tidak tercatat tampil "-".
    """
    baru = r.get("publikasi_baru") or []
    domain = r.get("domain") or []
    gagal_pub = sum(len(d.get("gagal") or []) for d in domain)
    gagal_wil = [d["wilayah"] for d in domain if d.get("status") == "gagal"]
    status = r.get("status")
    warna = {"sukses": "hijau", "tidak_ada_baru": "abu", "sebagian": "kuning"}.get(status, "merah")
    judul = {"sukses": "Pembaruan selesai", "tidak_ada_baru": "Semua sudah terbaru",
             "sebagian": "Pembaruan selesai sebagian"}.get(status, "Pembaruan gagal")

    kalimat = []
    if status == "sukses" and baru:
        wilayah = sorted({p["wilayah"] for p in baru if p.get("wilayah")})
        asal = f" {_dari_wilayah(wilayah)}" if wilayah else ""
        kalimat.append(f"{len(baru)} publikasi baru{asal} sudah bisa dicari.")
    elif status == "sukses":
        kalimat.append("Publikasi yang direvisi BPS sudah dibaca ulang dan bisa dicari.")
    elif status == "tidak_ada_baru":
        kalimat.append("Tidak ada publikasi baru."
                       + (f" {_angka(r['jumlah_publikasi'])} publikasi di daftar BPS semuanya sudah terindeks."
                          if r.get("jumlah_publikasi") is not None else ""))
    elif status == "sebagian":
        kalimat.append("Wilayah atau publikasi yang berhasil sudah bisa dicari; yang gagal tetap memakai "
                       "data lamanya dan dicoba lagi pada pembaruan berikutnya.")
    if gagal_wil:
        kalimat.append(f"Gagal di {_daftar_nama(gagal_wil)}.")
    if r.get("entri_sebelum") is not None and r.get("entri_sesudah") is not None and status != "gagal":
        kalimat.append(f"Entri dokumen {_angka(r['entri_sebelum'])} → {_angka(r['entri_sesudah'])}.")

    unduhan = r.get("unduhan") or {}
    durasi = r.get("durasi_detik")
    angka = [
        {"label": "Publikasi baru", "nilai": _angka(len(baru)), "satuan": "publikasi",
         "ket": f"diproses {r['diproses']}" if r.get("diproses") is not None else ""},
        {"label": "Gagal", "nilai": _angka(gagal_pub), "satuan": "publikasi",
         "ket": f"{len(gagal_wil)} wilayah gagal" if gagal_wil else "data lama tetap utuh"},
        {"label": "Terunduh", "nilai": format_ukuran(unduhan["mb"]) if "mb" in unduhan else "-",
         "satuan": "", "ket": f"{unduhan['berkas']} PDF" if "berkas" in unduhan else ""},
        {"label": "Durasi", "nilai": format_durasi(durasi) if durasi is not None else "-",
         "satuan": "", "ket": f"{durasi} detik" if durasi is not None else ""},
    ]
    return {"status": status, "warna": warna, "judul": judul, "kalimat": " ".join(kalimat),
            "angka": angka}
