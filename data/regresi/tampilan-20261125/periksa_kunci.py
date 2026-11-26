"""Uji peramban hitung mundur login terkunci (26 Nov 2026).

Server = server_kunci.py PORT DETIK (penguncian DETIK detik, DATABASE UJI).
  C:/Users/Dani/alat-playwright/Scripts/python.exe periksa_kunci.py PORT DETIK KELUAR.json

A. JavaScript HIDUP:
   - 5 sandi salah -> kotak terkunci, hitung mundur mm:ss (dibaca tiap 250 ms);
   - tombol dan kotak sandi DIAKTIFKAN PAKSA (DOM), sandi BENAR dikirim ->
     server menolak 429, tetap di login, tidak masuk;
   - di halaman baru itu: penanda window bertahan sampai akhir (= tidak dimuat
     ulang), wilayah aria-live berubah tepat SEKALI (MutationObserver), pesan
     "Silakan coba lagi.", kotak + tombol aktif, fokus di kotak sandi;
   - sandi benar sesudahnya -> tujuan semula (/admin/log).
B. JavaScript MATI: 5 sandi salah -> meta refresh "DETIK;url=..." aktif,
   halaman dimuat ulang sendiri (GET) saat penguncian berakhir, formulir aktif.
"""
import json
import re
import sys
import time

from playwright.sync_api import sync_playwright

PORT, DETIK, KELUAR = sys.argv[1], int(sys.argv[2]), sys.argv[3]
DASAR = f"http://127.0.0.1:{PORT}"
SANDI = "sandi-tangkapan-layar"
hasil = {}


def salah_lima(hal):
    hal.goto(DASAR + "/admin/login?next=/admin/log")
    pesan = []
    for _ in range(5):
        hal.fill('input[name="sandi"]', "salah-sekali")
        with hal.expect_navigation():
            hal.click('button[type="submit"]')
        teks = hal.locator(".kabar").first.inner_text()
        pesan.append(" ".join(teks.split()))
    return pesan


def keadaan(hal):
    return hal.evaluate("""() => {
        const i = document.querySelector('input[name="sandi"]');
        const b = document.querySelector('form.form-admin button[type="submit"]');
        const k = document.getElementById('kotak-kunci');
        const h = document.querySelector('.hitung-mundur');
        return {url: location.pathname + location.search,
                input_aktif: i && !i.disabled, tombol_aktif: b && !b.disabled,
                fokus_sandi: document.activeElement === i,
                kotak: k ? k.className : null, data_sisa: k ? k.dataset.sisa : null,
                pesan: k ? document.getElementById('pesan-kunci').textContent.replace(/\\s+/g, ' ').trim() : null,
                hitung_tampak: h ? !h.hidden && h.offsetParent !== null : null,
                hitung: h ? h.textContent.replace(/\\s+/g, ' ').trim() : null,
                statis_tampak: (() => { const s = document.querySelector('.sisa-statis');
                    return s ? s.getBoundingClientRect().width > 1 : null; })(),
                meta: [...document.querySelectorAll('meta[http-equiv="refresh"]')].map(m => m.content)};
    }""")


with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome")

    # ---- A. JavaScript hidup ----
    hal = br.new_page(viewport={"width": 1280, "height": 900})
    hasil["A_pesan_salah"] = salah_lima(hal)
    hasil["A_terkunci"] = keadaan(hal)
    # Diaktifkan paksa, sandi benar: server tetap menolak.
    hal.evaluate("""() => { document.querySelector('input[name="sandi"]').disabled = false;
        document.querySelector('form.form-admin button[type="submit"]').disabled = false; }""")
    hal.fill('input[name="sandi"]', SANDI)
    with hal.expect_navigation() as nav:
        hal.click('button[type="submit"]')
    hasil["A_paksa_status"] = nav.value.status
    hasil["A_paksa"] = keadaan(hal)
    # Pengamat: penanda halaman + mutasi wilayah aria-live.
    hal.evaluate("""() => { window.__penanda = 'halaman-sama'; window.__mutasi = [];
        new MutationObserver(r => window.__mutasi.push(
            document.getElementById('pesan-kunci').textContent.replace(/\\s+/g, ' ').trim()))
          .observe(document.getElementById('pesan-kunci'),
                   {childList: true, characterData: true, subtree: true}); }""")
    detak, mulai = [], time.time()
    while time.time() - mulai < DETIK + 6:
        k = keadaan(hal)
        if not detak or detak[-1][1] != k["hitung"] or detak[-1][2] != k["input_aktif"]:
            detak.append([round(time.time() - mulai, 2), k["hitung"], k["input_aktif"]])
        if k["input_aktif"]:
            break
        time.sleep(0.25)
    hasil["A_detak"] = detak
    hal.wait_for_timeout(1500)        # beri waktu kalau ada perubahan susulan
    hasil["A_akhir"] = keadaan(hal)
    hasil["A_penanda"] = hal.evaluate("() => window.__penanda || null")
    hasil["A_mutasi"] = hal.evaluate("() => window.__mutasi")
    hal.fill('input[name="sandi"]', SANDI)
    with hal.expect_navigation():
        hal.click('button[type="submit"]')
    hasil["A_masuk"] = hal.evaluate("() => location.pathname")
    hal.context.close()

    # ---- B. JavaScript mati ----
    ktx = br.new_context(java_script_enabled=False, viewport={"width": 375, "height": 800})
    hal = ktx.new_page()
    permintaan = []
    hal.on("request", lambda r: r.resource_type == "document" and permintaan.append(
        [round(time.time(), 2), r.method, r.url.replace(DASAR, "")]))
    hasil["B_pesan_salah"] = salah_lima(hal)
    hasil["B_terkunci"] = keadaan(hal)
    t0 = time.time()
    with hal.expect_navigation(timeout=(DETIK + 10) * 1000):
        pass
    hasil["B_muat_ulang_detik"] = round(time.time() - t0, 2)
    hasil["B_sesudah"] = keadaan(hal)
    hasil["B_permintaan_terakhir"] = permintaan[-1][1:]
    ktx.close()
    br.close()

json.dump(hasil, open(KELUAR, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- Penilaian ----
a1, ap, ak = hasil["A_terkunci"], hasil["A_paksa"], hasil["A_akhir"]
mmss = [d[1] for d in hasil["A_detak"] if not d[2] and d[1] and re.fullmatch(r"Coba lagi dalam \d\d:\d\d", d[1])]
detik_turun = [int(x[-2:]) + 60 * int(x[-5:-3]) for x in mmss]
nilai = {
    "pesan sisa percobaan 4/3/2/1, lalu terkunci": all(
        t.startswith(f"Kata sandi salah. Sisa {n} percobaan sebelum login dikunci ")
        for n, t in zip((4, 3, 2, 1), hasil["A_pesan_salah"]))
        and hasil["A_pesan_salah"][4].startswith("Kata sandi salah 5 kali. Login dari komputer ini dikunci sementara."),
    "terkunci: formulir nonaktif, hitung mundur tampak, kalimat statis disembunyikan visual":
        not a1["input_aktif"] and not a1["tombol_aktif"] and a1["hitung_tampak"] and a1["statis_tampak"] is False
        and a1["data_sisa"] == str(DETIK),
    "diaktifkan paksa + sandi benar: server 429, tetap di login, tetap terkunci":
        hasil["A_paksa_status"] == 429 and ap["url"].startswith("/admin/login") and ap["data_sisa"] is not None
        and not ap["input_aktif"],
    "hitung mundur mm:ss turun per detik, tanpa lompatan":
        len(detik_turun) >= DETIK - 2 and all(b - a == -1 for a, b in zip(detik_turun, detik_turun[1:])),
    "akhir: tanpa muat ulang, kotak+tombol aktif, fokus sandi, 'Silakan coba lagi.', hitung mundur hilang":
        hasil["A_penanda"] == "halaman-sama" and ak["input_aktif"] and ak["tombol_aktif"] and ak["fokus_sandi"]
        and ak["pesan"] == "Silakan coba lagi." and ak["hitung_tampak"] is False and "kabar-sukses" in ak["kotak"],
    "aria-live berubah tepat sekali (di akhir)": hasil["A_mutasi"] == ["Silakan coba lagi."],
    "sesudah habis sandi benar -> tujuan semula /admin/log (next terjaga)": hasil["A_masuk"] == "/admin/log",
    "JS mati: meta refresh tepat saat berakhir, formulir nonaktif":
        hasil["B_terkunci"]["meta"] == [f"{DETIK};url=/admin/login?next=/admin/log"]
        and not hasil["B_terkunci"]["input_aktif"] and not hasil["B_terkunci"]["tombol_aktif"],
    "JS mati: dimuat ulang sendiri (GET) saat berakhir, formulir aktif, tanpa kotak kunci":
        DETIK - 1 <= hasil["B_muat_ulang_detik"] <= DETIK + 3
        and hasil["B_permintaan_terakhir"] == ["GET", "/admin/login?next=/admin/log"]
        and hasil["B_sesudah"]["input_aktif"] and hasil["B_sesudah"]["kotak"] is None,
}
for k, v in nilai.items():
    print(("LULUS " if v else "GAGAL ") + k)
print(f"{sum(nilai.values())}/{len(nilai)}")
