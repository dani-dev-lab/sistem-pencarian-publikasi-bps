"""Application factory untuk sistem pencarian publikasi BPS."""

import re

from flask import Flask
from markupsafe import Markup, escape

from app.config import Config
from app.models import db


def _sorot(teks, kata):
    """Tandai kata kunci di dalam teks hasil pencarian.

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
    return Markup(
        re.sub(f"({pola})", lambda m: f"<mark>{m.group(1)}</mark>",
               aman, flags=re.IGNORECASE))


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    app.add_template_filter(_sorot, "sorot")

    from app.routes.admin import bp as bp_admin
    from app.routes.pencarian import bp as bp_pencarian

    app.register_blueprint(bp_pencarian)
    app.register_blueprint(bp_admin, url_prefix="/admin")

    return app
    