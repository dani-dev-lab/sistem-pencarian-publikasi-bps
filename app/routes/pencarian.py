"""Endpoint pencarian untuk petugas PST."""

import os

from flask import (
    Blueprint,
    abort,
    current_app,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from app.models import EntriDokumen, LogPencarian, Publikasi, db
from app.services import alamat_kembali, pencarian_wilayah, sampul
from app.services.mesin_pencari import AMBANG_DITEMUKAN, AMBANG_SARAN
from app.services.preprocessing import normalisasi_token
from app.services.wilayah import DOMAIN_PROVINSI, wilayah_aktif

MIN_KARAKTER_SARAN = 3
MAKS_SARAN = 8
MAKS_HALAMAN_SARAN_KECAMATAN = 10   # paling banyak 10 x 32 baris saat kec=1

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


def _ada_kecamatan():
    """Database berisi publikasi Kecamatan Dalam Angka? Selama tidak (seperti
    produksi sampai ada keputusan), kotak centang, dropdown kecamatan, dan
    kotak info TIDAK dirender: halaman sama persis dengan sebelumnya."""
    return db.session.query(db.exists().where(Publikasi.kecamatan.isnot(None))).scalar()


def _konteks_kecamatan(domain, kec=False, kc=""):
    """Data form kecamatan (18 Nov 2026). `semua` untuk JavaScript yang
    mengganti isi dropdown saat wilayah diganti; `daftar` dirender server
    untuk wilayah aktif (berfungsi tanpa JavaScript)."""
    if not _ada_kecamatan():
        return {"ada": False}
    from app.services.mesin_pencari import korpus
    semua = {d: [list(x) for x in v] for d, v in korpus().daftar_kecamatan.items()}
    return {"ada": True, "kec": bool(kec or kc), "kc": kc or "",
            "daftar": semua.get(domain or "", []), "semua": semua}


def _arg_kecamatan():
    """(kec, kc, semua_kec) dari URL. kc menyiratkan kec."""
    kc = (request.args.get("kc") or "").strip().lower()
    return request.args.get("kec") == "1" or bool(kc), kc, request.args.get("semua_kec") == "1"


def _catat_log(hasil, kecamatan_tersedia=False):
    """Rekam kueri ke log_pencarian.

    Dipakai untuk closed-loop improvement: kueri berskor rendah direview
    berkala untuk memperkaya kamus sinonim dan mengkalibrasi ambang.

    Hasil tingkat publikasi ikut dihitung, sama seperti halaman hasil: kueri
    yang hanya cocok ke judul/abstrak publikasi bukan kueri gagal. Skor memakai
    max() karena tiga daftar itu masing-masing terurut sendiri, jadi elemen
    pertama gabungannya belum tentu yang tertinggi.

    Kegagalan pencatatan TIDAK boleh menggagalkan pencarian - petugas tetap
    harus dapat hasilnya.

    Tidak mencatat apa pun kalau CATAT_LOG_PENCARIAN mati, yaitu hanya di
    KonfigurasiUji (lihat app/config.py).
    """
    if not current_app.config.get("CATAT_LOG_PENCARIAN", True):
        return
    # Entri provinsi pelengkap ("Juga ada di publikasi provinsi") ikut
    # dihitung: kueri yang hanya terjawab tabel provinsi bukan kueri gagal.
    semua = (hasil["publikasi"] + hasil["ditemukan"] + hasil["saran"]
             + hasil.get("provinsi", []))
    try:
        db.session.add(LogPencarian(
            keyword=hasil["kueri"][:255],
            keyword_ternormalisasi=hasil["kueri_ternormalisasi"][:255] or None,
            jumlah_hasil=len(semua),
            # Kueri yang hanya berisi nama wilayah tidak punya skor.
            skor_tertinggi=max((h["skor"] for h in semua if h["skor"] is not None),
                               default=None),
            # Waktu cari() saja - angka yang sama dengan "... ms" di halaman
            # hasil. Penulisan log dan render halaman tidak ikut terhitung.
            durasi_ms=round(hasil["waktu_ms"], 1),
            wilayah_filter=hasil["filter"]["kode"],
            sertakan_kecamatan=(hasil.get("kecamatan") is not None) if kecamatan_tersedia else None,
        ))
        db.session.commit()
    except Exception:  # noqa: BLE001 - log gagal bukan alasan menolak hasil
        db.session.rollback()


@bp.get("/sampul/<pub_id>")
def sampul_publikasi(pub_id):
    """Sampul publikasi dari data/sampul/ (19 Nov 2026), disajikan lokal: browser
    petugas tidak pernah meminta gambar ke situs luar.

    pub_id hanya boleh huruf/angka (RE_PUB_ID), dan nama berkas disusun
    sampul.path_*; tanpa berkas -> 404 (kartu tidak memasang <img> kalau berkas
    tidak ada, jadi 404 hanya untuk permintaan langsung). URL dari kartu
    membawa ?v=<waktu ubah>, sehingga cache browser boleh panjang.
    """
    if not sampul.RE_PUB_ID.fullmatch(pub_id):
        abort(404)
    path = sampul.berkas(pub_id)
    if path is None:
        abort(404)
    return send_from_directory(os.path.dirname(path), os.path.basename(path),
                               mimetype="image/jpeg", max_age=30 * 24 * 3600)


@bp.get("/pdf/<pub_id>")
def buka_pdf(pub_id):
    """Sajikan PDF dari salinan lokal, bukan dari server BPS.

    Tiap klik ke url_pdf berarti mengunduh ulang 3-30 MB dari webapi.bps.go.id.
    Semua 72 PDF sudah ada lokal, jadi tidak ada alasan membebani server BPS -
    sejalan dengan Term of Use yang melarang membebani layanan mereka.

    pub_id DIVALIDASI ke database lebih dulu; subfolder dan nama berkas disusun
    dari kolom `domain` dan `id` hasil query, bukan dari input mentah. Jadi
    tidak ada jalan bagi input untuk menyusun path sendiri.
    """
    pub = db.session.get(Publikasi, pub_id)
    if pub is None:
        abort(404)

    folder = str(current_app.config["DIR_PUBLIKASI_PDF"] / pub.domain)
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
    # Publikasi Kecamatan Dalam Angka hanya ikut kalau kotak centangnya aktif
    # (saran.js mengirim kec=1), 18 Nov 2026. Urutan tidak bergantung pada
    # klausa ini karena ORDER BY di bawah punya pemecah seri.
    if request.args.get("kec") != "1":
        q = q.filter(Publikasi.kecamatan.is_(None))
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
    # Seri (judul sama panjang): EDISI TERBARU dulu, lalu id - keputusan
    # pemilik project 18 Nov 2026. Tanpa pemecah seri, edisi yang tampil
    # ditentukan filesort MySQL dan berubah menurut rencana kueri (klausa
    # WHERE tambahan, isi tabel berubah).
    urut = q.order_by(db.func.char_length(EntriDokumen.judul).asc(),
                      Publikasi.tanggal_rilis.desc(), Publikasi.id, EntriDokumen.id)
    ukuran = MAKS_SARAN * 4        # ambil lebih, sisakan ruang untuk dedup
    # Dengan kotak centang kecamatan, satu judul ("3 Penduduk") ada di ratusan
    # publikasi kecamatan, sehingga 32 baris pertama bisa hanya berisi 3-4
    # judul berbeda (19 Nov 2026). Halaman berikutnya diambil sampai 8 judul
    # berbeda terkumpul. Tanpa centang tetap SATU halaman, sama persis dengan
    # sebelumnya.
    maks_halaman = MAKS_HALAMAN_SARAN_KECAMATAN if request.args.get("kec") == "1" else 1

    saran = []
    terlihat = set()
    for nomor_halaman in range(maks_halaman):
        baris = urut.offset(nomor_halaman * ukuran).limit(ukuran).all()
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
        if len(saran) >= MAKS_SARAN or len(baris) < ukuran:
            break

    return jsonify({"saran": saran})


def _tandai_dari_admin():
    """g.dari_admin = halaman ini dibuka lewat tombol "Kembali ke Pencarian"
    (penanda sekali pakai dari /kembali, untuk alamat yang SAMA persis).
    Penanda selalu dibuang di sini, supaya tidak tertinggal ke pencarian
    berikutnya."""
    if alamat_kembali.KUNCI_DARI_ADMIN not in session:
        g.dari_admin = False
        return
    penanda = session.pop(alamat_kembali.KUNCI_DARI_ADMIN)
    g.dari_admin = penanda == request.full_path.rstrip("?")


@bp.get("/kembali")
def kembali_ke_pencarian():
    """Tombol "Kembali ke Pencarian" di kop admin (26 Nov 2026): ke halaman
    pencarian terakhir sebelum masuk admin (session, disimpan admin dari
    `?dari=`), atau ke halaman awal kalau tidak ada / tidak sah.

    Penanda sekali pakai membuat halaman tujuan tidak menulis log pencarian
    (kueri itu sudah tercatat saat pertama dicari) dan memulihkan posisi
    gulir. Penanda hanya dipasang di sini; pencarian biasa tetap tercatat.
    Tidak perlu login: tujuannya hanya halaman pencarian.
    """
    tujuan = alamat_kembali.alamat_aman(session.get(alamat_kembali.KUNCI_ALAMAT))
    if not tujuan:
        return redirect(url_for("pencarian.halaman_pencarian"))
    session[alamat_kembali.KUNCI_DARI_ADMIN] = tujuan
    return redirect(request.script_root + tujuan)


@bp.get("/")
def halaman_pencarian():
    _tandai_dari_admin()
    w = (request.args.get("w") or "").strip()
    kec, kc, _ = _arg_kecamatan()
    return render_template("pencarian.html", daftar_wilayah=wilayah_aktif(), w=w,
                           kecamatan=_konteks_kecamatan(w, kec, kc))


@bp.get("/hasil")
def hasil_pencarian():
    _tandai_dari_admin()
    kueri = (request.args.get("q") or "").strip()
    w = (request.args.get("w") or "").strip()
    kec, kc, semua_kec = _arg_kecamatan()
    if not kueri:
        return render_template("pencarian.html", pesan="Masukkan kata kunci dulu.",
                               daftar_wilayah=wilayah_aktif(), w=w,
                               kecamatan=_konteks_kecamatan(w, kec, kc))

    hasil = pencarian_wilayah.cari(
        kueri, w=w,
        wo=(request.args.get("wo") or "").strip(),
        abaikan=(request.args.get("abaikan") or "").strip(),
        kec=kec, kc=kc, semua_kec=semua_kec)
    if not g.dari_admin:     # kembali dari admin: sudah tercatat saat dicari
        _catat_log(hasil, kecamatan_tersedia=_ada_kecamatan())

    kc_sah = hasil["kecamatan"]["kc"] if hasil["kecamatan"] else ""
    return render_template(
        "hasil.html",
        kueri=kueri,
        hasil=hasil,
        filter=hasil["filter"],
        daftar_wilayah=wilayah_aktif(),
        domain_provinsi=DOMAIN_PROVINSI,
        ambang_ditemukan=AMBANG_DITEMUKAN,
        ambang_saran=AMBANG_SARAN,
        kecamatan=_konteks_kecamatan(hasil["filter"]["kode"], kec, kc_sah),
        url_kecamatan=_url_dengan(kec="1"),
        url_jumlah_kecamatan=url_for("pencarian.jumlah_kecamatan", q=kueri,
                                     **{k: request.args[k] for k in ("w", "wo", "abaikan")
                                        if request.args.get(k)}),
        url_kecamatan_semua=_url_dengan(kec="1", semua_kec="1"),
    )


@bp.get("/api/kecamatan/jumlah")
def jumlah_kecamatan():
    """Jumlah bagian publikasi kecamatan yang cocok, untuk kotak info
    "Ada [n] bagian lain ..." di halaman hasil TANPA centang (18 Nov 2026).

    Dipanggil kecamatan.js SESUDAH halaman tampil, supaya penilaian bagian
    kecamatan (sampai +200 ms pada kueri umum tanpa filter wilayah) tidak
    menunda hasil utama. Fungsi skor dan ambang sama dengan seksi
    kecamatan. Tidak menulis log.
    """
    kueri = (request.args.get("q") or "").strip()
    if not kueri or not _ada_kecamatan():
        return jsonify({"jumlah": 0, "jenis": "bagian"})
    f = pencarian_wilayah.tentukan_filter(
        kueri, (request.args.get("w") or "").strip(),
        (request.args.get("wo") or "").strip(), (request.args.get("abaikan") or "").strip())
    hanya_wilayah = f["kode"] is not None and not normalisasi_token(f["kueri_topik"])
    b = pencarian_wilayah.cari_kecamatan(kueri, f, hanya_wilayah)
    return jsonify({"jumlah": b["jumlah"], "jenis": "publikasi" if hanya_wilayah else "bagian"})


def _url_dengan(**tambahan):
    """URL /hasil yang sama ditambah/diganti parameter (tombol kecamatan)."""
    args = request.args.to_dict()
    args.update(tambahan)
    return url_for("pencarian.hasil_pencarian", **args)
