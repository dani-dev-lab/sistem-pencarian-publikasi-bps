"""Pemeriksaan tampilan otomatis (25 Nov 2026), Playwright + Chrome terpasang.

Server = form-pembaruan-20261124/server_tangkapan.py (DATABASE UJI).

  C:/Users/Dani/alat-playwright/Scripts/python.exe periksa_tampilan.py PORT KELUAR.json

1. Tombol "Ke atas" tidak menimpa elemen interaktif: 12 lebar x 7 halaman,
   gulir per 250 px; di tiap posisi yang tombolnya tampil, kotak tombol
   dibandingkan dengan kotak SEMUA a[href], button, input, select, summary,
   label yang terlihat (bagian yang terpotong wadah bergulir tidak dihitung).
   Juga: tidak ada gulir mendatar.
2. Ukuran sentuh >= 44 px untuk semua tombol (kelas tombol aplikasi, menu,
   summary lipatan, tombol formulir) di 375 dan 1280 px.
3. Menu ponsel: tertutup -> Menu -> terbuka -> Esc tertutup; tanpa JavaScript
   menu selalu terbuka dan tombol Menu tidak tampil. Desktop: menu terbuka,
   tombol Menu tidak tampil.
4. Tombol ke atas: tersembunyi di 390 px, tampil di 410 px; klik -> ke atas
   (halus); dengan prefers-reduced-motion -> langsung.
5. Scrollbar: scrollbar-width thin, overflow halaman tidak disembunyikan.
6. Cincin fokus: Tab ke tombol -> outline 3 px solid.
"""
import json
import sys

from playwright.sync_api import sync_playwright

PORT, KELUAR = sys.argv[1], sys.argv[2]
DASAR = f"http://127.0.0.1:{PORT}"
LEBAR = [360, 375, 412, 640, 768, 960, 1024, 1180, 1181, 1280, 1366, 1920]
HALAMAN = ["/hasil?q=penduduk", "/hasil?q=pdrb&w=6301", "/hasil?q=penduduk&w=6301&kec=1",
           "/hasil?q=tanah+laut", "/admin/log?semua=1", "/admin/kamus", "/admin/perbarui"]
TOMBOL = (".tombol, .tombol-utama, .tombol-kedua, .lipat > summary, .menu-utama a, .kop-keluar button, "
          ".tombol-menu, .form-admin button, .form-sebaris button, .kotak-cari button, .varian button, "
          ".form-terapkan button, .ke-atas")
hasil = {"tindih": [], "gulir_mendatar": [], "posisi_diperiksa": 0, "sentuh_kecil": [], "sentuh_diperiksa": 0}

JS_TINDIH = """() => {
  const k = document.querySelector('.ke-atas');
  if (!k || k.hidden) return null;
  const a = k.getBoundingClientRect();
  const out = [];
  for (const el of document.querySelectorAll('a[href], button, input, select, summary, label, textarea')) {
    if (el === k || k.contains(el)) continue;
    // Bagian yang terpotong wadah bergulir (overflow bukan visible) tidak
    // terlihat, jadi kotaknya dipotong dulu sebelum dibandingkan.
    const b = el.getBoundingClientRect();
    const r = {left: b.left, top: b.top, right: b.right, bottom: b.bottom};
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (s.overflowX !== 'visible' || s.overflowY !== 'visible') {
        const c = p.getBoundingClientRect();
        r.left = Math.max(r.left, c.left); r.right = Math.min(r.right, c.right);
        r.top = Math.max(r.top, c.top); r.bottom = Math.min(r.bottom, c.bottom);
      }
    }
    if (r.right - r.left <= 0 || r.bottom - r.top <= 0) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none') continue;
    const x = Math.min(a.right, r.right) - Math.max(a.left, r.left);
    const y = Math.min(a.bottom, r.bottom) - Math.max(a.top, r.top);
    if (x > 0.5 && y > 0.5) out.push((el.className || el.tagName) + ' "' + (el.textContent || el.value || '').trim().slice(0, 30) + '"');
  }
  return out;
}"""


def masuk(hal):
    hal.goto(f"{DASAR}/admin/login?next=/admin/")
    hal.fill('input[name="sandi"]', "sandi-tangkapan-layar")
    hal.click('form.form-admin button[type="submit"]')
    hal.wait_for_load_state("networkidle")


with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome")
    ctx = br.new_context(viewport={"width": 1280, "height": 800})
    hal = ctx.new_page()
    masuk(hal)
    # 1. tindih + gulir mendatar
    for lebar in LEBAR:
        hal.set_viewport_size({"width": lebar, "height": 800})
        for u in HALAMAN:
            hal.goto(DASAR + u, wait_until="networkidle")
            sw = hal.evaluate("document.documentElement.scrollWidth")
            if sw > lebar:
                hasil["gulir_mendatar"].append([lebar, u, sw])
            tinggi = hal.evaluate("document.documentElement.scrollHeight")
            y = 0
            while y <= tinggi:
                hal.evaluate(f"window.scrollTo(0, {y})")
                hal.wait_for_timeout(30)
                t = hal.evaluate(JS_TINDIH)
                if t is not None:
                    hasil["posisi_diperiksa"] += 1
                    if t:
                        hasil["tindih"].append([lebar, u, y, t])
                y += 250
    # 2. ukuran sentuh
    for lebar in (375, 1280):
        hal.set_viewport_size({"width": lebar, "height": 800})
        for u in HALAMAN + ["/", "/admin/", "/admin/sandi", "/admin/log/periksa?q=p0", "/hasil?q=zzqqxx&w=6301"]:
            hal.goto(DASAR + u, wait_until="networkidle")
            if lebar == 375 and hal.locator(".tombol-menu").is_visible():
                hal.click(".tombol-menu")          # menu dibuka supaya butirnya ikut diukur
            hal.evaluate("window.scrollTo(0, 600)")
            hal.wait_for_timeout(50)
            ukuran = hal.evaluate("""(sel) => [...document.querySelectorAll(sel)].filter(e => {
                const r = e.getBoundingClientRect(); return r.width && r.height; }).map(e => {
                const r = e.getBoundingClientRect();
                return [e.className || e.tagName, (e.textContent || '').trim().slice(0, 25), Math.round(r.width), Math.round(r.height)]; })""",
                                  TOMBOL)
            hasil["sentuh_diperiksa"] += len(ukuran)
            for kelas, teks, w, h in ukuran:
                if w < 44 or h < 44:
                    hasil["sentuh_kecil"].append([lebar, u, kelas, teks, w, h])
    # 3. menu ponsel dan desktop
    hal.set_viewport_size({"width": 375, "height": 800})
    hal.goto(DASAR + "/hasil?q=penduduk", wait_until="networkidle")
    m = {"awal_tertutup": not hal.locator("#menu-utama").is_visible(),
         "tombol_tampil": hal.locator(".tombol-menu").is_visible()}
    hal.click(".tombol-menu")
    m["terbuka"] = hal.locator("#menu-utama").is_visible() and \
        hal.get_attribute(".tombol-menu", "aria-expanded") == "true"
    hal.screenshot(path=KELUAR.replace(".json", "-menu-ponsel-terbuka.png"))
    hal.keyboard.press("Escape")
    m["esc_tertutup"] = not hal.locator("#menu-utama").is_visible() and \
        hal.get_attribute(".tombol-menu", "aria-expanded") == "false"
    hal.set_viewport_size({"width": 1280, "height": 800})
    m["desktop_terbuka"] = hal.locator("#menu-utama").is_visible() and not hal.locator(".tombol-menu").is_visible()
    tanpa = br.new_context(viewport={"width": 375, "height": 800}, java_script_enabled=False)
    h2 = tanpa.new_page()
    h2.goto(DASAR + "/hasil?q=penduduk")
    m["tanpa_js_terbuka"] = h2.locator("#menu-utama").is_visible() and not h2.locator(".tombol-menu").is_visible()
    h2.screenshot(path=KELUAR.replace(".json", "-menu-ponsel-tanpa-js.png"))
    tanpa.close()
    hasil["menu"] = m
    # 4. tombol ke atas
    k = {}
    for lebar in (375, 1280):
        hal.set_viewport_size({"width": lebar, "height": 800})
        hal.emulate_media(reduced_motion="no-preference")
        hal.goto(DASAR + "/hasil?q=penduduk", wait_until="networkidle")
        hal.evaluate("window.scrollTo(0, 390)"); hal.wait_for_timeout(100)
        k[f"{lebar}-390"] = hal.locator(".ke-atas").is_visible()
        hal.evaluate("window.scrollTo(0, 410)"); hal.wait_for_timeout(100)
        k[f"{lebar}-410"] = hal.locator(".ke-atas").is_visible()
        k[f"{lebar}-teks"] = hal.inner_text(".ke-atas").replace("\n", " ")
        hal.evaluate("window.scrollTo(0, 3000)"); hal.wait_for_timeout(100)
        hal.click(".ke-atas")
        hal.wait_for_timeout(60)
        k[f"{lebar}-halus-60ms"] = hal.evaluate("window.scrollY")
        hal.wait_for_timeout(1500)
        k[f"{lebar}-halus-akhir"] = hal.evaluate("window.scrollY")
        hal.emulate_media(reduced_motion="reduce")
        hal.evaluate("window.scrollTo(0, 3000)"); hal.wait_for_timeout(100)
        hal.click(".ke-atas")
        hal.wait_for_timeout(60)
        k[f"{lebar}-kurangi-gerak-60ms"] = hal.evaluate("window.scrollY")
        hal.evaluate("window.scrollTo(0, 1500)"); hal.wait_for_timeout(100)
        hal.screenshot(path=KELUAR.replace(".json", f"-ke-atas-{lebar}.png"))
    hal.emulate_media(reduced_motion="no-preference")
    hasil["ke_atas"] = k
    # 5. scrollbar
    hasil["scrollbar"] = hal.evaluate("""() => ({
        width: getComputedStyle(document.documentElement).scrollbarWidth,
        color: getComputedStyle(document.documentElement).scrollbarColor,
        overflow_html: getComputedStyle(document.documentElement).overflowY,
        overflow_body: getComputedStyle(document.body).overflowY,
        bisa_digulir: document.documentElement.scrollHeight > innerHeight})""")
    # 6. cincin fokus
    hal.set_viewport_size({"width": 1280, "height": 800})
    hal.goto(DASAR + "/admin/log?semua=1", wait_until="networkidle")
    hal.focus(".tabel-log .tombol-kedua")
    hal.keyboard.press("Tab")
    hal.keyboard.press("Shift+Tab")
    hasil["fokus"] = hal.evaluate("""() => { const e = document.activeElement, s = getComputedStyle(e);
        return [e.className, s.outlineStyle, s.outlineWidth, s.outlineColor]; }""")
    br.close()

json.dump(hasil, open(KELUAR, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
ringkas = {k: (v if not isinstance(v, list) else len(v)) for k, v in hasil.items()}
print(json.dumps(ringkas, indent=1, ensure_ascii=False))
