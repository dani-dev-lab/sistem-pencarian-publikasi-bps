"""Perkiraan halaman fisik PDF dari selisih halaman cetak entri tetangga.

Masalahnya (16 Nov 2026): ±2.100 tabel/gambar/lampiran dari jalur Daftar
punya nomor halaman CETAK, tetapi halaman FISIK PDF-nya tidak ditemukan jalur
badan (keterangannya tidak terbaca). Tombol "Buka PDF" entri itu membuka
halaman 1.

Di dalam satu publikasi, selisih halaman fisik - halaman cetak biasanya tetap
di rentang yang panjang (halaman depan beromawi, lalu halaman 1 = fisik k).
Entri yang KEDUANYA sudah diketahui disebut jangkar. Perkiraan untuk entri
lain = halaman cetak + selisih jangkar di sekitarnya, dengan syarat:

  1. Jangkar = entri tipe APA PUN (termasuk isi) yang halaman cetaknya angka
     dan halaman fisiknya asli (bukan perkiraan). Perkiraan tidak pernah jadi
     jangkar, jadi tidak ada perkiraan berantai.
  2. Entri ISI hanya memakai jangkar tabel/gambar/lampiran (alasannya di
     perkirakan()). Untuk tabel/gambar/lampiran:
     Jangkar SETIPE didahulukan: kalau tipe entri itu (tabel/gambar/lampiran)
     punya jangkar tersaring di publikasi ini, hanya jangkar setipe yang
     dipakai; kalau tidak ada, jangkar semua tipe. Alasannya: sebagian
     publikasi menomori halaman Daftar Gambar dengan urutan yang tidak sama
     dengan folio tabel (Tabalong Dalam Angka 2026: selisih gambar 50-89,
     tabel di sekitarnya 36; Gambar 13.2 meleset 53 halaman dengan jangkar
     gabungan). Leave-one-out: 97,2% -> 97,7% tepat, meleset >=10 halaman
     107 -> 61, cakupan sama.
  3. Jangkar disaring:
       - halaman cetak yang jangkarnya tidak sepakat soal selisih dibuang;
       - jangkar dipakai hanya kalau selisihnya SAMA dengan jangkar
         tetangganya (urut halaman cetak). Satu angka menyimpang - misalnya
         halaman cetak yang salah baca di Daftar - tidak dipakai sendirian.
  4. Entri diperkirakan kalau:
       - ada jangkar di halaman cetak yang sama; atau
       - jangkar terdekat di bawah DAN di atasnya punya selisih yang sama
         (di antaranya tidak ada halaman sisipan); atau
       - ia di tepi (jangkar hanya di satu sisi) dan jangkar terdekat paling
         jauh JARAK_TEPI halaman cetak.
     Selain itu dibiarkan kosong.

Diuji leave-one-out di ±12.300 entri yang halaman fisiknya diketahui
(database uji, 16 Nov 2026): 97,7% tepat. Laporan:
data/regresi/perkiraan-halaman-20261116.md.

Fungsi di sini murni (tidak menyentuh database) dan tidak bergantung pada
urutan entri, sehingga pemuatan lewat pipeline_data.simpan_entri dan pengisian
data lama lewat scripts/isi_perkiraan_halaman.py menghasilkan nilai yang sama.
"""

import bisect
from collections import defaultdict

# Tipe yang diperkirakan. Tabel/gambar/lampiran sejak 16 Nov 2026; isi
# (bab/subbab) ditambahkan 16 Nov 2026 sore atas permintaan pemilik project.
TIPE_NON_ISI = ("tabel", "gambar", "lampiran")
TIPE_DIPERKIRAKAN = TIPE_NON_ISI + ("isi",)

# Jarak terjauh (halaman cetak) ke jangkar untuk entri di tepi publikasi.
JARAK_TEPI = 10


def _angka(halaman):
    """Halaman cetak -> int, atau None kalau bukan angka biasa ("v", "xxi", None)."""
    if halaman is None:
        return None
    teks = str(halaman).strip()
    return int(teks) if teks.isdigit() else None


def _jangkar(entri):
    """[(halaman cetak, selisih)] terurut, sesudah disaring (lihat docstring modul)."""
    selisih = defaultdict(set)
    for e in entri:
        cetak = _angka(e.get("halaman"))
        fisik = e.get("halaman_fisik")
        if cetak is None or not fisik or e.get("halaman_fisik_perkiraan"):
            continue
        selisih[cetak].add(fisik - cetak)

    titik = [(c, next(iter(s))) for c, s in sorted(selisih.items()) if len(s) == 1]
    return [
        (c, o) for k, (c, o) in enumerate(titik)
        if (k > 0 and titik[k - 1][1] == o) or (k + 1 < len(titik) and titik[k + 1][1] == o)
    ]


def _tebak(jangkar, kunci, cetak):
    """Selisih untuk halaman cetak `cetak`, atau None."""
    j = bisect.bisect_left(kunci, cetak)
    if j < len(kunci) and kunci[j] == cetak:
        return jangkar[j][1]
    bawah = jangkar[j - 1] if j > 0 else None
    atas = jangkar[j] if j < len(kunci) else None
    if bawah and atas:
        return bawah[1] if bawah[1] == atas[1] else None
    tepi = bawah or atas
    if tepi and abs(cetak - tepi[0]) <= JARAK_TEPI:
        return tepi[1]
    return None


def perkirakan(entri):
    """Perkiraan halaman fisik untuk entri satu publikasi.

    `entri`: urutan dict (atau objek berperilaku dict lewat .get) dengan kunci
    tipe, halaman, halaman_fisik, dan opsional halaman_fisik_perkiraan.
    Return {indeks: halaman fisik perkiraan}, hanya untuk entri bertipe
    TIPE_DIPERKIRAKAN yang halaman fisiknya kosong. Nilai yang sudah ada tidak
    pernah dikembalikan, jadi tidak pernah diubah.
    """
    gabungan = _jangkar(entri)
    if not gabungan:
        return {}
    pilihan = {}
    for tipe in TIPE_NON_ISI:
        jangkar = _jangkar([e for e in entri if e.get("tipe") == tipe]) or gabungan
        pilihan[tipe] = (jangkar, [c for c, _ in jangkar])
    # Entri ISI: HANYA jangkar tabel/gambar/lampiran. Ini sengaja BUKAN
    # "setipe dulu", dan jangkar isi tidak dipakai sama sekali.
    # Alasannya: halaman fisik isi dicari dari teks judul
    # (lengkapi_halaman_isi), dan di sebagian publikasi bergeser dari halaman
    # yang dirujuk Daftar Isi:
    #   - +2 di PDRB: sampul bab tanpa teks, judulnya tercetak lagi sesudahnya;
    #   - +1 di Booklet Sakernas.
    # Halaman fisik tabel/gambar/lampiran berasal dari keterangan bernomor
    # dan cocok dengan folio. Bukti dari folio di halaman perkiraan (yang
    # terbaca), 16 Nov 2026:
    #   - jangkar non-isi 91% tepat;
    #   - jangkar isi (cadangan) 61%;
    #   - "isi dulu" 78%.
    # Tanpa jangkar non-isi, entri isi dibiarkan kosong.
    jangkar = _jangkar([e for e in entri if e.get("tipe") in TIPE_NON_ISI])
    pilihan["isi"] = (jangkar, [c for c, _ in jangkar])

    hasil = {}
    for i, e in enumerate(entri):
        if e.get("tipe") not in TIPE_DIPERKIRAKAN or e.get("halaman_fisik"):
            continue
        cetak = _angka(e.get("halaman"))
        if cetak is None:
            continue
        jangkar, kunci = pilihan[e["tipe"]]
        selisih = _tebak(jangkar, kunci, cetak)
        if selisih is not None and cetak + selisih >= 1:
            hasil[i] = cetak + selisih
    return hasil
