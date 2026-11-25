"""Pergeseran tata letak antara halaman pendek dan panjang (25 Nov 2026).

Dengan scrollbar-gutter: stable, ruang scrollbar dipesan juga di halaman yang
tidak bisa digulir, jadi kop, judul, dan kartu tidak bergeser. Diukur dengan
Chrome terpasang lewat Playwright, TANPA --hide-scrollbars (Playwright memasang
opsi itu secara bawaan di mode headless, sehingga scrollbar tidak memakan
tempat dan uji ini akan lulus palsu).

  C:/Users/Dani/alat-playwright/Scripts/python.exe periksa_gutter.py PORT KELUAR.json [CSS_PENGGANTI]

CSS_PENGGANTI: style.css lain yang disajikan menggantikan /static/css/style.css
(intersepsi request), untuk membuktikan alatnya menangkap pergeseran pada CSS
tanpa scrollbar-gutter.

Pasangan yang dibandingkan (kotak elemen, dibulatkan ke px):
  A. /admin/ yang SAMA di tinggi layar 900 (tidak bisa digulir) vs 300
     (bisa digulir): kop, identitas, tombol kop, judul, kartu pertama.
  B. /admin/ (pendek) vs /admin/log?semua=1 (panjang), tinggi 900: kop,
     identitas, tombol kop, <main>, judul.
  C. / (beranda, pendek) vs /hasil?q=penduduk (panjang): kop, identitas,
     tombol kop.
"""
import json
import sys

from playwright.sync_api import sync_playwright

PORT, KELUAR = sys.argv[1], sys.argv[2]
CSS = open(sys.argv[3], "rb").read() if len(sys.argv) > 3 else None
DASAR = f"http://127.0.0.1:{PORT}"
SEL = {"kop": ".kop", "identitas": ".kop-identitas", "tombol_kop": ".kop-tombol", "main": "main",
       "judul": "h1.judul-admin", "kartu": ".kartu-admin a"}
JS = """(sel) => { const o = {};
  for (const [k, s] of Object.entries(sel)) { const e = document.querySelector(s);
    if (e) { const r = e.getBoundingClientRect();
      o[k] = [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; } }
  o._gulir = document.documentElement.scrollHeight > innerHeight;
  o._gutter = innerWidth - document.documentElement.clientWidth;
  return o; }"""


def ukur(hal, u, lebar, tinggi):
    hal.set_viewport_size({"width": lebar, "height": tinggi})
    hal.goto(DASAR + u, wait_until="networkidle")
    return hal.evaluate(JS, SEL)


def banding(a, b, kunci):
    return {k: (a.get(k), b.get(k)) for k in kunci if a.get(k) != b.get(k)}


hasil = {}
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", ignore_default_args=["--hide-scrollbars"])
    ctx = br.new_context()
    hal = ctx.new_page()
    if CSS is not None:
        hal.route("**/static/css/style.css*",
                  lambda r: r.fulfill(status=200, body=CSS, content_type="text/css; charset=utf-8"))
    hal.goto(f"{DASAR}/admin/login?next=/admin/")
    hal.fill('input[name="sandi"]', "sandi-tangkapan-layar")
    hal.click('form.form-admin button[type="submit"]')
    hal.wait_for_load_state("networkidle")
    for lebar in (1280, 375):
        a1, a2 = ukur(hal, "/admin/", lebar, 900), ukur(hal, "/admin/", lebar, 300)
        b1, b2 = a1, ukur(hal, "/admin/log?semua=1", lebar, 900)
        c1, c2 = ukur(hal, "/", lebar, 900), ukur(hal, "/hasil?q=penduduk", lebar, 900)
        hasil[str(lebar)] = {
            "A_sama_halaman_pendek_vs_panjang": {"gulir": [a1["_gulir"], a2["_gulir"]],
                                                  "gutter": [a1["_gutter"], a2["_gutter"]],
                                                  "beda": banding(a1, a2, ["kop", "identitas", "tombol_kop", "judul", "kartu"])},
            "B_beranda_admin_vs_log": {"gulir": [b1["_gulir"], b2["_gulir"]],
                                        "gutter": [b1["_gutter"], b2["_gutter"]],
                                        # tinggi <main> memang beda; yang dibandingkan posisi kiri dan lebar
                                        "beda": {**banding(b1, b2, ["kop", "identitas", "tombol_kop"]),
                                                 **{k: (b1[k][::2], b2[k][::2]) for k in ("main", "judul")
                                                    if b1[k][::2] != b2[k][::2]}}},
            "C_beranda_vs_hasil": {"gulir": [c1["_gulir"], c2["_gulir"]],
                                   "gutter": [c1["_gutter"], c2["_gutter"]],
                                   "beda": banding(c1, c2, ["kop", "identitas", "tombol_kop"])},
        }
    br.close()
hasil["tanpa_pergeseran"] = all(not v["beda"] for w in ("1280", "375") for v in hasil[w].values())
hasil["skenario_sah"] = all(v["gulir"][0] is False and v["gulir"][1] is True
                            for w in ("1280", "375") for v in hasil[w].values())
json.dump(hasil, open(KELUAR, "w", encoding="utf-8"), indent=1)
print(json.dumps(hasil, indent=1))
