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

    from app.routes.admin import bp as bp_admin
    from app.routes.pencarian import bp as bp_pencarian

    app.register_blueprint(bp_pencarian)
    app.register_blueprint(bp_admin, url_prefix="/admin")

    # Kolom log_pencarian.wilayah_filter (filter wilayah, 10 Nov 2026) untuk
    # database lama. Di awal request, bukan di sini: create_app() juga
    # dipanggil skrip dan pemeriksa .bat sebelum koneksi MySQL dipastikan.
    from app.models.log_pencarian import pastikan_kolom

    @app.before_request
    def _pastikan_kolom_log():
        pastikan_kolom()

    return app
    