# Penanda halaman fisik berhenti di batas nomor (9 Nov 2026)

Perubahan tersendiri sebelum C2, atas keputusan pemilik project.

## Bug
`lengkapi_halaman_fisik` mencocokkan penanda "tabel 3.1" dengan
`startswith` (awal baris) dan `find` (tengah baris). Akibatnya penanda itu
ikut cocok dengan:
- **nomor lain berawalan sama:** "Tabel 3.12", "Gambar 2.20", "Gambar 23";
- **folio berjalan halaman lampiran:** "Lampiran 137", "Lampiran 141",
  "Lampiran 31".

## Perubahan
`_pola_penanda(penanda)` adalah regex yang menolak penanda bila diikuti
digit atau ".digit". "Tabel 3.1 Judul", "Tabel 3.1." dan "Tabel 3.1:" tetap
cocok; "Tabel 3.12", "Tabel 3.1.2", dan "Tabel 3.10" tidak. Pola dibuat
sekali per entri. Logika lain (syarat kata judul, awal vs tengah baris,
cadangan) tidak diubah.

## Regresi 79 PDF (uji kering vs database = baseline `potret-79-sesudah-C3.json`)

| Syarat | Hasil |
|---|---|
| `(publikasi, tipe, nomor)` hilang / bertambah | 0 / 0 |
| Sumber berubah | 0 |
| `halaman_fisik` berubah | 8: 7 pindah, 1 menjadi kosong; semuanya dibuktikan di bawah |
| Medan lain berubah | 0 |

### Bukti per entri
Bukti yang ditampilkan adalah baris yang benar-benar memicu kecocokan, di
halaman lama dan halaman baru, dengan pencocokan cara lama dan cara baru.

| Entri | Lama: halaman, pemicu | Baru: halaman, pemicu | Penilaian |
|---|---|---|---|
| Tinjauan PDRB Kab/Kota `11487263` gambar 2.2 | 47, "gambar **2.20** peranan sektor" | 34, "... berkebalikan gambar 2.2 peranan sektor pdrb" (tengah baris, dua kolom) | **calon 1: korban**, kini benar |
| PDRB LU `2223fbff` gambar 2 | 23, "gambar **23**/**24**/**25** ..." | 11, "... (persen) gambar 2 proporsi rumah tangga menurut status" | **calon 2: korban**, kini benar |
| PDRB LU `fed52821` gambar 2 | 23, "gambar **23**/**24**/**25** ..." | kosong | **calon 3: korban**; nilai lama pasti salah, kosong lebih benar (lihat bawah) |
| IKR `b4541a05` lampiran 1 | 161, "lampiran 1 relative standard error (rse) persentase perempuan" | tidak berubah | **calon 4: BUKAN korban.** Calon palsu: halaman 161 juga ditunjuk lampiran 13 (di bawah), dan itulah yang membuatnya terdeteksi |
| IKR `b4541a05` lampiran 13 | 161, "lampiran **137**" (folio berjalan) | 166, "lampiran 13 relative standard error (rse) angka partisipasi sekolah" | korban di luar daftar calon, kini benar |
| IKR `b4541a05` lampiran 14 | 165, "lampiran **141**" (folio berjalan) | 166, "lampiran 14 relative standard error (rse) angka partisipasi murni" | korban di luar daftar calon, kini benar |
| Impor `ff0ff482` lampiran 3 | 47, "lampiran **31**" (folio berjalan) | 48, "lampiran 3. perkembangan impor kalimantan selatan berdasarkan pelabuhan bongkar" | korban di luar daftar calon, kini benar |
| NTP `d8082cb1` lampiran "6" ×2 | 40, "lampiran **6.2**." (rujukan di halaman badan) | 54, "lampiran 6 indeks harga yang diterima petani (it) ..." | korban; kini MENDEKATI (lihat bawah) |

Keempat korban di luar daftar calon tidak terdeteksi kemarin karena
pemicunya folio berjalan, bukan entri lain. Pendeteksi calon hanya mencari
pasangan entri yang berhalaman sama.

**fed52821 gambar 2 menjadi kosong.** Keterangan aslinya ada di dua tempat:
- hal. 5: halaman Daftar Gambar, memang dilewati;
- hal. 11: di TENGAH baris dua kolom dengan titik ("... di gambar 2.
  proporsi ru...").

Aturan "tengah baris" lama mensyaratkan huruf tepat sesudah penanda, jadi
titik membuatnya ditolak. Perilaku itu tidak diubah oleh perbaikan ini.
Melonggarkannya untuk titik bisa menjadi perbaikan kecil terpisah.

**NTP lampiran "6" ×2:** kedua entri itu sebenarnya lampiran 6.1 dan 6.2,
tetapi jalur daftar membacanya sebagai "6" dengan judul berawalan
"1 ..."/"2 ...". Keduanya termasuk kelompok kembar yang sudah diketahui.
- Lama: hal. 40 (halaman badan, folio cetak 26), salah.
- Baru: hal. 54, halaman keterangan "Lampiran 6"; meleset 1-2 halaman
  untuk sub-lampirannya (semestinya hal. 55/56 menurut selisih +14
  publikasi itu). Lebih dekat dan tidak lagi menunjuk halaman yang tidak
  berkaitan.

## Sampel kab/kota (tidak masuk DB utama)
Terhadap parser sesudah C3: **0 perubahan**.

## Pemuatan dan baseline
- Cadangan: `~/cadangan-bps/db_pencarian_bps-20261109-0952-sebelum-awalan.sql`,
  terbukti bisa dipulihkan.
- Dimuat dengan `perbarui.py --lokal --paksa` (log `awalan_muat_log.txt`,
  exit 0, tanpa kunci API).
- Database = uji kering di 79/79 publikasi, medan dan urutan sama;
  `teks_ternormalisasi` kosong: 0.
- **Baseline:** `potret-79-sesudah-awalan.json`, 79 publikasi, 6.821 entri,
  SHA-256 `f1f88dc42f4ff911ac736d801a06274b8a4e04735e17be0fd8c3b0af6b8aded4`.
  Terhadap `potret-79-sesudah-C3.json`: 8 perbedaan di 6 publikasi, persis
  8 entri di atas.
- **Daftar perubahan disengaja:** `awalan-perubahan-20261109.tsv`.
