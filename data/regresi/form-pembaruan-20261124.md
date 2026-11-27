# Formulir pilihan penarikan di /admin/perbarui (24 Nov 2026)

Masukan mentor. Dikerjakan dan diuji di **database uji** saja. Produksi tidak
ditulis, tidak di-push, dan tidak ada penarikan sungguhan ke BPS: semua uji
memakai WebAPI tiruan di 127.0.0.1. Bahan dan alat ada di folder
`form-pembaruan-20261124/`.

## Yang dibuat

| # | Permintaan | Hasil |
|---|---|---|
| 1a | Centang wilayah (provinsi + 13 kab/kota aktif), pilih/hapus semua | Ada. Pilih/hapus semua lewat `js/form-pembaruan.js`, tombolnya tersembunyi tanpa JS |
| 1b | Jenis: Publikasi kabupaten/kota, Kecamatan Dalam Angka (`pola_kecamatan`) | Ada. Kelompok jenis nonaktif (JS) kalau tidak ada kab/kota dicentang |
| 1c | Tahun rilis Dari/Sampai, `tahun_min_pilihan` .. tahun berjalan | Ada. Bawaan tahun lalu - tahun ini |
| 1d | `tahun_min_pilihan` di `data/wilayah.json` | `"tahun_min_pilihan": 2020` + catatan |
| 1e | Tombol **Cek dulu** | `perbarui.py --cek-dulu`, hasil tabel per wilayah + perkiraan waktu/ukuran + kotak "Penarikan besar" |
| 1f | Validasi di server | `pilihan_pembaruan.periksa`, dipakai route DAN `perbarui.py`; ditolak = HTTP 400 + pesan, tidak ada proses |
| 2 | `--tahun-maks`, `--wilayah`, `--jenis` di perbarui.py | Ada; formulir menjalankan perbarui.py dengan argumen yang sama (jalur .bat) |
| 3 | Kunci, jeda 1 detik, tidak menghapus, ringkasan mencatat pilihan | Tetap; `pilihan` di `pembaruan_terakhir.json` + baris "Pilihan: ..." di halaman |
| 4 | Sampul ikut revisi, atomik, gagal = sampul lama | `sampul.perbarui`; dipanggil `proses_sampul` hanya untuk publikasi yang PDF-nya diunduh ulang karena updt_date berubah |

### Rancangan singkat

- **Satu aturan, dua jalan masuk.** `app/services/pilihan_pembaruan.py`
  memeriksa pilihan dan menerjemahkannya ke argumen perbarui.py
  (`Pilihan.argumen()`). Bagian pilihan yang sama dengan bawaan **tidak**
  ditulis sebagai argumen, jadi formulir bawaan menjalankan perintah yang persis
  sama dengan tombol lama (`perbarui.py` tanpa argumen). POST tanpa medan
  `formulir` (tombol lama, uji W1) = bawaan.
- **Saringan.** Daftar API disaring tahun -> `kecualikan_judul` -> jenis. Kalau
  jenis/tahun bukan bawaan, data lama di database juga disaring dengan aturan
  yang sama (`cocok_pilihan`: `tahun_terbit` + judul), di empat tempat: rencana
  kerja (`susun_rencana(pilih=)`, termasuk `--paksa`/`--lokal`), sampul,
  laporan "tidak lagi di daftar API", dan penjaga "0 lolos padahal database
  berisi". Tanpa ini, misalnya pilihan "hanya kecamatan" akan melaporkan semua
  publikasi kabupaten sebagai "tidak lagi di daftar", dan tahun tanpa publikasi
  akan dianggap kegagalan penarikan.
- **Wilayah terhalang** (`--hanya-periksa`) tetap dihitung dari SEMUA wilayah
  aktif, lalu diambil yang terpilih.
- **`--cek-dulu`**: daftar WebAPI (berhenti lebih awal seperti pembaruan, jeda
  1 detik) + membaca database. Tidak mengunduh PDF/sampul, tidak menulis
  database (tanpa `pastikan_skema`), tetapi tetap memegang kunci pembaruan.
  Hasil di `data/cek_pembaruan.json` (`-uji` untuk `--db-uji`, di-gitignore).
  Kategori: baru, direvisi (updt_date), baca ulang (PDF hilang/rusak/berubah),
  tidak berubah; aturannya meniru `simpan_metadata` + `susun_rencana`.
  Perkiraan: daftar = waktu cek itu sendiri; unduh 5 MB/detik (terukur kantor)
  + jeda; baca PDF 1,8 detik/MB (terukur 9 Nov); sampul 1,5 detik/publikasi.
  "Besar" = >= 50 publikasi, >= 1 GB, atau >= 1 jam. Catatan tetap: OCR belum
  dihitung; PDF rilis sebelum 2025 belum teruji mutunya.
- **Sampul ikut revisi.** `proses_tugas` mencatat publikasi yang PDF-nya
  berhasil diunduh ulang karena "updt_date berubah" (dan pernah diproses).
  `sampul.perbarui`: unduh -> `.part` -> `os.replace` (sudah begitu sejak 19
  Nov; `_tulis_atomik` kini juga menghapus `.part` kalau penulisan gagal).
  Gagal -> berkas resmi tidak disentuh ("lama_dipertahankan"); kalau belum
  punya sampul resmi, cadangan dibuat ulang dari halaman 1 PDF yang baru.

### Perubahan perilaku yang perlu diketahui

1. **Sampul publikasi direvisi diunduh ulang** pada pembaruan tanpa argumen.
   Ini permintaan nomor 4, dan satu-satunya beda terhadap kode sebelumnya
   (dibuktikan Q1).
2. `perbarui.py` dengan argumen salah kini keluar **kode 1**, bukan 2 bawaan
   argparse. Kode 2 dibaca `perbarui-data.bat` sebagai "pembaruan lain sedang
   berjalan" - menyesatkan.
3. `--tahun-min` di bawah `tahun_min_pilihan` (2020) atau di atas tahun ini kini
   **ditolak**; dulu diterima (dan tahun masa depan menghasilkan "0 lolos" =
   gagal per wilayah).
4. `perbarui-data.bat`: sesudah `--cek-dulu` penutupnya `CEK SELESAI - tidak ada
   PDF yang diunduh, database tidak diubah`, bukan `PEMBARUAN SELESAI.`. Kode
   keluar disimpan ke variabel dulu; urutan pemeriksaan sama (3/2/1/0).
5. Halaman admin: tabel ringkasan per wilayah kini dibungkus `.gulir-tabel`.
   Di layar 375 px tabel lama melebarkan halaman ke 446 px; sekarang bergulir di
   kotaknya sendiri. (`/admin/log` juga melebar, 559 px; tidak disentuh.)

## Uji

Semua tanpa menghubungi BPS: WebAPI tiruan di 127.0.0.1, proxy mati untuk
alamat luar (U4).

### `tests/uji_pipeline.py` bagian Q (baru) dan A6-A7 (baru)

Wilayah aktif di salinan: 6305 Tapin (17 publikasi kab/kota + 24 Kecamatan
Dalam Angka) dan 6300 provinsi (79; PDF hardlink, tidak diunduh).

| Uji | Isi | Hasil |
|---|---|---|
| Q0 | tanpa pilihan, tanpa perubahan: 0 PDF, 0 sampul; ringkasan mencatat pilihan bawaan | lulus |
| Q1 | **tanpa pilihan = kode sebelumnya**: kode `git HEAD` (saat itu = sebelum formulir; kini commit tetap `4c57072`, lihat "Lanjutan") dan kode baru dijalankan pada keadaan yang sama (1 publikasi baru, 1 direvisi). Permintaan daftar+PDF sama persis berikut urutannya (15/15), database sama per kunci, ringkasan inti sama, keluaran layar sama (angka/waktu dan baris sampul diabaikan). Satu-satunya beda: sampul publikasi direvisi diunduh ulang, dan kunci `pilihan` di ringkasan | 4/4 lulus |
| Q2a | `--wilayah 6305 --jenis kecamatan`: hanya kecamatan direvisi; kab/kota dan provinsi tidak disentuh, metadata pun tidak; daftar 6300 tidak diminta; "tidak lagi di daftar" kosong | lulus |
| Q2b | `--jenis kabkota` | lulus |
| Q2c | `--wilayah 6300 --tahun-min 2025 --tahun-maks 2025`: rilis 2026 tidak disentuh | lulus |
| Q2d | tahun tanpa publikasi (2024): bukan kegagalan, data tidak berubah | lulus |
| Q2e | lalu tanpa pilihan: sisa revisi diproses | lulus |
| Q2 | jeda antar-permintaan >= 1 detik (1,00-1,02) | lulus |
| Q2f | `--lokal --paksa --wilayah 6305 --jenis kecamatan`: tepat 24 dibaca ulang, 0 permintaan | lulus |
| Q3 | 11 pilihan tidak sah di perbarui.py: exit 1 + DITOLAK, 0 permintaan, DB dan ringkasan tidak berubah | lulus |
| Q4 | formulir: 9 kiriman tidak sah -> HTTP 400 + pesan, tidak ada proses; bawaan = tanpa argumen; tahun 2020..2026; "Cek dulu" dari formulir sampai ke perbarui.py, hasil tampil, formulir terisi; hanya daftar 6305, DB tidak berubah | 5/5 lulus |
| Q5 | `--cek-dulu`: baru 1 / direvisi 1 / baca ulang 1 / tidak berubah 39 / unduh 3; `--jenis kabkota` tidak menghitung kecamatan; 0 PDF/sampul, DB tidak berubah; ambang peringatan besar | 4/4 lulus |
| Q6 | terkunci: cek dan pembaruan berpilihan exit 2, 0 permintaan | lulus |
| Q7 | `perbarui-data.bat` sungguhan: koma di `--wilayah 6305,6300` sampai utuh, penutup `CEK SELESAI`; pilihan tidak sah -> `PEMBARUAN GAGAL` | 2/2 lulus di run penuh (gagal di run pertama, lihat di bawah) |
| A6 | revisi berhasil: sampul resmi ditimpa (byte = sampul baru), tanpa `.part`; sampul publikasi lain tidak diminta, mtime tetap | 2/2 lulus |
| A7 | revisi, unduhan sampul gagal (HTTP 400 dan bukan gambar): sampul lama tetap (byte sama), `lama_dipertahankan`, PDF tetap diproses, status domain `sukses` | lulus |

**Q7 gagal di run pertama** (`uji-pipeline-QA-1.txt`: 46 lulus, 1 gagal).
Penyebab: `.bat` memakai `find`, dan di PATH lingkungan uji `find` milik Git
(`/usr/bin/find`) ada lebih dulu; perintah itu tidak mengenal `/i` sehingga
`--cek-dulu` tidak terdeteksi. Diperbaiki dengan jalur lengkap
`%SystemRoot%\System32\find.exe`, dibuktikan dengan PATH yang sama (Git di
depan): terdeteksi / tidak terdeteksi sesuai argumen. Run penuh di bawah
memakai perbaikan ini.

### Run penuh `uji_pipeline.py` (semua bagian)

**`--kamus-head`: 140 lulus, 0 gagal, 0 dilewati, kode keluar 0, 3.299 detik**
(`uji-pipeline-penuh.txt`). Termasuk Q (26 uji, Q7 lulus dengan perbaikan
`find.exe`), A1-A7, W1 (tombol lama tanpa formulir), R5 (halaman admin semua
status ringkasan), Z1 (database uji pulih), Z2 (produksi tidak berubah).

Run penuh pertama, **tanpa** `--kamus-head` (`uji-pipeline-penuh-kamus-kerja.txt`):
96 lulus, 5 gagal. Penyebabnya dua, keduanya sudah ditangani:

1. **P2, C2 (2x), O1: bukan dari kode ini.** `data/kamus_sinonim.json` di
   working tree punya perubahan pemilik project yang belum di-commit dan belum
   diterapkan ke database uji (kelompok `p0` = "persentase penduduk miskin").
   Salinan uji menyalin kamus itu, sehingga publikasi yang diekstrak ulang
   mendapat `teks_ternormalisasi` baru, berbeda dari isi database uji. Bukti:
   ketiga publikasi yang berbeda (`1d520ab0` Tapin DA 2026, `37274162` IKR
   Tapin 2025, `42732c61` Tapin DA 2025) adalah tepat dan hanya publikasi
   Tapin yang judul entrinya memuat "persentase ... penduduk miskin". Dengan
   kamus versi HEAD, keempatnya lulus. Kamus pemilik tidak disentuh dan tidak
   ikut di-commit. Opsi baru `--kamus-head` di `uji_pipeline.py` untuk keadaan
   ini; tanpa opsi, perilakunya tetap seperti dulu. **Diganti sore harinya:**
   kamus di-commit dan ekspektasi uji disesuaikan (bagian N, lihat "Lanjutan").
2. **Galat di bagian Q (bug uji saya):** domain publikasi ditebak dari
   `per_id`, sehingga publikasi uji tambahan bagian B dianggap provinsi.
   Diperbaiki: domain dibaca dari database; publikasi tanpa PDF lokal tidak
   dipakai sebagai sampel; sisa gangguan tiruan dari bagian lain dikosongkan
   di awal Q (Q0 membuktikan keadaan bersih).

Waktu run penuh kini ±55 menit (dulu ±37); bagian Q ±8 menit, termasuk
mengunduh 120 sampul tiruan dengan jeda 1 detik.

## Halaman pencarian tidak berubah

Template halaman pencarian dan `base.html` tidak disentuh. Yang dibagi dengan
halaman pencarian hanya `style.css`; aturan barunya semua diawali kelas khusus
admin (`.form-pembaruan`, `.hasil-cek`, `.gulir-tabel`).

1. **HTML**: `tests/potret_tampilan.py` (28 URL: beranda, 21 kueri, 5 awalan
   saran) di database uji, sebelum perubahan vs sesudah: **IDENTIK 28/28**
   byte demi byte (`potret-sebelum.json`, `potret-sesudah.json`, tidak
   di-commit).
2. **Piksel** (CSS): 6 halaman x 2 lebar (1280, 375), dirender Chrome lewat
   Playwright di server yang sama, "sebelum" = CSS versi HEAD (disajikan
   lewat intersepsi request), "sesudah" = CSS baru: **12/12 identik piksel demi
   piksel** (`banding-layar-sebelum-vs-sesudah.txt`).
   - Alatnya diuji dulu: dua potret dari kode yang sama = 12/12 identik
     (`banding-layar-sebelum-vs-sebelum2.txt`); CSS yang diubah 1 px = 12/12
     BEDA (`banding-layar-uji-alat.txt`).
   - **Jebakan alat** yang ditemukan dan ditangani: sampul JPEG dirender
     berbeda sampai 9/255 antara dua potret kode yang sama, dan fokus
     autofocus kotak cari kadang belum terpasang saat dipotret. Potret karena
     itu membuat isi gambar transparan (kotaknya tetap dibandingkan) dan
     melepas fokus. Lihat `tangkap_pencarian.py`.

Membuat ulang: jalankan `server_tangkapan.py 5011`, lalu
`tangkap_pencarian.py 5011 <folder> [style-HEAD.css]` dan `banding_layar.py`.

## Tangkapan layar formulir

`form-pembaruan-20261124/layar-formulir/`, lebar 1280 (desktop) dan 375
(ponsel). Server = database uji + **WebAPI tiruan** (`tiruan_tangkapan.py`,
dibangun dari database uji, dengan simulasi: Tanah Laut 3 publikasi rekaan
rilis 2024 + 2 direvisi; semua publikasi provinsi direvisi). Sandi admin
sementara hanya di memori server; `.env` tidak dibuka.

| Berkas | Isi |
|---|---|
| `*-1-bawaan` | formulir bawaan (semua wilayah, kedua jenis, 2025-2026) |
| `*-2-hanya-provinsi` | hanya provinsi dicentang: kelompok jenis nonaktif |
| `*-3-ditolak` | tanpa wilayah + Dari 2026 > Sampai 2024: HTTP 400, dua pesan |
| `*-4-cek-tanah-laut` | Cek dulu, Tanah Laut 2024-2026: 3 baru, 2 direvisi, 68 MB, ±3 menit; formulir terisi pilihan yang sama |
| `*-5-cek-besar` | Cek dulu, semua wilayah: 81 publikasi, ±758 MB, kotak "Penarikan besar" |

`catatan.json`: 10/10 potret tanpa gulir mendatar (sebelum tabel ringkasan
dibungkus: 446 px di layar 375). Database uji sebelum = sesudah dua kali cek
lewat UI (`checksum-uji-*-cek-ui.json`).

## CHECKSUM

- **Produksi**: `uji_pipeline.py` Z2 (CHECKSUM TABLE awal = akhir) lulus di
  run Q+A dan di kedua run penuh. Tambahan: `checksum-produksi-awal.json`
  (diambil sebelum fase uji) = `checksum-produksi-akhir.json` (sesudah semua
  uji), 6/6 tabel, jumlah baris + CHECKSUM. Aplikasi produksi tidak
  berjalan selama pengerjaan (port 5000 kosong); semua aplikasi dan skrip
  memakai `KonfigurasiUji` / `--db-uji`.
- **Database uji**: dipulihkan dari dump di akhir tiap run uji (Z1 lulus).

## Belum dikerjakan / catatan

- Tarik sungguhan ke BPS: lihat "Lanjutan" di bawah (database uji saja).
- Laju unduhan di perkiraan (5 MB/detik) dari pengukuran kantor; waktu
  "memeriksa daftar" pada pilihan tahun lama belum pernah diukur (halaman
  daftar yang dibaca bertambah sampai tahun tertua terpilih).
- Ringkasan dan hasil cek mencatat pilihan; log pencarian tidak berubah.
- Kode ini belum di-push dan belum menyentuh produksi.

## Lanjutan 24 Nov 2026 (sore)

### 1. Kamus `p0` di-commit; ekspektasi uji disesuaikan

`"p0": ["p0", "persentase penduduk miskin"]` (arahan mentor, P0 = istilah
resmi BPS) di-commit. Akhir baris dirapikan ke format repo: LF, tanpa baris
baru di akhir, byte demi byte sama dengan keluaran `_tulis_kamus` di
/admin/kamus (berkas kerja sempat CRLF). Diff kamus: 4 baris.

**Kenapa P2, C2 (2x), dan O1 dulu gagal, dan kenapa ekspektasi barunya benar.**
- Yang diuji keempatnya: "ekstraksi ulang menghasilkan isi yang sama dengan
  sebelumnya, per kunci, termasuk `teks_ternormalisasi`".
- "Sebelumnya" = potret database uji, yang teksnya masih dinormalkan dengan
  kamus lama. Pipeline mengekstrak ulang dengan kamus baru, sehingga frasa
  "persentase duduk miskin" (sesudah stemming) menjadi "p0".
- Jadi isi lama bukan lagi jawaban yang benar. Jawaban yang benar = isi lama
  dengan kamus sekarang, dan itulah yang dihasilkan pipeline maupun tombol
  "Terapkan ke data". Produksi sudah dalam keadaan itu: diperiksa dengan hanya
  membaca, 0 teks produksi berbeda dari kamus sekarang (`cek_kamus_p0.py`).
  Database uji belum: 47 publikasi, 67 entri, dan 1 teks publikasi berbeda.

Perubahan uji (`tests/uji_pipeline.py`):
- **Bagian N (baru, selalu jalan sebelum potret s0):** kamus salinan diterapkan
  ke database uji lewat `normalisasi_data.jalankan()`, fungsi tombol "Terapkan
  ke data". **N1** mewajibkan:
  - hanya `teks_ternormalisasi` yang berubah, semua kolom lain identik;
  - penerapan kedua mengubah 0 (idempoten).
  Hasilnya: 67 entri, 1 publikasi, 47 publikasi terkena; di domain uji
  `1d520ab0`, `37274162`, `42732c61`, persis tiga publikasi Tapin yang dulu
  gagal. Database uji tetap dipulihkan dari dump awal di Z1.
- **P2, C2, O1 tidak diubah:** tetap identik per kunci, termasuk teks.
  Ekspektasinya (s0) kini isi database uji dengan kamus yang sama dengan
  pipeline.
- **P2b (baru, lebih ketat):** ketiga publikasi domain uji yang terkena kamus
  baru harus berteks = s0 dan ≠ teks lama. Jadi uji juga gagal kalau pipeline
  diam-diam memakai kamus lama.
- `--kamus-head` tetap ada sebagai opsi, tetapi tidak diperlukan lagi.
- `--hanya P` dengan kamus sekarang: 13 lulus, 0 gagal (N1, P1-P4, P2b, Z1-Z3).

### 2. CLAUDE.md: jadwal

Presentasi sudah 23 Nov 2026; pembekuan diundur ke **Jumat 27 Nov 2026**.

### 3. Tarik kecil ke DATABASE UJI: Tanah Laut, rilis 2024

Jaringan "BPS - Pegawai", webapi.bps.go.id -> 203.123.60.70. Bukti di
`tarik-kecil-20261124/`.

| | Cek dulu | Tarik |
|---|---|---|
| Perintah | `perbarui.py --db-uji --wilayah 6301 --tahun-min 2024 --tahun-maks 2024 --cek-dulu` | sama, tanpa `--cek-dulu` |
| Publikasi | 27 baru, 0 direvisi | 27 diunduh, 27 diproses, **0 gagal**, kode keluar 0 |
| Ukuran | ~212 MB (field size API) | 221,7 MB PDF + 4,0 MB sampul (27 resmi, 0 cadangan, 0 gagal) |
| Waktu | perkiraan ~9 menit; cek 24 detik | **765 detik (12,8 menit)**: daftar 14,8 d, unduh 76,9 d (2.818 KB/detik, putus 0), ekstraksi 583,6 d, sampul 58 d |
| OCR | - | **0 publikasi perlu OCR** (semua berlapis teks) |

- Hasil: 27 publikasi (11 Kecamatan Dalam Angka), **3.726 entri**. Database
  uji: 618 -> 645 publikasi, 44.455 -> 48.181 entri.
- "Perlu diperiksa manual" (2):
  - IKR 2024: 8/8 entri tanpa halaman cetak;
  - Statistik Daerah 2024: 19/53, karena Daftarnya bertulisan rapat tanpa
    spasi ("Gambar14.3 JumlahKendaraan...").
- Yang berubah hanya data tarikan ini (`bukti-db-uji.txt`):
  - 0 publikasi lain diekstrak ulang atau berubah metadatanya;
  - entri publikasi lain tetap 44.455;
  - di luar 6301/2024 tidak ada publikasi rilis sebelum 2025.
- Folder bersama PDF/sampul/cache OCR: 0 berkas lama berubah (ukuran dan
  mtime); baru 27 PDF + 27 sampul (`banding-berkas.txt`).
  - Berkas itu milik publikasi yang hanya ada di database uji; produksi tidak
    merujuknya.
- **Produksi: CHECKSUM TABLE 6/6 sebelum = sesudah**
  (`checksum-produksi-*.json`).

**Mutu ekstraksi PDF rilis 2024**, sampel 25 acak dibaca satu per satu,
dibandingkan dengan 25 acak Tanah Laut 2025-2026 dengan alat dan seed yang sama
(`tarik-kecil-20261124/penilaian-sampel.md`):

| | 2024 | 2025-2026 |
|---|---|---|
| Benar seluruhnya (judul, nomor, hal cetak, hal PDF) | 12/25 | 15/25 |
| Nilai terisi tapi salah | **0** | 1 (subbab tercatat sebagai tabel) |
| Tanpa tombol PDF | 11 (10 tabel Sensus Pertanian, 1 hal romawi) | 3 (entri isi) |
| Tanpa halaman cetak | 1 | 5 (utang lama Tanah Laut 2025) |
| Judul cacat | 2 (kop menempel; terpotong) | 1 (kop menempel) |

- Mutu per entri setara, dan cacatnya berjenis sama.
- Selisihnya dari satu seri yang hanya ada di rilis 2024: **Hasil Pencacahan
  Lengkap Sensus Pertanian 2023 Tahap II** (6 publikasi, 1.967 entri).
  - Tata letak keterangannya "Tabel <judul>" / "<nomor> <lanjutan>" / "Table"
    tidak dikenali jalur badan maupun `lengkapi_halaman_fisik`.
  - Halaman PDF asli hanya 3,4%; dengan perkiraan 35%; 1.240 tabel tanpa
    tombol PDF.
  - Nomor, judul, dan halaman cetaknya benar, dan 5/5 perkiraan di sampel tepat.
- Tanpa seri itu, kab/kota 2024: halaman PDF 86,6% (2025-2026: 88,3%),
  halaman cetak 94,8% (95,9%).
- Kecamatan Dalam Angka 2024 justru lebih lengkap halaman cetaknya: 100% vs
  58,1%.

**Saran (belum dikerjakan, perlu keputusan):** kenali keterangan bertumpuk
gaya Sensus Pertanian (baris "Tabel ..." diikuti baris berawal nomor) di
`lengkapi_halaman_fisik`. Kerjakan dengan regresi penuh, seperti C1(a).
Sebelum itu, Sensus Pertanian 2023 tetap dapat dicari, tetapi sebagian besar
tabelnya tanpa tombol PDF.

### Uji penuh dengan kamus sekarang

**Tanpa `--kamus-head`: 142 lulus, 0 gagal, 0 dilewati, kode keluar 0,
3.123 detik** (`uji-pipeline-penuh-kamus-p0.txt`). Termasuk N1, P2b, P2, C2,
O1, Q1 (4/4), Z1, Z2. Database uji saat itu sudah berisi tarikan Tanah Laut
2024 (P2: 645 publikasi identik per kunci).

Run sebelumnya (`uji-pipeline-penuh-kamus-p0-q1head.txt`): 140 lulus, 2 gagal,
keduanya Q1, dan penyebabnya ada di alat uji.
- Q1 mengambil "kode sebelum formulir" dari `git HEAD`. Itu benar saat Q1
  ditulis (fitur belum di-commit), tetapi sejak `abeab3b` HEAD sudah memuat
  fiturnya.
- Penjaga Q1 ("kode lama tanpa `--cek-dulu`") menangkapnya, sehingga uji
  gagal, tidak lulus palsu.
- Perbaikannya: pembanding dikunci ke commit tetap `4c57072` (=
  `abeab3b^`). P2, C2, dan O1 sudah lulus di run itu.
