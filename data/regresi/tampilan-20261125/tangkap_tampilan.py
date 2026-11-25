"""Tangkapan layar tampilan sebelum/sesudah (25 Nov 2026), 1280 dan 375 px.

Server = form-pembaruan-20261124/server_tangkapan.py (DATABASE UJI, sandi admin
sementara di memori). Gambar sampul TAMPIL (ini potret untuk dilihat orang,
bukan banding piksel). Untuk tiap halaman: satu potret penuh, ditambah potret
layar sesudah digulir 1.500 px untuk halaman hasil (tombol "ke atas").

  C:/Users/Dani/alat-playwright/Scripts/python.exe tangkap_tampilan.py PORT FOLDER
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

PORT, KELUAR = sys.argv[1], sys.argv[2]
DASAR = f"http://127.0.0.1:{PORT}"
os.makedirs(KELUAR, exist_ok=True)
PENCARIAN = [("01-beranda", "/"), ("02-hasil-penduduk", "/hasil?q=penduduk"),
             ("03-hasil-pdrb-tanah-laut", "/hasil?q=pdrb&w=6301"),
             ("04-hasil-wilayah-saja", "/hasil?q=tanah+laut"),
             ("05-hasil-kecamatan", "/hasil?q=penduduk&w=6301&kec=1")]
ADMIN = [("11-admin-beranda", "/admin/"), ("12-admin-kamus", "/admin/kamus"),
         ("13-admin-log", "/admin/log"), ("14-admin-perbarui", "/admin/perbarui"),
         ("15-admin-sandi", "/admin/sandi"), ("16-admin-periksa", "/admin/log/periksa?q=p0")]
catatan = {}


def siap(hal):
    hal.evaluate("""async () => { const im = [...document.images];
        im.forEach(i => { i.loading = 'eager'; });
        await Promise.all(im.map(i => i.decode().catch(() => null))); }""")
    hal.wait_for_load_state("networkidle")
    hal.add_style_tag(content="* { caret-color: transparent !important; }")
    hal.evaluate("() => document.activeElement && document.activeElement.blur()")


with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome")
    for lebar in (1280, 375):
        ctx = br.new_context(viewport={"width": lebar, "height": 900}, device_scale_factor=1)
        hal = ctx.new_page()
        for nama, u in PENCARIAN:
            hal.goto(DASAR + u, wait_until="networkidle")
            siap(hal)
            hal.screenshot(path=f"{KELUAR}/{lebar:04d}-{nama}.png", full_page=True)
            catatan[f"{lebar:04d}-{nama}"] = {"scrollWidth": hal.evaluate("document.documentElement.scrollWidth")}
            if u.startswith("/hasil"):
                hal.evaluate("window.scrollTo(0, 1500)")
                hal.wait_for_timeout(400)
                hal.screenshot(path=f"{KELUAR}/{lebar:04d}-{nama}-gulir.png")
        hal.goto(f"{DASAR}/admin/login?next=/admin/")
        siap(hal)
        hal.screenshot(path=f"{KELUAR}/{lebar:04d}-10-admin-login.png", full_page=True)
        hal.fill('input[name="sandi"]', "sandi-tangkapan-layar")
        hal.click('form button[type="submit"]')
        hal.wait_for_load_state("networkidle")
        for nama, u in ADMIN:
            hal.goto(DASAR + u, wait_until="networkidle")
            siap(hal)
            hal.screenshot(path=f"{KELUAR}/{lebar:04d}-{nama}.png", full_page=True)
            catatan[f"{lebar:04d}-{nama}"] = {"scrollWidth": hal.evaluate("document.documentElement.scrollWidth")}
        # halaman pencarian sesudah login (penanda admin di kop)
        hal.goto(DASAR + "/hasil?q=penduduk", wait_until="networkidle")
        siap(hal)
        hal.screenshot(path=f"{KELUAR}/{lebar:04d}-17-hasil-saat-login.png")
        ctx.close()
    br.close()
json.dump(catatan, open(f"{KELUAR}/catatan.json", "w", encoding="utf-8"), indent=1)
print("selesai", len(catatan))
