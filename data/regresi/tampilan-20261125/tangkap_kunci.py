"""Tangkapan layar revisi 26 Nov 2026 (kartu beranda admin + login terkunci), 1280 dan 375 px.

Server (semuanya DATABASE UJI, sandi sementara di memori):
  P_RIWAYAT  server_kunci.py P 10                 (beranda dengan riwayat; penguncian 10 detik)
  P_TANPA    server_kunci.py P 300 tanpa-riwayat  (beranda tanpa riwayat)
  P_KUNCI1   server_kunci.py P 300                (login terkunci di 1280 px)
  P_KUNCI2   server_kunci.py P 300                (login terkunci di 375 px; satu server per
                                                   lebar karena penguncian berlaku per alamat)

  C:/Users/Dani/alat-playwright/Scripts/python.exe tangkap_kunci.py P_RIWAYAT P_TANPA P_KUNCI1 P_KUNCI2 FOLDER

Nama berkas 10/11 sama dengan layar-v3 (desain final 25 Nov) supaya bisa dibandingkan
dengan gabung_banding.py; 11b, 18-21 halaman baru.
"""
import os
import sys

from playwright.sync_api import sync_playwright

P_RIWAYAT, P_TANPA, P_KUNCI1, P_KUNCI2, KELUAR = sys.argv[1:6]
SANDI = "sandi-tangkapan-layar"
os.makedirs(KELUAR, exist_ok=True)


def u(port, jalur):
    return f"http://127.0.0.1:{port}{jalur}"


def potret(hal, nama, lebar, lepas_fokus=True, js=True):
    hal.wait_for_load_state("networkidle")
    if not js:                              # tanpa JavaScript: evaluate/add_style_tag macet
        hal.screenshot(path=f"{KELUAR}/{lebar:04d}-{nama}.png", full_page=True)
        return
    hal.add_style_tag(content="* { caret-color: transparent !important; }")
    if lepas_fokus:
        hal.evaluate("() => document.activeElement && document.activeElement.blur()")
    hal.screenshot(path=f"{KELUAR}/{lebar:04d}-{nama}.png", full_page=True)


def masuk(hal, port):
    hal.goto(u(port, "/admin/login"))
    hal.fill('input[name="sandi"]', SANDI)
    with hal.expect_navigation():
        hal.click('button[type="submit"]')


def salah(hal, kali):
    for _ in range(kali):
        hal.fill('input[name="sandi"]', "salah-sekali")
        with hal.expect_navigation():
            hal.click('button[type="submit"]')


with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome")
    for lebar, p_kunci in ((1280, P_KUNCI1), (375, P_KUNCI2)):
        vp = {"width": lebar, "height": 900 if lebar == 1280 else 800}
        ktx = br.new_context(viewport=vp)
        hal = ktx.new_page()
        hal.goto(u(P_RIWAYAT, "/admin/login"))
        potret(hal, "10-admin-login", lebar)
        masuk(hal, P_RIWAYAT)
        potret(hal, "11-admin-beranda", lebar)
        ktx.close()

        ktx = br.new_context(viewport=vp)
        hal = ktx.new_page()
        masuk(hal, P_TANPA)
        potret(hal, "11b-admin-beranda-tanpa-riwayat", lebar)
        ktx.close()

        ktx = br.new_context(viewport=vp)
        hal = ktx.new_page()
        hal.goto(u(p_kunci, "/admin/login"))
        salah(hal, 4)
        potret(hal, "18-login-sisa-1-percobaan", lebar)
        salah(hal, 1)
        hal.wait_for_timeout(2300)          # hitung mundur sudah berjalan beberapa detik
        potret(hal, "19-login-terkunci", lebar)
        ktx.close()

        ktx = br.new_context(viewport=vp, java_script_enabled=False)
        hal = ktx.new_page()
        hal.goto(u(p_kunci, "/admin/login"))  # masih terkunci (alamat sama), tanpa JavaScript
        potret(hal, "20-login-terkunci-tanpa-js", lebar, js=False)
        ktx.close()

        ktx = br.new_context(viewport=vp)
        hal = ktx.new_page()
        hal.goto(u(P_RIWAYAT, "/admin/login"))
        salah(hal, 5)
        hal.wait_for_function("() => !document.querySelector('input[name=\"sandi\"]').disabled",
                              timeout=20000)
        potret(hal, "21-login-silakan-coba-lagi", lebar, lepas_fokus=False)  # fokus di kotak sandi
        masuk(hal, P_RIWAYAT)               # kosongkan hitungan alamat ini untuk lebar berikutnya
        ktx.close()
    br.close()
print("selesai", sorted(os.listdir(KELUAR)))
