"""Cetak baris koordinat halaman Daftar + jalur yang dipakai parser (hanya baca).
  python diagnosa_daftar.py <pid_awalan> [halaman fisik ...]
Tanpa halaman: semua halaman Daftar tabel/gambar yang ditemukan cari_heading."""
import glob, os, sys
sys.stdout.reconfigure(encoding="utf-8"); os.chdir("C:/sistem-pencarian-bps"); sys.path.insert(0, ".")
import pdfplumber
from app.services import ekstraksi_pdf as E
f = glob.glob(f"data/publikasi_pdf/*/{sys.argv[1]}*.pdf")[0]
with pdfplumber.open(f) as pdf:
    hs = [int(x) for x in sys.argv[2:]]
    if not hs:
        print("heading:", E.cari_heading(pdf))
    for h in hs:
        baris = E._kelompokkan_baris(E._kata_halaman(pdf.pages[h - 1]))
        bk = E._batas_kanan(baris, "tabel")
        print(f"== hal {h}  batas_kanan={bk:.0f}  tanpa_label={E._mode_tanpa_label(baris,'tabel',bk)}  sebaris={E._mode_nomor_sebaris(baris,'tabel',bk)}")
        for b in baris[:int(os.environ.get('N', 40))]:
            print("  " + "  ".join(f"[{k['x0']:.0f}-{k['x1']:.0f}]{k['text']}" for k in b)[:260])
