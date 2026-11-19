"""Pola kartu PUBLIKASI di V5 (diambil dari tests/uji_pipeline.py, bukan diketik ulang) pada
halaman nyata tanpa sampul dan dengan sampul + kelas jebakan."""
import ast, json, re, sys
sys.stdout.reconfigure(encoding="utf-8")
baris = next(b for b in open("tests/uji_pipeline.py", encoding="utf-8") if "re.findall(r'<article class=\"kartu kartu-pub" in b and "(.*?)" in b)
POLA = ast.literal_eval(re.search(r"re\.findall\((r'[^']*')", baris).group(1))
print("pola V5:", POLA)
def hitung(berkas):
    p = json.load(open(berkas, encoding="utf-8"))["potret"]
    semua = cocok = pub = pub_sampul = bukan_pub_cocok = 0
    for u, v in p.items():
        h = v["isi"]
        kelas = re.findall(r'<article class="(kartu [^"]*)">', h)
        semua += len(kelas); pub += sum(k.startswith("kartu kartu-pub") for k in kelas)
        pub_sampul += sum(k == "kartu kartu-pub ada-sampul" for k in kelas)
        isi = re.findall(POLA, h, re.S); cocok += len(isi)
        bukan_pub_cocok += sum(bool(re.search(r'class="tipe tipe-(?!publikasi)', k)) for k in isi)
    return semua, pub, pub_sampul, cocok, bukan_pub_cocok
ok = True
for nama, f in (("tanpa sampul (potret DB uji siang)", "data/regresi/tombol-atas-20261119/potret-uji-tombol.json"),
                ("dengan sampul (potret DB uji sore)", "data/regresi/sampul-20261119/potret-uji-sampul.json")):
    semua, pub, ps, cocok, salah = hitung(f)
    b = cocok == pub and salah == 0
    ok &= b
    print(f"{nama}: {semua} kartu, {pub} kartu PUBLIKASI ({ps} bersampul), {semua - pub} kartu tabel/gambar/lampiran/bab; "
          f"dikenali pola {cocok}, kartu non-publikasi ikut {salah} -> {'OK' if b else 'MASALAH'}")
jebakan = ['<article class="kartu kartu-tabel">x</article>', '<article class="kartu kartu-isi">x</article>',
           '<article class="kartu kartu-gambar">x</article>', '<article class="kartu kartu-lampiran">x</article>',
           '<article class="kartu kartu-publikasi">x</article>', '<article class="kartu kartu-pub lain">x</article>',
           '<article class="kartu kartu-pub ada-sampul x">x</article>', '<article class="kartu kartu-tabel ada-sampul">x</article>']
lolos = [j for j in jebakan if re.findall(POLA, j, re.S)]
benar = ['<article class="kartu kartu-pub">x</article>', '<article class="kartu kartu-pub ada-sampul">x</article>']
kenal = [j for j in benar if re.findall(POLA, j, re.S)]
print(f"jebakan cocok: {len(lolos)}/{len(jebakan)} {lolos}; dua bentuk sah dikenali: {len(kenal)}/2")
ok &= not lolos and len(kenal) == 2
print("LULUS" if ok else "GAGAL"); sys.exit(0 if ok else 1)
