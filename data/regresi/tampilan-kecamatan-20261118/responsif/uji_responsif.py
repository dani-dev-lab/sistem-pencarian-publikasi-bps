"""Uji tampilan form kecamatan di beberapa lebar layar (Playwright + Chrome terpasang).

  <venv alat>/python uji_responsif.py [url_dasar=http://127.0.0.1:5001] [awalan_berkas]

Server: aplikasi dengan DATABASE UJI (jalankan-aplikasi-uji.bat / run.py --db-uji).
Per (lebar, halaman): tangkapan layar layar pertama -> <lebar>-<halaman>.png, dan
pengukuran DOM yang dipakai menilai (bukan heuristik visual):
  - kotak centang terlihat (>= 12x12 px) dan di dalam layar;
  - elemen kotak <= 24 px lebar, jarak kanan kotak -> kiri tulisan 6-12 px;
    kotak sejajar baris pertama tulisan;
  - tulisan SATU blok di kanan kotak (tidak terpecah kolom);
  - label rata kiri dengan kolom kata kunci (selisih <= 2 px); tinggi label >= 44 px;
  - dropdown kecamatan (kalau terlihat) di dalam layar, tinggi >= 36 px;
  - tidak ada gulir horizontal;
  - beranda > 640 px dengan dropdown kecamatan: kolom kata kunci >= 95% lebar form;
  - kartu hasil: label "Kec." sejajar (saudara) label wilayah, tidak bersarang.
"""
import json, os, sys
from playwright.sync_api import sync_playwright

DASAR = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5001"
AWALAN = sys.argv[2] if len(sys.argv) > 2 else ""
KELUAR = os.path.dirname(os.path.abspath(__file__))
LEBAR = [320, 360, 375, 390, 412, 440, 768, 1024, 1366]
HALAMAN = {
    "beranda": "/",
    "beranda-kab": "/?w=6301",
    "hasil-mati": "/hasil?q=penduduk&w=6301",
    "hasil-hidup-kc": "/hasil?q=penduduk&w=6301&kec=1&kc=pelaihari",
}
UKUR = r"""() => {
  const f = document.querySelector('form.kotak-cari');
  const lab = f.querySelector('.centang-kecamatan');
  const cb = lab && lab.querySelector('input[type=checkbox]');
  // Tulisan = kotak HURUF dari setiap node teks di label (bukan kotak elemen
  // <span>: tepi elemen menempel ke kotak centang walaupun hurufnya dipusatkan
  // jauh darinya - alat versi awal terkecoh di beranda yang text-align:center).
  // Berlaku untuk markup lama (teks lepas + span) maupun baru (.teks-centang).
  let tx = null, rects = [];
  if (cb) {
    const jalan = document.createTreeWalker(lab, NodeFilter.SHOW_TEXT);
    for (let n = jalan.nextNode(); n; n = jalan.nextNode()) {
      if (!n.textContent.trim()) continue;
      const rg = document.createRange(); rg.selectNodeContents(n);
      for (const b of rg.getClientRects())
        if (b.width > 1 && b.height > 1) rects.push({x: b.left, y: b.top, r: b.right, b: b.bottom});
    }
    if (rects.length) {
      const y0 = Math.min(...rects.map(b => b.y));
      const baris1 = rects.filter(b => b.y < y0 + 4);
      tx = {x: Math.min(...baris1.map(b => b.x)), y: y0, r: Math.max(...rects.map(b => b.r)),
            b: Math.max(...rects.map(b => b.b))};
    }
  }
  const q = f.querySelector('input[type=search]');
  const kc = f.querySelector('select[name=kc]');
  const r = e => { const b = e.getBoundingClientRect(); return {x: b.left, y: b.top, w: b.width, h: b.height, r: b.right, b: b.bottom}; };
  // Label kartu kecamatan: harus SEJAJAR dengan label wilayah, bukan bersarang.
  const bersarang = document.querySelectorAll('.label-wilayah .label-kecamatan').length;
  const kec = Array.from(document.querySelectorAll('.lokasi > .label-kecamatan')).slice(0, 5).map(e => {
    const w = e.nextElementSibling, a = e.getBoundingClientRect(), b = w.getBoundingClientRect();
    return {wilayah: w.classList.contains('label-wilayah'), sebaris: Math.abs(a.top - b.top) < 2 || b.top >= a.bottom - 1};
  });
  return {lebar: innerWidth, gulir: document.documentElement.scrollWidth, form: r(f),
          beranda: document.body.classList.contains('beranda'), bersarang, kec,
          cb: cb && r(cb), cbTampil: cb && getComputedStyle(cb).display !== 'none' && getComputedStyle(cb).visibility !== 'hidden',
          tx: tx, txBaris: rects, lab: lab && r(lab), q: r(q),
          kc: kc && !kc.hidden ? r(kc) : null, centang: cb && cb.checked};
}"""

def nilai(m):
    masalah = []
    cb, tx, lab, q = m["cb"], m["tx"], m["lab"], m["q"]
    if not cb or not m["cbTampil"] or cb["w"] < 12 or cb["h"] < 12:
        masalah.append(f"kotak centang tidak terlihat ({cb})")
    else:
        if cb["x"] < 0 or cb["r"] > m["lebar"]:
            masalah.append("kotak di luar layar")
        # Elemen kotak centang yang melebar menggambar kotaknya di ujung kiri,
        # jauh dari tulisan: jarak tepi-elemen ke tulisan saja tidak menangkapnya.
        if cb["w"] > 24:
            masalah.append(f"elemen kotak centang melebar {cb['w']:.0f}px (kotak jauh dari tulisan)")
        jarak = tx["x"] - cb["r"]
        if not 6 <= jarak <= 12:
            masalah.append(f"jarak kotak-tulisan {jarak:.1f}px")
        baris1 = min(m["txBaris"], key=lambda b: b["y"])
        tengah = (cb["y"] + cb["b"]) / 2
        if not baris1["y"] - 4 <= tengah <= baris1["b"] + 4:
            masalah.append("kotak tidak sejajar baris pertama tulisan")
        if any(b["x"] < cb["r"] for b in m["txBaris"]):
            masalah.append("tulisan terpecah/di bawah kotak")
        kiri = {}
        for b in m["txBaris"]:
            y = round(b["y"] / 4)
            kiri[y] = min(kiri.get(y, 1e9), b["x"])
        if max(kiri.values()) - min(kiri.values()) > 2:
            masalah.append("baris-baris tulisan tidak rata kiri")
    if abs(lab["x"] - q["x"]) > 2:
        masalah.append(f"label tidak rata kiri dengan kata kunci ({lab['x']:.0f} vs {q['x']:.0f})")
    if lab["h"] < 44:
        masalah.append(f"area sentuh {lab['h']:.0f}px")
    if m["kc"]:
        if m["kc"]["r"] > m["lebar"] or m["kc"]["x"] < 0:
            masalah.append("dropdown kecamatan keluar layar")
        if m["kc"]["h"] < 36:
            masalah.append(f"dropdown kecamatan {m['kc']['h']:.0f}px")
    if m["beranda"] and m["kc"] and m["lebar"] > 640 and m["q"]["w"] < 0.95 * m["form"]["w"]:
        masalah.append(f"kolom kata kunci menyempit {m['q']['w']:.0f}/{m['form']['w']:.0f}px")
    if m["bersarang"]:
        masalah.append(f"{m['bersarang']} label kecamatan bersarang di label wilayah")
    if any(not k["wilayah"] for k in m["kec"]):
        masalah.append("label kecamatan tidak diikuti label wilayah")
    if m["gulir"] > m["lebar"]:
        masalah.append(f"gulir horizontal {m['gulir']}>{m['lebar']}")
    return masalah

hasil = []
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome")
    for w in LEBAR:
        ctx = br.new_context(viewport={"width": w, "height": 900 if w >= 768 else 780},
                             device_scale_factor=2 if w <= 768 else 1, is_mobile=w <= 440, has_touch=w <= 768)
        pg = ctx.new_page()
        for nama, url in HALAMAN.items():
            pg.goto(DASAR + url, wait_until="networkidle")
            if os.environ.get("SUNTIK_CSS"):      # hanya untuk membuktikan alat ini menangkap cacat
                pg.add_style_tag(content=os.environ["SUNTIK_CSS"])
            m = pg.evaluate(UKUR)
            masalah = nilai(m)
            pg.screenshot(path=os.path.join(KELUAR, f"{AWALAN}{w:04d}-{nama}.png"))
            if nama == "hasil-hidup-kc" and w in (360, 1366):
                el = pg.query_selector("section:has(.seksi-kecamatan)")
                if el:
                    el.screenshot(path=os.path.join(KELUAR, f"{AWALAN}{w:04d}-seksi-kecamatan.png"))
            hasil.append({"lebar": w, "halaman": nama, "masalah": masalah,
                          "jarak": round(m["tx"]["x"] - m["cb"]["r"], 1) if m["cb"] and m["tx"] else None,
                          "tinggi_label": round(m["lab"]["h"]), "kc": bool(m["kc"]), "centang": m["centang"]})
            print(f"{w:5d} {nama:15s} {'OK' if not masalah else 'MASALAH: ' + '; '.join(masalah)}")
        ctx.close()
    br.close()
json.dump(hasil, open(os.path.join(KELUAR, f"{AWALAN}hasil.json"), "w"), indent=1)
n = sum(1 for h in hasil if h["masalah"])
print(f"\n{len(hasil) - n}/{len(hasil)} lulus")
sys.exit(1 if n else 0)
