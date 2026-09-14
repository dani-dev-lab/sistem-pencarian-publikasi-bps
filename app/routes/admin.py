"""Endpoint admin: kelola kamus sinonim dan review log pencarian.

Seluruh /admin/* dilindungi SATU kata sandi bersama (hash-nya di .env sebagai
ADMIN_PASSWORD_HASH), bukan akun per orang - cukup untuk beberapa petugas yang
merawat kamus. Halaman pencarian untuk petugas PST tetap terbuka tanpa login.
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
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from app.models import LogPencarian, db
from app.services.normalisasi_data import jalankan as terapkan_normalisasi
from app.services.preprocessing import muat_ulang_kamus, normalisasi

bp = Blueprint("admin", __name__)

# Kunci di session Flask yang menandai pengunjung sudah memasukkan sandi.
KUNCI_SESSION = "admin_masuk"

# Kueri dianggap "gagal" kalau tidak menghasilkan apa pun, atau skor
# tertingginya masih di bawah ambang "ditemukan".
AMBANG_KUERI_LEMAH = 75


# --------------------------------------------------------------------------
# Autentikasi
# --------------------------------------------------------------------------

@bp.before_request
def wajib_login():
    """Tolak semua /admin/* sebelum login, kecuali halaman login itu sendiri.

    Dipasang di blueprint, bukan per-route, supaya route baru yang ditambah
    nanti otomatis ikut terlindungi - tidak bergantung pada ingatan untuk
    memasang dekorator.
    """
    if request.endpoint == "admin.login":
        return None
    if session.get(KUNCI_SESSION):
        return None
    return redirect(url_for("admin.login", next=request.path))


def _tujuan_aman(next_url):
    """Hanya izinkan kembali ke path lokal di bawah /admin/.

    Parameter `next` datang dari URL dan bisa diisi siapa saja; tanpa
    pemeriksaan ini halaman login bisa dipakai melempar orang ke situs lain.
    """
    if next_url and next_url.startswith("/admin") and not next_url.startswith("//"):
        return next_url
    return url_for("admin.beranda")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get(KUNCI_SESSION):
        return redirect(url_for("admin.beranda"))

    salah = False
    if request.method == "POST":
        sandi = request.form.get("sandi") or ""
        if sandi and check_password_hash(current_app.config["ADMIN_PASSWORD_HASH"],
                                         sandi):
            session.clear()
            session[KUNCI_SESSION] = True
            return redirect(_tujuan_aman(request.form.get("next")))
        salah = True

    return render_template("admin/login.html", salah=salah,
                           next=request.values.get("next") or "")


@bp.post("/logout")
def logout():
    session.pop(KUNCI_SESSION, None)
    return redirect(url_for("admin.login"))


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
              f"Klik \"Terapkan ke data\" supaya berlaku pada pencarian.", "sukses")

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
              f"Klik \"Terapkan ke data\" supaya berlaku pada pencarian.", "sukses")

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


@bp.post("/kamus/terapkan")
def terapkan():
    """Tulis ulang teks_ternormalisasi seluruh data memakai kamus terbaru.

    Pengganti perintah terminal `scripts/isi_normalisasi.py` - perubahan kamus
    tidak berpengaruh pada pencarian sebelum ini dijalankan, dan petugas yang
    merawat kamus tidak seharusnya perlu membuka terminal untuk itu.
    Berjalan sinkron (~2 detik untuk ~6.000 entri).
    """
    try:
        muat_ulang_kamus()
        ringkasan = terapkan_normalisasi()
    except Exception as e:  # noqa: BLE001 - tampilkan ke admin, jangan HTTP 500
        db.session.rollback()
        flash(f"Gagal menerapkan: {e}", "gagal")
        return redirect(url_for("admin.kamus"))

    if ringkasan is None:
        flash("Database masih kosong - jalankan perbarui-data.bat dulu.", "gagal")
    else:
        flash(f"Kamus diterapkan ke data dalam {ringkasan['waktu_detik']:.1f} detik: "
              f"{ringkasan['entri_diubah']} dari {ringkasan['entri_total']} entri "
              f"dan {ringkasan['publikasi_diubah']} dari "
              f"{ringkasan['publikasi_total']} publikasi diperbarui "
              f"(sisanya sudah sesuai).", "sukses")
    return redirect(url_for("admin.kamus"))


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
