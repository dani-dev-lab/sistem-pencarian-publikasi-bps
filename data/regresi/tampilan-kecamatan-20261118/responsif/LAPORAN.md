# Tampilan responsif kotak centang kecamatan (19 Nov 2026)

Keluhan dari cek browser pemilik project:
- desktop dan iPad Mini (768 px): kotak di kiri jauh, tulisan di kanan jauh;
- iPhone SE (375 px) dan Galaxy A55 (360 px): kotak hilang, dan tulisan
  terpecah dua kolom;
- iPhone 16 Pro Max (440 px): sudah benar.

## Penyebab
- Aturan kotak kata kunci `.kotak-cari input` (`flex: 1`, padding, border,
  `min-width: 0`) ikut mengenai kotak centang. Di layar lebar, elemen kotak
  centang melebar sampai 333-365 px, dan kotaknya tergambar di ujung kiri.
  Di 320-412 px, lebarnya menyusut sampai 0 px.
- Teks label terdiri dari dua bagian lepas (teks dan `span.ket`), sehingga
  menjadi dua item flex.
- Beranda memakai `text-align: center`, sehingga tulisan ikut dipusatkan.

## Perbaikan
- `app/static/css/style.css`:
  - `.kotak-cari .centang-kecamatan` dan aturan kotak centangnya lebih
    spesifik daripada `.kotak-cari input`;
  - kotak 20 px, jarak 8 px, `text-align: left`;
  - label minimal 44 px (seluruh label adalah area sentuh), selalu baris
    terakhir form.
  - Di layar <= 640 px, dropdown kecamatan menempati satu baris penuh di
    bawah wilayah + Cari.
- `app/templates/_form_cari.html`: teks label dalam satu
  `span.teks-centang`.

## Uji (`uji_responsif.py`, Playwright + Chrome terpasang)
- Server: `run.py --db-uji --port 5001`, perintah yang sama dengan
  `jalankan-aplikasi-uji.bat`.
- Lebar: 320, 360, 375, 390, 412, 440, 768, 1024, 1366.
- Halaman: beranda, beranda + Kab. Tanah Laut (dropdown kecamatan), hasil
  tanpa centang (dropdown + kotak info), hasil dengan centang + kc=pelaihari.
- Yang dinilai adalah pengukuran DOM, dan tangkapan layarnya juga dilihat
  satu per satu. Kriteria:
  - kotak terlihat (>= 12 px);
  - elemen kotak <= 24 px lebar;
  - jarak ke huruf pertama 6-12 px;
  - kotak sejajar dengan baris pertama;
  - baris tulisan rata kiri dan tidak masuk ke bawah kotak;
  - label rata kiri dengan kolom kata kunci;
  - label >= 44 px;
  - dropdown di dalam layar;
  - tanpa gulir horizontal.
- **Sesudah: 36/36 lulus** (jarak 8 px di semua lebar, label 44 px).
  Tangkapan layar: `<lebar>-<halaman>.png` dan `<lebar>-seksi-kecamatan.png`.
- **Alat dibuktikan dulu terhadap kode lama** (`sebelum-keluaran.txt`, 0/36):
  - kotak 0 px di 320-412;
  - kotak melebar 333-365 px di 768+;
  - 440 benar kecuali area sentuh 21 px.
  - Tangkapan layar kode lama (`sebelum-*.png`) disimpan lokal, di-gitignore.
- **Dua kali alatnya sendiri salah, lalu diperbaiki:**
  1. Elemen kotak yang melebar lolos cek jarak, karena jarak diukur dari tepi
     elemen. Ditambahkan syarat lebar elemen <= 24 px.
  2. Tulisan yang dipusatkan di beranda lolos, karena Range ikut
     mengembalikan kotak elemen `span`. Kini yang diukur kotak huruf node
     teks. Dibuktikan dengan menyuntikkan `text-align: center`: 16/36,
     semua beranda gagal.
- **Produksi:** potret salinan produksi 28/28 identik.
  `uji_pipeline.py --hanya V`: 10 lulus (V1 23/23).

## Catatan (tidak diminta, belum diubah)
- Kartu hasil kecamatan: "Kec. X" tampil sebagai kapsul di dalam kapsul
  wilayah, karena gaya `span` di `.lokasi` ikut mengenainya.
- Beranda 1366 px dengan wilayah terpilih: kolom kata kunci menyempit karena
  dropdown kecamatan ikut di baris yang sama (form maksimal 760 px).
