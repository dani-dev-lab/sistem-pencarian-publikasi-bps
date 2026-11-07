"""Ekstraksi struktur dokumen dari PDF publikasi BPS.

Pendekatan: berbasis KOORDINAT KATA (pdfplumber extract_words), bukan parsing
baris teks. Spike minggu 1 membuktikan parsing baris gagal total pada layout
dua kolom, dan watermark menyusup ke dalam kata sehingga regex teks tidak bisa
diandalkan.

Dipakai lewat satu fungsi:

    entri = ekstrak_struktur("data/publikasi_pdf/abc.pdf", "abc")

Mengembalikan list of dict: {publikasi_id, tipe, nomor, judul, halaman}.
Modul ini tidak menyentuh database sama sekali.
"""

import re
from collections import Counter

import pdfplumber

BATAS_HALAMAN_CARI = 25     # heading DAFTAR X dicari di 25 halaman pertama
TOLERANSI_BARIS = 3.0       # selisih `top` (poin) yang masih dianggap satu baris
TOLERANSI_KOLOM = 4.0       # selisih `x0` yang masih dianggap satu kolom
BATAS_KANAN_RASIO = 0.80    # kandidat nomor halaman harus berakhir di 80% kanan
MAKS_BARIS_PER_ENTRI = 8    # pengaman supaya penggabungan tidak lari jauh
MIN_NOMOR_KOLOM = 3         # minimal baris angka-tunggal sebelum mode tanpa-label aktif
MAKS_LOMPAT_AWAL = 1        # daftar kadang baru mulai di halaman setelah headingnya

LABEL_ENTRI = ("tabel", "gambar", "grafik", "lampiran")

# Sebagian publikasi memakai heading dwibahasa: "DAFTAR TABEL/LIST OF TABLES",
# "DAFTAR ISI / CONTENTS", "DAFTAR LAMPIRAN/APPENDICES". Garis miring dan kata
# Inggrisnya harus ikut tertampung, kalau tidak headingnya tidak terdeteksi
# sama sekali dan publikasi menghasilkan nol entri.
RE_HEADING = re.compile(r"^DAFTAR\s+([A-Z][A-Z, /]{2,60})$", re.IGNORECASE)
RE_NOMOR = re.compile(r"^[0-9]+(?:[.][0-9]+)*[.]?$")
RE_ANGKA = re.compile(r"^[0-9]+$")
RE_ROMAWI = re.compile(r"^[ivxlcdm]+$", re.IGNORECASE)
RE_TAHUN = re.compile(r"^(19|20)[0-9]{2}")

# Judul yang muncul di kolom kanan sering diawali sisa dot leader / glyph rusak.
RE_SAMPAH = re.compile(r"^[.…�\s]+$")

# Judul kolom di atas daftar: "Halaman", "Tabel Halaman", "Table Page".
# HANYA dipakai di dalam mode tanpa-label; jalur normal tidak menyentuhnya.
RE_KOP_KOLOM = re.compile(
    r"^(halaman|hal|page|"
    r"(tabel|table|gambar|figure|grafik|lampiran|appendix)\s+(halaman|page))$",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------
# Lapisan 1: ambil kata bersih dari halaman
# --------------------------------------------------------------------------

def _bukan_watermark(obj):
    """Watermark BPS dicetak miring 45 derajat, teks asli tidak.

    Dibedakan lewat matriks transformasi karakter, BUKAN lewat pola teks.
    Teks normal punya matrix (1, 0, 0, 1, ...); watermark (0.707, 0.707, ...).
    Inilah yang menyelesaikan masalah "Pertaniano" dan "kKategori" di spike:
    huruf watermark dibuang sebelum kata terbentuk, bukan sesudahnya.
    """
    m = obj.get("matrix")
    if m is None:
        return True
    return abs(m[1]) < 0.01 and abs(m[2]) < 0.01


def _kata_halaman(halaman):
    """Semua kata pada satu halaman, watermark sudah dibuang."""
    return halaman.filter(_bukan_watermark).extract_words()


def _kelompokkan_baris(kata):
    """Kelompokkan kata jadi baris berdasarkan kedekatan koordinat `top`.

    Tidak memakai newline dari extract_text() - itu yang bikin layout dua kolom
    tertukar urutannya.
    """
    baris = []
    for k in sorted(kata, key=lambda a: (a["top"], a["x0"])):
        if baris and abs(k["top"] - baris[-1][0]["top"]) <= TOLERANSI_BARIS:
            baris[-1].append(k)
        else:
            baris.append([k])
    return [sorted(b, key=lambda a: a["x0"]) for b in baris]


def _teks_baris(baris):
    return " ".join(k["text"] for k in baris)


# --------------------------------------------------------------------------
# Lapisan 2: cari heading DAFTAR X
# --------------------------------------------------------------------------

def _tipe_dari_heading(teks):
    """'TABEL, GRAFIK, DAN GAMBAR' -> ['tabel', 'gambar'].

    Satu heading bisa mewakili lebih dari satu tipe. Grafik disamakan dengan
    gambar supaya tipe di database tetap empat macam.
    """
    t = teks.lower()
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


LABEL_UNTUK_TIPE = {
    "tabel": ("tabel",),
    "gambar": ("gambar", "grafik"),
    "lampiran": ("lampiran",),
}


def _indeks_mulai(baris, tipe, batas_kanan):
    """Dari baris ke berapa entri sebenarnya mulai, atau None kalau tak ketemu.

    Halaman daftar diawali kop: ISSN, judul publikasi, volume - dan letaknya
    bisa di ATAS maupun di BAWAH heading DAFTAR X (berbeda antar publikasi),
    serta tidak selalu diakhiri label kolom "Halaman".

    Dua penanda dipakai berurutan: label "Halaman" kalau ada, lalu posisi kiri.
    Kop dicetak rata tengah sehingga x0-nya menjorok jauh ke kanan dibanding
    entri yang rata kiri.
    """
    idx_heading = None
    for i, b in enumerate(baris[:8]):
        cocok = RE_HEADING.match(_teks_baris(b).strip())
        if cocok and tipe in _tipe_dari_heading(cocok.group(1)):
            idx_heading = i
            break
    if idx_heading is None:
        return None

    mulai = idx_heading + 1
    for j in range(mulai, min(mulai + 8, len(baris))):
        if _teks_baris(baris[j]).strip().upper() in ("HALAMAN", "HAL"):
            mulai = j + 1
            break

    # Margin kiri daftar = x0 terkecil di antara baris yang jelas berakhir
    # nomor halaman.
    kiri = [b[0]["x0"] for b in baris[mulai:]
            if _cari_halaman_di_baris(b, batas_kanan, tipe)[1]]
    if not kiri:
        return mulai

    margin = min(kiri)
    while (mulai < len(baris)
           and baris[mulai][0]["x0"] > margin + TOLERANSI_KOLOM):
        mulai += 1
    return mulai


def _mode_tanpa_label(daftar_baris, tipe, batas_kanan):
    """Apakah halaman ini daftar bernomor TANPA kata label? -> (aktif, x_judul).

    Syaratnya sengaja ketat supaya jalur ini benar-benar terkurung dan tidak
    pernah menyentuh publikasi berformat biasa. SEMUA harus terpenuhi:

    1. bukan Daftar Isi
    2. tidak ada satu pun baris berlabel (judul kolom "Tabel Halaman" tidak
       dihitung sebagai label - itu kop, bukan entri)
    3. ada kolom judul yang jelas, diukur dari x0 yang paling sering muncul
       pada baris yang berakhir nomor halaman
    4. ada MINIMAL MIN_NOMOR_KOLOM baris berisi angka tunggal di kolom kiri -
       satu saja bisa kebetulan, beberapa berarti memang pola penomorannya
    """
    if tipe == "isi":
        return False, None

    for b in daftar_baris:
        if RE_KOP_KOLOM.match(_teks_baris(b).strip()):
            continue
        if _label_baris(b):
            return False, None

    kolom = Counter(round(b[0]["x0"]) for b in daftar_baris
                    if _cari_halaman_di_baris(b, batas_kanan, tipe)[1])
    if not kolom:
        return False, None
    x_judul = kolom.most_common(1)[0][0]

    nomor_kiri = sum(
        1 for b in daftar_baris
        if len(b) == 1
        and RE_NOMOR.match(b[0]["text"])
        and b[0]["x0"] < x_judul - TOLERANSI_KOLOM
    )
    if nomor_kiri < MIN_NOMOR_KOLOM:
        return False, None

    return True, x_judul


def _lanjutan_masuk_akal(baris, tipe, batas_kanan):
    """Apakah halaman ini benar lanjutan daftar, bukan sudah masuk isi buku?

    Tanpa penjagaan ini pembacaan meluber ke halaman isi: baris badan teks yang
    kebetulan diakhiri angka ikut terhitung sebagai entri.
    """
    if tipe == "isi":
        # Daftar Isi dikenali dari kepadatan baris yang berakhir nomor halaman.
        isi_baris = [b for b in baris if _teks_baris(b).strip()]
        if not isi_baris:
            return False
        berhalaman = sum(
            1 for b in isi_baris
            if _cari_halaman_di_baris(b, batas_kanan, tipe)[1]
        )
        return berhalaman >= max(3, len(isi_baris) * 0.5)

    # Daftar tanpa kata label punya kriteria sendiri.
    aktif, _ = _mode_tanpa_label(baris, tipe, batas_kanan)
    if aktif:
        return True

    # Daftar bernomor: halaman lanjutan pasti masih memuat labelnya.
    label_sah = LABEL_UNTUK_TIPE.get(tipe, ())
    return any(_label_baris(b) in label_sah for b in baris)


def cari_heading(pdf):
    """Cari halaman tiap heading DAFTAR X. Return {tipe: nomor_halaman}.

    Heading yang tidak ada bukan error - DAFTAR LAMPIRAN memang hanya ada di
    sebagian publikasi.
    """
    ketemu = {}
    for i in range(min(BATAS_HALAMAN_CARI, len(pdf.pages))):
        baris = _kelompokkan_baris(_kata_halaman(pdf.pages[i]))
        for b in baris[:6]:                       # heading selalu di atas halaman
            cocok = RE_HEADING.match(_teks_baris(b).strip())
            if cocok:
                for tipe in _tipe_dari_heading(cocok.group(1)):
                    ketemu.setdefault(tipe, i)
    return ketemu


# --------------------------------------------------------------------------
# Lapisan 3: nomor halaman (kata paling kanan)
# --------------------------------------------------------------------------

def _pisah_nomor_halaman(teks, tipe):
    """Ambil nomor halaman dari kata paling kanan.

    Menangani kasus nomor halaman menempel pada tahun karena dot leader hilang:
    '20259' -> ('2025', '9'). Tanpa ini, judul kehilangan tahunnya DAN nomor
    halamannya salah.

    Return (sisa_untuk_judul, nomor_halaman) atau (teks, None).
    """
    bersih = teks.strip(".…�")
    if not bersih:
        return teks, None

    if RE_ANGKA.match(bersih):
        # "20259" = tahun 2025 + halaman 9, dot leader-nya hilang.
        if len(bersih) >= 5 and RE_TAHUN.match(bersih):
            return bersih[:4], bersih[4:]
        # Tahun utuh di ujung baris BUKAN nomor halaman. Pada layout dua kolom
        # judul sering berakhir "..., 2025" sementara nomor halamannya baru
        # muncul di baris berikutnya; tanpa penjagaan ini entri terbelah dua.
        if len(bersih) == 4 and RE_TAHUN.match(bersih):
            return teks, None
        return "", bersih

    # Daftar Isi memakai angka romawi untuk halaman depan (v, vii, ix).
    if tipe == "isi" and RE_ROMAWI.match(bersih):
        return "", bersih.lower()

    return teks, None


def _cari_halaman_di_baris(baris, batas_kanan, tipe):
    """Cek apakah baris ini diakhiri nomor halaman di margin kanan.

    Posisi yang menentukan, bukan dot leader - di sebagian publikasi dot leader
    berupa glyph rusak (U+FFFD) sehingga tidak bisa dijadikan penanda.
    """
    if not baris:
        return None, None
    terakhir = baris[-1]
    if terakhir["x1"] < batas_kanan:
        return None, None
    sisa, halaman = _pisah_nomor_halaman(terakhir["text"], tipe)
    return (sisa, halaman) if halaman else (None, None)


# --------------------------------------------------------------------------
# Lapisan 4: rakit entri
# --------------------------------------------------------------------------

def _label_baris(baris):
    """Return label ('tabel'/'gambar'/...) kalau baris diawali label entri."""
    if not baris:
        return None
    awal = baris[0]["text"].lower().strip(".:")
    return awal if awal in LABEL_ENTRI else None


def _bersihkan_judul(potongan):
    """Buang dot leader, glyph rusak, dan spasi berlebih."""
    kata = [p for p in potongan if p and not RE_SAMPAH.match(p)]
    teks = " ".join(kata)
    teks = re.sub(r"[.…�]{2,}", " ", teks)
    teks = re.sub(r"\s+", " ", teks)
    return teks.strip(" .…�")


def _rakit_entri(kumpulan, tipe, publikasi_id, batas_kanan, tanpa_label=False):
    """Ubah kumpulan baris satu entri menjadi dict hasil.

    `kumpulan` = list of baris; tiap baris = list kata terurut kiri->kanan.
    Nomor bisa berada di baris berbeda dari labelnya (layout dua kolom PDRB),
    jadi pencarian nomor melihat seluruh kolom kiri entri ini.

    `tanpa_label=True` hanya dipakai oleh _parse_baris_tanpa_label.
    """
    semua_kata = [k for b in kumpulan for k in b]
    if not semua_kata:
        return None

    nomor = None
    dilewati = set()          # kata yang tidak ikut masuk ke judul

    if tanpa_label:
        # Nomor entri berdiri sendiri sebagai satu-satunya kata pada barisnya.
        for b in kumpulan:
            if len(b) == 1 and RE_NOMOR.match(b[0]["text"]):
                nomor = b[0]["text"].rstrip(".")
                dilewati.add(id(b[0]))
                break
    elif tipe != "isi":
        label_kata = kumpulan[0][0]
        if label_kata["text"].lower().strip(".:") in LABEL_ENTRI:
            dilewati.add(id(label_kata))
            x_label = label_kata["x0"]

            # Kasus 1 (umum): nomor tepat setelah label, baris yang sama.
            if len(kumpulan[0]) > 1 and RE_NOMOR.match(kumpulan[0][1]["text"]):
                nomor = kumpulan[0][1]["text"].rstrip(".")
                dilewati.add(id(kumpulan[0][1]))
            else:
                # Kasus 2 (dua kolom): nomor di baris berikutnya, kolom kiri
                # yang sama dengan label.
                for k in semua_kata:
                    if id(k) in dilewati:
                        continue
                    if (abs(k["x0"] - x_label) <= TOLERANSI_KOLOM
                            and RE_NOMOR.match(k["text"])):
                        nomor = k["text"].rstrip(".")
                        dilewati.add(id(k))
                        break

    # Nomor halaman dicari di kata paling kanan SETIAP baris entri, bukan hanya
    # baris terakhir. Letaknya berbeda-beda antar publikasi: ada yang menaruh di
    # baris pertama lalu judulnya menyambung ke bawah, ada yang sebaliknya.
    halaman = None
    potongan = []
    for b in kumpulan:
        for j, k in enumerate(b):
            if id(k) in dilewati:
                continue
            if halaman is None and j == len(b) - 1 and k["x1"] >= batas_kanan:
                sisa, hal = _pisah_nomor_halaman(k["text"], tipe)
                if hal:
                    halaman = hal
                    if sisa:
                        potongan.append(sisa)
                    continue
            potongan.append(k["text"])

    judul = _bersihkan_judul(potongan)
    if not judul:
        return None

    # Buang sisa yang bukan judul: nomor halaman berjalan di kaki halaman
    # daftar ("ix", "xii") dan potongan nomor entri yang terlepas ("4.1").
    inti = judul.strip(".,;: ")
    if RE_ROMAWI.match(inti) or RE_NOMOR.match(inti) or RE_ANGKA.match(inti):
        return None

    return {
        "publikasi_id": publikasi_id,
        "tipe": tipe,
        "nomor": nomor,
        "judul": judul,
        "halaman": halaman,
    }


def _parse_baris_tanpa_label(daftar_baris, tipe, publikasi_id, batas_kanan,
                             x_judul):
    """Jalur khusus daftar bernomor TANPA kata label ("Kalsel Dalam Angka").

    Penutup entri adalah nomor halaman, seperti Daftar Isi. Judul berada di
    kolom kanan; baris di kolom kiri yang bukan nomor entri adalah judul seksi
    ("1.1 KEADAAN GEOGRAFI") dan dibuang supaya tidak mencemari judul.

    Penyaringan judul kolom hanya terjadi di sini, tidak di jalur normal.
    """
    entri = []
    buffer = []

    def tutup():
        hasil = _rakit_entri(buffer, tipe, publikasi_id, batas_kanan,
                             tanpa_label=True)
        if hasil:
            entri.append(hasil)

    for baris in daftar_baris:
        teks = _teks_baris(baris).strip()
        if not teks or RE_HEADING.match(teks) or RE_KOP_KOLOM.match(teks):
            continue

        sendirian = len(baris) == 1 and bool(RE_NOMOR.match(baris[0]["text"]))
        di_kiri = baris[0]["x0"] < x_judul - TOLERANSI_KOLOM
        if di_kiri and not sendirian:
            continue

        buffer.append(baris)

        _, halaman = _cari_halaman_di_baris(baris, batas_kanan, tipe)
        if halaman or len(buffer) >= MAKS_BARIS_PER_ENTRI:
            tutup()
            buffer = []

    if buffer:
        tutup()

    return entri


def _parse_baris(daftar_baris, tipe, publikasi_id, batas_kanan):
    """Rakit entri dari baris-baris satu halaman daftar.

    Aturan penutupan entri berbeda menurut tipe daftar:

    - Daftar bernomor (tabel/gambar/lampiran): entri dibatasi oleh LABEL, bukan
      oleh nomor halaman. Letak nomor halaman tidak konsisten antar publikasi -
      ada yang menaruhnya di baris pertama lalu judul menyambung ke bawah, ada
      yang di baris terakhir setelah judul membungkus. Memakai label sebagai
      batas menangani kedua-duanya.
    - Daftar Isi: tidak punya label, jadi nomor halaman yang jadi penutup.

    Halaman yang lolos syarat ketat _mode_tanpa_label dialihkan seluruhnya ke
    _parse_baris_tanpa_label, sehingga jalur normal di bawah ini tidak berubah
    sedikit pun untuk publikasi berformat biasa.
    """
    aktif, x_judul = _mode_tanpa_label(daftar_baris, tipe, batas_kanan)
    if aktif:
        return _parse_baris_tanpa_label(
            daftar_baris, tipe, publikasi_id, batas_kanan, x_judul)

    entri = []
    buffer = []

    def tutup():
        hasil = _rakit_entri(buffer, tipe, publikasi_id, batas_kanan)
        if hasil:
            entri.append(hasil)

    for baris in daftar_baris:
        teks = _teks_baris(baris).strip()

        # Lewati heading dan label kolom.
        if RE_HEADING.match(teks) or teks.upper() in ("HALAMAN", "HAL"):
            continue
        if not teks:
            continue

        if tipe != "isi" and buffer and _label_baris(baris):
            tutup()
            buffer = []

        buffer.append(baris)

        if tipe == "isi":
            _, halaman = _cari_halaman_di_baris(baris, batas_kanan, tipe)
            selesai = bool(halaman)
        else:
            selesai = False

        if selesai or len(buffer) >= MAKS_BARIS_PER_ENTRI:
            tutup()
            buffer = []

    if buffer:  # sisa di akhir halaman
        tutup()

    return entri


# --------------------------------------------------------------------------
# Lapisan 5: satu daftar bisa memanjang ke beberapa halaman fisik
# --------------------------------------------------------------------------

def _baca_daftar(pdf, halaman_awal, tipe, publikasi_id, jejak=None):
    """Baca satu DAFTAR X, termasuk lanjutannya ke beberapa halaman fisik.

    Sebagian publikasi hanya memuat heading di halaman itu dan baru memulai
    daftarnya di halaman berikutnya. Karena itu, SELAMA belum ada satu entri
    pun, halaman kosong boleh dilewati sampai MAKS_LOMPAT_AWAL kali. Setelah
    entri pertama didapat, halaman kosong tetap berarti daftarnya habis.
    """
    entri = []
    h = halaman_awal
    lompat = 0
    heading_daftar = None     # tipe heading milik daftar ini, dari halaman awalnya

    def boleh_lompat():
        # Hanya berlaku di awal; tidak pernah menyentuh daftar yang sudah jalan.
        nonlocal lompat, h
        if entri or lompat >= MAKS_LOMPAT_AWAL:
            return False
        lompat += 1
        h += 1
        return True

    while h < len(pdf.pages):
        baris = _kelompokkan_baris(_kata_halaman(pdf.pages[h]))
        if not baris:
            if boleh_lompat():
                continue
            break

        kanan_maks = max(k["x1"] for b in baris for k in b)
        batas_kanan = kanan_maks * BATAS_KANAN_RASIO

        # Tipe heading pada halaman ini (kalau ada).
        heading_tipe = None
        for b in baris[:6]:
            cocok = RE_HEADING.match(_teks_baris(b).strip())
            if cocok:
                heading_tipe = _tipe_dari_heading(cocok.group(1))
                break

        if not entri:
            # Masih mencari awal daftar. Heading untuk tipe LAIN berarti daftar
            # yang dicari memang tidak ada; heading untuk tipe yang sama berarti
            # halaman inilah awal sebenarnya - kop samping halaman kadang membuat
            # heading terdeteksi satu halaman terlalu awal.
            if heading_tipe and tipe not in heading_tipe:
                break
            if heading_tipe:
                heading_daftar = heading_tipe
            idx = _indeks_mulai(baris, tipe, batas_kanan)
            if idx is not None:
                baris = baris[idx:]
        else:
            if heading_tipe:
                # Heading DAFTAR lain -> daftar habis. Tapi heading yang SAMA
                # PERSIS bisa diulang di tiap halaman lanjutan (TPB 2024
                # mencetak "DAFTAR GAMBAR" di ketiga halaman daftarnya). Dulu
                # itu juga dianggap akhir daftar, sehingga Gambar 14-38 hilang
                # dari jalur daftar. Syaratnya kesamaan seluruh tipe, bukan
                # sekadar memuat tipe ini: "DAFTAR GAMBAR" sesudah "DAFTAR
                # TABEL DAN GAMBAR" tetap mengakhiri daftar tabelnya.
                if heading_tipe != heading_daftar:
                    break
                idx = _indeks_mulai(baris, tipe, batas_kanan)
                if idx is not None:
                    baris = baris[idx:]
            if not _lanjutan_masuk_akal(baris, tipe, batas_kanan):
                break

        # Catat halaman mana yang memakai jalur tanpa-label, supaya bisa
        # diperiksa apakah syarat pengaktifannya masih terlalu longgar.
        if jejak is not None:
            aktif, _ = _mode_tanpa_label(baris, tipe, batas_kanan)
            if aktif:
                jejak.append(f"{tipe}:hal{h}")

        hasil = _parse_baris(baris, tipe, publikasi_id, batas_kanan)
        if not hasil:
            if boleh_lompat():
                continue
            break

        entri.extend(hasil)
        h += 1

    return entri


# --------------------------------------------------------------------------
# Lapisan 6: keterangan tabel/gambar di BADAN dokumen
# --------------------------------------------------------------------------

# "Tabel 1.3", "Gambar 4.1 Judul...", "Grafik 2. Judul..."
# Label yang benar-benar ada di korpus. Disurvei pada 12 publikasi: tabel 256x,
# gambar 187x, lampiran 182x. "Diagram", "Peta", "Boks", "Bagan", "Appendix"
# NOL kemunculan - sengaja tidak dimasukkan supaya tidak menambah risiko tanpa
# manfaat. "Table"/"Figure" juga tidak: satu-satunya kemunculan adalah kop
# kolom dwibahasa ("Table 2022-2025"), bukan keterangan.
RE_KETERANGAN = re.compile(
    r"^(Tabel|Gambar|Grafik|Lampiran)\s+([0-9]+(?:[.][0-9]+)*)[.:]?\s*(.*)$",
    re.IGNORECASE)

MAKS_BARIS_KETERANGAN = 4   # judul keterangan jarang lebih dari 4 baris
MIN_PANJANG_JUDUL = 8


def _warna(kata):
    """Warna teks sebagai tuple yang bisa dijadikan kunci dict."""
    c = kata.get("non_stroking_color")
    if c is None:
        return None
    try:
        return tuple(round(float(x), 2) for x in c)
    except TypeError:
        return (round(float(c), 2),)


def _gaya(kata):
    """(fontname, size, warna) - penanda gaya visual satu kata.

    WARNA wajib ikut. Sebagian publikasi menulis keterangan dengan font dan
    ukuran yang SAMA PERSIS dengan teks badan, hanya warnanya yang berbeda -
    contoh nyata: "Lampiran 1 Formula Perhitungan Indeks Williamson" berwarna
    oranye (0.976, 0.416, 0.106) di atas badan hitam (0.0,). Tanpa warna,
    keterangan itu disangka teks badan dan dibuang.
    """
    return (str(kata.get("fontname")),
            round(float(kata.get("size") or 0), 1),
            _warna(kata))


def _gaya_dominan(kata):
    """Gaya teks badan halaman: (fontname, size) dan warna dihitung TERPISAH.

    Menghitung keduanya sebagai satu kesatuan menimbulkan efek samping halus:
    baris data tabel sering memuat beberapa warna sekaligus, sehingga hitungan
    gaya badan terpecah-pecah dan gaya KETERANGAN justru bisa naik jadi yang
    paling banyak - lalu keterangannya sendiri disangka teks badan dan dibuang.
    Terbukti menghilangkan "Tabel 54 Nilai Tukar Usaha Rumah Tangga Pertanian".

    Dihitung terpisah, syarat penerimaan jadi longgar dengan cara yang aman:
    keterangan diterima kalau font/ukurannya BEDA (aturan lama) ATAU warnanya
    beda (tambahan baru). Tidak ada keterangan yang tadinya diterima jadi
    tertolak.
    """
    font_size = Counter((str(k.get("fontname")),
                         round(float(k.get("size") or 0), 1)) for k in kata)
    warna = Counter(_warna(k) for k in kata)
    return font_size.most_common(1)[0][0], warna.most_common(1)[0][0]


def _beda_dari_badan(gaya, dominan):
    """Apakah gaya ini berbeda dari teks badan - lewat font/ukuran ATAU warna."""
    dom_fs, dom_warna = dominan
    return (gaya[0], gaya[1]) != dom_fs or gaya[2] != dom_warna


def _x_awal_judul(baris, label, nomor):
    """Posisi x tempat teks judul mulai pada baris keterangan.

    Return None kalau barisnya hanya berisi "Tabel N" tanpa judul - berarti
    judulnya ada di baris-baris SESUDAHNYA, bukan sebelumnya.
    """
    awalan = f"{label} {nomor}".lower()
    akum = ""
    for idx, k in enumerate(baris):
        akum = (akum + " " + k["text"]).strip()
        if akum.rstrip(".:").lower() == awalan:
            return baris[idx + 1]["x0"] if idx + 1 < len(baris) else None
    return None


def _halaman_daftar(teks_baris):
    """Apakah ini halaman DAFTAR (isi/tabel/gambar/lampiran), bukan badan?

    `teks_baris`: teks tiap baris halaman, berurutan dari atas.
    Dua tanda: heading DAFTAR di 6 baris teratas, atau dot leader lebih dari
    tiga - halaman lanjutan daftar tidak selalu mengulang headingnya.

    Dipakai dua tahap yang sama-sama mencari keterangan di BADAN dokumen:
    ekstrak_badan() dan lengkapi_halaman_fisik(). Baris daftar memuat label
    dan nomor yang persis sama dengan keterangan aslinya, dan sebagian
    publikasi mencetaknya tebal atau berwarna sehingga lolos aturan gaya.
    Tanpa pemeriksaan ini halaman daftar terbaca sebagai halaman keterangan:
    tombol PDF membuka halaman daftar, dan nomor halaman di ujung baris daftar
    ikut masuk ke judul ("... 2021-2024 26").
    """
    if any(RE_HEADING.match(b) for b in teks_baris[:6]):
        return True
    return " ".join(teks_baris).lower().count(".....") > 3


def ekstrak_badan(pdf, publikasi_id):
    """Ambil keterangan tabel/gambar dari BADAN dokumen, seluruh halaman.

    Diperlukan karena publikasi yang tidak punya halaman DAFTAR TABEL sama
    sekali tidak terindeks - contoh nyata: Master File Desa, yang tabelnya
    hanya ada di badan dokumen.

    Pembeda keterangan asli dari kalimat prosa yang kebetulan menyebut
    "Gambar 3": GAYA VISUAL. Keterangan selalu memakai font/ukuran yang BERBEDA
    dari teks badan halaman itu, sedangkan prosa memakai gaya yang sama.
    Diuji pada 4 publikasi berlayout berbeda; menolak "Gambar 3 di bawah ini
    menunjukkan..." sekaligus menerima keterangan asli di keempatnya.

    Nomor halaman yang dicatat adalah halaman FISIK PDF (indeks + 1), karena
    itu yang berguna untuk membuka PDF langsung di halaman tersebut.

    Halaman DAFTAR dilewati (lihat _halaman_daftar). Ini satu-satunya
    pengecualian terhadap aturan superset gaya - lihat CLAUDE.md: yang
    dijaga adalah keterangan ASLI, dan baris daftar bukan keterangan asli.
    """
    hasil = []

    for indeks, halaman in enumerate(pdf.pages):
        kata = halaman.filter(_bukan_watermark).extract_words(
            extra_attrs=["size", "fontname", "non_stroking_color"])
        if not kata:
            continue

        baris = _kelompokkan_baris(kata)
        if _halaman_daftar([_teks_baris(b).strip() for b in baris]):
            continue

        dominan = _gaya_dominan(kata)
        terpakai = set()      # baris yang sudah diserap keterangan lain

        for i, b in enumerate(baris):
            teks = _teks_baris(b).strip()
            cocok = RE_KETERANGAN.match(teks)
            if not cocok:
                continue

            gaya_keterangan = _gaya(b[0])
            if not _beda_dari_badan(gaya_keterangan, dominan):
                continue        # gaya sama dengan teks badan -> kalimat prosa

            label, nomor, sisa = cocok.groups()
            nomor = nomor.rstrip(".")

            # Angka tahun bukan nomor tabel. Label sumbu grafik ("2020 2021
            # 2022") kadang sejajar dengan baris keterangan lalu ikut terbaca,
            # menghasilkan "Gambar 2020".
            if RE_TAHUN.fullmatch(nomor):
                continue

            potongan = [sisa] if sisa else []

            # Judul bisa MENDAHULUI baris labelnya. Pada layout dua kolom,
            # "Tabel 3.2" berada di kolom kiri sejajar tengah blok judul, jadi
            # baris pertama judul muncul lebih dulu menurut urutan baca.
            # Tanpa penyerapan ke belakang, judulnya kehilangan bagian depan -
            # justru bagian yang paling sering diketik petugas.
            x_judul = _x_awal_judul(b, label, nomor)
            awalan = []
            if x_judul is not None:
                j = i - 1
                while j >= 0 and len(awalan) < MAKS_BARIS_KETERANGAN:
                    sebelum = baris[j]
                    teks_sebelum = _teks_baris(sebelum).strip()
                    gaya_sebelum = _gaya(sebelum[0])
                    # Font boleh berbeda asalkan UKURAN sama, sejajar dengan
                    # kolom judul, dan bukan gaya teks badan. Sebagian
                    # publikasi menata blok judul dan label "Tabel N" dengan
                    # font yang berlainan.
                    if (j in terpakai
                            or not _beda_dari_badan(gaya_sebelum, dominan)
                            or gaya_sebelum[1] != gaya_keterangan[1]
                            or RE_KETERANGAN.match(teks_sebelum)
                            or abs(sebelum[0]["x0"] - x_judul) > TOLERANSI_KOLOM):
                        break
                    awalan.insert(0, teks_sebelum)
                    terpakai.add(j)
                    j -= 1

            # Judul bisa berada di baris-baris berikutnya dengan gaya yang sama
            # persis (pola Master File Desa: "Tabel 1.3" sendirian di barisnya).
            for j in range(i + 1, min(i + 1 + MAKS_BARIS_KETERANGAN, len(baris))):
                lanjut = baris[j]
                if j in terpakai or _gaya(lanjut[0]) != gaya_keterangan:
                    break
                teks_lanjut = _teks_baris(lanjut).strip()
                if RE_KETERANGAN.match(teks_lanjut):
                    break       # sudah masuk keterangan berikutnya
                potongan.append(teks_lanjut)
                terpakai.add(j)

            judul = _bersihkan_judul(awalan + potongan)
            if len(judul) < MIN_PANJANG_JUDUL:
                continue

            rendah = label.lower()
            if rendah in ("gambar", "grafik"):
                tipe = "gambar"
            elif rendah == "lampiran":
                tipe = "lampiran"
            else:
                tipe = "tabel"
            hasil.append({
                "publikasi_id": publikasi_id,
                "tipe": tipe,
                "nomor": nomor,
                "judul": judul,
                "halaman": None,            # nomor cetak tidak diketahui dari badan
                "halaman_fisik": indeks + 1,
                "sumber": "badan",
            })

    return hasil


def _gabung(dari_daftar, dari_badan):
    """Satukan hasil dua jalur supaya tidak ada entri kembar.

    Kunci penggabungan: (tipe, nomor) dalam satu publikasi. Entri tanpa nomor
    tidak bisa dipasangkan, jadi dibiarkan berdiri sendiri.

    Kalau judulnya berbeda, yang dipakai adalah versi dari BADAN - itu judul
    lengkap yang sebenarnya, sementara versi di daftar kadang terpotong.
    """
    gabungan = list(dari_daftar)
    indeks = {}
    for e in gabungan:
        if e.get("nomor"):
            indeks.setdefault((e["tipe"], e["nomor"]), e)

    for b in dari_badan:
        kunci = (b["tipe"], b["nomor"])
        pasangan = indeks.get(kunci)
        if pasangan is None:
            gabungan.append(b)
            indeks[kunci] = b
            continue

        # Sudah ada dari daftar: lengkapi, jangan gandakan.
        pasangan["halaman_fisik"] = b["halaman_fisik"]
        if b["judul"] and len(b["judul"]) > len(pasangan["judul"]):
            pasangan["judul"] = b["judul"]
        pasangan["sumber"] = "keduanya"

    return gabungan


# --------------------------------------------------------------------------
# Lapisan 7: lengkapi halaman fisik untuk entri yang sudah diketahui
# --------------------------------------------------------------------------

LABEL_UNTUK_PENANDA = {"tabel": "Tabel", "gambar": "Gambar", "lampiran": "Lampiran"}

MIN_KATA_JUDUL = 2      # bukti minimal dari judul yang sudah kita punya
PANJANG_KATA_ISI = 5    # kata pendek terlalu umum untuk jadi bukti
MAKS_KATA_DIPAKAI = 5
AWALAN_COCOK = 6        # berapa huruf awal kata judul yang harus cocok


def _kata_isi(judul):
    """Kata isi dari judul yang SUDAH diketahui, dipakai sebagai bukti."""
    return [w.lower() for w in
            re.findall(rf"[A-Za-z]{{{PANJANG_KATA_ISI},}}", judul)][:MAKS_KATA_DIPAKAI]


def _cocokkan_di_halaman(baris, teks, penanda, kunci):
    """Cek satu halaman untuk satu entri. Return 'awal baris' | 'tengah' | None.

    Keterangan dibedakan dari kalimat prosa yang menyebutnya:
      - "Gambar 2.1 Persentase Konsumen..." di AWAL baris  -> keterangan
      - "...penggerak Gambar 2.7 Struktur..." tengah baris tapi langsung
        diikuti kata judul -> keterangan yang tergabung dengan kolom sebelah
      - "Berdasarkan Gambar 2.1, sebesar 60 persen" diikuti koma/angka
        -> PROSA, ditolak
    """
    if sum(1 for k in kunci if k in teks) < MIN_KATA_JUDUL:
        return None

    tengah = None
    for b in baris:
        if b.startswith(penanda):
            return "awal baris"
        pos = b.find(penanda)
        if pos < 0 or tengah:
            continue
        sisa = b[pos + len(penanda):].strip()
        if sisa[:1].isalpha() and any(
                sisa.startswith(k[:AWALAN_COCOK]) for k in kunci):
            tengah = "tengah baris (dua kolom)"
    return tengah


def lengkapi_halaman_fisik(pdf, entri):
    """Isi halaman_fisik untuk entri yang punya nomor tapi belum punya letaknya.

    Ini tahap PELENGKAP, bukan penemu entri: entrinya sudah diketahui ada dari
    halaman daftar, yang dicari hanya letak fisiknya. Karena itu aturan gaya
    visual tidak dipakai sama sekali - yang dipakai adalah pencocokan terhadap
    fakta yang sudah kita punya (nomor DAN judul), dan itu jauh lebih sempit
    ruang salahnya.

    Hanya MENGISI kolom yang kosong - tidak menambah, menghapus, maupun
    mengubah entri. Risiko terburuknya halaman yang salah, bukan entri hilang.

    Halaman dipindai SEKALI untuk semua entri sekaligus. Memindai ulang per
    entri membuat publikasi 892 halaman dengan 291 entri praktis tidak selesai.
    """
    tugas = []
    for e in entri:
        if e.get("halaman_fisik") or not e.get("nomor") or e["tipe"] == "isi":
            continue
        label = LABEL_UNTUK_PENANDA.get(e["tipe"])
        if not label:
            continue
        kunci = _kata_isi(e["judul"])
        if len(kunci) < MIN_KATA_JUDUL:
            continue
        tugas.append((e, f"{label} {e['nomor']}".lower(), kunci))

    if not tugas:
        return 0

    # Kecocokan "awal baris" mengalahkan "tengah baris", jadi yang tengah
    # disimpan dulu sebagai cadangan dan baru dipakai kalau sampai akhir tidak
    # ada yang lebih baik.
    cadangan = {}
    belum = list(tugas)

    for i, halaman in enumerate(pdf.pages):
        if not belum:
            break
        kata = halaman.filter(_bukan_watermark).extract_words()
        if not kata:
            continue

        baris = [_teks_baris(b).strip() for b in _kelompokkan_baris(kata)]
        if _halaman_daftar(baris):
            continue                    # halaman DAFTAR, bukan badan

        baris_kecil = [b.lower() for b in baris]
        teks = " ".join(baris_kecil)

        tersisa = []
        for e, penanda, kunci in belum:
            cara = _cocokkan_di_halaman(baris_kecil, teks, penanda, kunci)
            if cara == "awal baris":
                e["halaman_fisik"] = i + 1
                e["cara_halaman_fisik"] = cara
                cadangan.pop(id(e), None)
                continue                # selesai, tidak perlu dicari lagi
            if cara and id(e) not in cadangan:
                cadangan[id(e)] = (e, i + 1, cara)
            tersisa.append((e, penanda, kunci))
        belum = tersisa

    for e, hal, cara in cadangan.values():
        if not e.get("halaman_fisik"):
            e["halaman_fisik"] = hal
            e["cara_halaman_fisik"] = cara

    return sum(1 for e, _, _ in tugas if e.get("halaman_fisik"))


# --------------------------------------------------------------------------
# API modul
# --------------------------------------------------------------------------

def ekstrak_lengkap(path_pdf, publikasi_id, jejak=None, heading_keluar=None):
    """Ekstraksi DUA jalur: halaman daftar + badan dokumen, lalu digabung.

    Jalur daftar memberi nomor halaman CETAK; jalur badan memberi halaman
    FISIK PDF. Entri yang ditemukan keduanya disatukan sehingga punya
    dua-duanya, dengan kolom `sumber` menandai asalnya.

    `heading_keluar` opsional, sama polanya dengan `jejak`: kalau diberi dict,
    diisi heading DAFTAR yang ditemukan {tipe: indeks halaman}. Pemanggil yang
    perlu mencatat heading tidak usah memanggil cari_heading() sendiri - itu
    memakan sekitar 16% waktu ekstraksi karena seluruh halaman depan dibaca dua kali.
    """
    with pdfplumber.open(path_pdf) as pdf:
        dari_daftar = []
        heading = cari_heading(pdf)
        if heading_keluar is not None:
            heading_keluar.update(heading)
        for tipe, halaman in sorted(heading.items(), key=lambda x: x[1]):
            dari_daftar.extend(_baca_daftar(pdf, halaman, tipe, publikasi_id, jejak))
        for e in dari_daftar:
            e.setdefault("halaman_fisik", None)
            e.setdefault("sumber", "daftar")

        dari_badan = ekstrak_badan(pdf, publikasi_id)
        gabungan = _gabung(dari_daftar, dari_badan)
        n_dilengkapi = lengkapi_halaman_fisik(pdf, gabungan)

    return gabungan, len(dari_daftar), len(dari_badan), n_dilengkapi


def ekstrak_struktur(path_pdf, publikasi_id, jejak=None):
    """Ekstrak seluruh entri terstruktur dari satu PDF publikasi.

    Return list of dict {publikasi_id, tipe, nomor, judul, halaman}.
    List kosong berarti tidak ada daftar yang bisa dibaca - bukan error.

    `jejak` opsional: kalau diberi list, diisi penanda halaman yang memakai
    jalur tanpa-label. Berguna untuk memastikan jalur itu tidak melebar ke
    publikasi yang seharusnya tidak tersentuh.
    """
    entri = []
    with pdfplumber.open(path_pdf) as pdf:
        heading = cari_heading(pdf)
        for tipe, halaman in sorted(heading.items(), key=lambda x: x[1]):
            entri.extend(_baca_daftar(pdf, halaman, tipe, publikasi_id, jejak))
    return entri
