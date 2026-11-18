# RENCANA: memuat publikasi Kecamatan Dalam Angka ke produksi (Kamis 20 Nov 2026 pagi)

STATUS: **DISETUJUI 19 Nov 2026 malam**, dikerjakan **Kamis 20 Nov pagi**
(semula Jumat). Belum ada yang dimuat. Pembekuan Selasa 24 Nov; presentasi
25-26 Nov.

Keputusan pemilik project:
1. cara muat: **salin dari database uji**;
2. `kecualikan_judul.aktif` -> **`false`** saat pemuatan;
3. 5 publikasi produksi yang membaik oleh parser pola 2+3: **dimuat**, di
   langkah terpisah (langkah 5).

## Yang dimuat
312 publikasi kecamatan dari **database uji**, persis seperti yang sudah
diperiksa:
- 19.955 bagian, 18.381 berhalaman PDF;
- 26 publikasi OCR;
- parser pola 2+3;
- regresi penuh lulus;
- sampel 27/30 (teks) dan 9/10 (OCR).

**Cara yang diusulkan: salin baris dari database uji ke produksi** (server
MySQL yang sama), BUKAN tarik ulang dari BPS.
- Cepat: ±20 ribu baris, hitungan detik.
- Tidak butuh jaringan.
- Isinya sama dengan yang sudah diuji, dan bisa dibuktikan per isi baris.
- Alternatifnya, `aktif: false` lalu pembaruan online, berarti ekstraksi
  ulang 312 PDF (±1-1,5 jam). Itu lebih lama, dan hasilnya harus diperiksa
  ulang.

Fakta yang sudah dicek (hanya baca, 19 Nov):
- produksi: 0 publikasi berjudul Kecamatan … Dalam Angka; 0 `pub_id`
  bertabrakan;
- kolom yang belum ada di produksi hanya `publikasi.kecamatan` dan
  `log_pencarian.sertakan_kecamatan`, yang ditambahkan aplikasi sendiri;
- 86 publikasi kecamatan ber-`updt_date_diproses` kosong. Semuanya juga
  ber-`updt_date_api` kosong dari BPS, dan aturan yang ada (uji B3) tidak
  menganggap itu perubahan, jadi pembaruan berikutnya **tidak** mengunduh
  ulang. 226 sisanya sama dengan API.

## Keputusan yang diminta
1. **Cara muat:** salin dari database uji (disarankan) atau tarik ulang
   online.
2. **`data/wilayah.json` > `kecualikan_judul`: ubah `"aktif": true` menjadi
   `false` saat pemuatan (disarankan).**
   - Kalau tetap `true`, publikasi kecamatan sudah ada di produksi tetapi:
     - setiap pembaruan rutin mencetak 312 baris "tidak lagi di daftar API
       (dibiarkan)";
     - edisi kecamatan baru dan perubahan `updt_date` tidak pernah
       ditarik.
   - Kalau `false`, pembaruan rutin menangani kecamatan seperti publikasi
     lain:
     - beban ke BPS tidak bertambah, karena halaman daftar yang ditarik
       sama; publikasi kecamatan selama ini hanya disaring sesudah
       ditarik;
     - hanya publikasi kecamatan BARU yang diunduh.
   - Sesudah itu, `--kecamatan` (mode uji) tidak berguna lagi, karena tidak
     ada lagi yang dikecualikan. Dicatat di PANDUAN.
   - `pola_kecamatan` tetap, karena itulah penanda untuk kotak centang.
3. **5 publikasi produksi yang membaik oleh parser pola 2+3** (SHK, IHK,
   PDRB Banjar dua edisi, PDRB Tabalong; hanya Daftar Isi/Lampiran,
   0 kunci hilang): ikut dimuat dari database uji di langkah terpisah
   (disarankan), atau dibiarkan sampai ekstraksi ulang berikutnya.
   Dibiarkan pun, kode yang berjalan sudah parser baru, sehingga publikasi
   itu berubah sendiri begitu PDF-nya berganti.

## Langkah (±45-60 menit; jangan ada pembaruan data yang berjalan)
| # | Langkah | Perkiraan |
|---|---|---|
| 0 | Prasyarat: tidak ada `pembaruan.lock`; potret database uji dicatat (jumlah baris + CHECKSUM), supaya sumbernya pasti yang sudah dinilai | 2 mnt |
| 1 | **Cadangan produksi:** `mysqldump` (perintah PANDUAN bagian 7) -> `C:/Users/Dani/cadangan-bps/db_pencarian_bps-20261120-sebelum-kecamatan.sql`; pulihkan ke database sementara, bandingkan 6/6 tabel (baris + CHECKSUM), hapus database sementara | 10 mnt |
| 2 | **Kolom baru:** jalankan `skema.pastikan_kolom()` ke produksi (ALTER `publikasi`, `log_pencarian`; `sinkron_kecamatan` = 0 baris). Lalu **potret produksi SEBELUM** (`tests/potret_tampilan.py`, log mati, 28 URL) | 5 mnt |
| 3 | **`muat_kecamatan_terarah.py --coba`:** dalam SATU transaksi yang lalu di-rollback, cek: target 312 tidak ada di produksi, kolom sama, `INSERT publikasi ... SELECT` dan `INSERT entri_dokumen (tanpa id) ... SELECT` dari database uji, hitungan 312/19.955 | 3 mnt |
| 4 | **Muat** (`--produksi-disetujui`): transaksi yang sama, ditambah `versi_data` naik 1, lalu commit. Atomik: aplikasi yang sedang berjalan melihat semua atau tidak sama sekali | < 1 mnt |
| 5 | (Kalau keputusan 3 = ya) muat terarah 5 publikasi pola 2+3 dari database uji: hapus + sisip entri per publikasi, satu transaksi per publikasi (pola `muat_parser_terarah.py`) | 3 mnt |
| 6 | `wilayah.json`: `kecualikan_judul.aktif` -> `false` (keputusan 2), commit | 1 mnt |
| 7 | **Bukti** (lihat di bawah) | 15 mnt |
| 8 | **Pembaruan rutin online sekali** (`perbarui-data.bat`): harapannya tidak ada publikasi baru, 0 kecamatan diunduh ulang, tidak ada baris "tidak lagi di daftar" | ±2-3 mnt |
| 9 | Catatan: PANDUAN bagian 8 ("sudah dimuat"), CLAUDE.md; push sesudah disetujui | 5 mnt |

## Bukti yang dicatat (`data/regresi/muat-kecamatan-20261120.md`)
- **Isi kecamatan di produksi = database uji per isi baris** (id produksi ≠
  id uji): 312 publikasi dan 19.955 entri, termasuk `halaman_fisik`,
  perkiraan, sumber, dan `teks_ternormalisasi`.
- **Publikasi lain tidak berubah:**
  - 307 publikasi produksi lain: entri identik per id (atau, kalau langkah
    5 dijalankan, hanya 5 publikasi itu yang berubah, persis sama dengan
    database uji);
  - `publikasi` lama identik kecuali kolom baru `kecamatan` = NULL.
- **Tabel lain tidak berubah:**
  - `log_pencarian`: jumlah baris dan CHECKSUM kolom lama sama (CHECKSUM
    TABLE berubah karena ada kolom baru);
  - `kategori`, `publikasi_kategori`: CHECKSUM sama;
  - `versi_data` +1 (+5 kalau langkah 5).
- **Tanpa centang identik, langsung di produksi:** potret SESUDAH vs
  SEBELUM (langkah 2), 23 halaman byte-identik sesudah widget kecamatan
  dibuang. `/api/saran` tanpa `kec=1`: 0 saran kecamatan.
- **Dengan centang:** 3 kueri (umum, satu kab/kota, satu kecamatan), seksi
  kecamatan tampil, dan tombol PDF dicek ke halaman yang benar.
- **Kinerja di produksi:** `ukur_kinerja.py` setara dengan sebelum (tanpa
  centang); memori korpus ±144 MB.

## Kalau harus dibatalkan
- **Cepat:** dalam satu transaksi, `DELETE` entri dan publikasi yang
  `kecamatan IS NOT NULL`, lalu `versi_data` naik, dan `aktif` kembali
  `true`. Kotak centang hilang sendiri (tidak ada kecamatan). Kedua kolom
  baru boleh tetap ada (NULL).
- **Penuh:** pulihkan cadangan langkah 1 (±5-10 menit). Pemulihannya sudah
  diuji di langkah 1.

## Yang perlu diketahui sebelum menyetujui
- Kode yang dipakai `jalankan-aplikasi.bat` sekarang sudah memuat fitur ini.
  Sesudah pemuatan, petugas langsung melihat kotak centang (bawaan mati).
- Saran saat mengetik di produksi sudah berganti ke "edisi terbaru dulu"
  begitu aplikasi produksi dijalankan dengan kode ini, terlepas dari
  pemuatan kecamatan (keputusan 18 Nov).
- Folder PDF dan cache OCR dipakai bersama database uji dan produksi; tidak
  ada berkas yang perlu disalin.
- Utang teknis yang ikut masuk (sudah dicatat): Tanah Laut 2025 tanpa
  halaman cetak (tombol PDF benar), nomor salah cetak Banjar 2026, folio
  romawi Balangan.
