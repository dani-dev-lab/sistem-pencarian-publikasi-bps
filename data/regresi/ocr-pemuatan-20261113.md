# OCR ujung ke ujung di database uji + rancangan pemuatan terarah (13 Nov 2026)

Berkas kerja: `data/regresi/ocr-pemuatan-20261113/`. Potret DB (`potret/`,
±8 MB per berkas) di-gitignore.

## 1. Run OCR: `perbarui.py --db-uji --lokal --paksa`
- 07:44-09:15, kode keluar 0, log `data/log_pembaruan/20261113-074449.log`.
- Baris pertama: `Database tujuan: db_pencarian_bps_uji @ localhost:3306 (UJI - bukan produksi)`.
- Cache terpakai penuh: 1.192 halaman dari cache, 0 di-OCR, 0 dilewati.
- Ekstraksi 5.445 detik untuk 306 PDF.
- Dibandingkan per kunci dengan produksi (`banding_kunci.py`, keluaran
  `banding-ocr.txt`):
  - hanya 8 publikasi target yang berubah, 0 di luar target;
  - medan publikasi yang berubah hanya `halaman_ocr`, di 8 target saja.
- Produksi tidak tersentuh: potret identik, `versi_data` tetap 345.

| Publikasi | Entri sebelum | Entri sesudah | Tetap | Berubah | Hilang | Bertambah | Halaman OCR |
|---|---|---|---|---|---|---|---|
| HST Dalam Angka 2026 | 0 | 163 | 0 | 0 | 0 | 163 | 320 |
| PDRB Tapin Pengeluaran | 0 | 44 | 0 | 0 | 0 | 44 | 99 |
| Profil TK Tapin Agt 2024 | 0 | 34 | 0 | 0 | 0 | 34 | 99 |
| Statistik Daerah Banjarbaru 2025 | 0 | 20 | 0 | 0 | 0 | 20 | 63 |
| PDRB Banjarbaru LU | 0 | 74 | 0 | 0 | 0 | 74 | 139 |
| PDRB Tapin LU 2020-2024 | 41 | 43 | 10 | 31 | 0 | 2 | 174 |
| PDRB Tapin LU 2021-2025 | 41 | 43 | 10 | 31 | 0 | 2 | 181 |
| PDRB Tabalong LU 2020-2024 | 1 | 87 | 1 | 0 | 0 | 86 | 117 |

### 62 entri "berubah" di dua PDRB Tapin LU - DITERIMA (keputusan pemilik project)
- Judul, nomor, halaman cetak, dan teks ternormalisasi tidak berubah. Yang
  berubah hanya `halaman_fisik`, ditambah `sumber` daftar -> keduanya.
- 43 entri dulu tanpa `halaman_fisik`, kini terisi.
- 19 entri (Tabel 4.8-4.17) dulu `halaman_fisik` = 12, yaitu halaman
  **Daftar Tabel**. Sebelum OCR, halaman badannya tanpa teks, jadi penanda
  "tabel 4.x" hanya terbaca di halaman Daftar lanjutan itu.
- Bukti: `bukti-fisik-tapin.txt`. Keterangan "Tabel/Lampiran N" ditemukan di
  halaman fisik baru **28/28 dan 27/27**.
- Jebakan alat: versi pertama pemeriksa hanya melihat 14 kata teratas
  halaman dan melaporkan 31 "tidak ada".
- 7 entri `isi` (judul BAB) menunjuk halaman pertama bab yang memuat judul
  BAB, 2 halaman sesudah sampul bab yang ditunjuk Daftar Isi.
- Diterima sebagai **pengecualian aturan superset**: tidak ada kunci yang
  hilang, dan nilai lama yang diganti terbukti salah.

## 2. Sampel manual 30 entri (`sampel/`, penilaian di `sampel/penilaian-sampel.tsv`)
- Pool: 425 entri yang bertambah; 2 per publikasi + 14 acak, seed 20261113.
- Bukti: potongan render PDF asli.
- Hasil:
  - **19** benar seluruhnya;
  - **6** benar dengan judul bersampah ringan ("Kesehatan Bab", "Halaman
    Table Page ...", "21 ... Tanggar");
  - **3** nomor hilang (Tabalong Tabel 4.9 dan 3.3, Banjarbaru LU Gambar 3.1);
  - **1** judul berawalan nomor tetangga ("2.2 2.3 Industri Pengolahan");
  - **1** `halaman_fisik` meleset 2 halaman (Profil TK, Lampiran: sampul vs isi).
- Lokasi: halaman cetak 25/25 benar, halaman fisik 15/16 benar.
- Jebakan alat: potongan D pertama memilih kata pertama yang cocok, sehingga
  9 potongan menampilkan baris tetangga. Dipotong ulang menurut nomor/judul
  (`potong_ulang.py`, berkas `*-D2-*`, `*-D3*`).
- Diterima untuk dimuat (25/30 dapat ditemukan dengan benar).

### Utang teknis (dicatat, parser TIDAK diubah)
- **PDRB Tabalong LU:**
  - 37/37 entri tabel/gambar/lampiran tanpa nomor ("Table 4.9" masuk ke
    tengah judul);
  - hanya 1/86 punya `halaman_fisik`;
  - lampirannya blok gabungan.
- **PDRB Banjarbaru LU:** 15/29 entri non-isi tanpa nomor.
- Uji pencarian di database uji: "menara telekomunikasi hst" menemukan HST
  Tabel 8.2.5 (hal. 241, PDF hal. 264), dan "tpak tapin" menemukan Profil TK
  Gambar 2.5.

## 3. Run `--tanpa-ocr`: `perbarui.py --db-uji --lokal --paksa --tanpa-ocr`
- 09:21-11:07, kode keluar 0, log `20261113-092105.log`.
- Baris pertama: database uji.
- Kedelapan publikasi: halaman tanpa teks dilewati (174/181/99/99/320/117/63/139)
  dan masuk "Perlu diperiksa manual" dengan alasan OCR dimatikan.
- Hasil: database uji **identik per kunci dengan produksi** di 306
  publikasi, 23.948 entri, `halaman_ocr` kosong.
  - Artinya perilaku tanpa OCR sama persis dengan sebelum OCR ada.
  - Artinya juga ekstraksi ulang `--paksa` deterministik.

## 4. Rancangan pemuatan terarah (`muat_ocr_terarah.py`) - BELUM ke produksi
- Isi: hanya 8 publikasi di `target_ocr.json`. Tanpa tarik metadata, tanpa
  unduh. Memakai `ekstrak_berkas(ocr_aktif=True)` + `simpan_entri`, fungsi
  yang sama dengan perbarui.py, satu transaksi per publikasi.
- Pengaman:
  - baris pertama = database tujuan;
  - produksi butuh `--produksi-disetujui`;
  - memakai berkas kunci perbarui.py;
  - semua publikasi diperiksa dulu (PDF ada, syarat OCR, cache setiap
    halaman lengkap) sebelum menulis apa pun;
  - berhenti kalau ekstraksi sempat meng-OCR halaman baru.
- Uji coba di database uji sesudah `--tanpa-ocr`, yaitu keadaan sama dengan
  produksi sekarang:
  - 30 detik;
  - hasilnya **identik per kunci dengan run OCR penuh** di 306 publikasi
    (24.373 entri);
  - tanpa `--produksi-disetujui`, sasaran produksi ditolak.

### Langkah produksi (menunggu persetujuan)
1. Cadangan mysqldump baru ke `C:/Users/Dani/cadangan-bps/`, dibuktikan bisa
   dipulihkan (pola `cadangan_13.py`).
2. `potret_kunci.py produksi potret/produksi-sebelum-muat.json`.
3. `muat_ocr_terarah.py target_ocr.json --sasaran produksi --produksi-disetujui`.
4. `potret_kunci.py produksi potret/produksi-sesudah-muat.json`, lalu:
   - banding dengan `potret/uji-sesudah-terarah.json`: harus 0 perbedaan
     (8 target identik dengan database uji);
   - banding dengan `produksi-sebelum-muat`: hanya 8 target berubah,
     0 di luar target, `versi_data` naik.

## 5. Pemuatan produksi (13 Nov 2026, disetujui pemilik project)
- Cadangan: `C:/Users/Dani/cadangan-bps/db_pencarian_bps-20261113-1359-sebelum-muat-ocr.sql`
  (8,2 MB, SHA-256 `f61a3785...d67321`). Dipulihkan ke DB sementara: 6 tabel
  baris + CHECKSUM sama, DB sementara dihapus (`cadangan_produksi.py`).
- `potret/produksi-sebelum-muat.json` = produksi-sebelum (versi 345).
- `muat_ocr_terarah.py --sasaran produksi --produksi-disetujui`: 8 publikasi,
  kunci dilepas (`muat-produksi.out`).
- Pemeriksaan:
  - vs `uji-sesudah-terarah.json`: **0 perbedaan** di 306 publikasi
    (`banding-produksi-vs-uji.txt`);
  - vs sebelum muat: hanya 8 target berubah, **0 di luar target**, 23.948 ->
    24.373 entri (`banding-produksi-muat.txt`);
  - `versi_data` 345 -> 353.
- Uji pencarian (`uji_pencarian_produksi.py`, konfigurasi produksi dengan log
  pencarian dimatikan; `log_pencarian` tetap 51 baris, id maks 53):
  - "jumlah pasar hulu sungai tengah" -> HST Tabel 11.1, PDF hal. 287;
  - "perbandingan konsumsi rumah tangga terhadap pmtb tapin" -> PDRB Tapin
    Pengeluaran Tabel 4.2, PDF hal. 79;
  - "menara telekomunikasi hst" -> HST Tabel 8.2.5, PDF hal. 264.
  - Ketiga halaman dicocokkan dengan render sampel (14-F, 16-F, 30-F).
- Temuan mutu tambahan (kelas cacat OCR yang sudah diterima, dicatat saja),
  PDRB Tapin Pengeluaran:
  - judul Tabel 4.2 menyerap baris pertama Tabel 4.3;
  - Tabel 4.3 kehilangan nomor;
  - "3.11" terbaca "3.71";
  - Tabel 4.1 tanpa halaman cetak ("66 ix" masuk ke judul).
