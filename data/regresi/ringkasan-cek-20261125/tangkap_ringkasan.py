"""Tangkapan layar kartu ringkasan /admin/perbarui (25 Nov 2026), 1280 dan 375 px.

Server = server_tangkapan.py di folder ini (DATABASE UJI) dengan WebAPI TIRUAN
(form-pembaruan-20261124/tiruan_tangkapan.py, dibangun dari database uji +
simulasi). "Cek dulu" tidak pernah menghubungi BPS dan tidak mengubah
database. Tombol "Mulai pembaruan" TIDAK pernah diklik di sini.

  C:/Users/Dani/alat-playwright/Scripts/python.exe tangkap_ringkasan.py PORT FOLDER

Urutan: (1) ringkasan sesudah pembaruan = ringkasan_terakhir-uji.json asli
(tarik kecil Tanah Laut 24 Nov), (2) cek Kota Banjarmasin = abu-abu,
(3) cek Tanah Laut 2024-2026 = hijau, (4) sama dengan sisa disk palsu 40 MB
= merah, (5) cek semua wilayah rilis 2024-2026 = kuning. Dicatat juga: jumlah
kolom kotak angka, gulir mendatar, tombol Mulai nonaktif, dan <details>
rincian yang dibuka TANPA JavaScript.
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

PORT, KELUAR = sys.argv[1], sys.argv[2]
DASAR = f"http://127.0.0.1:{PORT}"
FLAG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SISA_DISK_MB.txt")
os.makedirs(KELUAR, exist_ok=True)
catatan = {}


def ukur(hal, nama, id_kartu):
    lebar = hal.viewport_size["width"]
    info = hal.evaluate("""(id) => {
        const k = document.getElementById(id);
        const kotak = k ? [...k.querySelectorAll('.kotak-angka')] : [];
        const kiri = [...new Set(kotak.map(x => Math.round(x.getBoundingClientRect().left)))];
        const tombol = document.querySelector('button[value=mulai]');
        return {status: k && k.dataset.status, judul: k && k.querySelector('.status-ringkasan').textContent.trim(),
                kalimat: k && (k.querySelector('.kalimat-ringkasan') || {}).textContent,
                nilai: kotak.map(x => x.querySelector('.nilai-angka').textContent.trim()),
                kolom: kiri.length, baris: Math.ceil(kotak.length / Math.max(kiri.length, 1)),
                nilai_satu_baris: kotak.every(x => { const n = x.querySelector('.nilai-angka');
                    return n.getClientRects().length && n.getBoundingClientRect().height < 1.6 * parseFloat(getComputedStyle(n).lineHeight); }),
                scrollWidth: document.documentElement.scrollWidth,
                mulai_nonaktif: tombol ? tombol.disabled : null,
                alasan_mulai: (document.getElementById('alasan-mulai') || {}).textContent || null};
    }""", id_kartu)
    info["gulir_mendatar"] = info["scrollWidth"] > lebar
    catatan[f"{lebar:04d}-{nama}"] = info


def potret(hal, nama, id_kartu):
    hal.add_style_tag(content="* { caret-color: transparent !important; }")
    hal.evaluate("() => document.activeElement && document.activeElement.blur()")
    ukur(hal, nama, id_kartu)
    hal.screenshot(path=f"{KELUAR}/{hal.viewport_size['width']:04d}-{nama}.png", full_page=True)


def cek_dulu(hal, wilayah, dari):
    hal.set_viewport_size({"width": 1280, "height": 900})
    hal.goto(f"{DASAR}/admin/perbarui")
    hal.click("button[data-centang=kosong]")
    for w in wilayah:
        hal.check(f'input[name="wilayah"][value="{w}"]')
    hal.select_option('select[name="dari"]', dari)
    hal.click('button[value="cek"]')
    hal.wait_for_selector("text=Cek sedang berjalan", timeout=30000)
    hal.wait_for_selector("#hasil-cek, .kabar-gagal", timeout=900000)


def dua_lebar(hal, nama, id_kartu="ringkasan-cek"):
    for lebar in (1280, 375):
        hal.set_viewport_size({"width": lebar, "height": 900})
        hal.goto(f"{DASAR}/admin/perbarui")
        potret(hal, nama, id_kartu)


if os.path.exists(FLAG):
    os.remove(FLAG)
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome")
    ctx = br.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
    hal = ctx.new_page()
    hal.goto(f"{DASAR}/admin/login?next=/admin/perbarui")
    hal.fill('input[name="sandi"]', "sandi-tangkapan-layar")
    hal.click('button[type="submit"]')
    hal.wait_for_url("**/admin/perbarui")

    dua_lebar(hal, "1-sesudah-pembaruan", "ringkasan-pembaruan")
    cek_dulu(hal, ["6371"], "2025")
    dua_lebar(hal, "2-cek-terbaru")
    cek_dulu(hal, ["6301"], "2024")
    dua_lebar(hal, "3-cek-siap")
    # rincian per wilayah dibuka, desktop
    hal.set_viewport_size({"width": 1280, "height": 900})
    hal.goto(f"{DASAR}/admin/perbarui")
    hal.click("#hasil-cek details.rincian-wilayah > summary")
    potret(hal, "3b-cek-siap-rincian-dibuka", "ringkasan-cek")
    # <details> tanpa JavaScript
    tanpa_js = br.new_context(viewport={"width": 375, "height": 900}, java_script_enabled=False,
                              storage_state=ctx.storage_state())
    h2 = tanpa_js.new_page()
    h2.goto(f"{DASAR}/admin/perbarui")
    sebelum = h2.locator("#hasil-cek table.tabel-cek").is_visible()
    h2.click("#hasil-cek details.rincian-wilayah > summary")
    catatan["tanpa-js-rincian"] = {"tabel_terlihat_sebelum_klik": sebelum,
                                   "tabel_terlihat_sesudah_klik": h2.locator("#hasil-cek table.tabel-cek").is_visible()}
    h2.screenshot(path=f"{KELUAR}/0375-3c-tanpa-js-rincian-dibuka.png", full_page=True)
    tanpa_js.close()
    # sisa disk palsu 40 MB: merah, Mulai nonaktif
    open(FLAG, "w").write("40")
    try:
        dua_lebar(hal, "4-cek-disk-kurang")
    finally:
        os.remove(FLAG)
    cek_dulu(hal, ["6300", "6301", "6302", "6303", "6304", "6305", "6306", "6307", "6308", "6309",
                   "6310", "6311", "6371", "6372"], "2024")
    dua_lebar(hal, "5-cek-semua-wilayah")
    br.close()

json.dump(catatan, open(f"{KELUAR}/catatan.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(json.dumps(catatan, indent=1, ensure_ascii=False))
