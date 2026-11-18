# Perbaikan parser Daftar untuk kecamatan: pola 2, 3, 1 (18 Nov 2026)

Rancangan: `rancangan-kecamatan-20261118.md`, disetujui dengan dua syarat:
urutan pola 2 -> 3 -> 1, dan pengaman tingkat halaman untuk pola 1.
Produksi tidak disentuh. Database uji juga belum ditulis (hanya uji kering).

| Commit | Isi |
|---|---|
| `7481e19` | Pola 2: `_rapikan_nomor_halaman`, nomor halaman yang ditimpa leader |
| `390f3d4` | Pola 3: digit di dalam kata leader, ditambah buang "." sendirian |
| `4d5c7c5` | Pola 1: `_gabung_nomor_terbelah`, aktif hanya kalau >= 3 baris berpola sama di satu halaman |
| `5419397` | `uji_pipeline.py` bagian I: 15 kasus (K1-K3, termasuk 2 kasus "aman") |

## Alat (folder `kecamatan-parser-20261118/`)
- `uji_kering.py`: mengekstrak tanpa DB dan membandingkan per kunci
  `(tipe, nomor)`. Divalidasi dulu: kode lama pada 3 publikasi identik dengan
  database uji.
- `jejak_rapikan.py`: mencatat kata yang dirapikan beserta aturannya. Dipakai
  untuk membuktikan bahwa publikasi yang berubah memang punya kata yang dirapikan.
- `sampel_baru.py`: sampel acak entri baru/berubah, dengan bukti baris Daftar
  dan folio halaman yang dituju tombol PDF.
- Kasus bagian I diperiksa terbalik: tanpa kedua fungsi itu, K1/K2/K3 positif
  SALAH dan kasus aman tetap OK.

## Uji kering 38 publikasi (11 Tanah Laut 2025, 20 Banjar 2026, 7 Balangan 2025)

| Tahap | Publikasi berubah | Kunci hilang | Kunci baru | Halaman cetak terisi |
|---|---|---|---|---|
| DB uji (awal) | - | - | - | 1.197 / 2.788 |
| + pola 2 | 22 | 0 | 44 | 2.010 |
| + pola 3 | 21 (dari pola 2) | 0 | 3 | 2.067 |
| + pola 1 | 11 (dari pola 3) | 49 | 20 | **2.662 / 2.843** |

Penjelasan tiap tahap:
- **Pola 2:** 20 Banjar 2026 dan 2 Balangan 2025.
  - Entri isi tanpa nomor +35, karena Daftar Isi yang dulu menggumpal
    ("2 Pemerintahan .1 1. 3 Penduduk ...") kini terpecah per bab.
  - 44 kunci baru adalah entri yang dulu tertelan blok gabungan.
- **Pola 3:**
  - Tebing Tinggi 2025: blok tanpa nomor 15 -> 2, halaman cetak 19 -> 48.
  - Banjar ikut berubah karena kata halaman yang ditimpa leader diikuti "."
    (jejak: `hal_ditimpa+buang_titik`).
  - Sisa blok di Batu Mandi 2025 berasal dari sumber: Daftarnya tercetak
    "Error! Bookmark not defined.", tanpa nomor halaman.
- **Pola 1:** hanya Tanah Laut 2025.
  - 49 kunci hilang semuanya **judul seksi** ("Pendidikan", "Kesehatan",
    "Wilayah Administratif" ...): sumber daftar, tanpa halaman cetak maupun
    fisik, dan sub-nomornya ada. Aturan C2 membuangnya, sama seperti di semua
    publikasi bernomor-sebaris lain. Tidak ada tabel yang hilang.
  - **Memburuk: 27 pasangan daftar+badan bergeser satu halaman** (2 -> 29 dari
    1.543 'keduanya'; >1 halaman 33 -> 35). Sebabnya penomoran Daftar Tabel ≠
    penomoran keterangan badan di sumber (Tanah Laut 2025 bab 2.1 dan 4.4).
    Contoh Jorong: Daftar "4.4.6 Agama" hal. 67 (fisik 91), sedangkan badan
    mencetak "Tabel 4.4.6" = Nikah di fisik 92. Sesudah digabung per kunci,
    judul/halaman cetak berasal dari tabel A dan tombol menuju tabel B. Dulu
    entri ini hanya dari badan, dengan judul dan tombol yang konsisten.

## Sampel manual 30 entri baru/berubah (seed 20261118, populasi 1.424)

Keluaran: `sampel_baru_20261118.txt`. **27/30 benar** (nomor, judul,
halaman cetak, tombol PDF). Ketiga yang salah berasal dari kesalahan
penomoran sumber:
- #13 Pelaihari 2025 2.1.15: judul Daftar "Karang Taruna" hal. 34, tombol ke
  badan "Tabel 2.1.15 Desa Telaga" (folio 35).
- #29 Pelaihari 2025 2.1.9: judul badan "Sarang Halang", halaman cetak 26 dari
  Daftar 2.1.9 "Tampang". Tombol benar.
- #19 Cintapuri Darussalam 2026 1.1: Banjar 2026 mencetak "1.1" untuk
  beberapa tabel bab 1. "Luas Daerah" hal. 5 bertombol ke tabel iklim (folio 7).
- Catatan #25: Sambung Makmur 2026 memberi nomor "3.1" pada semua tabel bab 5-7
  di Daftar dan di badan. Entrinya benar, tetapi dedup per kunci hanya
  menyimpan satu entri.

## Regresi penuh: MENUNGGU OCR selesai
Belum dijalankan, sesuai permintaan. Rencananya:
- 306 publikasi produksi di database uji: `perbarui.py --db-uji --lokal --paksa`;
- IPM HSU: ekstraksi kering;
- 312 kecamatan: pemuat terarah;
- `uji_pipeline.py` penuh.

Syarat: 0 kunci bernomor hilang di 307 publikasi produksi, dan setiap
publikasi yang berubah harus punya kata yang dirapikan menurut
`jejak_rapikan.py`.

## Utang teknis (keputusan pemilik project: dicatat)
- Folio romawi Daftar Isi Balangan yang bercampur titik ("v i.i.i."): entri
  isi gabungan tetap ada.
- Nomor bab/tabel salah cetak di sumber Banjar 2026 ("1.1" untuk 3.1/7.1,
  "3.1" untuk semua tabel Sambung Makmur), dan nomor halaman yang melayang di
  tengah baris.
- Perkiraan halaman fisik entri kepala bab ("tabel 1 Geografi", sampel mutu #29).
- BARU: penomoran Daftar ≠ badan di Tanah Laut 2025 (27 pasangan, lihat pola 1).
