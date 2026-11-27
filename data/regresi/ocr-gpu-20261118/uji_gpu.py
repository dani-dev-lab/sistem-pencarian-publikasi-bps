"""OCR ulang 5 halaman ke folder sementara (TIDAK menimpa cache).
python uji_gpu.py <cpu|gpu> <folder_keluar>"""
import json, os, sys, time, glob
sys.path.insert(0, r"C:\sistem-pencarian-bps")
os.chdir(r"C:\sistem-pencarian-bps")
from app.services import ocr

SAMPEL = [("289e7b7ffea9212fd954d849", 11), ("289e7b7ffea9212fd954d849", 70),
          ("4d55a44608bb761456d1204c", 9), ("8f34c2e76948f89e9a7b4a18", 27),
          ("8f34c2e76948f89e9a7b4a18", 14)]
mode, keluar = sys.argv[1], sys.argv[2]
os.makedirs(keluar, exist_ok=True)
ocr.GPU = mode == "gpu"
if ocr.GPU:
    import torch
    assert torch.cuda.is_available()

def pdf(pid):
    return glob.glob(f"data/publikasi_pdf/*/{pid}.pdf")[0]

# pemanasan: muat model + kernel pertama, tidak dihitung
ocr._ocr_halaman(pdf(SAMPEL[0][0]), 1)
for pid, h in SAMPEL:
    t0 = time.perf_counter()
    isi = ocr._ocr_halaman(pdf(pid), h)
    isi["detik_total"] = round(time.perf_counter() - t0, 2)   # render + OCR
    json.dump(isi, open(os.path.join(keluar, f"{pid}-{h:04d}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(mode, pid[:8], h, len(isi["kata"]), "kata", isi["detik_ocr"], "s ocr", isi["detik_total"], "s total", flush=True)
