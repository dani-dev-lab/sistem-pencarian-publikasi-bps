# C3: buang kepala seksi kapital di mode tanpa-label (9 Nov 2026)

Langkah kedua dari usulan `penyelidikan-C-20261107.md`. Aturannya sama
persis dengan yang disimulasikan di laporan penyelidikan.

## Perubahan
Di `_parse_baris_tanpa_label`, baris kolom judul yang **seluruh hurufnya
kapital** (minimal 3 huruf, `_kapital_semua`) dibuang **saat buffer entri
masih kosong**.

Alasannya: padanan Inggris kepala seksi ("GEOGRAPHY CONDITION") tercetak di
kolom JUDUL, sedangkan padanan Indonesianya ("1.1 KEADAAN GEOGRAFI") di
kolom kiri sudah dibuang sejak dulu. Aturan ini hanya berlaku di mode
tanpa-label, jadi publikasi lain tidak tersentuh.

## Regresi 79 PDF (uji kering vs database = baseline `potret-79-sesudah-C1a.json`)
Pembanding memasangkan entri menurut kunci `(tipe, nomor)`; entri tanpa
nomor dipasangkan menurut judul.

| Syarat | Hasil |
|---|---|
| `(publikasi, tipe, nomor)` BERNOMOR hilang | **0** |
| Entri kehilangan `halaman_fisik` / berpindah | 0 / 0 |
| Sumber berubah | 0 |
| Publikasi yang berubah | hanya Dalam Angka 2026 (33) dan 2025 (31); 77 lainnya identik |

Jumlah entri: 6.824 → 6.821.

### Yang dibaca: SEMUA 64 entri berubah + 5 entri tanpa nomor
- **62 judul:** judul baru = judul lama tanpa awalan, dan awalannya seluruh
  hurufnya kapital (diperiksa per entri). Awalan yang dibuang (34 macam),
  semuanya kepala seksi Inggris:
  ADMINISTRATIVE AREA, CLIMATE CONDITION, EDUCATION, HEALTH, POVERTY AND
  HUMAN DEVELOPMENT, REGIONAL HOUSE OF REPRESENTATIVES, …
  Termasuk dua yang berupa sisa kop bab: "AGRICULTURE, FORESTRY, LIVESTOCK,
  AND FISHERY FOOD CROPS" dan "IN KALIMANTAN SELATAN PROVINCE, FORESTRY,
  LIVESTOCK, AND FISHERY FOOD CROPS".
- **4.1.1 (2026):** awalan "EDUCATION" dibuang, DAN ekor judul
  "... Municipality in Kalimantan Selatan Province, 2024/2025 and 2025/2026"
  kembali ke entrinya, sehingga halaman cetak None → 172 didapat.
  Penyebabnya: baris kepala seksi tadinya memakan jatah 8 baris entri,
  sehingga ekornya terlempar menjadi entri sampah tanpa nomor.
- **10.3.1 (2026):** awalan "INVESTMENT" dibuang dan ekornya bertambah.
  **Judul ini sudah tercemar judul 10.3.2 sejak sebelum C3** ("...
  Investasi Penanaman Modal Asing (PMA) yang Telah Disetujui Pemerintah
  10.3.2 ..."), dan kini cemarannya sedikit lebih panjang. Cacat lama,
  dicatat di CLAUDE.md, tidak dikejar.
- **Entri sampah tanpa nomor yang hilang (4):**
  - 2026: "Municipality in Kalimantan Selatan Province, 2024/2025 and
    2025/2026" (kembali ke 4.1.1);
  - 2026: "Menurut Kabupaten/Kota di Provinsi Kalimantan Selatan, 2025
    Government-Approved Foreign Investment ..." (separuhnya ke 10.3.1);
  - 2025: "CRIME xxvii" (kepala seksi + folio);
  - 2025: "RELIGION AND OTHER SOCIAL AFFAIRS" (kepala seksi).
- **Entri sampah tanpa nomor yang bertambah (1):** "Government-Approved
  Foreign Investment by Regency/Municipality in Kalimantan Selatan Province,
  2025". Ini sisa potongan di atas yang berganti bentuk, tetap sampah, dan
  termasuk pola "potongan baris Inggris tanpa nomor" yang dicatat saja.

## Sampel kab/kota (tidak masuk DB utama), vs parser sesudah C1(a)

| Ukuran | Hasil |
|---|---|
| Kunci bernomor hilang | 0 |
| Entri berubah | 74 (6371: 34, 6306: 21, 6302: 19) |
| ... hanya awalan kapital dibuang | 70 |
| ... awalan dibuang + ekor judul kembali utuh + halaman cetak didapat | 4 (3.1.1 di ketiganya, 4.1.1 di 6371) |
| Sampah tanpa nomor hilang / berganti bentuk | 5 / 1 |
| `halaman_fisik` baru | 1 (6302 tabel 5.1.1 → hal. 178) |

Hal. 178 6302 diperiksa: ada keterangan bertumpuk "Tabel 5.1.1", folio 142
= halaman cetak. Dulu gagal karena kata kunci judulnya (`_kata_isi`, lima
kata ≥5 huruf pertama) diambil dari kepala seksi "AGRICULTURE, FORESTRY,
LIVESTOCK, ..." yang tidak ada di halaman tabel.

## Pemuatan dan baseline
- Cadangan: `~/cadangan-bps/db_pencarian_bps-20261109-0856-sebelum-C3.sql`,
  terbukti bisa dipulihkan.
- Dimuat dengan `perbarui.py --lokal --paksa` (log `C3_muat_log.txt`,
  exit 0, tanpa kunci API).
- Database = uji kering di 79/79 publikasi, medan dan urutan sama;
  `teks_ternormalisasi` kosong: 0.
- **Baseline:** `potret-79-sesudah-C3.json`, 79 publikasi, 6.821 entri,
  SHA-256 `9cd5cbf7c4ebd7d5d7960d3e4734c0b1a17ea1a08d13c3d8c95c3f2b7a0f76b7`.
- **Daftar perubahan disengaja per entri:** `C3-perubahan-20261109.tsv`
  (65 berubah, 4 hilang, 1 bertambah; yang hilang dan bertambah semuanya
  entri sampah tanpa nomor yang dijelaskan di atas).
- Cek UI (test_client, `KonfigurasiUji`): kueri "luas daerah dan jumlah
  pulau" menampilkan Dalam Angka 2026 tabel 1.1.1 tanpa awalan "GEOGRAPHY
  CONDITION", dengan tombol "Buka PDF hal. 65" (halaman fisik dari C1(a)).
