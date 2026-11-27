import os, json, glob, time, sys
sys.path.insert(0, '.')
target=[l.split()[0] for l in open('data/regresi/kecamatan-mutu-20261118/ocr_target_kecamatan.txt',encoding='utf-8') if l.strip() and not l.startswith('#')]
sekarang=time.time()
for i,pid in enumerate(target,1):
    pdfs=glob.glob(f'data/publikasi_pdf/*/{pid}.pdf')
    dom=os.path.basename(os.path.dirname(pdfs[0]))
    f=f'data/ocr_cache/{dom}/{pid}'
    if not os.path.isdir(f): continue
    isi=os.listdir(f); masalah=[]
    meta=None
    try:
        meta=json.load(open(f+'/_meta.json',encoding='utf-8'))
        st=os.stat(pdfs[0])
        if meta['sidik']!=[st.st_size,int(st.st_mtime)]: masalah.append('sidik meta != PDF')
    except Exception as e: masalah.append(f'_meta rusak: {e!r}')
    hal=[x for x in isi if x.endswith('-easyocr.json')]
    lain=[x for x in isi if x not in hal and x!='_meta.json']
    if lain: masalah.append(f'berkas lain: {lain}')
    nol=0; kunci_kurang=0
    for x in hal:
        p=f+'/'+x
        if os.path.getsize(p)==0: masalah.append(f'{x} 0 byte'); continue
        try:
            d=json.load(open(p,encoding='utf-8'))
            if not {'kata','lebar_pt','tinggi_pt','mesin'}<=set(d): kunci_kurang+=1; masalah.append(f'{x} kunci kurang')
            if not d['kata']: nol+=1
        except Exception as e:
            umur=sekarang-os.path.getmtime(p); masalah.append(f'{x} JSON rusak ({e.__class__.__name__}, umur {umur:.0f}s)')
    nomor=sorted(int(x[:4]) for x in hal)
    harap=meta['halaman_tanpa_teks'] if meta else []
    luar=set(nomor)-set(harap)
    if luar: masalah.append(f'halaman di luar daftar meta: {sorted(luar)}')
    print(f'{i:2d} {pid} {dom}: cache {len(hal)}/{len(harap)} hal (nomor {nomor[:1]}..{nomor[-1:]}), kata kosong {nol}, ' + ('OK' if not masalah else 'MASALAH: '+'; '.join(masalah)))
