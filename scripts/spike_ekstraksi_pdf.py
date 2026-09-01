"""Spike minggu 1: uji kelayakan ekstraksi struktur dokumen dari PDF publikasi BPS.

Eksperimen validasi, BUKAN kode produksi. Tujuannya menjawab 4 pertanyaan:
  1. Apakah heading DAFTAR ISI/TABEL/GAMBAR/LAMPIRAN selalu ada dan bisa dicari otomatis?
  2. Apakah watermark URL kalsel.bps.go.id ikut terekstrak sebagai teks?
  3. Berapa banyak judul entri yang membungkus ke lebih dari satu baris?
  4. Berapa persen entri yang berhasil di-parse dengan struktur masuk akal?

Jalankan:  venv/Scripts/python.exe scripts/spike_ekstraksi_pdf.py
"""

import glob
import json
import os
import re

import pdfplumber

DIR_SAMPEL = "data/sampel_pdf"
FILE_HASIL = "data/hasil_spike.json"
BATAS_HALAMAN_CARI = 25   # heading dicari di 25 halaman pertama saja
MAKS_BARIS_GABUNG = 6     # pengaman supaya penggabungan judul tidak lari jauh

# Heading "DAFTAR ...". Sengaja longgar supaya varian gabungan seperti
# "DAFTAR TABEL, GRAFIK, DAN GAMBAR" ikut tertangkap.
RE_HEADING = re.compile(r"^\s*DAFTAR\s+([A-Z][A-Z, ]{2,40})\s*$", re.IGNORECASE)

# Awal entri bernomor: "Tabel 1 Judul...", "Gambar 2.1 Judul...", "Lampiran 3 Judul..."
RE_AWAL_ENTRI = re.compile(
    r"^(Tabel|Gambar|Grafik|Lampiran)\s+([0-9]+(?:[.][0-9]+)*)[.]?\s+(.*)$",
    re.IGNORECASE,
)

# Akhir entri: titik-titik lalu nomor halaman (angka atau angka romawi).
RE_AKHIR_ENTRI = re.compile(r"[.]{2,}\s*([0-9]+|[ivxlc]+)\s*$", re.IGNORECASE)

# Entri DAFTAR ISI: apa saja yang punya dot leader lalu nomor halaman.
RE_ENTRI_ISI = re.compile(r"^(.+?)\s*[.]{3,}\s*([0-9]+|[ivxlc]+)\s*$", re.IGNORECASE)

# Watermark tercetak miring/vertikal sehingga terekstrak jadi huruf lepas per baris.
HURUF_WATERMARK = set("https://kalsel.bps.go.id")


def bersihkan_watermark(teks):
    """Buang jejak watermark, kembalikan (teks_bersih, jumlah_temuan)."""
    jumlah = 0
    baris_bersih = []

    for baris in teks.split("\n"):
        isi = baris.strip()

        # Kasus 1: watermark jadi baris berisi 1 karakter lepas ("d", "i", ".", "/").
        if len(isi) == 1 and isi.lower() in HURUF_WATERMARK:
            jumlah += 1
            continue

        # Kasus 2: huruf watermark nyelip di tengah dot leader
        # ("Umum .........d......... 1"). Buang hurufnya, sisakan titiknya.
        baris, n = re.subn(r"([.]{2,})[a-z]([.]{2,})", r"\1\2", baris)
        jumlah += n

        baris_bersih.append(baris)

    return "\n".join(baris_bersih), jumlah


def normalkan_tipe(teks_heading):
    """'TABEL, GRAFIK, DAN GAMBAR' -> ['tabel', 'gambar']. Grafik dianggap gambar."""
    t = teks_heading.lower()
    tipe = []
    if "isi" in t:
        tipe.append("isi")
    if "tabel" in t:
        tipe.append("tabel")
    if "gambar" in t or "grafik" in t:
        tipe.append("gambar")
    if "lampiran" in t:
        tipe.append("lampiran")
    return tipe


def cari_heading(pdf):
    """Cari halaman tiap heading DAFTAR X. Return ({tipe: halaman}, daftar_mentah)."""
    ketemu = {}
    mentah = []
    batas = min(BATAS_HALAMAN_CARI, len(pdf.pages))

    for i in range(batas):
        teks = pdf.pages[i].extract_text() or ""
        teks, _ = bersihkan_watermark(teks)

        # Heading selalu di baris-baris awal halaman.
        for baris in teks.split("\n")[:6]:
            cocok = RE_HEADING.match(baris)
            if not cocok:
                continue
            mentah.append({"halaman": i, "teks": baris.strip()})
            for tipe in normalkan_tipe(cocok.group(1)):
                ketemu.setdefault(tipe, i)

    return ketemu, mentah


def parse_entri_bernomor(baris_halaman):
    """Parse "Tabel 1 Judul ....... 7"; judul boleh membungkus ke baris berikutnya."""
    entri = []
    i = 0
    while i < len(baris_halaman):
        cocok = RE_AWAL_ENTRI.match(baris_halaman[i].strip())
        if not cocok:
            i += 1
            continue

        label, nomor, sisa = cocok.groups()
        potongan = [sisa]
        baris_terpakai = 1

        # Gabung terus sampai ketemu nomor halaman di ujung.
        while (not RE_AKHIR_ENTRI.search(potongan[-1])
               and baris_terpakai < MAKS_BARIS_GABUNG):
            j = i + baris_terpakai
            if j >= len(baris_halaman):
                break
            lanjutan = baris_halaman[j].strip()
            # Berhenti kalau ternyata sudah masuk entri berikutnya.
            if not lanjutan or RE_AWAL_ENTRI.match(lanjutan):
                break
            potongan.append(lanjutan)
            baris_terpakai += 1

        gabungan = " ".join(potongan)
        akhir = RE_AKHIR_ENTRI.search(gabungan)
        halaman = akhir.group(1) if akhir else None

        judul = RE_AKHIR_ENTRI.sub("", gabungan)
        judul = re.sub(r"[.]{2,}", " ", judul)
        judul = re.sub(r"\s+", " ", judul).strip(" .")

        entri.append({
            "label": label.lower(),
            "nomor": nomor,
            "judul": judul,
            "halaman": halaman,
            "membungkus": baris_terpakai > 1,
            "jumlah_baris": baris_terpakai,
        })
        i += baris_terpakai

    return entri


def parse_entri_isi(baris_halaman):
    """DAFTAR ISI lebih longgar: ada BAB, angka romawi, subbab. Cukup judul + halaman."""
    entri = []
    for baris in baris_halaman:
        cocok = RE_ENTRI_ISI.match(baris.strip())
        if not cocok:
            continue
        judul = re.sub(r"\s+", " ", cocok.group(1)).strip(" .")
        if len(judul) < 3:
            continue
        entri.append({
            "label": "isi",
            "nomor": None,
            "judul": judul,
            "halaman": cocok.group(2),
            "membungkus": False,
            "jumlah_baris": 1,
        })
    return entri


def baca_daftar(pdf, halaman_awal, tipe):
    """Baca satu DAFTAR X, lanjut ke halaman berikutnya selama masih ada entri.

    Daftar Lampiran Perhotelan misalnya memanjang ke beberapa halaman fisik.
    """
    semua = []
    halaman_dipakai = []
    h = halaman_awal

    while h < len(pdf.pages):
        teks = pdf.pages[h].extract_text() or ""
        teks, _ = bersihkan_watermark(teks)
        baris = teks.split("\n")

        # Halaman lanjutan yang ternyata heading DAFTAR lain -> berhenti.
        if h != halaman_awal and any(RE_HEADING.match(b) for b in baris[:6]):
            break

        entri = parse_entri_isi(baris) if tipe == "isi" else parse_entri_bernomor(baris)
        if not entri:
            break

        semua.extend(entri)
        halaman_dipakai.append(h)
        h += 1

    return semua, halaman_dipakai


def masuk_akal(e, tipe):
    """Kriteria 'struktur masuk akal' untuk menghitung tingkat keberhasilan."""
    if not e["judul"] or len(e["judul"]) < 5:
        return False
    if not e["halaman"]:
        return False
    if tipe != "isi" and not e["nomor"]:
        return False
    return True


def proses_pdf(path):
    hasil = {
        "file": os.path.basename(path),
        "heading_ditemukan": {},
        "heading_mentah": [],
        "watermark_ditemukan": 0,
        "entri": {},
    }

    with pdfplumber.open(path) as pdf:
        hasil["total_halaman"] = len(pdf.pages)

        heading, mentah = cari_heading(pdf)
        hasil["heading_ditemukan"] = heading
        hasil["heading_mentah"] = mentah

        # Watermark dihitung dari 25 halaman pertama supaya sebanding antar file.
        for i in range(min(BATAS_HALAMAN_CARI, len(pdf.pages))):
            _, n = bersihkan_watermark(pdf.pages[i].extract_text() or "")
            hasil["watermark_ditemukan"] += n

        for tipe, hal in sorted(heading.items(), key=lambda x: x[1]):
            entri, halaman_dipakai = baca_daftar(pdf, hal, tipe)
            hasil["entri"][tipe] = {
                "halaman_heading": hal,
                "halaman_dipakai": halaman_dipakai,
                "jumlah": len(entri),
                "jumlah_membungkus": sum(1 for e in entri if e["membungkus"]),
                "jumlah_masuk_akal": sum(1 for e in entri if masuk_akal(e, tipe)),
                "daftar": entri,
            }

    return hasil


def cetak_ringkasan(h):
    print()
    print("=" * 78)
    print(f"{h['file']}  ({h['total_halaman']} halaman)")
    print("=" * 78)

    if h["heading_mentah"]:
        print("  Heading ditemukan:")
        for m in h["heading_mentah"]:
            print(f"    hal {m['halaman']:>3} : {m['teks']}")
    else:
        print("  Heading ditemukan: TIDAK ADA")

    print(f"  Jejak watermark (25 hal pertama): {h['watermark_ditemukan']}")

    for tipe, d in h["entri"].items():
        pct = (d["jumlah_masuk_akal"] / d["jumlah"] * 100) if d["jumlah"] else 0
        print()
        print(f"  [{tipe.upper()}] halaman {d['halaman_dipakai']} -> {d['jumlah']} entri, "
              f"{d['jumlah_membungkus']} membungkus, "
              f"{d['jumlah_masuk_akal']} masuk akal ({pct:.0f}%)")
        for e in d["daftar"][:3]:
            nomor = f"{e['nomor']} " if e["nomor"] else ""
            print(f"      - {nomor}{e['judul'][:68]} | hal {e['halaman']}")


def main():
    daftar_pdf = sorted(glob.glob(os.path.join(DIR_SAMPEL, "*.pdf")))
    if not daftar_pdf:
        print(f"Tidak ada PDF di {DIR_SAMPEL}/")
        return

    print(f"Memproses {len(daftar_pdf)} PDF dari {DIR_SAMPEL}/")
    semua_hasil = [proses_pdf(p) for p in daftar_pdf]
    for h in semua_hasil:
        cetak_ringkasan(h)

    # ---------- Ringkasan agregat: jawaban 4 pertanyaan spike ----------
    tipe_wajib = ["isi", "tabel", "gambar", "lampiran"]
    total_entri = total_bungkus = total_ok = 0
    for h in semua_hasil:
        for d in h["entri"].values():
            total_entri += d["jumlah"]
            total_bungkus += d["jumlah_membungkus"]
            total_ok += d["jumlah_masuk_akal"]

    print()
    print("=" * 78)
    print("RINGKASAN AGREGAT")
    print("=" * 78)

    print()
    print("1. Apakah heading selalu ada dan bisa ditemukan otomatis?")
    for tipe in tipe_wajib:
        ada = [h["file"] for h in semua_hasil if tipe in h["heading_ditemukan"]]
        tidak = [h["file"] for h in semua_hasil if tipe not in h["heading_ditemukan"]]
        baris = f"   DAFTAR {tipe.upper():<9} : {len(ada)}/{len(semua_hasil)} publikasi"
        if tidak:
            baris += f"  (tidak ada: {', '.join(tidak)})"
        print(baris)

    print()
    print("2. Apakah watermark ikut terekstrak?")
    total_wm = sum(h["watermark_ditemukan"] for h in semua_hasil)
    kena = sum(1 for h in semua_hasil if h["watermark_ditemukan"] > 0)
    print(f"   YA pada {kena}/{len(semua_hasil)} publikasi, total {total_wm} jejak "
          f"(25 halaman pertama).")
    print("   Wajib dibersihkan sebelum parsing.")

    print()
    print("3. Berapa banyak judul yang membungkus ke lebih dari satu baris?")
    pct_b = (total_bungkus / total_entri * 100) if total_entri else 0
    print(f"   {total_bungkus} dari {total_entri} entri ({pct_b:.1f}%).")
    print("   Penggabungan baris WAJIB, bukan opsional.")

    print()
    print("4. Berapa persen entri ter-parse dengan struktur masuk akal?")
    pct_ok = (total_ok / total_entri * 100) if total_entri else 0
    print(f"   {total_ok} dari {total_entri} entri ({pct_ok:.1f}%)")

    with open(FILE_HASIL, "w", encoding="utf-8") as f:
        json.dump(semua_hasil, f, ensure_ascii=False, indent=2)
    print()
    print(f"Hasil mentah -> {FILE_HASIL}")


if __name__ == "__main__":
    main()
