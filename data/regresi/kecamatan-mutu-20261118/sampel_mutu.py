"""Sampel acak entri Kecamatan Dalam Angka bertekst (database UJI, hanya baca).

  python sampel_mutu.py [n] [seed]

Per entri dicetak bukti yang dipakai menilai:
  - DAFTAR: baris halaman Daftar (hal. fisik 1-60) yang memuat nomor entri;
  - FISIK: baris teratas halaman yang dituju tombol PDF, baris yang memuat
    nomor entri di halaman itu, dan baris angka saja (folio).
"""
import os, random, re, sys
DIR = "C:/sistem-pencarian-bps"; os.chdir(DIR); sys.path.insert(0, DIR)
import pdfplumber
from sqlalchemy import create_engine, text
from app.config import KonfigurasiUji
from app.services.ekstraksi_pdf import _bukan_watermark

n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
seed = int(sys.argv[2]) if len(sys.argv) > 2 else 20261118
target = {l.split()[0] for l in open("data/ocr_target_kecamatan.txt", encoding="utf-8") if l.strip() and not l.startswith("#")}
eng = create_engine(KonfigurasiUji.SQLALCHEMY_DATABASE_URI)
with eng.connect() as c:
    baris = c.execute(text("select e.id, p.id, p.domain, p.judul, e.tipe, e.nomor, e.judul, e.halaman, e.halaman_fisik, "
                           "e.halaman_fisik_perkiraan, e.sumber from entri_dokumen e join publikasi p on p.id=e.publikasi_id "
                           "where p.judul like 'Kecamatan%' order by e.id")).fetchall()
populasi = [b for b in baris if b[1] not in target]
print(f"populasi {len(populasi)} entri, {len({b[1] for b in populasi})} publikasi; seed {seed}")
sampel = random.Random(seed).sample(populasi, n)

def baris_hal(pdf, i):
    t = pdf.pages[i - 1].filter(_bukan_watermark).extract_text() or ""
    return [x.strip() for x in t.splitlines() if x.strip()]

for k, (eid, pid, dom, pjudul, tipe, nomor, judul, hal, fis, prk, sumber) in enumerate(sampel, 1):
    print(f"\n#{k} id={eid} {pjudul} [{pid[:8]}]\n   {tipe} {nomor} | hal {hal} | fisik {fis}{' (perkiraan)' if prk else ''} | {sumber}\n   JUDUL: {judul}")
    with pdfplumber.open(f"data/publikasi_pdf/{dom}/{pid}.pdf") as pdf:
        kunci = re.escape(nomor) + r"(?![\d.]\d)" if nomor else None
        cari = re.compile(r"(^|\s)" + kunci) if kunci else None
        if cari:
            for i in range(1, min(60, len(pdf.pages)) + 1):
                ls = baris_hal(pdf, i)
                if sum(1 for x in ls if re.search(r"\.{4,}|…", x)) < 3:
                    continue
                for j, x in enumerate(ls):
                    if cari.search(x) and (tipe == "tabel") == bool(re.search(r"tabel|table|^\d", x, re.I) or True):
                        ikut = [x]
                        for y in ls[j + 1:j + 4]:
                            if re.search(r"[\d.]\s*\d\s*$|\d$", ikut[-1]) and len(ikut) > 0 and re.search(r"\.{3,}|\s\d+$", ikut[-1]): break
                            ikut.append(y)
                        print(f"   DAFTAR p{i}: " + " // ".join(z[:110] for z in ikut))
        if fis:
            ls = baris_hal(pdf, fis)
            print(f"   FISIK p{fis} atas: " + " | ".join(x[:70] for x in ls[:4]))
            if cari:
                for x in ls:
                    if cari.search(x): print(f"   FISIK cocok: {x[:120]}")
            print(f"   FISIK folio: angka={[x for x in ls if re.fullmatch(r'[\divxlc]{1,4}', x)][:3]} kop={[x[:60] for x in ls if re.search(r'DALAM ANGKA|IN FIGURE', x, re.I)][:2]} bawah={[x[:50] for x in ls[-2:]]}")
