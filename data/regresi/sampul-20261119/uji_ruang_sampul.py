"""Ruang sampul dipesan SEBELUM gambar dimuat: permintaan /sampul/ DITAHAN (tidak dijawab
selama pengukuran; abort() salah karena membuat gambar berstatus rusak), kotak <img>
harus sudah selebar tetap dan setinggi rasio asli (atribut width/height). Validasi alat:
RUSAK=tanpa-atribut (atribut dibuang) dan RUSAK=lebar (CSS 120 px) harus tertangkap."""
import os, sys
from playwright.sync_api import sync_playwright
RUSAK = os.environ.get("RUSAK", "")
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome"); gagal = 0
    for w in (360, 1366):
        ctx = br.new_context(viewport={"width": w, "height": 800})
        tertahan = []
        ctx.route("**/sampul/**", lambda r: tertahan.append(r))
        if RUSAK == "tanpa-atribut":
            ctx.add_init_script("new MutationObserver(m => document.querySelectorAll('img.sampul').forEach(i => "
                                "{ i.removeAttribute('width'); i.removeAttribute('height'); })).observe(document, {subtree: true, childList: true});")
        if RUSAK == "lebar":
            ctx.add_init_script("document.addEventListener('DOMContentLoaded', () => { const s = document.createElement('style'); "
                                "s.textContent = '.ada-sampul .sampul{width:120px!important}'; document.head.appendChild(s); });")
        pg = ctx.new_page(); pg.goto("http://127.0.0.1:5001/hasil?q=penduduk", wait_until="domcontentloaded")
        pg.wait_for_timeout(800)
        r = pg.evaluate("""() => [...document.querySelectorAll('img.sampul')].map(i => { const b = i.getBoundingClientRect();
            return [b.width, b.height, +i.getAttribute('width') || 0, +i.getAttribute('height') || 0, i.naturalWidth]; })""")
        harap = 64 if w <= 640 else 96
        salah = [x for x in r if x[4] != 0 or abs(x[0] - harap) > 0.5 or not x[2] or abs(x[1] - harap * x[3] / x[2]) > 1]
        gagal += bool(salah)
        print(f"{w:5d} {len(r)} sampul, {len(tertahan)} permintaan ditahan (belum dimuat): {'OK, ruang sudah dipesan' if not salah else 'MASALAH ' + str(salah[:2])}")
        for t in tertahan:
            t.abort()
        ctx.close()
    br.close()
sys.exit(1 if gagal else 0)
