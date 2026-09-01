"""Endpoint admin: kelola kamus sinonim dan review log pencarian.

TANPA AUTENTIKASI - aplikasi berjalan lokal di laptop selama masa magang.
Tercatat sebagai keterbatasan di CLAUDE.md; wajib ditambahkan sebelum deploy
ke jaringan mana pun.
"""

import json
import os

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app.models import LogPencarian, db
from app.services.preprocessing import muat_ulang_kamus, normalisasi

bp = Blueprint("admin", __name__)

# Kueri dianggap "gagal" kalau tidak menghasilkan apa pun, atau skor
# tertingginya masih di bawah ambang "ditemukan".
AMBANG_KUERI_LEMAH = 75


def _file_kamus():
    return str(current_app.config["FILE_KAMUS_SINONIM"])


def _baca_kamus():
    path = _file_kamus()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            isi = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return isi if isinstance(isi, dict) else {}


def _tulis_kamus(kamus):
    """Tulis kamus lalu muat ulang yang dipakai mesin pencari.

    Penulisan lewat berkas sementara supaya kamus tidak pernah tertangkap
    separuh tertulis kalau proses mati di tengah.
    """
    path = _file_kamus()
    sementara = path + ".tmp"
    with open(sementara, "w", encoding="utf-8") as f:
        json.dump(kamus, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(sementara, path)
    muat_ulang_kamus()


@bp.get("/")
def beranda():
    kamus = _baca_kamus()
    return render_template(
        "admin/beranda.html",
        jumlah_kelompok=len(kamus),
        jumlah_varian=sum(len(v) for v in kamus.values()),
        jumlah_log=LogPencarian.query.count(),
        jumlah_lemah=LogPencarian.query.filter(
            db.or_(LogPencarian.jumlah_hasil == 0,
                   LogPencarian.skor_tertinggi < AMBANG_KUERI_LEMAH)).count(),
    )


# --------------------------------------------------------------------------
# Kamus sinonim
# --------------------------------------------------------------------------

@bp.get("/kamus")
def kamus():
    isi = _baca_kamus()
    cari = (request.args.get("q") or "").strip().lower()
    kelompok = sorted(isi.items())
    if cari:
        kelompok = [(k, v) for k, v in kelompok
                    if cari in k.lower() or any(cari in x.lower() for x in v)]
    return render_template("admin/kamus.html", kelompok=kelompok, cari=cari,
                           total=len(isi))


@bp.post("/kamus/tambah-varian")
def tambah_varian():
    kanonik = (request.form.get("kanonik") or "").strip()
    varian = (request.form.get("varian") or "").strip()
    isi = _baca_kamus()

    if not kanonik or not varian:
        flash("Kelompok dan varian tidak boleh kosong.", "gagal")
    elif kanonik not in isi:
        flash(f"Kelompok {kanonik!r} tidak ada.", "gagal")
    elif varian.lower() in (x.lower() for x in isi[kanonik]):
        flash(f"{varian!r} sudah ada di kelompok {kanonik!r}.", "gagal")
    else:
        isi[kanonik].append(varian)
        _tulis_kamus(isi)
        flash(f"{varian!r} ditambahkan ke kelompok {kanonik!r}. "
              f"Jalankan normalisasi ulang supaya berlaku pada data.", "sukses")

    return redirect(url_for("admin.kamus", q=request.form.get("q") or None))


@bp.post("/kamus/tambah-kelompok")
def tambah_kelompok():
    kanonik = (request.form.get("kanonik") or "").strip()
    varian = [v.strip() for v in (request.form.get("varian") or "").split(",")
              if v.strip()]
    isi = _baca_kamus()

    if not kanonik:
        flash("Bentuk kanonik tidak boleh kosong.", "gagal")
    elif kanonik in isi:
        flash(f"Kelompok {kanonik!r} sudah ada.", "gagal")
    else:
        # Bentuk kanonik selalu ikut jadi anggota kelompoknya sendiri.
        isi[kanonik] = [kanonik] + [v for v in varian if v.lower() != kanonik.lower()]
        _tulis_kamus(isi)
        flash(f"Kelompok {kanonik!r} dibuat dengan {len(isi[kanonik])} kata. "
              f"Jalankan normalisasi ulang supaya berlaku pada data.", "sukses")

    return redirect(url_for("admin.kamus"))


@bp.post("/kamus/hapus-varian")
def hapus_varian():
    kanonik = (request.form.get("kanonik") or "").strip()
    varian = (request.form.get("varian") or "").strip()
    isi = _baca_kamus()

    if kanonik in isi and varian in isi[kanonik]:
        if varian.lower() == kanonik.lower():
            flash("Bentuk kanonik tidak bisa dihapus dari kelompoknya sendiri.",
                  "gagal")
        else:
            isi[kanonik].remove(varian)
            _tulis_kamus(isi)
            flash(f"{varian!r} dihapus dari kelompok {kanonik!r}.", "sukses")
    else:
        flash("Varian tidak ditemukan.", "gagal")

    return redirect(url_for("admin.kamus", q=request.form.get("q") or None))


# --------------------------------------------------------------------------
# Review log pencarian
# --------------------------------------------------------------------------

@bp.get("/log")
def log():
    """Kueri yang gagal atau berskor rendah, diurut dari yang paling sering.

    Inilah closed-loop yang dirancang sejak awal: kueri yang tidak menemukan
    apa pun adalah bahan paling berharga untuk memperkaya kamus sinonim.
    """
    hanya_gagal = request.args.get("semua") != "1"

    q = db.session.query(
        LogPencarian.keyword,
        LogPencarian.keyword_ternormalisasi,
        db.func.count(LogPencarian.id).label("frekuensi"),
        db.func.max(LogPencarian.jumlah_hasil).label("hasil_terbaik"),
        db.func.max(LogPencarian.skor_tertinggi).label("skor_terbaik"),
        db.func.max(LogPencarian.waktu_pencarian).label("terakhir"),
    ).group_by(LogPencarian.keyword, LogPencarian.keyword_ternormalisasi)

    if hanya_gagal:
        q = q.having(db.or_(
            db.func.max(LogPencarian.jumlah_hasil) == 0,
            db.func.max(LogPencarian.skor_tertinggi) < AMBANG_KUERI_LEMAH,
            db.func.max(LogPencarian.skor_tertinggi).is_(None),
        ))

    baris = q.order_by(db.desc("frekuensi"), db.desc("terakhir")).limit(100).all()

    return render_template("admin/log.html", baris=baris,
                           hanya_gagal=hanya_gagal,
                           ambang=AMBANG_KUERI_LEMAH,
                           total_log=LogPencarian.query.count())


@bp.get("/log/periksa")
def periksa():
    """Lihat hasil normalisasi satu kueri - untuk menebak kenapa ia gagal."""
    kueri = (request.args.get("q") or "").strip()
    return render_template("admin/periksa.html", kueri=kueri,
                           hasil=normalisasi(kueri) if kueri else "")
