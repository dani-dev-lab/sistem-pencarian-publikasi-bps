# Pengukuran akhir v1.0.0 (27 November 2026)

Pembekuan untuk serah terima. Semua angka diukur 27 November 2026 di laptop
pengembang (Windows 11, Python 3.14.6, MySQL 8.0.30), dari database produksi
`db_pencarian_bps`, hanya dengan membaca. Aplikasi produksi ditutup pemilik
project selama pekerjaan ini. `.env` tidak dibuka; tidak ada pembaruan data.
Rincian mentah: `pengukuran-akhir-20261127/ukuran.json`.

## Kode yang diuji

- Uji akhir dijalankan pada commit **`bd5b63d`** ("Rapikan pohon kerja
  sebelum pembekuan v1.0.0").
- Commit sesudahnya (laporan ini, README, CHANGELOG, alat manifest di folder
  laporan) tidak mengubah `app/`, `scripts/`, `tests/`, `run.py`,
  `requirements*.txt`, `.bat`, maupun `.sh`. Diperiksa dengan `git diff
  --stat bd5b63d` sebelum merge.
- Versi rilis: tag **`v1.0.0`** pada commit merge "Serah terima v1.0.0" di
  `main`.

## Uji akhir

`tests/uji_pipeline.py` penuh, tanpa argumen, di database uji
`db_pencarian_bps_uji` (`pengukuran-akhir-20261127/uji-pipeline-penuh.txt`):

- **184 lulus, 0 gagal, 0 dilewati**, kode keluar 0, 3.502 detik.
- Z1: database uji dipulihkan, CHECKSUM sama dengan awal.
- Z2: produksi tidak berubah.

**CHECKSUM TABLE produksi** sebelum dan sesudah uji
(`checksum-produksi-awal.json` = `checksum-produksi-akhir.json`):

| Tabel | Baris | CHECKSUM | Sebelum = sesudah |
|---|---|---|---|
| publikasi | 622 | 1776278352 | sama |
| entri_dokumen | 44.649 | 1514962164 | sama |
| versi_data | 1 | 2623566961 | sama |
| kategori | 14 | 1501779208 | sama |
| publikasi_kategori | 0 | 0 | sama |
| log_pencarian (tambahan) | 368 | 3141993398 | sama |

## Data

**Publikasi:** 622.
- 312 publikasi "Kecamatan … Dalam Angka";
- 34 memakai OCR (`halaman_ocr` > 0);
- rilis 2025: 346, rilis 2026: 276 (10 Januari 2025 – 25 November 2026);
- per wilayah:

| 6300 | 6301 | 6302 | 6303 | 6304 | 6305 | 6306 | 6307 | 6308 | 6309 | 6310 | 6311 | 6371 | 6372 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 81 | 39 | 61 | 55 | 52 | 41 | 39 | 38 | 40 | 41 | 40 | 32 | 34 | 29 |

**Bagian terindeks (`entri_dokumen`):** 44.649.

| Per tipe | Jumlah | | Per sumber | Jumlah |
|---|---|---|---|---|
| tabel | 24.931 | | daftar | 30.911 |
| isi (bab/subbab) | 11.773 | | keduanya | 11.329 |
| gambar | 5.219 | | badan | 2.409 |
| lampiran | 2.726 | | | |

**Halaman PDF:**
- 39.694 bagian (88,9%) punya nomor halaman PDF: 34.682 asli dan 5.012
  perkiraan ("±hal.");
- 415 bagian tidak punya nomor halaman sama sekali (cetak maupun PDF).

**Lainnya:**
- `versi_data`: 549.
- `log_pencarian`: 368 baris (3 November – 27 November 2026), sebagian
  besar pencarian pengembang dan pemilik project.

## Berkas

| Folder | Berkas | Ukuran |
|---|---|---|
| `data/publikasi_pdf/` | 649 PDF (+ `.gitkeep`) | 6.806.084.783 bait (6.490,8 MiB) |
| `data/sampul/` | 649 sampul resmi, 0 cadangan | 76.598.362 bait (73,0 MiB) |
| `data/ocr_cache/` | 4.000 berkas | 37.200.469 bait (35,5 MiB) |

- 649 PDF = 622 publikasi produksi + 27 publikasi Tanah Laut rilis 2024 yang
  hanya ada di database uji (tarik kecil 24 November).
- **Kamus sinonim** (`data/kamus_sinonim.json`): 101 kelompok kanonik, 212
  kata varian; berkasnya 416 baris.
- `scripts/periksa_sidik.py` (produksi): 622/622 PDF cocok, 0 berbeda,
  0 tidak ada; 34/34 cache OCR cocok; 649 sampul. Hasil: "SEMUA COCOK".

## Paket serah terima (`data/serah_terima/`, tidak masuk Git)

| Berkas | Ukuran | Keterangan |
|---|---|---|
| `db_pencarian_bps-20261127.sql` | 15.973.440 bait | mysqldump produksi 27 Nov 15.12, pilihan PANDUAN bagian 7; sha256 `479210242b86acfb565ece7fc968217ad691e1925c2f9b9cb31b01ae52a02028` |
| `db_pencarian_bps-20261126.sql` | 15.972.754 bait | dump 26 Nov, dibiarkan (sha256 `807ce7a3…3200`) |
| `manifest-berkas-20261127.tsv` | 774.254 bait | 5.298 berkas (PDF, sampul, cache OCR): jalur, ukuran, detik waktu ubah, sha256; dibuat `pengukuran-akhir-20261127/buat_manifest.py` (hanya membaca, 41 detik) |
| `periksa-sidik-20261127.txt` | 429 bait | keluaran `periksa_sidik.py` di komputer asal |
| `BACA-DULU.txt` | ±5 KB | untuk Tim IT: isi paket, folder yang disalin terpisah (tar, bukan ZIP), pemulihan dump, `.env` baru dari `.env.example`, pemeriksaan sesudah menyalin, rujukan PANDUAN 2/7/7.4 |

- **Uji pulih dump 27 Nov:** dimuat ke database sementara
  `db_pencarian_bps_serah_uji`. 6/6 tabel sama dengan produksi, jumlah baris
  dan CHECKSUM (`pengukuran-akhir-20261127/uji-pulih-cadangan.json`). Lalu
  **hanya** database sementara itu yang dihapus.
- `.env` tidak ada di paket.
- **Manifest tanpa mengubah kode:** `periksa_sidik.py` hanya mencetak
  ringkasan, bukan daftar per berkas. Menambah pilihan manifest ke skrip itu
  sesudah uji akhir berarti kode yang dibekukan bukan kode yang diuji. Karena
  itu manifest per berkas dibuat oleh alat terpisah di folder laporan, dengan
  sidik yang sama (ukuran + detik waktu ubah) ditambah sha256. Di server baru,
  pemeriksaan resminya tetap `periksa_sidik.py` (bandingkan dengan
  `periksa-sidik-20261127.txt`).

## Pohon kerja sebelum pembekuan

- `data/ocr_target_kecamatan.{txt,json}` (daftar target OCR kecamatan dari
  17 Nov) dipindah ke `kecamatan-mutu-20261118/`. Berkas ini hanya dipakai 4
  alat regresi, yang kini menunjuk ke jalur baru; tidak dipakai `app/` atau
  `scripts/`.
- 6 potret HTML di `sampul-20261119/` dan `tombol-atas-20261119/` di-gitignore
  (`potret-*.json`, seperti folder laporan lain), tidak dihapus.
- `.git/stale-maintenance-lock-dari-claude` dihapus (disetujui pemilik
  project).
- `git status` bersih.
