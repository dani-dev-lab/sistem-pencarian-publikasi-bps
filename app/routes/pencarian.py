"""Endpoint pencarian untuk petugas PST."""

import os

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
)

from app.models import EntriDokumen, LogPencarian, Publikasi, db
from app.services.mesin_pencari import AMBANG_DITEMUKAN, AMBANG_SARAN, cari
from app.services.preprocessing import normalisasi_token

MIN_KARAKTER_SARAN = 3
MAKS_SARAN = 8

# Bagian nama yang muncul di hampir semua judul publikasi; dibuang supaya nama
# publikasi di daftar saran tetap pendek dan mudah dibedakan.
POTONG_NAMA = (
    "Provinsi Kalimantan Selatan",
    "Kabupaten/Kota Provinsi Kalimantan Selatan",
)


def _nama_singkat(judul):
    for frasa in POTONG_NAMA:
        judul = judul.replace(frasa, "").replace("  ", " ")
    return judul.strip(" -,")

bp = Blueprint("pencarian", __name__)


def _catat_log(hasil):
    """Rekam kueri ke log_pencarian.

    Dipakai untuk closed-loop improvement: kueri berskor rendah direview
    berkala untuk memperkaya kamus sinonim dan mengkalibrasi ambang.

    Hasil tingkat publikasi ikut dihitung, sama seperti halaman hasil: kueri
    yang hanya cocok ke judul/abstrak publikasi bukan kueri gagal. Skor memakai
    max() karena tiga daftar itu masing-masing terurut sendiri, jadi elemen
    pertama gabungannya belum tentu yang tertinggi.

    Kegagalan pencatatan TIDAK boleh menggagalkan pencarian - petugas tetap
    harus dapat hasilnya.
    """
    semua = hasil["publikasi"] + hasil["ditemukan"] + hasil["saran"]
    try:
        db.session.add(LogPencarian(
            keyword=hasil["kueri"][:255],
            keyword_ternormalisasi=hasil["kueri_ternormalisasi"][:255] or None,
            jumlah_hasil=len(semua),
            skor_tertinggi=max((h["skor"] for h in semua), default=None),
        ))
        db.session.commit()
    except Exception:  # noqa: BLE001 - log gagal bukan alasan menolak hasil
        db.session.rollback()


@bp.get("/pdf/<pub_id>")
def buka_pdf(pub_id):
    """Sajikan PDF dari salinan lokal, bukan dari server BPS.

    Tiap klik ke url_pdf berarti mengunduh ulang 3-30 MB dari webapi.bps.go.id.
    Semua 72 PDF sudah ada lokal, jadi tidak ada alasan membebani server BPS -
    sejalan dengan Term of Use yang melarang membebani layanan mereka.

    pub_id DIVALIDASI ke database lebih dulu; nama berkas disusun dari kolom
    `id` hasil query, bukan dari input mentah. Jadi tidak ada jalan bagi input
    untuk menyusun path sendiri.
    """
    pub = db.session.get(Publikasi, pub_id)
    if pub is None:
        abort(404)

    folder = str(current_app.config["DIR_PUBLIKASI_PDF"])
    nama = f"{pub.id}.pdf"

    if not os.path.isfile(os.path.join(folder, nama)):
        # Cadangan: berkas lokal hilang -> arahkan ke sumber aslinya supaya
        # tombolnya tidak pernah mati.
        if pub.url_pdf:
            return redirect(pub.url_pdf)
        abort(404)

    # as_attachment=False -> tampil inline di viewer browser, bukan diunduh.
    return send_from_directory(
        folder, nama, mimetype="application/pdf", as_attachment=False)


@bp.get("/api/saran")
def api_saran():
    """Saran judul entri saat petugas mengetik.

    SENGAJA tidak memakai pipeline scoring penuh (fuzzy + coverage + penalti
    panjang). Endpoint ini dipanggil jauh lebih sering daripada /hasil, jadi
    pencocokannya cukup substring pada teks_ternormalisasi lewat SQL LIKE -
    pekerjaan berat diserahkan ke database, bukan ke Python.
    """
    kueri = (request.args.get("q") or "").strip()
    if len(kueri) < MIN_KARAKTER_SARAN:
        return jsonify({"saran": []})

    token = normalisasi_token(kueri)
    if not token:
        return jsonify({"saran": []})

    q = (
        db.session.query(EntriDokumen.judul, EntriDokumen.tipe, Publikasi.judul)
        .join(Publikasi, EntriDokumen.publikasi_id == Publikasi.id)
    )
    # Dicocokkan ke teks ternormalisasi ATAU judul asli. Keduanya perlu:
    # kamus sinonim mengubah "tingkat penghunian kamar" menjadi "tpk", sehingga
    # potongan "tingkat penghunian" tidak lagi ada di teks ternormalisasi -
    # padahal justru potongan seperti itu yang diketik petugas.
    for t in token:
        q = q.filter(db.or_(
            EntriDokumen.teks_ternormalisasi.like(f"%{t}%"),
            EntriDokumen.judul.like(f"%{t}%"),
        ))

    # Judul terpendek lebih dulu: makin pendek makin spesifik, dan entri
    # gabungan yang panjang (utang teknis yang tercatat) tidak menutupi daftar.
    baris = (
        q.order_by(db.func.char_length(EntriDokumen.judul).asc())
        .limit(MAKS_SARAN * 4)     # ambil lebih, sisakan ruang untuk dedup
        .all()
    )

    saran = []
    terlihat = set()
    for judul, tipe, judul_pub in baris:
        kunci = judul.strip().lower()
        # Judul yang sama muncul di beberapa edisi. Untuk SARAN cukup satu -
        # ini pemantik kueri, bukan jawaban. Hasil pencarian tetap menampilkan
        # semua edisi secara terpisah.
        if kunci in terlihat:
            continue
        terlihat.add(kunci)
        saran.append({
            "judul": judul,
            "tipe": tipe,
            "publikasi": _nama_singkat(judul_pub),
        })
        if len(saran) >= MAKS_SARAN:
            break

    return jsonify({"saran": saran})


@bp.get("/")
def halaman_pencarian():
    return render_template("pencarian.html")


@bp.get("/hasil")
def hasil_pencarian():
    kueri = (request.args.get("q") or "").strip()
    if not kueri:
        return render_template("pencarian.html", pesan="Masukkan kata kunci dulu.")

    hasil = cari(kueri)
    _catat_log(hasil)

    return render_template(
        "hasil.html",
        kueri=kueri,
        hasil=hasil,
        ambang_ditemukan=AMBANG_DITEMUKAN,
        ambang_saran=AMBANG_SARAN,
    )
