"""Application factory untuk sistem pencarian publikasi BPS."""

import re

from flask import Flask
from markupsafe import Markup, escape

from app.config import Config, periksa_konfigurasi
from app.models import db


def _sorot(teks, kata):
    """Tandai kata kunci di dalam teks hasil pencarian.

    Pencocokan hanya di AWAL KATA, dan seluruh kata ikut tersorot. Pencocokan
    substring bebas menghasilkan sorotan yang jatuh di tengah kata dan terlihat
    rusak: "impor" menyorot separuh "Import", "miskin" menyorot bagian tengah
    "Kemiskinan". Menyorot dari awal kata sampai habis membuat kata utuh yang
    memang berkaitan tetap tertandai ("Ekspor" -> "Ekspornya") tanpa pernah
    memotong kata di tengah.

    Teks di-escape DULU, penanda <mark> ditambahkan sesudahnya - jadi judul
    yang memuat karakter HTML tidak bisa menyuntikkan markup.
    """
    if not teks:
        return ""
    aman = str(escape(teks))
    if not kata:
        return Markup(aman)
    pola = "|".join(re.escape(k) for k in kata if k)
    if not pola:
        return Markup(aman)
    # (?<![0-9A-Za-z]) mengunci awal kata; [0-9A-Za-z]* melahap sisa katanya.
    lengkap = rf"(?<![0-9A-Za-z])(?:{pola})[0-9A-Za-z]*"
    return Markup(
        re.sub(lengkap, lambda m: f"<mark>{m.group(0)}</mark>",
               aman, flags=re.IGNORECASE))


def create_app(config_class: type[Config] = Config) -> Flask:
    # Gagal di sini, bukan saat request pertama: .env yang belum lengkap
    # harus ketahuan begitu perintah dijalankan, bukan saat petugas sudah
    # membuka halaman.
    periksa_konfigurasi(config_class)

    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    app.add_template_filter(_sorot, "sorot")
    from app.services import sampul
    app.add_template_global(sampul.info, "info_sampul")

    from app.config import menit_sesi_admin
    from app.routes.admin import bp as bp_admin
    from app.routes.admin import konteks_menu, periksa_sesi
    from app.routes.pencarian import bp as bp_pencarian

    app.register_blueprint(bp_pencarian)
    app.register_blueprint(bp_admin, url_prefix="/admin")

    # Sesi admin (25 Nov 2026): kedaluwarsa sesudah tidak aktif, diperiksa di
    # SEMUA halaman (menu admin ada di kop tiap halaman). Didaftarkan sebelum
    # pastikan_kolom supaya urutannya: sesi dulu, lalu penjaga blueprint admin.
    app.before_request(periksa_sesi)
    app.context_processor(konteks_menu)
    menit, sah = menit_sesi_admin(config_class.SESI_ADMIN_MENIT_TEKS)
    if not sah:
        print(f"PERINGATAN: SESI_ADMIN_MENIT di .env tidak sah "
              f"({config_class.SESI_ADMIN_MENIT_TEKS!r}); dipakai bawaan {menit} menit.",
              flush=True)

    # Reverse proxy (25 Nov 2026): dengan JUMLAH_PROXY = N > 0, alamat pengguna
    # (request.remote_addr, dipakai penguncian login) diambil dari entri ke-N
    # dari kanan di X-Forwarded-For. Hanya isi kalau memang ada proxy: tanpa
    # proxy, header itu bisa dipalsukan pengguna untuk lolos dari penguncian.
    from app.config import jumlah_proxy
    n_proxy, sah = jumlah_proxy(config_class.JUMLAH_PROXY_TEKS)
    if not sah:
        print(f"PERINGATAN: JUMLAH_PROXY di .env tidak sah "
              f"({config_class.JUMLAH_PROXY_TEKS!r}); dipakai 0 (tanpa proxy).", flush=True)
    app.config["JUMLAH_PROXY"] = n_proxy
    if n_proxy:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n_proxy)

    # Kolom tambahan (log_pencarian.wilayah_filter, publikasi.halaman_ocr)
    # untuk database lama. Di awal request, bukan di sini: create_app() juga
    # dipanggil skrip dan pemeriksa .bat sebelum koneksi MySQL dipastikan.
    from app.models.skema import pastikan_kolom

    @app.before_request
    def _pastikan_kolom_tambahan():
        pastikan_kolom()

    return app
    