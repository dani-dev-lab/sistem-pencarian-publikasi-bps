"""Endpoint admin: kamus sinonim, review log, pembaruan data, ganti sandi.

Seluruh /admin/* dilindungi SATU kata sandi bersama (hash-nya di .env sebagai
ADMIN_PASSWORD_HASH), bukan akun per orang - cukup untuk beberapa petugas yang
merawat kamus. Halaman pencarian untuk petugas PST tetap terbuka tanpa login.
"""

import json
import math
import os
import threading
import time
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from app.config import PANJANG_SANDI_MINIMAL, tulis_admin_hash
from app.models import LogPencarian, Publikasi, db
from app.services import pembaruan, pilihan_pembaruan, ringkasan_pembaruan
from app.services.pilihan_pembaruan import PilihanTidakSah
from app.services.normalisasi_data import jalankan as terapkan_normalisasi
from app.services.preprocessing import muat_ulang_kamus, normalisasi

bp = Blueprint("admin", __name__)

# Kunci di session Flask yang menandai pengunjung sudah memasukkan sandi.
KUNCI_SESSION = "admin_masuk"

# Kueri dianggap "gagal" kalau tidak menghasilkan apa pun, atau skor
# tertingginya masih di bawah ambang "ditemukan".
AMBANG_KUERI_LEMAH = 75


# --------------------------------------------------------------------------
# Autentikasi dan sesi (diperluas 25 Nov 2026: menu admin di semua halaman,
# sesi kedaluwarsa, penguncian sesudah sandi salah berulang)
# --------------------------------------------------------------------------

# Waktu aktif terakhir (detik epoch) di session; diperbarui tiap permintaan.
KUNCI_AKTIF = "admin_aktif"
# Penguncian login: sesudah BATAS_SALAH sandi salah berturut-turut dari satu
# alamat, login dari alamat itu ditolak LAMA_KUNCI_DETIK.
BATAS_SALAH = 5
LAMA_KUNCI_DETIK = 5 * 60
# alamat -> {"salah": n, "sampai": epoch}. Di memori proses: hilang kalau
# aplikasi dijalankan ulang, dan semua thread waitress berbagi satu kamus.
_PERCOBAAN = {}
_KUNCI_PERCOBAAN = threading.Lock()



def _sekarang():
    """Jam yang dipakai sesi dan penguncian (satu tempat, supaya bisa diuji)."""
    return time.time()


def periksa_sesi():
    """app.before_request (dipasang create_app): sesi admin yang tidak aktif
    lebih dari SESI_ADMIN_MENIT menit diakhiri; yang masih berlaku diperbarui
    waktunya. Berlaku untuk SEMUA halaman, termasuk pencarian, supaya penanda
    "Masuk sebagai admin" di kop ikut hilang. Berkas statis tidak dihitung.
    Session tanpa waktu aktif (misalnya dari versi lama) dianggap kedaluwarsa.
    """
    if request.endpoint == "static" or not session.get(KUNCI_SESSION):
        return None
    aktif = session.get(KUNCI_AKTIF)
    sekarang = _sekarang()
    batas = current_app.config["SESI_ADMIN_MENIT"] * 60
    if not isinstance(aktif, (int, float)) or sekarang - aktif > batas:
        session.pop(KUNCI_SESSION, None)
        session.pop(KUNCI_AKTIF, None)
        g.sesi_berakhir = True
        return None
    session[KUNCI_AKTIF] = int(sekarang)
    return None


def konteks_menu():
    """context_processor (dipasang create_app): kop semua halaman. Halaman
    pencarian memakai admin_masuk untuk ikon gembok tombol "Halaman Admin";
    halaman admin untuk menampilkan tombol Keluar."""
    return {"admin_masuk": bool(session.get(KUNCI_SESSION))}


@bp.before_request
def wajib_login():
    """Tolak semua /admin/* sebelum login, kecuali halaman login itu sendiri.

    Dipasang di blueprint, bukan per-route, supaya route baru yang ditambah
    nanti otomatis ikut terlindungi - tidak bergantung pada ingatan untuk
    memasang dekorator.

    Tujuan sesudah login: halaman yang diminta (path + query). Untuk kiriman
    POST yang ditolak (misalnya sesi habis saat menyimpan kamus), tujuannya
    halaman asal kiriman itu, karena URL POST tidak bisa dibuka dengan GET.
    """
    if request.endpoint == "admin.login":
        return None
    if session.get(KUNCI_SESSION):
        return None
    if g.get("sesi_berakhir"):
        flash(f"Sesi admin berakhir karena tidak aktif lebih dari "
              f"{current_app.config['SESI_ADMIN_MENIT']} menit. Silakan masuk lagi.", "gagal")
    if request.method == "GET":
        tujuan = request.full_path.rstrip("?")
    else:
        asal = urlsplit(request.referrer or "")
        tujuan = (asal.path + (f"?{asal.query}" if asal.query else "")
                  if asal.netloc == request.host else "")
    return redirect(url_for("admin.login", next=_tujuan_aman(tujuan)))


def _tujuan_aman(next_url):
    """Hanya izinkan kembali ke path LOKAL aplikasi ini.

    Parameter `next` datang dari URL dan bisa diisi siapa saja; tanpa
    pemeriksaan ini halaman login bisa dipakai melempar orang ke situs lain
    ("//situs-lain", "/\\situs-lain", "http://..."). Halaman login/keluar
    sendiri tidak dipakai sebagai tujuan.
    """
    u = (next_url or "").strip()
    if (u.startswith("/") and not u.startswith("//") and "\\" not in u
            and not urlsplit(u).scheme and not urlsplit(u).netloc
            and not u.startswith(("/admin/login", "/admin/logout"))):
        return u
    return url_for("admin.beranda")


def _sisa_kunci(alamat, sekarang):
    """Detik sisa penguncian alamat ini (0 = tidak terkunci)."""
    with _KUNCI_PERCOBAAN:
        p = _PERCOBAAN.get(alamat)
        if p and p.get("sampai"):
            if sekarang < p["sampai"]:
                return p["sampai"] - sekarang
            _PERCOBAAN.pop(alamat, None)     # penguncian selesai: hitungan mulai lagi
    return 0


def _catat_salah(alamat, sekarang):
    """Catat sandi salah; kembalikan sisa percobaan (0 = baru saja dikunci)."""
    with _KUNCI_PERCOBAAN:
        p = _PERCOBAAN.setdefault(alamat, {"salah": 0, "sampai": None})
        p["salah"] += 1
        if p["salah"] >= BATAS_SALAH:
            p.update(salah=0, sampai=sekarang + LAMA_KUNCI_DETIK)
            return 0
        return BATAS_SALAH - p["salah"]


def _teks_menit(detik):
    menit = max(1, math.ceil(detik / 60))
    return f"{menit} menit"


def teks_sisa_kunci(detik):
    """Sisa penguncian untuk pembaca tanpa JavaScript: 277 -> "4 menit 37 detik",
    300 -> "5 menit", 37 -> "37 detik"."""
    menit, det = divmod(int(detik), 60)
    bagian = ([f"{menit} menit"] if menit else []) + ([f"{det} detik"] if det or not menit else [])
    return " ".join(bagian)


@bp.route("/login", methods=["GET", "POST"])
def login():
    tujuan = _tujuan_aman(request.values.get("next"))
    if session.get(KUNCI_SESSION):
        return redirect(tujuan)

    alamat = request.remote_addr or "?"
    sekarang = _sekarang()
    galat, status, sisa_kunci = None, 200, None
    sisa = _sisa_kunci(alamat, sekarang)
    if sisa:
        # Sisa dihitung server (detik bulat ke atas); halaman hanya
        # menampilkannya. Penguncian tetap ditegakkan di sini (429).
        sisa_kunci = math.ceil(sisa)
        galat = "Terlalu banyak kata sandi salah dari komputer ini. Login dikunci sementara."
        status = 429
    elif request.method == "POST":
        sandi = request.form.get("sandi") or ""
        if sandi and check_password_hash(current_app.config["ADMIN_PASSWORD_HASH"], sandi):
            with _KUNCI_PERCOBAAN:
                _PERCOBAAN.pop(alamat, None)
            session.clear()
            session[KUNCI_SESSION] = True
            session[KUNCI_AKTIF] = int(sekarang)
            return redirect(tujuan)
        sisa_coba = _catat_salah(alamat, sekarang)
        if sisa_coba:
            galat = (f"Kata sandi salah. Sisa {sisa_coba} percobaan sebelum login dikunci "
                     f"{_teks_menit(LAMA_KUNCI_DETIK)}.")
        else:
            sisa_kunci = LAMA_KUNCI_DETIK
            galat = (f"Kata sandi salah {BATAS_SALAH} kali. Login dari komputer ini dikunci "
                     f"sementara.")
            status = 429

    return render_template("admin/login.html", galat=galat, terkunci=status == 429,
                           sisa_kunci=sisa_kunci,
                           teks_sisa=teks_sisa_kunci(sisa_kunci) if sisa_kunci else None,
                           next=request.values.get("next") or ""), status


@bp.post("/logout")
def logout():
    session.pop(KUNCI_SESSION, None)
    session.pop(KUNCI_AKTIF, None)
    flash("Anda sudah keluar dari admin.", "sukses")
    return redirect(url_for("admin.login"))


@bp.route("/sandi", methods=["GET", "POST"])
def ganti_sandi():
    """Ganti kata sandi admin dari browser, tanpa terminal.

    Pengelola harian (yang merawat kamus) belum tentu orang yang memegang
    akses server. Hash baru ditulis ke .env (hanya baris itu, atomik) DAN
    dipasang ke config aplikasi yang sedang berjalan, jadi tidak perlu
    restart. Sesi saat ini dikeluarkan supaya sandi baru langsung terbukti
    berlaku saat login ulang.
    """
    if request.method == "GET":
        return render_template("admin/sandi.html",
                               panjang_minimal=PANJANG_SANDI_MINIMAL)

    lama = request.form.get("sandi_lama") or ""
    baru = request.form.get("sandi_baru") or ""
    ulang = request.form.get("sandi_ulang") or ""

    if not lama or not check_password_hash(current_app.config["ADMIN_PASSWORD_HASH"],
                                           lama):
        galat = "Kata sandi lama salah. Tidak ada yang diubah."
    elif len(baru) < PANJANG_SANDI_MINIMAL:
        galat = f"Kata sandi baru minimal {PANJANG_SANDI_MINIMAL} karakter."
    elif baru != ulang:
        galat = "Kata sandi baru dan ulangannya tidak sama."
    elif baru == lama:
        galat = "Kata sandi baru harus berbeda dari yang lama."
    else:
        galat = None

    if galat:
        return render_template("admin/sandi.html", galat=galat,
                               panjang_minimal=PANJANG_SANDI_MINIMAL)

    path_env = current_app.config["FILE_ENV"]
    if not os.path.exists(path_env):
        # Hash datang dari variabel lingkungan sistem, bukan berkas - tidak
        # ada yang bisa ditulis dari sini.
        return render_template(
            "admin/sandi.html", panjang_minimal=PANJANG_SANDI_MINIMAL,
            galat="Berkas .env tidak ditemukan di server, jadi sandi tidak bisa "
                  "diganti dari sini. Minta tim IT mengganti ADMIN_PASSWORD_HASH "
                  "di konfigurasi server.")

    hash_baru = generate_password_hash(baru)
    try:
        tulis_admin_hash(path_env, hash_baru)
    except OSError as e:
        return render_template(
            "admin/sandi.html", panjang_minimal=PANJANG_SANDI_MINIMAL,
            galat=f"Gagal menulis .env: {e}. Sandi TIDAK berubah.")

    # Berlaku seketika untuk proses ini; .env sudah berisi hash baru untuk
    # kali berikutnya aplikasi dijalankan.
    current_app.config["ADMIN_PASSWORD_HASH"] = hash_baru
    session.clear()
    flash("Kata sandi berhasil diganti. Masuk lagi dengan kata sandi baru.",
          "sukses")
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
    ringkasan = pembaruan.ringkasan_terakhir(_mode_uji())
    return render_template(
        "admin/beranda.html",
        jumlah_kelompok=len(kamus),
        jumlah_varian=sum(len(v) for v in kamus.values()),
        jumlah_log=LogPencarian.query.count(),
        jumlah_lemah=LogPencarian.query.filter(
            db.or_(LogPencarian.jumlah_hasil == 0,
                   LogPencarian.skor_tertinggi < AMBANG_KUERI_LEMAH)).count(),
        pembaruan_berjalan=pembaruan.sedang_berjalan(),
        # Kartu Perbarui Data dan Ganti Kata Sandi (26 Nov 2026): angka dari
        # data, bukan ditulis tetap di template.
        tanggal_pembaruan=_tanggal_singkat(ringkasan["selesai_pada"]) if ringkasan else None,
        pembaruan_gagal=bool(ringkasan and ringkasan.get("status") == "gagal"),
        jumlah_publikasi=db.session.query(db.func.count(Publikasi.id)).scalar(),
        lama_sesi=teks_lama_sesi(current_app.config["SESI_ADMIN_MENIT"]),
    )


BULAN_SINGKAT = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


def _tanggal_singkat(dt):
    """Waktu UTC -> "25 Nov" (zona waktu komputer), untuk kartu beranda admin."""
    if not dt:
        return None
    lokal = dt.astimezone()
    return f"{lokal.day} {BULAN_SINGKAT[lokal.month - 1]}"


def teks_lama_sesi(menit):
    """120 -> "2 jam", 90 -> "1 jam 30 menit", 45 -> "45 menit"."""
    jam, sisa = divmod(int(menit), 60)
    if not jam:
        return f"{sisa} menit"
    return f"{jam} jam" + (f" {sisa} menit" if sisa else "")


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
# Pembaruan data dari WebAPI BPS
# --------------------------------------------------------------------------

def _waktu_lokal(dt):
    return dt.astimezone().strftime("%d-%m-%Y %H:%M") if dt else None


def _teks_durasi(detik):
    """Detik -> "±3 menit" / "±2,5 jam" untuk perkiraan di hasil cek."""
    detik = detik or 0
    if detik < 90:
        return f"±{max(1, round(detik))} detik"
    if detik < 5400:
        return f"±{round(detik / 60)} menit"
    return f"±{detik / 3600:.1f} jam".replace(".", ",")


def _nilai_formulir(p):
    """Isi formulir dari Pilihan (bawaan, run terakhir, atau kiriman yang ditolak)."""
    return {"wilayah": set(p.wilayah), "jenis": set(p.jenis), "dari": p.dari, "sampai": p.sampai}


def _nilai_kiriman(form):
    """Isi formulir dari kiriman yang DITOLAK: hanya nilai yang sah yang
    ditampilkan ulang, sisanya bawaan."""
    b = pilihan_pembaruan.bawaan()
    tahun = pilihan_pembaruan.daftar_tahun()

    def tahun_sah(nama, cadangan):
        try:
            t = int(form.get(nama, ""))
        except ValueError:
            return cadangan
        return t if t in tahun else cadangan

    return {"wilayah": set(form.getlist("wilayah")) & set(b.wilayah),
            "jenis": set(form.getlist("jenis")) & set(pilihan_pembaruan.SEMUA_JENIS),
            "dari": tahun_sah("dari", b.dari), "sampai": tahun_sah("sampai", b.sampai)}


def _halaman_perbarui(nilai=None, galat=None, status=200):
    """Satu halaman untuk tiga keadaan: siap dimulai / sedang berjalan / selesai.

    Ringkasan hasil TIDAK ditebak dari teks log - dibaca dari
    data/pembaruan_terakhir.json yang ditulis perbarui.py sendiri. Karena
    berkas itu ditulis di jalur .bat juga, halaman ini tetap tahu hasil
    pembaruan terakhir meski dijalankan tim IT dari terminal.

    Formulir pilihan (24 Nov 2026): diisi bawaan, atau pilihan run terakhir di
    sesi server ini (supaya "Cek dulu" lalu "Mulai pembaruan" memakai pilihan
    yang sama), atau kiriman yang ditolak.
    """
    uji = _mode_uji()
    k = pembaruan.keadaan()
    pid_lain = None if k["berjalan"] else pembaruan.pid_proses_lain()
    ringkasan = pembaruan.ringkasan_terakhir(uji)
    cek_sesi_ini = bool(k["selesai"]) and k["jenis"] == "cek"

    # Ringkasan dianggap milik run di sesi ini hanya kalau ditulis SETELAH
    # run itu dimulai; kalau tidak, proses berhenti sebelum sempat menulis.
    dari_sesi_ini = bool(
        k["selesai"] and not cek_sesi_ini and ringkasan and ringkasan["selesai_pada"]
        and ringkasan["selesai_pada"] >= k["mulai"])
    cek = _cek_sesi_ini(uji, k)
    # Kartu ringkasan (25 Nov 2026). Sisa ruang disk dibaca saat halaman dibuka.
    kartu_cek = _kartu_cek(cek) if cek and cek["status"] != "gagal" else None
    kartu_pembaruan = ringkasan_pembaruan.ringkas_pembaruan(ringkasan) if ringkasan else None

    aktif = pilihan_pembaruan.wilayah_aktif()
    if nilai is None:
        nilai = _nilai_formulir(k["pilihan"] or pilihan_pembaruan.bawaan())
    return render_template(
        "admin/perbarui.html",
        berjalan=k["berjalan"], pid_lain=pid_lain, jenis_proses=k["jenis"] or "pembaruan",
        baris=k["baris"], kode_keluar=k["kode_keluar"],
        selesai_sesi_ini=bool(k["selesai"]) and not cek_sesi_ini, dari_sesi_ini=dari_sesi_ini,
        cek_sesi_ini=cek_sesi_ini, cek=cek,
        waktu_cek=_waktu_lokal(cek["selesai_pada"]) if cek else None,
        ringkasan=ringkasan,
        waktu_ringkasan=_waktu_lokal(ringkasan["selesai_pada"]) if ringkasan else None,
        waktu_mulai=_waktu_lokal(k["mulai"]),
        f_provinsi=[w for w in aktif if w["kode"] == pilihan_pembaruan.DOMAIN_PROVINSI],
        f_kabkota=[w for w in aktif if w["kode"] != pilihan_pembaruan.DOMAIN_PROVINSI],
        f_tahun=pilihan_pembaruan.daftar_tahun(), f_nilai=nilai, f_galat=galat,
        f_jumlah_wilayah=len(aktif), nama_jenis=pilihan_pembaruan.NAMA_JENIS,
        tahun_teruji=pilihan_pembaruan.TAHUN_TERUJI, durasi=_teks_durasi,
        kartu_cek=kartu_cek, kartu_pembaruan=kartu_pembaruan,
        mulai_nonaktif=bool(kartu_cek and not kartu_cek["boleh_mulai"]),
    ), status


def _cek_sesi_ini(uji, k):
    """Hasil cek milik run "Cek dulu" terakhir di sesi server ini, atau None.
    Berkas cek dianggap milik run itu hanya kalau ditulis SETELAH run dimulai."""
    if not (k["selesai"] and k["jenis"] == "cek"):
        return None
    c = pembaruan.hasil_cek(uji)
    if c and c["selesai_pada"] and c["selesai_pada"] >= k["mulai"]:
        return c
    return None


def _kartu_cek(cek):
    return ringkasan_pembaruan.ringkas_cek(
        cek, ringkasan_pembaruan.sisa_ruang_mb(), ringkasan_pembaruan.ambang(),
        ringkasan_pembaruan.nama_drive())


@bp.get("/perbarui")
def perbarui():
    return _halaman_perbarui()


def _mode_uji():
    """KonfigurasiUji: tombol pembaruan menjalankan perbarui.py --db-uji."""
    return bool(current_app.config.get("KONFIGURASI_UJI", False))


@bp.post("/perbarui/mulai")
def perbarui_mulai():
    """Tombol "Mulai pembaruan" dan "Cek dulu" (aksi=cek) di formulir pilihan.

    Pilihan diperiksa DI SINI (pilihan_pembaruan.dari_formulir), bukan hanya
    di browser; yang ditolak dirender ulang dengan pesan, HTTP 400, dan tidak
    ada proses yang dimulai. POST tanpa formulir (tombol lama) = bawaan.
    """
    try:
        pilihan = pilihan_pembaruan.dari_formulir(request.form)
    except PilihanTidakSah as e:
        return _halaman_perbarui(nilai=_nilai_kiriman(request.form), galat=e.galat, status=400)
    cek = request.form.get("aksi") == "cek"
    if not cek:
        # Tombol Mulai pembaruan dinonaktifkan kalau cek terakhir (pilihan yang
        # sama) menunjukkan ruang disk kurang; di server ditolak juga, dengan
        # sisa ruang yang dibaca SEKARANG (25 Nov 2026).
        hasil = _cek_sesi_ini(_mode_uji(), pembaruan.keadaan())
        if hasil and hasil["status"] != "gagal" and hasil["pilihan"] == pilihan.ke_dict():
            kartu = _kartu_cek(hasil)
            if not kartu["boleh_mulai"]:
                return _halaman_perbarui(nilai=_nilai_formulir(pilihan),
                                         galat=[kartu["alasan_tidak_boleh"]], status=409)
    if not pembaruan.mulai(_mode_uji(), pilihan=pilihan, cek=cek):
        flash("Pembaruan sedang berjalan. Tunggu sampai selesai - dua pembaruan "
              "bersamaan bisa saling menimpa data.", "gagal")
    return redirect(url_for("admin.perbarui"))


@bp.get("/perbarui/aliran")
def perbarui_aliran():
    """Keluaran proses sebagai teks yang mengalir; berhenti saat proses usai.

    Dipakai pembaruan.js. Tanpa JS, halaman /admin/perbarui memuat ulang
    dirinya tiap 5 detik lewat <meta refresh> di <noscript>.
    """
    try:
        dari = max(0, int(request.args.get("dari", 0)))
    except ValueError:
        dari = 0
    return Response(pembaruan.aliran(dari), mimetype="text/plain",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


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

    # Gagal = tidak ada hasil, ATAU skor terbaiknya di bawah ambang. Aturan
    # yang sama dengan hitungan "kueri lemah" di beranda admin. Skor kosong
    # saja BUKAN tanda gagal: kueri yang hanya berisi nama wilayah ("tanah
    # laut") menampilkan publikasi wilayah itu tanpa skor (lihat _catat_log).
    # Kueri tanpa hasil sudah tertangkap oleh syarat pertama. Di SQL,
    # NULL < ambang bernilai NULL, jadi skor kosong tidak lolos syarat kedua.
    if hanya_gagal:
        q = q.having(db.or_(
            db.func.max(LogPencarian.jumlah_hasil) == 0,
            db.func.max(LogPencarian.skor_tertinggi) < AMBANG_KUERI_LEMAH,
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
