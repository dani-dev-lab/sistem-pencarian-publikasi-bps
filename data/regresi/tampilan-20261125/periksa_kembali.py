"""Uji peramban "Kembali ke Pencarian" (26 Nov 2026).

Server = server_kunci.py PORT 300 catat-log (DATABASE UJI, log pencarian
HIDUP). Jumlah baris log dihitung lewat Python proyek (KonfigurasiUji); baris
yang ditambahkan alat ini dihapus di akhir (id > id terbesar sebelum mulai).

  C:/Users/Dani/alat-playwright/Scripts/python.exe periksa_kembali.py PORT KELUAR.json FOLDER_LAYAR

Untuk 1280 dan 375 px, JavaScript hidup:
  hasil (wilayah + kecamatan) -> gulir -> Halaman Admin (belum login) -> login
  -> kartu Kamus Sinonim -> Kembali ke Pencarian. Diperiksa: alamat sama, isi
  <main> sama, posisi gulir pulih, log +1 untuk pencarian lalu +0 untuk
  kembali. Juga kartu beranda admin sejajar, dan judul "Log Pencarian".
Tanpa kecamatan (kotak info kecamatan disembunyikan kecamatan.js sesudah
  halaman tampil): posisi gulir tetap pulih.
JavaScript mati: kembali ke hasil yang sama, log +0, gulir tidak dipulihkan.
"""
import json
import os
import re
import subprocess
import sys

from playwright.sync_api import sync_playwright

PORT, KELUAR, LAYAR = sys.argv[1], sys.argv[2], sys.argv[3]
DASAR = f"http://127.0.0.1:{PORT}"
SANDI = "sandi-tangkapan-layar"
PROYEK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PY = os.path.join(PROYEK, "venv", "Scripts", "python.exe")
os.makedirs(LAYAR, exist_ok=True)
DB = """
import sys; sys.path.insert(0, r'{p}')
from sqlalchemy import create_engine, text
from app.config import KonfigurasiUji
e = create_engine(KonfigurasiUji.SQLALCHEMY_DATABASE_URI)
assert e.url.database.endswith('_uji'), e.url.database
with e.begin() as c:
    {aksi}
"""


def db(aksi):
    r = subprocess.run([PY, "-c", DB.format(p=PROYEK, aksi=aksi)], capture_output=True, text=True, check=True)
    return r.stdout.strip()


def log():
    return [int(x) for x in db("print(*c.execute(text('SELECT COUNT(*), COALESCE(MAX(id),0) "
                                 "FROM log_pencarian')).fetchone())").split()]


def isi_main(hal):
    return re.sub(r"\d+ ms", "N ms", hal.inner_text("main"))


def gulir(hal):
    return hal.evaluate("() => Math.round(window.pageYOffset)")


hasil = {}
n_awal, id_awal = log()
hasil["log_awal"] = [n_awal, id_awal]
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome")
    for lebar in (1280, 375):
        k = f"js_{lebar}"
        ktx = br.new_context(viewport={"width": lebar, "height": 900 if lebar == 1280 else 800})
        hal = ktx.new_page()
        alamat = "/hasil?q=penduduk&w=6301&kec=1"
        n0 = log()[0]
        hal.goto(DASAR + alamat)
        hal.wait_for_load_state("networkidle")
        isi1 = isi_main(hal)
        maks = hal.evaluate("() => document.documentElement.scrollHeight - innerHeight")
        sasaran = min(2400, maks - 200)
        hal.mouse.wheel(0, sasaran)
        hal.wait_for_function(f"() => Math.abs(pageYOffset - {sasaran}) < 2")
        y1 = gulir(hal)
        n1 = log()[0]
        with hal.expect_navigation():
            hal.click(".tombol-admin")
        url_login = hal.url.replace(DASAR, "")
        hal.fill('input[name="sandi"]', SANDI)
        with hal.expect_navigation():
            hal.click('form.form-admin button[type="submit"]')
        url_beranda = hal.url.replace(DASAR, "")
        hal.wait_for_load_state("networkidle")
        # Kartu beranda admin: sejajar (atas, tinggi, judul, angka, keterangan).
        kartu = hal.evaluate("""() => [...document.querySelectorAll('.kartu-admin > *')].map(k => {
            const r = k.getBoundingClientRect(), q = s => k.querySelector(s).getBoundingClientRect();
            return {judul: k.querySelector('h2').textContent.trim(), x: Math.round(r.left),
                    atas: Math.round(r.top), tinggi: Math.round(r.height), lebar: Math.round(r.width),
                    h2: Math.round(q('h2').top - r.top), angka: Math.round(q('.angka').top - r.top),
                    ket: Math.round(q('.ket').top - r.top), tinggi_h2: Math.round(q('h2').height)}; })""")
        hal.screenshot(path=f"{LAYAR}/{lebar:04d}-31-admin-beranda.png", full_page=True)
        with hal.expect_navigation():
            hal.click("text=Kamus Sinonim")
        url_kamus = hal.url.replace(DASAR, "")
        href_kembali = hal.get_attribute('a[aria-label="Kembali ke Pencarian"]', "href")
        with hal.expect_navigation():
            hal.click('a[aria-label="Kembali ke Pencarian"]')
        hal.wait_for_load_state("networkidle")
        hal.wait_for_timeout(3500)          # pengamat tinggi halaman selesai (3 detik)
        y2 = gulir(hal)
        hal.screenshot(path=f"{LAYAR}/{lebar:04d}-32-hasil-sesudah-kembali-layar.png")
        hasil[k] = {
            "alamat_tiba": hal.url.replace(DASAR, ""), "alamat_awal": alamat,
            "isi_sama": isi_main(hal) == isi1, "panjang_isi": len(isi1),
            "gulir_sebelum": y1, "gulir_sesudah": y2,
            "penanda": hal.evaluate("() => document.body.hasAttribute('data-pulihkan-gulir')"),
            "log_cari": n1 - n0, "log_kembali": log()[0] - n1,
            "url_login": url_login, "url_beranda": url_beranda, "url_kamus": url_kamus,
            "href_kembali": href_kembali, "kartu": kartu}
        # Halaman Log Pencarian: judul halaman dan judul tab.
        hal.goto(DASAR + "/admin/log")
        hasil[k]["log_judul"] = [hal.inner_text("h1"), hal.title()]
        hal.screenshot(path=f"{LAYAR}/{lebar:04d}-33-admin-log.png")
        ktx.close()

    # Tanpa kecamatan: kotak info kecamatan berubah/hilang sesudah tampil.
    ktx = br.new_context(viewport={"width": 1280, "height": 900})
    hal = ktx.new_page()
    hal.goto(DASAR + "/hasil?q=jumlah+penduduk")
    hal.wait_for_load_state("networkidle")
    hal.mouse.wheel(0, 1500)
    hal.wait_for_function("() => Math.abs(pageYOffset - 1500) < 2")
    y1 = gulir(hal)
    with hal.expect_navigation():
        hal.click(".tombol-admin")
    hal.fill('input[name="sandi"]', SANDI)
    with hal.expect_navigation():
        hal.click('form.form-admin button[type="submit"]')
    with hal.expect_navigation():
        hal.click('a[aria-label="Kembali ke Pencarian"]')
    hal.wait_for_load_state("networkidle")
    hal.wait_for_timeout(3500)
    hasil["tanpa_kec"] = {"alamat_tiba": hal.url.replace(DASAR, ""), "gulir_sebelum": y1, "gulir_sesudah": gulir(hal),
                          "info": hal.evaluate("() => { const i = document.getElementById('info-kecamatan');"
                                               " return i ? (i.hidden ? 'tersembunyi' : i.textContent.trim()) : null; }")}
    ktx.close()

    # JavaScript mati.
    ktx = br.new_context(viewport={"width": 375, "height": 800}, java_script_enabled=False)
    hal = ktx.new_page()
    alamat = "/hasil?q=penduduk&w=6301&kec=1"
    n0 = log()[0]
    hal.goto(DASAR + alamat)
    n1 = log()[0]
    with hal.expect_navigation():
        hal.click(".tombol-admin")
    hal.fill('input[name="sandi"]', SANDI)
    with hal.expect_navigation():
        hal.click('form.form-admin button[type="submit"]')
    with hal.expect_navigation():
        hal.click("text=Kamus Sinonim")
    with hal.expect_navigation():
        hal.click('a[aria-label="Kembali ke Pencarian"]')
    hasil["tanpa_js"] = {"alamat_tiba": hal.url.replace(DASAR, ""), "log_cari": n1 - n0, "log_kembali": log()[0] - n1}
    ktx.close()
    br.close()

# Bersihkan baris log yang ditambahkan alat ini (database uji).
db(f"c.execute(text('DELETE FROM log_pencarian WHERE id > {id_awal}'))")
hasil["log_akhir"] = log()
json.dump(hasil, open(KELUAR, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- Penilaian ----
nilai = {}
for lebar in (1280, 375):
    h = hasil[f"js_{lebar}"]
    kt = h["kartu"]
    if lebar == 1280:
        sejajar = (len({k["atas"] for k in kt}) == 1 and len({k["tinggi"] for k in kt}) == 1
                   and len({k["angka"] for k in kt}) == 1 and len({k["ket"] for k in kt}) == 1
                   and len({k["tinggi_h2"] for k in kt}) == 1)
    else:
        sejajar = (len({k["x"] for k in kt}) == 1 and len({k["lebar"] for k in kt}) == 1
                   and len({k["tinggi"] for k in kt}) == 1)
    nilai[f"{lebar}: hasil -> Halaman Admin (belum login) -> login -> Kamus -> Kembali = alamat hasil yang sama, "
          f"isi <main> sama"] = (
        h["alamat_tiba"] == h["alamat_awal"] and h["isi_sama"] and h["panjang_isi"] > 1000
        and h["url_login"].startswith("/admin/login?next=") and h["url_beranda"].startswith("/admin/?dari=")
        and h["url_kamus"] == "/admin/kamus" and h["href_kembali"] == "/kembali")
    nilai[f"{lebar}: posisi gulir pulih (±2 px)"] = (
        h["gulir_sebelum"] > 500 and abs(h["gulir_sesudah"] - h["gulir_sebelum"]) <= 2 and h["penanda"])
    nilai[f"{lebar}: log +1 saat mencari, +0 saat kembali"] = h["log_cari"] == 1 and h["log_kembali"] == 0
    nilai[f"{lebar}: kartu admin sejajar, judul 'Log Pencarian'"] = (
        sejajar and [k["judul"] for k in kt] == ["Kamus Sinonim", "Log Pencarian", "Perbarui Data", "Ganti Kata Sandi"]
        and h["log_judul"] == ["Log Pencarian", "Log Pencarian — Admin"])
t = hasil["tanpa_kec"]
nilai["tanpa kecamatan (kotak info berubah sesudah tampil): gulir tetap pulih"] = (
    t["alamat_tiba"] == "/hasil?q=jumlah+penduduk" and abs(t["gulir_sesudah"] - t["gulir_sebelum"]) <= 2)
t = hasil["tanpa_js"]
nilai["JavaScript mati: kembali ke hasil yang sama, log +1 lalu +0"] = (
    t["alamat_tiba"] == "/hasil?q=penduduk&w=6301&kec=1" and t["log_cari"] == 1 and t["log_kembali"] == 0)
nilai["baris log alat dihapus (jumlah = awal)"] = hasil["log_akhir"][0] == hasil["log_awal"][0]
for k, v in nilai.items():
    print(("LULUS " if v else "GAGAL ") + k)
print(f"{sum(nilai.values())}/{len(nilai)}")
