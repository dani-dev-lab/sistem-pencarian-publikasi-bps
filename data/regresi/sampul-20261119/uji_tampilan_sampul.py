"""Tampilan sampul (Playwright + Chrome terpasang). Server: run.py --db-uji --port 5001.
Per lebar x halaman (pengukuran DOM, bukan kesan visual):
  - semua kartu publikasi yang punya <img class="sampul"> memuat gambarnya (naturalWidth > 0);
  - lebar tampil tetap: 96 px (> 640 px) / 64 px (<= 640 px); rasio = rasio asli (selisih <= 1 px);
  - sampul di KIRI judul (kanan sampul <= kiri judul), di dalam kartu;
  - kartu tabel/gambar/bab tanpa sampul; tanpa gulir horizontal;
  - CLS (layout-shift) = 0 sesudah gulir ke bawah (gambar lazy dimuat tanpa menggeser);
  - semua permintaan browser ke 127.0.0.1 (tidak ada ke situs luar).
Tangkapan layar layar pertama seksi Publikasi -> responsif/<lebar>-<halaman>.png
"""
import os, sys
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
DASAR = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5001"
KELUAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "responsif")
LEBAR = [360, 390, 440, 768, 1366]
HALAMAN = {"hasil": "/hasil?q=penduduk", "kecamatan": "/hasil?q=penduduk&w=6301&kec=1&kc=kintap",
           "wilayah": "/hasil?q=tanah+laut"}
UKUR = """() => {
  const out = {kartu: [], entri_sampul: document.querySelectorAll('.kartu:not(.kartu-pub) .sampul').length,
               geser_h: document.documentElement.scrollWidth > innerWidth + 1};
  for (const k of document.querySelectorAll('.kartu-pub')) {
    const img = k.querySelector('img.sampul'); if (!img) { out.kartu.push({tanpa: true}); continue; }
    const bi = img.getBoundingClientRect(), bk = k.getBoundingClientRect(), bj = k.querySelector('.kartu-judul').getBoundingClientRect();
    out.kartu.push({w: bi.width, h: bi.height, nw: img.naturalWidth, nh: img.naturalHeight,
      aw: +img.getAttribute('width'), ah: +img.getAttribute('height'), kiri: bi.right <= bj.left + 0.5,
      dalam: bi.left >= bk.left && bi.right <= bk.right && bi.top >= bk.top && bi.bottom <= bk.bottom + 0.5,
      alt: img.alt, lazy: img.loading});
  }
  return out;
}"""
total = 0
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome")
    for w in LEBAR:
        ctx = br.new_context(viewport={"width": w, "height": 780 if w < 768 else 900},
                             device_scale_factor=2 if w <= 768 else 1, is_mobile=w <= 440, has_touch=w <= 768)
        ctx.add_init_script("window.__cls = 0; new PerformanceObserver(l => { for (const e of l.getEntries()) "
                            "if (!e.hadRecentInput) window.__cls += e.value; }).observe({type: 'layout-shift', buffered: true});")
        pg = ctx.new_page()
        luar = []
        pg.on("request", lambda r: luar.append(r.url) if urlparse(r.url).hostname not in ("127.0.0.1", "localhost") else None)
        for nama, url in HALAMAN.items():
            pg.goto(DASAR + url, wait_until="networkidle")
            pg.wait_for_timeout(200)
            pg.screenshot(path=os.path.join(KELUAR, f"{w:04d}-{nama}.png"))
            maks = pg.evaluate("document.documentElement.scrollHeight - innerHeight")
            for y in range(0, maks + 1, 400):
                pg.evaluate(f"window.scrollTo(0, {y})"); pg.wait_for_timeout(40)
            pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(200)
            u = pg.evaluate(UKUR); cls = pg.evaluate("window.__cls")
            lebar_harap = 64 if w <= 640 else 96
            masalah = []
            ada = [k for k in u["kartu"] if not k.get("tanpa")]
            if not ada: masalah.append("tidak ada kartu bersampul")
            for i, k in enumerate(ada):
                if k["nw"] == 0: masalah.append(f"#{i} gambar tidak dimuat")
                if abs(k["w"] - lebar_harap) > 0.5: masalah.append(f"#{i} lebar {k['w']}")
                if k["nw"] and abs(k["h"] - k["w"] * k["nh"] / k["nw"]) > 1: masalah.append(f"#{i} rasio {k['w']}x{k['h']} vs {k['nw']}x{k['nh']}")
                if (k["aw"], k["ah"]) != (k["nw"], k["nh"]): masalah.append(f"#{i} atribut {k['aw']}x{k['ah']} != asli {k['nw']}x{k['nh']}")
                if not k["kiri"] or not k["dalam"]: masalah.append(f"#{i} posisi (kiri {k['kiri']}, dalam {k['dalam']})")
                if not k["alt"].startswith("Sampul ") or k["lazy"] != "lazy": masalah.append(f"#{i} alt/lazy")
            if u["entri_sampul"]: masalah.append(f"{u['entri_sampul']} sampul di kartu entri")
            if u["geser_h"]: masalah.append("gulir horizontal")
            if cls > 0.001: masalah.append(f"CLS {cls:.3f}")
            total += bool(masalah)
            print(f"{w:5d} {nama:10s} {'OK' if not masalah else 'MASALAH: ' + '; '.join(masalah[:4])}  "
                  f"({len(ada)} kartu bersampul, {len(u['kartu']) - len(ada)} tanpa, CLS {cls:.3f})")
        if luar: total += 1; print(f"{w:5d} PERMINTAAN KE LUAR: {luar[:3]}")
        ctx.close()
    br.close()
print("LULUS" if not total else f"{total} bermasalah")
sys.exit(1 if total else 0)
