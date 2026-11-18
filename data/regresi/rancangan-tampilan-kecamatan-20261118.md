# Rancangan: tampilan publikasi Kecamatan Dalam Angka (18 Nov 2026)

STATUS: RANCANGAN, belum ada kode. Pembanding kinerja ada di
`kinerja-kecamatan-20261118.md`.

## 1. Menandai publikasi kecamatan
- **Kolom baru `publikasi.kecamatan`** (VARCHAR, NULL = bukan publikasi
  kecamatan), ditambahkan oleh `skema.pastikan_kolom`.
  - Isinya kunci kecamatan: nama huruf kecil tanpa spasi/tanda baca, misalnya
    `banjarbaruselatan`. Kunci ini menyatukan beda ejaan antaredisi ("Banjar
    Baru Selatan" 2025 / "Banjarbaru Selatan" 2026).
  - Diisi oleh `simpan_metadata` dari judul dengan pola baru di
    `data/wilayah.json`:
    `"pola_kecamatan": "^Kecamatan\\s+(?P<nama>.+?)\\s+Dalam Angka\\s+\\d{4}$"`.
  - Data lama diisi oleh `pastikan_kolom` sekali jalan (idempoten).
- Kenapa bukan `kecualikan_judul`: pola itu mengatur apa yang DITARIK. Kalau
  kecamatan nanti dimasukkan ke produksi, `aktif` menjadi false dan polanya
  tidak dibaca lagi.
- Dicek di database uji: 312/312 judul cocok, 156 kecamatan di 13 kab/kota,
  satu beda ejaan. Nama tampilan diambil dari edisi terbaru.

## 2. Daftar nama kecamatan: dari mana
Diambil dari database: `SELECT domain, kecamatan, judul` publikasi yang
kolomnya terisi, lalu dikelompokkan per domain dan diurutkan menurut abjad.
- Tidak ada daftar manual. Kecamatan baru ikut muncul saat publikasinya
  ditarik.
- Daftar ini dibangun bersama Korpus, jadi berganti otomatis kalau
  `versi_data` berubah.
- Konsekuensinya, kecamatan yang belum punya publikasi tidak muncul. Bagi
  petugas itu benar, karena tidak ada yang bisa dicari.

## 3. Korpus
`Korpus` mendapat bagian kedua:
- `entri_kec`, `publikasi_kec`, `entri_kec_per_domain`, `entri_per_kecamatan`;
- `entri`, `publikasi`, dan `entri_per_domain` yang sekarang tetap berisi baris
  yang SAMA dan berurutan sama, tanpa kecamatan.

Pencarian tanpa centang memakai bagian lama saja. Simulasi membuktikan waktu
dan hasilnya sama dengan produksi.

## 4. Antarmuka (form GET, semuanya berfungsi tanpa JavaScript)
- **Kotak centang** di form, di bawah kotak cari: "Sertakan publikasi
  Kecamatan Dalam Angka". Bawaannya mati, dan centang dikirim sebagai `kec=1`.
- **Dropdown kecamatan** di sebelah dropdown wilayah: "Semua kecamatan" + daftar
  kecamatan wilayah terpilih.
  - Tampil hanya kalau `w` adalah kab/kota, karena provinsi dan "Semua wilayah"
    tidak punya daftar kecamatan.
  - Tanpa JS, daftarnya dirender server untuk `w` yang sedang aktif.
  - Dengan JS (`app.js`), dropdown ini aktif hanya kalau kotak dicentang, dan
    isinya diganti saat wilayah diganti. Datanya JSON kecil yang ditanam di
    halaman.
  - Memilih kecamatan otomatis berarti `kec=1`.
- **Hasil (`kec=1`)**: urutan halaman yang ada TIDAK berubah. Sesudah
  "Bagian yang ditemukan" / "Bagian yang mungkin Anda cari" muncul seksi baru
  "Dari publikasi Kecamatan Dalam Angka", lalu "Juga ada di publikasi provinsi"
  seperti biasa.
  - Kartu memakai format kartu entri yang sama, ditambah label
    "Kec. Pelaihari · Kab. Tanah Laut · edisi 2026".
  - Ambang sama (>= 50), diurutkan menurut skor, maksimal 20 kartu, lalu
    tautan "tampilkan semua" (`semua_kec=1`).
  - Kueri yang hanya berisi nama wilayah ("tanah laut") + `kec=1`
    menampilkan seksi "Publikasi kecamatan di Kab. Tanah Laut".
- **Kotak info (tanpa centang)**: "Ada [n] bagian lain dari publikasi Kecamatan
  Dalam Angka (rincian per desa)" + tombol "Tampilkan", yaitu URL yang sama
  ditambah `kec=1`.
  - Menghitung n berarti menilai bagian kecamatan, yang memakan biaya sampai
    +210 ms. Supaya respons utama tidak melambat, n dihitung **sesudah halaman
    tampil** lewat `GET /api/kecamatan/jumlah?q=&w=&wo=&abaikan=`. Endpoint ini
    memakai fungsi skor dan ambang yang sama, dan tidak menulis log.
  - Kotak hanya tampil kalau n > 0.
  - Tanpa JS: kotak berisi tautan tanpa angka, "Cari juga di publikasi
    Kecamatan Dalam Angka".
  - **Selama database tidak berisi publikasi kecamatan, seperti produksi
    sekarang, kotak, centang, dan dropdown TIDAK dirender.** Halaman produksi
    tetap sama sampai ada keputusan memuat kecamatan.

## 5. Parameter URL
| Parameter | Arti | Kalau tidak sah |
|---|---|---|
| `q`, `w`, `wo`, `abaikan` | tetap seperti sekarang | - |
| `kec=1` | sertakan kecamatan | selain "1" = mati |
| `kc=<kunci>` | satu kecamatan, misalnya `kc=pelaihari`; menyiratkan `kec=1` | diabaikan + pesan, kalau `w` bukan kab/kota atau kunci tidak ada di `w` |
| `semua_kec=1` | tampilkan semua kartu kecamatan | - |

Deteksi wilayah otomatis tetap berjalan seperti sekarang. `kc` tidak
dideteksi dari kueri (lihat bagian 8).

## 6. Jalur lain yang harus ikut dijaga
- `/api/saran` (SQL LIKE ke seluruh `entri_dokumen`): tambah
  `Publikasi.kecamatan IS NULL`, kecuali `kec=1` dikirim `saran.js` dari kotak
  centang.
- `publikasi_wilayah()` (kueri yang hanya berisi nama wilayah): tanpa
  kecamatan.
- `log_pencarian`: isi kolom lama tetap dari hasil utama. Kolom opsional
  `sertakan_kecamatan` (TINYINT, nullable) mencatat pemakaian centang untuk
  bahan evaluasi tim PST.
- Halaman admin (`/admin/log`) tidak berubah.

## 7. Menjamin hasil tanpa centang IDENTIK dengan sekarang
1. **Jalur kode:** tanpa `kec`, `pencarian_wilayah.cari` memanggil fungsi yang
   sama dengan tuple yang sama. Pencarian kecamatan adalah pemanggilan
   TAMBAHAN yang hasilnya disimpan di kunci baru (`hasil["kecamatan"]`).
   Kunci lama tidak disentuh.
2. **Uji potret HTML di produksi (tanpa kecamatan):** 12 kueri uji + 9 kueri
   wilayah + 5 awalan `/api/saran` dirender lewat test_client sebelum dan
   sesudah perubahan, lalu dibandingkan byte demi byte. Hanya angka
   "waktu ms" yang disamarkan. Syaratnya identik.
3. **Uji di database uji (dengan kecamatan, tanpa centang):** isi hasil
   (publikasi, tipe, nomor, judul, halaman, skor, urutan) = hasil korpus yang
   baris kecamatannya dibuang, dengan cara yang sama seperti
   `simulasi_tanpa_kecamatan.py`. Ditambah: `/api/saran` tidak memuat entri
   kecamatan, dan baris `log_pencarian` sama.
4. **Kinerja:** `ukur_kinerja.py --db-uji` tanpa centang harus setara dengan
   produksi (±5%).
5. Ketiganya masuk `uji_pipeline.py` sebagai bagian baru.

## 8. Deteksi nama kecamatan dari kata kunci: perkiraan saja
**Sekitar 1 hari kerja (6-8 jam)**, termasuk uji dan aturan konflik.
Penyebab utamanya keambiguan:
- "Simpang Empat" ada di Banjar dan Tanah Bumbu.
- 10 nama memuat nama kab/kota ("Tapin Selatan", "Banjarmasin Utara") dan
  bertabrakan dengan deteksi wilayah yang ada.
- Banyak nama kecamatan sekaligus nama ibu kota kabupaten (Martapura,
  Pelaihari, Barabai, Kandangan, Paringin), sehingga "penduduk martapura"
  bisa berarti Kab. Banjar.

Saran: kerjakan sesudah presentasi.

## Perkiraan pengerjaan rancangan ini (tanpa deteksi)
±1 hari: kolom + Korpus 2 jam, form/hasil/kotak info 3 jam, uji identik dan
kinerja 2-3 jam.
