"""Tangkapan layar halaman PENCARIAN (bukti tidak berubah), 24 Nov 2026.

Jalankan dengan venv Playwright:
  C:/Users/Dani/alat-playwright/Scripts/python.exe tangkap_pencarian.py PORT FOLDER [CSS_PENGGANTI]

CSS_PENGGANTI: berkas style.css yang disajikan menggantikan /static/css/style.css
(intersepsi request di browser). Dipakai untuk potret "sebelum" = CSS versi
HEAD (git show HEAD:app/static/css/style.css), dengan server dan HTML yang sama.
HTML halaman pencarian dibuktikan identik terpisah (tests/potret_tampilan.py).

Supaya dua potret dari kode yang sama identik piksel demi piksel:
  - angka "N ms" diganti "__ ms";
  - fokus autofocus kotak cari dilepas, kursor teks transparan;
  - gambar sampul dimuat penuh lalu dibuat transparan (opacity 0). Kotaknya
    tetap ikut dibandingkan; isinya derau penskalaan JPEG (beda <= 9/255 di
    antara dua potret kode yang sama).
"""
import os
import sys

from playwright.sync_api import sync_playwright

PORT, KELUAR = sys.argv[1], sys.argv[2]
CSS = open(sys.argv[3], "rb").read() if len(sys.argv) > 3 else None
URL = [("beranda", "/"), ("beranda-kab", "/?w=6301"), ("hasil", "/hasil?q=penduduk"),
       ("hasil-wilayah", "/hasil?q=pdrb&w=6301"), ("hasil-kec", "/hasil?q=penduduk&kec=1"),
       ("hasil-kosong", "/hasil?q=zzqqxx")]
LEBAR = [1280, 375]
os.makedirs(KELUAR, exist_ok=True)
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome")
    for lebar in LEBAR:
        hal = br.new_page(viewport={"width": lebar, "height": 900}, device_scale_factor=1)
        if CSS is not None:
            hal.route("**/static/css/style.css*",
                      lambda r: r.fulfill(status=200, body=CSS, content_type="text/css; charset=utf-8"))
        for nama, u in URL:
            hal.goto(f"http://127.0.0.1:{PORT}{u}", wait_until="networkidle")
            hal.evaluate(r"""() => { for (const el of document.querySelectorAll('body *')) {
                for (const n of el.childNodes) if (n.nodeType === 3 && /\d+ ms/.test(n.textContent))
                    n.textContent = n.textContent.replace(/\d+ ms/g, '__ ms'); } }""")
            hal.evaluate("""async () => { const im = [...document.images];
                im.forEach(i => { i.loading = 'eager'; });
                await Promise.all(im.map(i => i.decode().catch(() => null))); }""")
            hal.wait_for_load_state("networkidle")
            hal.wait_for_function("[...document.images].every(i => i.complete)")
            hal.add_style_tag(content="* { caret-color: transparent !important; } "
                                      "img { opacity: 0 !important; }")
            hal.evaluate("() => document.activeElement && document.activeElement.blur()")
            hal.wait_for_timeout(300)
            hal.screenshot(path=f"{KELUAR}/{lebar:04d}-{nama}.png", full_page=True)
        hal.close()
    br.close()
print("selesai", len(URL) * len(LEBAR))
