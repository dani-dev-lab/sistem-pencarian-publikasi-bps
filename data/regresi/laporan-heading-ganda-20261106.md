# Pencarian heading ganda dihapus (revisi 3, 6 Nov 2026)

Commit `b7779cb`. Bahan laporan revisi 3 (ekstraksi langsung ke MySQL).

## Masalah
Pipeline baru mencatat heading DAFTAR yang ditemukan per publikasi
(`catatan_ekstraksi.heading_ditemukan`). Awalnya `ekstrak_berkas()` membuka PDF
sendiri untuk `cari_heading()`, lalu `ekstrak_lengkap()` membuka PDF lagi dan
mencari heading yang sama. Halaman depan dibaca dua kali.

Perbaikan: `ekstrak_lengkap()` menerima `heading_keluar` dan pemanggil membaca
heading dari situ. Logika parser tidak berubah.

## Regresi 2 (ulang)
`perbarui.py --lokal --paksa`, 79 publikasi, data 6300, 11:23-11:49.

| Pemeriksaan | Hasil |
|---|---|
| Potret DB vs `potret-79-sebelum-rombakan.json` | IDENTIK (79 publikasi, 6.812 entri) |
| `catatan_ekstraksi` vs potret sebelum perubahan | 0 perbedaan (79 publikasi) |
| Kode keluar perbarui.py | 0 |

Log: `regresi2-poin3_log.txt`.

## Waktu jalur lama vs baru
Satu sesi, 79 PDF. Urutan dibalik tiap PDF (AB, BA, ...) supaya pergeseran
keadaan mesin terbagi rata. A = cari_heading terpisah + ekstrak_lengkap,
B = ekstrak_berkas (jalur sekarang). Script: `ukur-heading-ganda.py`, data
mentah: `ukur-heading-ganda-20261106.json`.

| Ukuran | A (lama) | B (baru) |
|---|---|---|
| Waktu dinding total | 1.836,1 d | 1.561,6 d |
| Waktu CPU total | 1.825,6 d | 1.552,0 d |
| Penghematan | | 274,5 d (14,9%) |
| Median penghematan per PDF | | 16,1% |
| PDF yang B-nya lebih lambat | | 2 dari 79 |
| Keluaran A berbeda dari B | | 0 dari 79 |

Penghematan per urutan: AB 16,5% (40 PDF), BA 11,7% (39 PDF). Selisih ini
menunjukkan ada efek urutan (cache berkas), dan itulah sebabnya urutannya
diselang-seling. Dua PDF yang B-nya lebih lambat berukuran kecil (7-12 detik),
jadi masih dalam variasi antar-jalan.

Waktu CPU hampir sama dengan waktu dinding (selisih <1%), jadi kerjanya terikat
CPU, bukan disk. Ini sejalan dengan temuan sebelumnya bahwa Windows Search
dan Defender bukan penyebab perlambatan.
