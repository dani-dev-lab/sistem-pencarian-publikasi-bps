# Laporan uji rombakan pipeline multi-domain - 5 November 2026

## Kesimpulan

Uji terisolasi lolos **71 dari 71** pada satu run utuh dari awal. Log lengkapnya
ada di [`uji_log.txt`](uji_log.txt).

Uji ini memakai salinan data dan API tiruan. Migrasi ke database dan PDF asli
**belum dijalankan**, dan pipeline **belum pernah dihubungkan ke API BPS
sungguhan**. Tes regresi 1 dan 2 pada data asli dijadwalkan bersama migrasi.

## Yang diuji

| Komponen | Keadaan |
|---|---|
| Kode | Commit `d257228`, ditambah perbaikan `scripts/perbarui.py` yang kemudian di-commit sebagai `779f6e3` |
| Database | `db_uji_pipeline_bps`, dipulihkan dari cadangan `db_pencarian_bps-20261105-1118-sebelum-rombakan.sql`, lalu dihapus |
| PDF | Hardlink ke 79 PDF asli di folder uji, sudah dihapus. Isi PDF asli tidak ditulis |
| API BPS | Server tiruan di `127.0.0.1:5981` dengan API key tiruan |
| Baseline | `potret-79-sebelum-rombakan.json` (79 publikasi, 6.812 entri), diambil dari MySQL sebelum rombakan |

Keadaan data asli diperiksa di awal dan akhir uji: jumlah baris, `updated_at`
terakhir, `id` entri terbesar, jumlah kolom, serta nama, ukuran, dan waktu ubah
tiap PDF. Hasilnya **sama persis**.

## Hasil per kelompok

| Kelompok | Lulus | Yang dibuktikan |
|---|---:|---|
| M. Migrasi | 10 | Dibatalkan tanpa isian separuh kalau ada PDF hilang; aman diulang; potret IDENTIK dengan baseline |
| P. Ekstraksi penuh 79 PDF | 4 | Potret IDENTIK lewat jalur baru; `--lokal --paksa` tidak memajukan 7 PDF usang |
| L. Mode lokal | 2 | Tidak ada permintaan ke API; 7 PDF usang tercatat menunggu |
| O. Online pertama | 6 | Tepat 7 PDF usang diunduh dan diproses; run kedua tidak mengerjakan apa pun; jeda antar request minimal 1,01 detik |
| B. Publikasi baru dan `updt_date` | 4 | Publikasi baru masuk; `updt_date` berubah memicu unduh ulang; `updt_date` kosong bukan perubahan |
| G. Unduhan gagal | 4 | HTTP 500, halaman HTML, dan berkas terpotong tidak mengubah data dan PDF lama; dicoba ulang otomatis |
| E. PDF rusak dan 0 entri | 7 | Galat tercatat dan entri lama utuh; PDF sah tanpa entri tidak diekstrak ulang; PDF hilang atau diganti terdeteksi |
| T. Transaksi | 6 | Gagal di tengah transaksi membatalkan semua; proses dibunuh pulih pada run berikutnya; kunci ganda ditolak |
| D. Multi-domain | 13 | Domain baru ditolak sebelum `--hanya-periksa`; satu domain gagal tidak menghentikan yang lain; `pub_id` domain lain tidak ditimpa |
| K. API key | 4 | Key tersamar di keluaran, ringkasan, dan laporan |
| R. Route PDF dan admin | 5 | `/pdf/<id>` menyajikan berkas lokal untuk 82 publikasi uji; 40 dari 40 tombol Buka PDF tanpa redirect; semua status admin tampil |
| W. Tombol web dan `.bat` | 6 | Alur tombol web sungguhan; keempat hasil `.bat` benar; `.bat` tetap ASCII + CRLF |
| **Total** | **71** | **0 gagal** |

## Riwayat run

| Run | Selesai | Hasil | Catatan |
|---|---|---|---|
| 1 | 13.30 | 59 lulus, 1 gagal (60 uji) | Tetap berjalan setelah VS Code tertutup. Tidak dipakai sebagai bukti kelulusan |
| 2 | 15.05 | 67 lulus, 4 gagal (71 uji) | Kedua bug sudah diperbaiki, uji diperluas. Keempat kegagalan berasal dari alat uji |
| 3 | 15.50 | **71 lulus, 0 gagal** | Run yang menjadi dasar laporan ini |

## Masalah yang ditemukan

1. **Bug kode, jeda terlalu pendek.** Jeda antara halaman daftar terakhir dan
   unduhan PDF pertama hanya 0,22 detik, melanggar kewajiban jeda dari Term of
   Use BPS. Jeda dipindah ke sebelum unduhan, dan minimumnya menjadi 1,01 detik.
2. **Bug kode, tabrakan terhitung ganda.** `--hanya-periksa` mencatat satu
   `pub_id` bertabrakan dua kali. Run 1 tetap meluluskannya karena ujinya hanya
   memeriksa "ada tabrakan". Bug ini ketahuan saat membaca log, lalu ujinya
   diperketat menjadi "tepat satu".
3. **Bug alat uji, bukan kode.** Uji `.bat` di run 2 gagal karena sesi pengujian
   memasang `NoDefaultCurrentDirectoryInExePath=1`, sehingga `cmd` tidak mencari
   di folder kerja dan `.bat` tidak pernah berjalan. Uji kini memanggilnya dengan
   path lengkap. Klik dua kali oleh pengguna tidak terpengaruh.

## Yang belum terbukti

- **API BPS sungguhan.** Server tiruan meniru bentuk jawaban yang dibaca kode,
  bukan seluruh perilaku API. DNS kantor masih mengarahkan `webapi.bps.go.id` ke
  10.0.11.232, sehingga uji nyata pertama adalah pembaruan online pertama.
- **Isi 7 PDF usang.** Server tiruan menyajikan PDF lama, jadi isinya tidak
  berubah dalam uji ini. Isi versi BPS terbaru belum diketahui.
- **Regresi pada data asli.** Tes regresi 1 dan 2 belum dijalankan pada
  `db_pencarian_bps`.
- **Proses dibunuh tepat saat SQL commit.** Uji T2 membunuh proses setelah
  permintaan PDF pertama. Pembatalan transaksi diuji terpisah di T1 dengan
  memicu galat SQL.
- **`updt_date` kosong di 18 dari 79 publikasi.** Pembaruan pada publikasi itu
  tidak terdeteksi lewat tanggal ini.

## Angka yang belum boleh dipakai

Waktu ekstraksi 79 PDF lewat jalur baru adalah **1.560 dan 1.685 detik** pada
dua run, sedangkan uji kontrol kode lama **1.215 detik**. Selisihnya belum
diselidiki, sehingga **jangan dipakai dulu untuk revisi 3**. Satu perbedaan yang
sudah diketahui: uji kontrol tidak memanggil `cari_heading()` secara terpisah,
sedangkan `ekstrak_semua.py` lama dan jalur baru memanggilnya. Jadi kontrol itu
bukan pembanding yang setara, dan besarnya pengaruh hal ini belum diukur.
