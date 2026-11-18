# Perbaikan parser Daftar untuk kecamatan: pola 2, 3, 1 (18 Nov 2026)

Rancangan: `rancangan-kecamatan-20261118.md`, disetujui dengan dua syarat:
urutan pola 2 -> 3 -> 1, dan pengaman tingkat halaman untuk pola 1.
Produksi tidak disentuh. Database uji juga belum ditulis (hanya uji kering).

**KEPUTUSAN 18 Nov 2026: pola 1 DIBATALKAN (revert `4d5c7c5`); pola 2 dan 3
dipertahankan.** Alasan pemilik project: sebelum pola 1, tombol PDF tabel
Tanah Laut 2025 sudah benar dari badan dokumen. Pola 1 hanya menambah halaman
cetak, tetapi membuat 27 tombol meleset, dan bagi petugas tombol yang benar
lebih penting. Penomoran Daftar ≠ badan di Tanah Laut 2025 dicatat sebagai
utang teknis. Bagian pola 1 di bawah disimpan sebagai bukti
(`banding-pola1.txt` dipulihkan sesudah revert). Hasil yang berlaku = baris
"+ pola 3".

| Commit | Isi |
|---|---|
| `7481e19` | Pola 2: `_rapikan_nomor_halaman`, nomor halaman yang ditimpa leader |
| `390f3d4` | Pola 3: digit di dalam kata leader, ditambah buang "." sendirian |
| `4d5c7c5` | Pola 1: `_gabung_nomor_terbelah`; **DIBATALKAN lewat revert** |
| `5419397` | `uji_pipeline.py` bagian I: 15 kasus. Sesudah revert jadi 13 (kasus K1 dibuang) |

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
- Penomoran Daftar ≠ badan di Tanah Laut 2025 (27 pasangan; alasan pola 1 dibatalkan). Tabel Tanah Laut 2025 tetap tanpa halaman cetak, tombol dari badan benar.

## Regresi penuh di database uji (18 Nov 2026, sesudah OCR selesai)

Parser = `390f3d4` (pola 2 + 3; pola 1 dibatalkan). Produksi: CHECKSUM
`entri_dokumen`, `publikasi`, `versi_data`, `log_pencarian` awal = akhir.

1. **19 publikasi OCR kecamatan sisa** dimuat lewat `muat_ocr_terarah.py
   --sasaran uji` (cache lengkap, 0 OCR baru), masing-masing 42-73 entri, dalam
   23 detik.
2. **`perbarui.py --db-uji --lokal --paksa`** dijalankan 10.15-12.07, kode keluar 0
   (`regresi_perbarui_log.txt`). `--lokal --paksa` mengambil daftar dari
   database (`susun_rencana`), jadi 312 kecamatan ikut diekstrak ulang dengan
   fungsi yang sama. Pemuat terarah terpisah tidak diperlukan.
   - Database uji kini: 618 publikasi, 44.455 entri, 34 publikasi OCR.
   - Pembanding: `potret_awal.json` (sebelum langkah 1) vs `potret_akhir.json`,
     per kunci (`analisis_regresi.py`).

| Kelompok | Publikasi | Berubah | Kunci hilang | Kunci baru | Halaman cetak (publikasi berubah) |
|---|---|---|---|---|---|
| Produksi | 306 | 5 | **0** | 0 | 194 -> 208 |
| Kecamatan (punya entri di awal) | 294 | 25 | 0 | 78 | 682 -> 1.656 |

- **Bukti produksi:** kelima publikasi diekstrak ulang dengan
  `_rapikan_nomor_halaman` DIMATIKAN, dan hasilnya identik dengan potret awal
  (`bukti_tanpa_rapikan.txt`: tidak terjelaskan 0). Kata yang dirapikan ada di
  `jejak_produksi.txt`. Semuanya Daftar Isi/Lampiran, dan semuanya membaik:
  - SHK Komoditas Terpilih: "BAB I Pendahuluan 1…1 BAB II …" terpecah, hal. 11/15;
  - IHK Provinsi: lampiran 1-5 mendapat halaman cetak 24-28 (fisik 39-43,
    selisih tetap 15);
  - PDRB Banjar (dua edisi): subbab 2.2-2.6 terpecah, halaman 18/21/25/32;
  - PDRB Tabalong: "DAFTAR PUSTAKA .1.33 LAMPIRAN" terpecah, hal. 133.
- **Kecamatan:**
  - 22 dari 38 publikasi terdampak, sama dengan uji kering;
  - Halong 2026 dan Tebing Tinggi 2026 (Balangan 2026) identik dengan awal
    kalau pola dimatikan (`bukti_tanpa_rapikan_kec_luar38.txt`);
  - Tapin Utara 2025 berubah karena dimuat dengan OCR (langkah 1).
  - 18 publikasi OCR yang dulu 0 entri tidak ada di potret awal.
  - 26/26 publikasi OCR identik antara pemuatan terarah dan run `--paksa`.
3. **IPM HSU** (`a21060d6`, hanya di produksi): ekstraksi kering identik dengan
   produksi, 42 entri, urutan dan isi sama (`ipm_hsu_kering.txt`).

## Sampel 10 entri OCR kecamatan (seed 20261118, populasi 1.374 di 26 publikasi)

Bukti berupa GAMBAR render halaman (PDF tanpa teks): potongan baris Daftar dan
halaman yang dituju tombol PDF (`sampel_ocr.py`, `sampel_ocr_20261118.txt`).
- **9/10 benar seluruhnya, 10/10 tombol PDF benar.** Salah baca OCR ringan
  (";" untuk ",", "Desa'" untuk "Desa¹", "Lainnyal" untuk "Lainnya/") tidak
  dihitung salah.
- #6 Barabai 2026 tabel 7.1: judul berawalan sampah "COOPERATIVE, AND TRADE ops
  g0-" (kop bab + watermark). Nomor, halaman, dan tombol benar.
- #10 Hatungun "tabel 4.4 Sosial Lainnya" adalah kepala seksi dari Daftar,
  bukan tabel. Halaman dan tombolnya benar.

## uji_pipeline.py penuh (18 Nov 2026)
**94 lulus, 0 gagal, 0 dilewati**, 2.342 detik (`../uji-pipeline-20261118.txt`).
- Termasuk I1 13/13, Z1 (database uji dipulihkan, CHECKSUM sama), dan Z2
  (produksi tidak berubah).
- Domain uji 6305 kini memuat 24 kecamatan Tapin (P1 = 41 publikasi), dan C1
  memeriksa 16 publikasi OCR.
