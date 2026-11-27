"""Waktu ekstraksi jalur lama vs baru, bergantian per PDF, 79 PDF, satu sesi.

A (lama) = cara ekstrak_semua.py dulu: cari_heading() pada PDF yang dibuka
           sendiri, lalu ekstrak_lengkap() membuka dan mencarinya lagi.
B (baru) = pipeline_data.ekstrak_berkas(): heading diambil dari ekstrak_lengkap().
Urutan dibalik tiap PDF (AB, BA, AB, ...) supaya pergeseran keadaan mesin terbagi
rata. Hanya membaca PDF; tidak menyentuh database.
"""
import json, logging, os, sys, time
sys.path.insert(0, os.getcwd())
logging.getLogger("pdfminer").setLevel(logging.ERROR)   # sama dengan perbarui.py

import pdfplumber
from app.services.ekstraksi_pdf import cari_heading, ekstrak_lengkap
from app.services.pipeline_data import ekstrak_berkas

SP = sys.argv[1]
pdf_semua = sorted(os.listdir("data/publikasi_pdf/6300"))

def lama(p, pid):
    with pdfplumber.open(p) as pdf:
        heading = cari_heading(pdf)
    entri = ekstrak_lengkap(p, pid, [])[0]
    return entri, sorted(heading)

def baru(p, pid):
    entri, catatan = ekstrak_berkas(p, pid)
    return entri, catatan["heading_ditemukan"]

baris, beda = [], []
mulai = time.time()
for i, nama in enumerate(pdf_semua):
    pid, p = nama[:-4], f"data/publikasi_pdf/6300/{nama}"
    urutan = (("A", lama), ("B", baru)) if i % 2 == 0 else (("B", baru), ("A", lama))
    r = {"pub_id": pid, "urutan": "".join(k for k, _ in urutan)}
    keluaran = {}
    for k, f in urutan:
        w0, c0 = time.perf_counter(), time.process_time()
        keluaran[k] = f(p, pid)
        r[k] = round(time.perf_counter() - w0, 2)
        r[k + "_cpu"] = round(time.process_time() - c0, 2)
    if keluaran["A"] != keluaran["B"]:
        beda.append(pid)
    baris.append(r)
    if (i + 1) % 10 == 0:
        a = sum(x["A"] for x in baris); b = sum(x["B"] for x in baris)
        print(f"[{i+1}/{len(pdf_semua)}] A {a:.0f} d | B {b:.0f} d | hemat {100*(a-b)/a:.1f}% | beda keluaran {len(beda)}", flush=True)

A = sum(x["A"] for x in baris); B = sum(x["B"] for x in baris)
hemat_per_pdf = sorted(100 * (x["A"] - x["B"]) / x["A"] for x in baris)
ringkas = {
    "pdf": len(baris), "A_lama_detik": round(A, 1), "B_baru_detik": round(B, 1),
    "A_cpu": round(sum(x["A_cpu"] for x in baris), 1), "B_cpu": round(sum(x["B_cpu"] for x in baris), 1),
    "hemat_detik": round(A - B, 1), "hemat_persen": round(100 * (A - B) / A, 1),
    "hemat_persen_median_per_pdf": round(hemat_per_pdf[len(hemat_per_pdf) // 2], 1),
    "B_lebih_lambat_pada_pdf": sum(1 for x in baris if x["B"] > x["A"]),
    "keluaran_A_vs_B_berbeda": beda, "detik_sesi": round(time.time() - mulai),
}
print(json.dumps(ringkas, indent=1))
json.dump({"ringkas": ringkas, "baris": baris}, open(f"{SP}/ukur_lama_baru.json", "w"), indent=1)
