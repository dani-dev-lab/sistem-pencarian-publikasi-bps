# Korpus pencarian di memori proses (10 Nov 2026)

Perubahan tersendiri sebelum filter wilayah, atas keputusan pemilik project.
Latar belakang: sesudah 13 kab/kota masuk, rata-rata waktu pencarian 430 ms,
dan ±70% di antaranya untuk mengambil seluruh korpus dari MySQL di setiap
kueri (`tarik-13-domain-20261110.md`).

## Rancangan
- **`mesin_pencari.korpus()`** mengembalikan objek `Korpus` baca-saja berisi:
  - baris entri dan publikasi, dari query yang sama dengan sebelumnya;
  - himpunan token tiap entri dan publikasi, dihitung sekali;
  - judul publikasi ternormalisasi, dihitung sekali.
- `cari()` dan `_cari_publikasi()` membaca dari korpus. Logika penilaian
  tidak diubah.
- **Penanda versi:** tabel satu baris `versi_data` (`app/services/versi_data.py`).
  - Setiap penulis data menaikkan `versi` DI TRANSAKSI YANG SAMA dengan
    perubahannya:
    - `pipeline_data.simpan_metadata` (pembaruan, metadata publikasi);
    - `pipeline_data.simpan_entri` (pembaruan, entri);
    - `normalisasi_data.jalankan` (tombol "Terapkan ke data" dan
      `isi_normalisasi.py`).
  - Setiap pencarian membaca `versi` dengan satu SELECT berkunci primer:
    **0,25 ms** (p95 0,39 ms, 200 kali).
  - Mekanismenya berlaku lintas proses: .bat, halaman admin, skrip.
- **Alternatif yang ditolak:**
  - berkas penanda bisa basi kalau penulis berhenti di antara commit dan
    tulis berkas;
  - COUNT/MAX(id) tidak menangkap "Terapkan ke data", yang hanya mengubah
    teks;
  - checksum seluruh tabel terlalu mahal untuk dicek di setiap kueri.
- **Jebakan MySQL:** `CREATE TABLE` memaksa commit transaksi yang sedang
  berjalan. Karena itu `versi_data.pastikan_tabel()` dipanggil SEBELUM
  transaksi penulis dimulai (`perbarui.pastikan_skema`, awal
  `normalisasi_data.jalankan`, pembacaan pertama), dan `naikkan()` hanya
  berisi `UPDATE`.
- **Kamus:** korpus juga dibangun ulang kalau objek kamus berganti
  (`muat_ulang_kamus` sesudah kamus diedit di halaman admin). Judul
  publikasi lalu dinormalkan dengan kamus yang sama dengan kueri, persis
  seperti perilaku lama yang menormalkannya di setiap kueri.
- **Aman untuk banyak thread (waitress 4 thread):**
  - korpus baru disiapkan PENUH di bawah kunci dengan pemeriksaan ganda,
    lalu referensi globalnya ditukar dengan satu penugasan;
  - objek `Korpus` tidak pernah diubah sesudah dibuat, sehingga thread yang
    sedang mencari tetap memakai korpus lamanya.

## Bukti
| Uji | Hasil |
|---|---|
| Hasil 12 kueri uji: kode lama (HEAD) vs baru, proses dan DB sama, seluruh medan kecuali `waktu_ms` | **identik 12/12**: urutan, skor, jumlah publikasi/ditemukan/saran/dinilai. Diulang sesudah DB dimuat ulang (perbaikan elipsis): tetap 12/12 |
| Pembanding mampu mendeteksi beda | ya: urutan `ditemukan` yang dibalik terdeteksi |
| Kesegaran lintas proses | proses lain mengubah satu entri + naikkan versi -> pencarian berikutnya di proses pertama menemukan token uji (0 -> 1); dikembalikan -> 0; korpus dimuat ulang dua kali; data kembali persis |
| Penulis sungguhan menaikkan versi | pemuatan ulang 306 publikasi (`perbarui.py --lokal --paksa`): versi 8 -> 314, tepat satu per `simpan_entri` |
| Banyak thread | 56 pencarian di 4 thread selagi versi dinaikkan 6x (korpus dimuat ulang berulang): 0 galat, 0 hasil yang berbeda dari acuan |

## Waktu (diukur bergantian dalam satu proses, DB sama, tanpa proses lain)
12 kueri uji × 20 ulangan + 1 pemanasan.

| Urutan | Kode | Rata-rata median | Rata-rata p95 | Kueri terlambat (median) |
|---|---|---|---|---|
| 1 | baru (korpus memori) | **78,3 ms** | 79,4 ms | 188,3 ms |
| 2 | lama (ambil dari DB tiap kueri) | 429,9 ms | 478,9 ms | 535,6 ms |
| 3 | baru | **78,0 ms** | 79,4 ms | 186,7 ms |

Hasil `ukur_kinerja.py` resmi (`data/ukur_kinerja/20261110-1037-korpus-memori.json`):
rata-rata 79 ms, terlambat 190 ms, kueri bernama wilayah "penduduk tanah
laut" 79 ms dan "luas panen padi kotabaru" 28 ms. **Target < 300 ms
tercapai**, termasuk kueri terlambat.

## Biaya muat ulang dan memori
| Ukuran | Nilai |
|---|---|
| Muat ulang korpus (ambil dari DB + siapkan token + judul ternormalisasi) | median **472 ms**, maks 496 ms (5 kali) |
| Memori yang DITAHAN satu korpus (`tracemalloc`) | **77,1 MB** (23.461 entri, 306 publikasi) |
| Puncak memori saat membangun | 84,4 MB |

- Muat ulang hanya terjadi sekali sesudah data berubah. Pencarian
  pertama sesudah pembaruan atau "Terapkan ke data" karena itu ±0,5 detik
  lebih lambat.
- Saat muat ulang, korpus lama dan baru sempat ada bersamaan (±160 MB
  sesaat) sampai thread yang masih memakai korpus lama selesai.
