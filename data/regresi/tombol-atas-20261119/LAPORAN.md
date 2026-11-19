# Tombol "Kembali ke atas" (19 Nov 2026)

## Perubahan
- `base.html`: `<button class="ke-atas" aria-label="Kembali ke atas" hidden>` (ikon SVG,
  `aria-hidden`) + `js/ke-atas.js`, di SEMUA halaman.
- `ke-atas.js`:
  - tombol tampil kalau `scrollY > innerHeight` (lebih dari 1 layar);
  - klik = `scrollTo` halus; dengan `prefers-reduced-motion: reduce` langsung lompat;
  - fokus pindah ke kop sesudah klik.
- `style.css`:
  - bulat 44x44 px, pojok kanan bawah (kanan 6, bawah 16), latar `--kop-bps`
    (#002B6A), hover biru tua, cincin fokus kuning;
  - **di <= 960 px**: kartu, kotak info kecamatan, dan pita wilayah diberi ruang kanan
    38 px; notice di kaki diberi ruang 48 px kiri-kanan. Tujuannya supaya tombol hanya
    menimpa ruang kosong, bukan isi.

## Uji (database uji, `run.py --db-uji --port 5001`)
Alat: `uji_tombol_atas.py` (Playwright, Chrome terpasang), hasil di `hasil_uji.txt`.
- **Lebar 360, 390, 440, 768, 1366 x 2 halaman** (`?q=penduduk`; Tanah Laut + centang
  kecamatan), ditambah kurangi animasi: **15/15 lulus**.
- Pemeriksaannya:
  - tersembunyi di atas dan pada 0,5 layar; tampil pada 1,2 layar;
  - >= 44x44, `<button>` dengan label aksesibel, warna kop;
  - **0 irisan** dengan Buka PDF, judul, label, cuplikan, skor, tautan kotak info/pita,
    dan teks notice. Diperiksa di SETIAP posisi gulir (langkah 37 px, 238-458 posisi
    per halaman);
  - klik: halus (di tengah animasi 0 < y < awal), sampai 0, fokus ke kop;
  - kurangi animasi: y = 0 pada bingkai berikutnya;
  - Enter dan Spasi dari keyboard: ke atas.
- **Halaman pendek** (beranda, `?w=6301`, login admin, kueri tanpa hasil): tombol ada,
  tetapi tidak pernah tampil.
- Uji responsif lama (kotak centang kecamatan): **36/36**.
- Tangkapan layar: `responsif/<lebar>-<halaman>.png`, sekitar 2 layar ke bawah, tombol
  tampil.

**Validasi alat** (`validasi_alat.txt`): enam cacat disuntikkan, semuanya tertangkap.
- Ruang kanan dihapus: irisan dengan isi kartu di 360 px (di 1366 memang ada margin).
- Tombol selalu tampil: A gagal.
- 40 px: B gagal.
- Warna abu-abu: B gagal.
- `scrollTo` dipaksa lompat: D gagal.
- Kurangi animasi diabaikan: E gagal.

Jebakan alat: pemeriksaan pertama melaporkan tabrakan dengan `.notice`. Kotak elemen
`<p>` itu selebar layar, padahal teksnya di tengah. Pemeriksaan sekarang memakai kotak
huruf teks (Range), seperti pada uji kotak centang.

## Bukti selain tombol tidak ada yang berubah
Alat: `tests/potret_tampilan.py banding --buang-tombol-atas`. Blok tombol + skrip
dibuang PERSIS, dan halaman HTML yang tidak memuatnya tepat 1 kali ditolak. Hasil di
`bukti_potret.txt`:

| Potret | Dibanding dengan | Hasil |
|---|---|---|
| Produksi (log mati) | sesudah perbaikan `&nbsp;`, tanpa tombol | **28/28 identik** (tanpa membuang tombol: 23 halaman HTML berbeda) |
| Database uji | sesudah perbaikan `&nbsp;` | 28/28 identik |
| Salinan produksi | potret 19 Nov pagi (`potret-salinan-pubkec.json`) | 28/28 identik |

`uji_pipeline.py --hanya V`: 11 lulus, 0 gagal (Z2: produksi tidak berubah).
Perubahan CSS di <= 960 px (ruang kanan) tidak tertangkap potret HTML. Dampaknya hanya
tata letak, dan sudah tercakup uji Playwright di atas dan uji responsif lama.
