"""Uji tombol "Kembali ke atas" (Playwright + Chrome terpasang). Server: run.py --db-uji --port 5001.
  <venv alat>/python uji_tombol_atas.py [url_dasar] [awalan]
Pemeriksaan per lebar (pengukuran DOM, bukan kesan visual):
  A tersembunyi di posisi atas dan di 0,5 layar; terlihat di 1,2 layar
  B ukuran >= 44x44, <button>, aria-label "Kembali ke atas", warna latar = kop BPS rgb(0,43,106)
  C tidak menimpa (irisan luas > 0) tombol Buka PDF, isi kartu (judul, label, cuplikan, skor,
    tautan), tautan kotak info/pita/"tampilkan semua", dan teks notice BPS (kotak huruf) - di SETIAP posisi gulir
    (langkah 37 px dari 1 layar sampai dasar)
  D klik: gulir halus (di tengah animasi 0 < scrollY < awal), akhirnya 0; fokus pindah ke kop
  E prefers-reduced-motion: klik -> scrollY 0 pada bingkai berikutnya
  F keyboard: fokus tombol + Enter -> 0; + Spasi -> 0
"""
import os, sys, time
from playwright.sync_api import sync_playwright
DASAR = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5001"
AWALAN = sys.argv[2] if len(sys.argv) > 2 else ""
KELUAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "responsif")
LEBAR = [int(x) for x in os.environ.get("LEBAR", "360,390,440,768,1366").split(",")]
# Validasi alat: RUSAK=<jenis> menyuntikkan cacat yang HARUS tertangkap (tangkapan layar tidak disimpan).
RUSAK = os.environ.get("RUSAK", "")
CSS_RUSAK = {
    "ruang": ".kartu,.info-kecamatan,.pita-wilayah{padding-right:14px!important}.kaki .notice{padding:0!important}",
    "tampil": ".ke-atas[hidden]{display:flex!important}",
    "kecil": ".ke-atas{width:40px!important;height:40px!important}",
    "warna": ".ke-atas{background:#888!important}",
}
JS_RUSAK = {
    "lompat": "const _s = window.scrollTo.bind(window); window.scrollTo = (...a) => _s(...(a.length === 1 && typeof a[0] === 'object' ? [Object.assign({}, a[0], {behavior: 'auto'})] : a));",
    "abaikan-reduce": "const _m = window.matchMedia.bind(window); window.matchMedia = q => /reduced-motion/.test(q) ? {matches: false, addEventListener(){}} : _m(q);",
}
HALAMAN = {"hasil": "/hasil?q=penduduk", "kecamatan": "/hasil?q=penduduk&w=6301&kec=1"}
DILINDUNGI = """() => {
  const sel = ['.tombol-pdf', '.kartu-judul', '.lokasi > span', '.cuplikan', '.kartu-kaki .skor',
               '.info-kecamatan a', '.info-kecamatan .info-teks', '.pita-batal', '.lebih a'];
  const out = [];
  for (const s of sel) for (const e of document.querySelectorAll(s)) {
    const b = e.getBoundingClientRect();
    if (b.width > 0 && b.height > 0) out.push({s, x: b.left, y: b.top, r: b.right, b: b.bottom});
  }
  // notice: kotak HURUF teksnya (Range), bukan kotak elemen blok selebar layar
  for (const e of document.querySelectorAll('.notice')) {
    const r = document.createRange(); r.selectNodeContents(e);
    for (const b of r.getClientRects()) if (b.width > 0) out.push({s: '.notice (teks)', x: b.left, y: b.top, r: b.right, b: b.bottom});
  }
  return out;
}"""
TOMBOL = """() => { const t = document.querySelector('.ke-atas'); const b = t.getBoundingClientRect();
  return {tampil: t.checkVisibility({visibilityProperty: true, opacityProperty: true}) && b.width > 0, x: b.left, y: b.top, r: b.right, b: b.bottom,
          w: b.width, h: b.height, tag: t.tagName, label: t.getAttribute('aria-label'),
          warna: getComputedStyle(t).backgroundColor, tab: t.tabIndex}; }"""
def iris(a, b):
    return max(0, min(a["r"], b["r"]) - max(a["x"], b["x"])) * max(0, min(a["b"], b["b"]) - max(a["y"], b["y"]))
def tunggu_atas(pg, batas=3.0):
    t0 = time.time()
    while time.time() - t0 < batas:
        if pg.evaluate("window.scrollY") == 0: return True
        time.sleep(0.05)
    return False
masalah_total = 0
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome")
    for w in LEBAR:
        for kurangi in (False, True):
            ctx = br.new_context(viewport={"width": w, "height": 780 if w < 768 else 900}, device_scale_factor=2 if w <= 768 else 1,
                                 is_mobile=w <= 440, has_touch=w <= 768, reduced_motion="reduce" if kurangi else "no-preference")
            if RUSAK in CSS_RUSAK:
                ctx.add_init_script("document.addEventListener('DOMContentLoaded', () => { const st = document.createElement('style'); st.textContent = %r; document.head.appendChild(st); });" % CSS_RUSAK[RUSAK])
            elif RUSAK in JS_RUSAK:
                ctx.add_init_script(JS_RUSAK[RUSAK])
            elif RUSAK:
                sys.exit(f"RUSAK tidak dikenal: {RUSAK}")
            pg = ctx.new_page()
            for nama, url in HALAMAN.items():
                if kurangi and nama != "hasil": continue
                pg.goto(DASAR + url, wait_until="networkidle")
                tinggi, maks = pg.evaluate("innerHeight"), pg.evaluate("document.documentElement.scrollHeight - innerHeight")
                masalah = []
                if maks < tinggi * 1.5: masalah.append(f"halaman terlalu pendek ({maks})")
                if not kurangi:
                    # A
                    for y, harap in ((0, False), (int(tinggi * 0.5), False), (int(tinggi * 1.2), True)):
                        pg.evaluate(f"window.scrollTo(0, {y})"); pg.wait_for_timeout(120)
                        if pg.evaluate(TOMBOL)["tampil"] != harap: masalah.append(f"A: di y={y} tampil != {harap}")
                    # B
                    t = pg.evaluate(TOMBOL)
                    if t["w"] < 44 or t["h"] < 44: masalah.append(f"B: ukuran {t['w']}x{t['h']}")
                    if t["tag"] != "BUTTON" or t["label"] != "Kembali ke atas" or t["tab"] < 0: masalah.append(f"B: {t['tag']} {t['label']} tab {t['tab']}")
                    if t["warna"] != "rgb(0, 43, 106)": masalah.append(f"B: warna {t['warna']}")
                    # C
                    n_pos = 0; tabrak = []
                    for y in list(range(int(tinggi) + 1, int(maks), 37)) + [int(maks)]:
                        pg.evaluate(f"window.scrollTo(0, {y})"); n_pos += 1
                        t = pg.evaluate(TOMBOL)
                        if not t["tampil"]: continue
                        for e in pg.evaluate(DILINDUNGI):
                            if iris(t, e) > 0: tabrak.append((y, e["s"]))
                    if tabrak: masalah.append(f"C: {len(tabrak)} tabrakan, mis. {sorted(set(s for _, s in tabrak))[:4]} di y={tabrak[0][0]}")
                    # tangkapan layar: ±2 layar ke bawah, tombol terlihat
                    pg.evaluate(f"window.scrollTo(0, {int(min(maks, tinggi * 2))})"); pg.wait_for_timeout(150)
                    if not RUSAK: pg.screenshot(path=os.path.join(KELUAR, f"{AWALAN}{w:04d}-{nama}.png"))
                    # D
                    pg.evaluate(f"window.scrollTo(0, {int(tinggi * 3)})"); pg.wait_for_timeout(150)
                    awal = pg.evaluate("window.scrollY")
                    pg.click(".ke-atas"); pg.wait_for_timeout(60)
                    tengah = pg.evaluate("window.scrollY")
                    if not (0 < tengah < awal): masalah.append(f"D: tidak halus (awal {awal}, +60ms {tengah})")
                    if not tunggu_atas(pg): masalah.append("D: tidak sampai atas")
                    pg.wait_for_timeout(100)
                    if not pg.evaluate("document.activeElement && document.activeElement.classList.contains('kop-identitas')"):
                        masalah.append("D: fokus tidak pindah ke kop")
                    # F
                    for tombol in ("Enter", " "):
                        pg.evaluate(f"window.scrollTo(0, {int(tinggi * 2)})"); pg.wait_for_timeout(150)
                        pg.focus(".ke-atas"); pg.keyboard.press("Space" if tombol == " " else tombol)
                        if not tunggu_atas(pg): masalah.append(f"F: {tombol!r} tidak ke atas")
                    detail = f"posisi diuji {n_pos}"
                else:
                    # E
                    pg.evaluate(f"window.scrollTo(0, {int(tinggi * 3)})"); pg.wait_for_timeout(150)
                    pg.click(".ke-atas")
                    y1 = pg.evaluate("new Promise(r => requestAnimationFrame(() => r(window.scrollY)))")
                    if y1 != 0: masalah.append(f"E: tidak langsung lompat (scrollY {y1})")
                    detail = "kurangi animasi"
                masalah_total += bool(masalah)
                print(f"{w:5d} {nama:10s}{' [reduce]' if kurangi else '         '} {'OK' if not masalah else 'MASALAH: ' + '; '.join(masalah)}  ({detail})")
            ctx.close()
    br.close()
print("LULUS" if not masalah_total else f"{masalah_total} kombinasi bermasalah")
sys.exit(1 if masalah_total else 0)
