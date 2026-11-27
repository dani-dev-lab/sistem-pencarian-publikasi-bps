"""Manifes data/sampul (folder PRODUKSI): nama, ukuran, waktu ubah, SHA-256.
  python manifes_sampul.py simpan <keluar.json>
  python manifes_sampul.py banding <a.json> <b.json>"""
import hashlib, json, os, sys
from datetime import datetime
DIR = "data/sampul"
def buat():
    m = {}
    for n in sorted(os.listdir(DIR)):
        p = os.path.join(DIR, n); st = os.stat(p)
        m[n] = [st.st_size, st.st_mtime_ns, hashlib.sha256(open(p, "rb").read()).hexdigest()]
    return m
def ringkas(m):
    t = [v[1] / 1e9 for v in m.values()]
    return (f"{len(m)} berkas, {sum(v[0] for v in m.values()):,} byte ({sum(v[0] for v in m.values()) / 1e6:.1f} MB), "
            f".cadangan.jpg {sum(n.endswith('.cadangan.jpg') for n in m)}, lain-lain {sum(not n.endswith('.jpg') for n in m)}, "
            f"waktu ubah {datetime.fromtimestamp(min(t)):%H:%M:%S}-{datetime.fromtimestamp(max(t)):%H:%M:%S}")
if sys.argv[1] == "simpan":
    m = buat(); json.dump(m, open(sys.argv[2], "w")); print(datetime.now().strftime("%H:%M:%S"), ringkas(m))
else:
    a, b = json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))
    print("A:", ringkas(a)); print("B:", ringkas(b))
    beda = sorted(n for n in set(a) | set(b) if a.get(n) != b.get(n))
    print("IDENTIK (nama, ukuran, waktu ubah, SHA-256)" if not beda else f"BERBEDA {len(beda)}: {beda[:5]}")
    sys.exit(1 if beda else 0)
