# Saringan watermark hanya membuang teks berputar: DIBATALKAN (17 Nov 2026)

Pelaksanaan rancangan `rancangan-saringan-miring-20261118.md` (disetujui pemilik
project 17 Nov 2026 dan dikerjakan pada hari yang sama, bukan 18 Nov).
Produksi tidak disentuh.

**Keputusan: tidak meyakinkan, jadi dibatalkan dan dicatat sebagai utang
teknis.** Syarat rancangan ("sampel >= 27/30 **tanpa memburuk**") tidak
terpenuhi.
- Kode dikembalikan (`git checkout`).
- Database uji dipulihkan dari dump yang dibuat sebelum regresi.
- Perubahan kodenya disimpan sebagai patch
  `saringan-miring-20261117/usulan-saringan-berputar.patch`, supaya bisa
  dikerjakan ulang bersama mitigasinya.

## Perubahan yang diuji

`_bukan_watermark`: buang karakter hanya bila `abs(m[1]) >= 0,01` (berputar).
Dulu karakter juga dibuang bila `abs(m[2]) >= 0,01` (miring sintetis/shear).
Kasus uji baru di `tests/uji_pipeline.py` bagian I ("saringan-berputar":
tegak, miring, watermark 45°, vertikal, tanpa matriks): kode lama SALAH, kode
baru 11/11 OK. Kasus ini ikut dikembalikan bersama kodenya dan ada di patch.

## Langkah 0-3: lulus

| Langkah | Hasil |
|---|---|
| 0. Pindai penuh 307 PDF (45.960 halaman) | 45.510 karakter miring di **76 publikasi** (773 halaman). **0 watermark berbentuk shear**. Dua URL di antara karakter miring adalah teks asli: prosa `4e7821d9` hal. 23 dan baris Sumber `f3fa3067` hal. 36. Semua 1.485.490 karakter berputar juga ber-`m[2]` ≠ 0, jadi aturan lama dan baru membuang watermark yang sama. |
| 1. Pemilihan halaman OCR | Halaman "tanpa teks" hanya berubah di 2 publikasi bertekst (579e2194: 13 → 12, 2eae0ae6: 6 → 5). Tidak ada publikasi yang melewati ambang 50%, dan 8 target OCR tetap. Jadi `ocr.py` tidak perlu saringan terpisah. |
| 2. Kasus uji | Lihat di atas. |
| 3. Uji kering 76 publikasi | 11 berubah, 0 kunci hilang. |

## Langkah 4: regresi penuh 306 publikasi (database uji)

`perbarui.py --db-uji --lokal --paksa`: sukses, 10.48-11.54, kode keluar 0
(log `data/log_pembaruan/20261117-104849.log`). Potret sebelum/sesudah dan
`perubahan.txt` ada di folder `saringan-miring-20261117/`.

| | Hasil |
|---|---|
| Publikasi berubah | **11**, semuanya punya karakter miring dan sama dengan uji kering |
| Publikasi tanpa karakter miring yang berubah | **0** (230 publikasi) |
| Kunci hilang | **0** |
| Kunci baru | 12 (Tabalong DA 2025 6, IKR Banjarmasin 6) |
| Entri | 24.490 -> 24.502 |

Semua perubahan bisa dijelaskan (M1-M4). Yang tidak berasal LANGSUNG dari
karakter miring ada dua mekanisme, dan keduanya dibuktikan di PDF:

1. **Spasi miring.**
   - Spasi di "Tabel 4.2", "Tabel 6.1", "Tabel 8.1", "Tabel 8.2" (IKR
     Banjarmasin, Daftar) dan "Tabel 6.3" (Banjar Kesra, badan hal. 56)
     bermatriks `(1, 0, 0,333, 1)`.
   - Saringan lama membuangnya, sehingga kata menempel ("Tabel4.2"), label
     tidak dikenali, dan entri tergabung ke entri sebelumnya.
   - Kini terpisah: 6 kunci baru (M3). Halaman cetaknya (45, 47, 48, 65, 80,
     81) sudah ada sebelumnya di judul gabungan.
2. **Gaya dominan halaman bergeser.** Kata miring kini ikut menghitung gaya
   dominan jalur badan (risiko yang sudah dicatat di rancangan).
   - Sakernas Tanah Bumbu (`579e2194`), hal. 93 dan 143: dominan pindah dari
     Lato 5 pt (salinan keterangan PUTIH tersembunyi) ke Lato-Bold 9-10 pt.
     - Aturan keterangan tak terlihat kini aktif, dan keterangan yang terlihat
       dipakai.
     - Tabel 25 mendapat judul edisi yang benar (Agustus 2025, bukan sisa
       Februari).
     - Tabel 65 pindah dari hal. 143 ke hal. 141. Dulu salinan putih
       "Tabel 65" menunjuk halaman yang terlihatnya Tabel 67; kini menunjuk
       keterangan Tabel 65 dengan folio 89 = halaman cetaknya.
   - Hal. 153: dominan lama adalah gaya keterangan itu sendiri (28 kata),
     sehingga Tabel 76 disangka prosa. Kini diterima (sumber daftar ->
     keduanya, halaman tetap).

## Langkah 5: sampel manual

**Tabalong DA 2025, 13 entri** (6 tabel yang kembali: 4.1.3, 4.1.12, 4.3.1,
4.3.5, 4.4.2, 4.4.3; dan 7 entri yang dulu menyerapnya):
- **13/13 benar**: judul Indonesia + Inggris tanpa serapan tetangga, halaman
  cetak = Daftar (nomornya tercetak miring), halaman fisik = selisih bab +36.
- Dua potongan Inggris tanpa nomor baru (hal. 89 dan 136) adalah separuh 4.1.1
  dan 4.3.3, dua entri yang sudah cacat sebelum perubahan ini.

**30 entri berubah acak di luar Tabalong** (seed 20261118, dari 43). Tiap
entri dicocokkan dengan baris Daftar (teks miring ditandai) dan keterangan di
halaman fisiknya.

| Hasil | Jumlah |
|---|---|
| Benar | 24 |
| Cacat ringan, tidak memburuk | 3 |
| **Memburuk** | **3** |

Cacat ringan:
- 9a9fc81e 1.1: sampah "10" di ujung judul diganti kop tabel "Variabel
  Konsep Lama Konsep Baru";
- d42af148 gambar 6.2 dan tabel 4.1: judul kini lengkap, tetapi membawa folio
  halaman Daftar "xi"/"ix" (utang teknis lama: folio di baris sendiri).

Yang memburuk:

| Entri | Sebelum | Sesudah | Sebab |
|---|---|---|---|
| Banjar DA 2026 (`fd585db0`) tabel 4.1.3 | judul bersih, hal. 93 | judul + "NNuummbbeerr ooff SScchhoooollss ...", **halaman cetak hilang**, dan entri sampah baru "22002255//22002266" hal. 93 | baris Inggris miring di Daftar digambar DUA KALI di posisi yang sama (efek tebal palsu), sehingga setiap huruf terbaca ganda |
| IKR Banjarmasin (`d42af148`) lampiran 10 | fisik 103 perkiraan, **benar** | fisik 105, tabel lain (meleset 2) | lihat di bawah |
| Banjar Kesra (`caef04ac`) tabel 6.3 | judul bersih, fisik 56 perkiraan | judul + kop tabel "Status Penguasaan Tempat Tinggal Persentase", fisik 56 asli | spasi miring memulihkan keterangan "Tabel 6.3", tetapi penyerapan baris judul ikut mengambil kop tabel |

Di luar sampel, IKR Banjarmasin lampiran 8 dan 9 juga memburuk: dari tanpa
halaman fisik menjadi halaman yang salah (103 dan 104; lampiran 9 seharusnya
103, dan tabel lampiran 8 tidak ada di badan).

**Penyebab lampiran IKR Banjarmasin:**
- Kesalahan sumber: badan PDF tidak memuat Lampiran 1, 7, dan 8 versi Daftar
  (yang di Daftar tercetak "Kesalahan! Bookmark tidak ditentukan"), sehingga
  Lampiran badan 6-10 = Lampiran Daftar 9-13.
- Dulu `lengkapi_halaman_fisik` tidak memasangkan nomor yang sama ke tabel yang
  salah, karena syarat `MIN_KATA_JUDUL` (kata judul harus ada di halaman) tidak
  terpenuhi.
- Kini judul Daftar membawa "Relative Standard Error", teks miring yang juga
  tercetak di SETIAP halaman lampiran. Kata seragam itu mencukupkan syarat kata
  judul, sehingga pengaman itu melemah.

**Sampah dari teks miring, dicari khusus di seluruh potret:**
- "Tahukah Anda?" 1 -> 1 (sudah ada sebelumnya);
- "canva", "Dilarang", "wrap text", "in front of", "hak cipta" 0 -> 0;
- huruf ganda (4 pasang berturut-turut) 27 -> 28, satu-satunya yang baru
  adalah Banjar 4.1.3.

## Langkah 6: dampak ke pencarian

12 kueri uji, database uji sebelum (dipulihkan dari dump ke database sementara)
vs sesudah:
- **top-1 kedua belas kueri sama**;
- pergeseran hanya di batas 20 hasil:
  - "jumlah penduduk menurut kecamatan": Tabalong 4.3.1 baru masuk;
  - "penduduk miskin": Tabalong gambar 4.1 kini berjudul dwibahasa, skornya
    turun dari 79,5, dan tergeser;
  - "statistik ekspor impor": urutan entri berskor sama 61,3.

## Pembatalan

1. Patch disimpan, lalu `git checkout -- app/services/ekstraksi_pdf.py
   tests/uji_pipeline.py`.
2. Database uji: DROP, lalu CREATE (utf8mb4_unicode_ci, sama dengan
   sebelumnya), lalu dipulihkan dari
   `C:/Users/Dani/cadangan-bps/db_pencarian_bps_uji-20261117-sebelum-saringan-miring.sql`.
3. Bukti:
   - 6/6 tabel sama jumlah baris dan CHECKSUM dengan pulihan dump yang sama di
     database sementara;
   - potret entri sama byte demi byte dengan `potret-sebelum.tsv`;
   - `versi_data` kembali 1588 (regresi 1894).
4. Database sementara `db_pencarian_bps_miringlama_uji` dihapus.

## Kalau dikerjakan ulang (usulan, BELUM disetujui)

Manfaatnya nyata: 12 kunci kembali, judul dwibahasa lengkap, dan 3 keterangan
Sakernas tidak lagi tertukar salinan tersembunyi. Yang perlu diatasi dulu:

1. **Huruf ganda:** buang karakter miring yang menumpuk persis di posisi yang
   sama (teks, x0, top sama) sebelum `extract_words`, misalnya
   `dedupe_chars` hanya untuk karakter miring. Ini juga menghapus entri sampah
   "22002255//22002266".
2. **Pengaman kata judul `lengkapi_halaman_fisik`:** kata yang muncul di semua
   judul satu tipe dalam satu publikasi ("relative", "standard", "error") tidak
   dihitung untuk `MIN_KATA_JUDUL`. Mengubah aturan ini menyentuh semua
   publikasi, jadi butuh regresi penuh tersendiri.
3. **Kop tabel terserap ke keterangan badan** (caef04ac 6.3, 9a9fc81e 1.1):
   sejenis dengan cacat jalur badan yang sudah diterima (2,5-2,9%); belum ada
   usulan yang sempit.

Perkiraan: setengah hari termasuk regresi penuh (±66 menit).
