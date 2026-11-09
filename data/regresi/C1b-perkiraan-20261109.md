# C1(b): perkiraan waktu dan risiko, untuk keputusan (9 Nov 2026)

C1(b) = jalur badan (`ekstrak_badan`) mengenali keterangan BERTUMPUK
("Tabel" / "1.1.1" / "Table") sebagai keterangan, sehingga bisa menemukan
entri yang tidak ada di Daftar mana pun. C1(a) sudah mengisi halaman fisik
untuk entri yang DIKENAL; C1(b) menambah entri BARU.

## Manfaat yang tersisa sesudah C1(a) (dan C2)
Dihitung ulang dari `penyelidikan-C-20261107.md`:

| Kelompok | Entri baru | Catatan |
|---|---|---|
| Grafik Dalam Angka provinsi ("Gambar" / "1.1" / "Figure" di halaman infografis bab) | ±55 (27 + 28) | Dalam Angka tidak punya Daftar Gambar - saat ini sama sekali tidak terindeks |
| Grafik 3 Dalam Angka kab/kota (sampel) | ±59 | Sama; berlaku juga untuk 13 domain nanti |
| Tabel Kesra (107) | ~0 kalau C2 dimuat | C2 sudah memberi entri jalur daftar untuk tabel-tabel itu |
| KAK (159 di Agt 2024) | 0 | Keterangannya bergaya SAMA dengan badan - tidak lolos aturan gaya |

Manfaat nyata: **grafik Dalam Angka** (±55 prov + ±4-5 per Dalam Angka
kab/kota, jadi sekitar 60 untuk 13 domain).

## Risiko
- **Sedang-tinggi, terutama lewat aturan judul terpanjang di `_gabung`.**
  Sekitar 600 tabel Dalam Angka provinsi akan punya versi badan untuk kunci
  yang sudah ada dari Daftar. Versi mana yang menang ditentukan panjangnya,
  jadi ratusan judul yang sekarang bersih bisa berganti ke rekonstruksi badan
  (yang bisa membawa baris kop tabel atau label "Table"). Sumbernya juga
  berubah daftar → keduanya.
- Mengubah `ekstrak_badan` = menyentuh aturan superset gaya. Keterangan
  bertumpuk adalah tambahan (superset tetap terjaga), tapi derau yang sudah
  terlihat harus disaring: kop "LAMPIRAN" + folio (99 deteksi) dan judul
  yang dimulai di baris DI ATAS label (Kesra).
- Butuh baca sampel besar: semua entri baru (±55) + 25-40 dari ratusan
  judul yang berubah.

**Cara meredam (usulan):** C1(b) hanya MENAMBAH kunci yang belum ada dan
tidak menyentuh entri yang sudah dikenal Daftar - halaman fisiknya sudah
diisi C1(a). Itu membatasi perubahan ke ±55 entri baru, tanpa perubahan judul
massal.

## Perkiraan waktu
| Langkah | Waktu |
|---|---|
| Implementasi (pengenalan, rekonstruksi judul, saring derau, batas "hanya kunci baru") | 1,5-2 jam |
| Uji kering 79 PDF + kab/kota, regresi | ±1 jam (sebagian besar menunggu) |
| Baca semua entri baru + sampel | ±1 jam |
| Cadangan, muat, baseline, laporan | ±30 menit |
| **Total** | **±4-5 jam (setengah hari)** |

## Saran
**Tunda**, atau kerjakan versi sempit "hanya kunci baru" sesudah 13 domain
tertarik (supaya grafik Dalam Angka kab/kota ikut terhitung dalam satu kali
ekstraksi ulang). Nilai utama label bertumpuk - halaman fisik ±1.100 tabel
Dalam Angka - sudah didapat lewat C1(a).
