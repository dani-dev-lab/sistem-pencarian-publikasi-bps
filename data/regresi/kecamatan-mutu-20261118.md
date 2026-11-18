# Kecamatan Dalam Angka di database uji: cache OCR, muat HST 2026, mutu (18 Nov 2026)

Produksi tidak disentuh: CHECKSUM `entri_dokumen`, `publikasi`, `versi_data`
produksi sebelum = sesudah (`kecamatan-mutu-20261118/produksi_*.txt`).

## 1. Cache OCR sesudah mati lampu (hanya dibaca)

Alat: `kecamatan-mutu-20261118/cek_cache.py` (isinya: setiap `_meta.json` dan
`NNNN-easyocr.json` di folder cache 26 target di-`json.load`, dicek 0 byte,
kunci wajib, sidik PDF = sidik meta, halaman di luar daftar meta, sisa `.tmp`).

- **0 berkas rusak, 0 `.tmp`, 0 sidik berbeda.** `_tulis_atomik` (tulis
  `.tmp` lalu `os.replace`) bekerja: halaman yang sedang di-OCR saat listrik
  padam tidak meninggalkan berkas.
- Publikasi 1-7 (HST 2026): 104/104 halaman.
- Publikasi 8 (Labuan Amas Utara 2026) terhenti sesudah **halaman 16**,
  bukan halaman 1 (log `data/log_ocr/20261117-181751.log` berakhir 20:37:51
  di hal. 16). Run 18 Nov 07:52 melanjutkan dari hal. 17.
- Dua target 2025 sudah punya 3 halaman cache dari uji sebelumnya
  (Tatah Makmur, Binuang); bukan sisa kejadian semalam.

## 2. Muat 7 publikasi HST 2026 ke database uji

`ocr-pemuatan-20261113/muat_ocr_terarah.py kecamatan-mutu-20261118/hst2026_lengkap.json --sasaran uji`
(memeriksa cache lengkap SEBELUM menulis; OCR baru = berhenti). 5,7 detik.

| Publikasi 2026 | Entri OCR | Edisi 2025 (bertekst) |
|---|---|---|
| Barabai | 46 | 49 |
| Batang Alai Selatan | 41 | 48 |
| Batang Alai Timur | 41 | 48 |
| Batang Alai Utara | 43 | 49 |
| Batu Benawa | 46 | 48 |
| Hantakan | 45 | 49 |
| Labuan Amas Selatan | 46 | 48 |

Pembanding bertekst edisi yang sama: Haruyan 2026 = 49.

Bukti: entri dan publikasi di luar 7 target identik sebelum/sesudah
(jumlah + BIT_XOR CRC32 per baris, `sidik_luar_target.sql`); `log_pencarian`
dan `kategori` CHECKSUM sama; `versi_data` uji 1926 -> 1933; 7 target
`halaman_ocr` = 104. Mutu entri OCR ini BELUM disampel.

## 3. Mutu publikasi bertekst: DI BAWAH 27/30, pekerjaan dihentikan

Populasi: 286 publikasi kecamatan di luar 26 target OCR, 18.496 entri.
Sampel acak 30 entri, seed 20261118 (`sampel_mutu.py`, keluaran
`sampel_mutu_20261118.txt`; bukti = baris Daftar yang memuat nomor + folio/kop
halaman yang dituju tombol PDF). Dibaca satu per satu.

| Nilai | Jumlah | Nomor sampel |
|---|---|---|
| Benar seluruhnya (nomor, judul, hal. cetak, tombol PDF) | **20** | 1,3,5,6,7,8,12,13,14,15,16,17,19,20,23,24,25,27,28,30 |
| Entri isi halaman depan (Daftar Isi/Tabel/Gambar, Penjelasan Umum): judul + hal. romawi benar, tanpa tombol PDF | 4 | 10,18,21,22 |
| Tombol PDF benar, halaman cetak hilang (2 juga judul berekor ".3 2"/"3 5") | 4 | 2,4,11,26 |
| Salah | 2 | 9 (blok gabungan tanpa nomor), 29 (tombol "±hal." ke folio 70, seharusnya bab 1) |

Per kriteria: nomor 29/30, judul 27/30, halaman cetak 25/30, tombol PDF
24/30 (4 tanpa tombol, 1 tanpa entri, 1 salah). Catatan #20: Daftar menulis
42, tabelnya di folio 43 (kesalahan sumber); tombol benar.

### Penyebab terpusat di 3 kelompok (dari agregat, bukan sampel)

| Kelompok | Pub | Entri | Tanpa hal. cetak | Tanpa keduanya | Sebab |
|---|---|---|---|---|---|
| Tanah Laut 2025 (6301) | 11 | 919 | 643 | 50 | Nomor tabel di Daftar dicetak berspasi ("1. 1", "2.1. 1"); Daftar Tabel tidak terbaca, tabel hanya dari jalur badan (593 entri badan) |
| Banjar 2026 (6303) | 20 | 1.447 | 830 | 124 | Nomor halaman Daftar berselang titik ("3..3", ".3 5"); halaman tidak terbaca dan menempel ke judul (627 judul); sebagian nomor bab salah ("1.1" untuk 3.1, Aluh-Aluh) |
| Balangan 2025 (6311) | 7 | 422 | 118 | 47 | Blok gabungan tanpa nomor (54) |
| 22 kelompok lain | 248 | 15.708 | 452 | 55 | - |

Di 22 kelompok lain, `halaman_fisik` kosong hampir seluruhnya entri isi
halaman depan (isi tanpa fisik ≈ total tanpa fisik).

### Publikasi 0 entri
18, semuanya target OCR yang cache-nya belum lengkap (Labuan Amas Utara,
Limpasu, Pandawan 2026; Halong 2025 6311; Mataraman, Simpang Empat, Tatah
Makmur 2025 6303; 11 Tapin 2025). Tidak ada publikasi bertekst 0 entri.
Tapin Utara 2025 (target OCR, 83% halaman tanpa teks) punya entri dari halaman
bertekstnya; akan diganti saat dimuat dengan OCR.

## 4. Memori korpus dan waktu pencarian: TIDAK dijalankan
Ditahan karena syarat langkah 3 (sampel jauh di bawah 27/30).
