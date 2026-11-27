# Rancangan: saringan watermark hanya membuang teks yang DIPUTAR (untuk 18 Nov 2026)

Disetujui untuk dikerjakan Rabu 18 Nov 2026 (pemilik project, 17 Nov).
Dokumen ini hanya rancangan. Kode belum diubah.

## Masalah

`_bukan_watermark` (`app/services/ekstraksi_pdf.py`) membuang karakter bila
`abs(m[1]) >= 0,01` ATAU `abs(m[2]) >= 0,01`, dengan `m` = matriks
transformasi karakter `(a, b, c, d, e, f)`:

| Jenis | Matriks | Dibuang sekarang | Seharusnya |
|---|---|---|---|
| Teks tegak | (s, 0, 0, s) | tidak | tidak |
| Watermark BPS, diputar 45° | (0,707s, 0,707s, −0,707s, 0,707s) | ya | ya |
| Miring sintetis (shear) | (s, 0, 0,0875s, s) | **ya** | **tidak** |

Teks miring sintetis adalah teks asli yang dicetak miring. Di Tabalong DA
2025, 11 dari 83 nomor halaman Daftar Tabel tercetak miring dan ikut terbuang,
sehingga 6 tabel tergabung ke tabel sebelumnya
(`kolom-judul-20261117.md`).

## Perubahan

Satu baris di `_bukan_watermark`:

```python
return abs(m[1]) < 0.01          # dulu: abs(m[1]) < 0.01 and abs(m[2]) < 0.01
```

Docstring disesuaikan: yang dibuang adalah teks berputar, baik watermark 45°
maupun teks vertikal (sama dengan sekarang). Teks yang hanya miring
dipertahankan.

Pemakai fungsi ini, semuanya terdampak:
1. `_kata_halaman`, jalur Daftar;
2. `ekstrak_badan`, keterangan tabel/gambar dan penanda gaya;
3. `lengkapi_halaman_fisik` / `lengkapi_halaman_isi`;
4. **`ocr.halaman_tanpa_teks`**: menghitung karakter non-watermark untuk
   memilih halaman OCR. Ini yang paling berbahaya, lihat langkah 1.

## Yang sudah diketahui (pindai 17 Nov, 60 halaman pertama, 307 PDF)

- 54 publikasi punya karakter miring sintetis (17.057 karakter). Watermark
  tidak berubah: 1.440 karakter berputar per 60 halaman di setiap PDF.
- Isinya sebagian besar teks Inggris dwibahasa, juga:
  - catatan hak cipta ("Dilarang mereproduksi ...");
  - kotak "Tahukah Anda?";
  - sisa perangkat desain ("www.canva.com", "wrap text: in front of text").
- Dua publikasi OCR punya karakter miring: PDRB Tapin LU dua edisi (105 dan
  106 karakter).

## Langkah besok

Urutannya dari yang murah ke yang mahal. Tiap langkah punya syarat berhenti.

### 0. Pindai penuh, hanya baca (±20 menit)

Pindai SEMUA halaman di 307 PDF, bukan hanya 60 halaman pertama.
- Per publikasi: jumlah karakter miring dan jumlah halamannya.
- Pastikan tidak ada watermark yang hanya miring, yaitu teks
  "bps.go.id"/"https" di antara karakter `m[1]` = 0, `m[2]` ≠ 0.
- **Berhenti** kalau ada watermark berbentuk shear: aturannya salah.

### 1. Dampak ke pemilihan halaman OCR (±15 menit)

Hitung ulang `ocr.halaman_tanpa_teks` untuk 307 PDF dengan saringan baru dan
bandingkan dengan saringan lama.
- Harus sama: daftar halaman OCR 8 publikasi target, dan tidak ada publikasi
  baru yang melewati `AMBANG_PUBLIKASI` (50%).
- **Kalau berbeda:** ocr.py tetap memakai saringan lama (fungsi terpisah
  `_bukan_watermark_ketat`). Keputusan OCR tidak berubah, dan pengecualian ini
  ditulis di CLAUDE.md. Pilihan ini dipakai hanya kalau langkah 1 berbeda.

### 2. Kasus uji dulu

`tests/uji_pipeline.py` bagian I, kasus baru: daftar sintetis dengan nomor
halaman miring (matriks shear) dan watermark 45°. Harapannya nomor miring
terbaca dan watermark terbuang. Kasus ini gagal di kode lama dan lulus di kode
baru.

### 3. Uji kering 54 publikasi (±30 menit)

Ekstraksi dengan kode baru, lalu dibandingkan per kunci dengan database uji
(`kering.py`), tanpa menulis.
- Publikasi tanpa karakter miring terbukti tidak berubah: masukan parser
  identik.
- **Berhenti** kalau ada kunci bernomor hilang. Laporkan contohnya sebelum
  regresi penuh.

### 4. Regresi penuh 306 publikasi di database uji (±1,5 jam)

Sebelum mulai, buat mysqldump database uji untuk pemulihan kalau rancangan
ini dibatalkan.

`perbarui.py --db-uji --lokal --paksa`, dengan potret sebelum/sesudah per
kunci (`banding_regresi.py`).

Perubahan yang **bisa dijelaskan** oleh pola ini:

| Kode | Perubahan | Cara membuktikan |
|---|---|---|
| M1 | Judul bertambah teks | Setiap kata baru ada di karakter miring PDF itu |
| M2 | Halaman cetak kosong → angka | Angka itu karakter miring di halaman Daftar |
| M3 | Kunci baru, terpisah dari entri yang dulu menyerapnya | Judul entri lama berkurang persis sebanyak judul entri baru |
| M4 | `halaman_fisik` / `sumber` berubah | Diperiksa per entri; kartu keterangan baru berasal dari teks miring |

**Berhenti dan laporkan** kalau:
- ada kunci bernomor hilang;
- ada perubahan di luar M1-M4;
- ada publikasi tanpa karakter miring yang berubah.

### 5. Sampel manual

- Ke-6 tabel Tabalong 2025 yang kembali, dan entri yang dulu menyerapnya.
- 30 entri berubah secara acak di LUAR Tabalong (seed 20261118), dibaca satu
  per satu terhadap PDF. Bandingkan judul, nomor, halaman cetak, dan halaman
  fisik.
- Sisa sampah dari teks miring yang masuk ("Tahukah Anda?", "www.canva.com",
  catatan hak cipta) dicari khusus.

### 6. Dampak ke pencarian

Jalankan 12 kueri uji sebelum dan sesudah. Judul yang bertambah teks Inggris
sedikit lebih panjang, sehingga penalti panjangnya naik. Catat top-1 dan
pergeseran skor. Tidak ada yang diubah di scoring.

### 7. Keputusan

- **Meyakinkan:** 0 kunci hilang, semua perubahan masuk M1-M4, dan sampel ≥
  27/30 tanpa memburuk. Lalu commit (kode, kasus uji, potret, laporan) dan
  jalankan `uji_pipeline.py --hanya IC`. Push dan pemuatan produksi (terarah,
  hanya publikasi berubah) menunggu persetujuan.
- **Tidak meyakinkan:**
  - kode dikembalikan dengan `git checkout`;
  - database uji dipulihkan dari mysqldump yang dibuat sebelum langkah 4,
    lalu dibuktikan sama dengan CHECKSUM;
  - usulan ini dicatat sebagai utang teknis di CLAUDE.md, beserta temuan
    langkah 0-5.

## Perkiraan waktu

Langkah 0-3 ±1,5 jam, regresi ±1,5 jam (bisa berjalan sambil menyiapkan
sampel), analisis dan sampel ±2 jam. Total ±5 jam. Kalau regresi belum mulai
pukul 12.00, regresi dijalankan sore dan analisisnya Kamis pagi.

## Risiko yang sudah terlihat

- Teks dekoratif miring di halaman badan bisa mengubah **gaya dominan**
  halaman (penanda gaya jalur badan) dan menyusup sebagai baris prosa. Aturan
  superset terhadap keterangan asli harus tetap berlaku: dicek lewat "0 kunci
  hilang".
- Teks Inggris miring di Daftar bisa masuk ke judul, sehingga judul lebih
  panjang. Ini disengaja (CLAUDE.md: judul dwibahasa disimpan apa adanya),
  tetapi bisa memicu cacat gabung baru di mode tanpa-label/nomor-sebaris.
- PDRB Tapin LU (OCR) punya teks miring: langkah 1 menentukan apakah OCR
  dipisah.
