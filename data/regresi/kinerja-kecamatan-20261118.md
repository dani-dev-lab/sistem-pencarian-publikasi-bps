# Kinerja pencarian dengan publikasi kecamatan (18 Nov 2026)

Database uji (618 publikasi, 44.455 entri: 306 publikasi produksi + 312
kecamatan) dibandingkan dengan produksi (307 publikasi, 24.532 entri). Kode
`390f3d4` + `--db-uji` di `scripts/ukur_kinerja.py`. Kedua database hanya
dibaca, dan log pencarian tidak ditulis.

## Memori korpus (`kinerja-kecamatan-20261118/ukur_memori_korpus.py`, metode 10 Nov)

| | Produksi | Database uji | × |
|---|---|---|---|
| Memori ditahan satu korpus (tracemalloc) | 80,1 MB | 143,9 MB | 1,8 |
| Puncak saat membangun | 88,4 MB | 158,4 MB | 1,8 |
| Muat ulang korpus (median dari 5 kali) | 458 ms | 860 ms | 1,9 |

Saat muat ulang, korpus lama dan baru sempat ada bersamaan (±290 MB sesaat,
dulu ±160 MB). Muat ulang hanya terjadi sekali sesudah data berubah.

## Waktu pencarian (12 kueri uji × 20 ulangan, diukur bergantian dua kali)

| | Produksi | Database uji, kecamatan IKUT dicari | × |
|---|---|---|---|
| Rata-rata median | 86-89 ms | 142-144 ms | 1,65 |
| Kueri terlambat (median) | 206-232 ms | 412-414 ms | **2,0** |
| Terlambat dengan filter wilayah | 59-60 ms | 70 ms | 1,2 |

- Yang paling naik adalah kueri berkata umum. "jumlah penduduk menurut
  kecamatan" naik 203 -> 412 ms (dinilai 14.962 -> 29.593 entri); "jumlah hotel
  kabupaten kota 2024" naik 206 -> 347 ms. Keduanya **melewati target 300 ms**.
- Kueri spesifik juga naik (tpk 8 -> 13 ms) walaupun entri yang dinilai sama,
  karena seluruh korpus tetap ditelusuri.
- Rincian per kueri ada di `data/ukur_kinerja/20261118-13{45,46,47,48}-*.json`.

## Solusi yang diusulkan, dan buktinya
**Pisahkan baris kecamatan di dalam objek Korpus.** Pencarian tanpa centang
hanya menelusuri bagian non-kecamatan, yaitu tuple yang sama persis dengan
sekarang. Bagian kecamatan baru ditelusuri kalau petugas mencentangnya. Pola
ini sama dengan `entri_per_domain` untuk filter wilayah.

Simulasi (`simulasi_tanpa_kecamatan.py`): baris kecamatan dibuang dari korpus
di proses uji, kode aplikasi tidak diubah.
- Rata-rata median produksi 84 ms, database uji tanpa kecamatan 85 ms.
- **Hasil 12/12 kueri identik** dengan produksi, dibandingkan menurut isi
  (publikasi, tipe, nomor, judul, halaman, skor), karena id produksi ≠ id uji.

Dengan centang aktif dan "Semua wilayah", biaya tambahan tetap ada (sampai
±+210 ms pada kueri umum). Biaya itu hanya untuk pencarian yang memintanya.
Kalau ada wilayah yang dipilih, bagian kecamatan satu kab/kota hanya
1.300-3.300 entri (±+10-20 ms).

Memori 144 MB dinilai wajar untuk laptop/server dan tidak perlu ditangani
sekarang. Kalau nanti perlu, bagian kecamatan bisa dimuat malas, yaitu baru
saat pencarian bercentang pertama.
