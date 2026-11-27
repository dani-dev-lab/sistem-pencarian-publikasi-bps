"""Tangkapan layar formulir /admin/perbarui, desktop (1280) dan ponsel (375).

Server = server_tangkapan.py (DATABASE UJI) dengan WebAPI TIRUAN
(tiruan_tangkapan.py): "Cek dulu" tidak pernah menghubungi BPS dan hanya
membaca database uji. Tombol "Mulai pembaruan" TIDAK pernah diklik dengan
pilihan sah di sini (hanya kiriman yang ditolak server).

  C:/Users/Dani/alat-playwright/Scripts/python.exe tangkap_formulir.py PORT FOLDER
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

PORT, KELUAR = sys.argv[1], sys.argv[2]
DASAR = f"http://127.0.0.1:{PORT}"
os.makedirs(KELUAR, exist_ok=True)
catatan = {}


def potret(hal, nama):
    lebar = hal.viewport_size["width"]
    hal.add_style_tag(content="* { caret-color: transparent !important; }")
    hal.evaluate("() => document.activeElement && document.activeElement.blur()")
    # Tidak ada gulir mendatar di halaman (lebar dokumen <= lebar layar).
    gulir = hal.evaluate("() => document.documentElement.scrollWidth")
    catatan[f"{lebar:04d}-{nama}"] = {"scrollWidth": gulir, "lebar_layar": lebar,
                                      "gulir_mendatar": gulir > lebar}
    hal.screenshot(path=f"{KELUAR}/{lebar:04d}-{nama}.png", full_page=True)


def tunggu_cek(hal):
    hal.wait_for_selector("text=Cek sedang berjalan", timeout=30000)
    hal.wait_for_selector("#hasil-cek, .kabar-gagal", timeout=900000)


with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome")
    ctx = br.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
    hal = ctx.new_page()
    hal.goto(f"{DASAR}/admin/login?next=/admin/perbarui")
    hal.fill('input[name="sandi"]', "sandi-tangkapan-layar")
    hal.click('button[type="submit"]')
    hal.wait_for_url("**/admin/perbarui")

    for lebar in (1280, 375):
        hal.set_viewport_size({"width": lebar, "height": 900})
        hal.goto(f"{DASAR}/admin/perbarui")
        potret(hal, "1-bawaan")
        # hanya provinsi: kelompok jenis nonaktif (form-pembaruan.js)
        hal.click("button[data-centang=kosong]")
        hal.check('input[name="wilayah"][value="6300"]')
        catatan[f"{lebar:04d}-2-jenis-nonaktif"] = hal.evaluate(
            "() => document.getElementById('pilihan-jenis').disabled")
        potret(hal, "2-hanya-provinsi")
        # ditolak server: tanpa wilayah, Dari > Sampai
        hal.click("button[data-centang=kosong]")
        hal.select_option('select[name="dari"]', "2026")
        hal.select_option('select[name="sampai"]', "2024")
        with hal.expect_response("**/admin/perbarui/mulai") as r:
            hal.click('button[value="mulai"]')
        catatan[f"{lebar:04d}-3-status-ditolak"] = r.value.status
        potret(hal, "3-ditolak")

    # Cek dulu: Kab. Tanah Laut, rilis 2024-2026, kedua jenis
    hal.set_viewport_size({"width": 1280, "height": 900})
    hal.goto(f"{DASAR}/admin/perbarui")
    hal.click("button[data-centang=kosong]")
    hal.check('input[name="wilayah"][value="6301"]')
    hal.select_option('select[name="dari"]', "2024")
    hal.click('button[value="cek"]')
    tunggu_cek(hal)
    for lebar in (1280, 375):
        hal.set_viewport_size({"width": lebar, "height": 900})
        hal.goto(f"{DASAR}/admin/perbarui")
        potret(hal, "4-cek-tanah-laut")
    catatan["cek-tanah-laut-formulir-terisi"] = hal.evaluate("""() => ({
        wilayah: [...document.querySelectorAll('input[name=wilayah]:checked')].map(x => x.value),
        dari: document.querySelector('select[name=dari]').value,
        sampai: document.querySelector('select[name=sampai]').value})""")

    # Cek dulu: bawaan (semua wilayah) -> peringatan penarikan besar
    hal.set_viewport_size({"width": 1280, "height": 900})
    hal.click("button[data-centang=semua]")
    hal.select_option('select[name="dari"]', "2025")
    hal.click('button[value="cek"]')
    tunggu_cek(hal)
    for lebar in (1280, 375):
        hal.set_viewport_size({"width": lebar, "height": 900})
        hal.goto(f"{DASAR}/admin/perbarui")
        potret(hal, "5-cek-besar")
    br.close()

json.dump(catatan, open(f"{KELUAR}/catatan.json", "w", encoding="utf-8"), indent=1)
print(json.dumps(catatan, indent=1))
