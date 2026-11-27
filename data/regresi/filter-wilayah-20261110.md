# Filter wilayah di UI pencarian (10 Nov 2026)

Dikerjakan sesudah korpus di memori (`korpus-memori-20261110.md`), atas
rancangan pemilik project:
- dropdown wilayah di samping kotak cari;
- deteksi nama/singkatan wilayah dari kueri, dengan pita "dipasang otomatis"
  dan tombol Batalkan;
- label wilayah di setiap hasil;
- bagian terpisah "Juga ada di publikasi provinsi".

## Rancangan
- **`wilayah.deteksi(token)`** (`app/services/wilayah.py`) mencocokkan per
  KATA UTUH.
  - Bentuk nama yang dikenali:
    - `nama` tanpa awalan Kab./Kota;
    - `nama_lain` (ejaan API "kota baru", "banjar baru", baru di `wilayah.json`);
    - `singkatan`, yang statusnya masih "belum dikonfirmasi".
  - Frasa terpanjang menang. Awalan "kab/kabupaten/kota" yang langsung
    mendahului nama ikut dibuang.
  - Provinsi tidak dideteksi dari kueri dan hanya bisa dipilih lewat dropdown.
- **`pencarian_wilayah.tentukan_filter()`** menentukan filter:
  - pilihan dropdown petugas didahulukan;
  - kalau tidak ada, dipakai wilayah yang terdeteksi, asalkan tepat satu dan
    belum dibatalkan;
  - kata wilayah dibuang dari kueri yang dinilai HANYA kalau wilayahnya sama
    dengan filter yang aktif.
- **`mesin_pencari.cari(..., domain=, provinsi=)`**:
  - menyaring di korpus memori lewat indeks per domain (`entri_per_domain`,
    `publikasi_per_domain`);
  - entri provinsi dinilai dengan korpus dan kueri yang sama.
  - `domain=None` menjalankan jalur yang sama persis dengan sebelumnya.
- **Parameter URL** (form GET, berfungsi tanpa JavaScript):
  - `w`: kode wilayah dari dropdown;
  - `wo`: wilayah yang dipasang otomatis di halaman sebelumnya. `w == wo`
    berarti petugas tidak memilihnya, jadi deteksi diulang terhadap kueri
    baru;
  - `abaikan`: wilayah yang deteksinya dibatalkan.
- **Kueri yang hanya berisi nama wilayah** ("tanah laut") menampilkan seluruh
  publikasi wilayah itu, terbaru dulu, tanpa skor.
- **`log_pencarian.wilayah_filter`** (CHAR(4), nullable) menyimpan filter
  yang aktif.
  - Kolom ini ditambahkan ke database lama oleh `pastikan_kolom()`, sekali per
    proses di awal request.
  - Juga tercantum di `migrasi_multidomain.py`.

## Syarat 1: kata wilayah tidak ikut dinilai
**Premisnya tidak didukung data.** Judul tabel kab/kota justru SERING
menyebut nama wilayahnya sendiri:

| Tipe | Menyebut nama wilayahnya sendiri |
|---|---|
| tabel | 6.345 dari 8.389 (75,6%) |
| lampiran | 1.407 dari 1.734 (81,1%) |
| gambar | 982 dari 1.293 (75,9%) |
| isi (bab) | 215 dari 5.307 (4,1%) |
| semua | 8.949 dari 16.723 (53,5%) |

Hitungan ini diperiksa dengan sampel acak 12 + 12 judul (seed 20261110).
Semuanya benar menyebut atau tidak menyebut nama wilayahnya.

Membuang kata wilayah tetap lebih baik, karena tiga alasan:

1. **Singkatan tidak pernah tercetak di judul.** Kalau "hss", "bjm", atau
   "tala" ikut dinilai, coverage setiap entri turun. Hasilnya dengan filter
   terpasang:
   - "pdrb hss": 0 ditemukan / 3 saran, berbanding 15 / 20 kalau dibuang;
   - "inflasi bjm": 0 / 20 berbanding 19 / 9;
   - "penduduk miskin tala": 0 / 15 berbanding 9 / 7.
2. **Konsisten.** Lima cara berikut memberi hasil yang IDENTIK di semua medan:
   - dropdown Tanah Laut + "penduduk";
   - "penduduk tanah laut";
   - "penduduk tala";
   - "penduduk kabupaten tanah laut";
   - dropdown + "penduduk tanah laut".

   Hal yang sama berlaku untuk Kotabaru (3 bentuk) dan HSS (3 bentuk).
3. **Di dalam filter, kata wilayah tidak membedakan relevansi.** Semua
   kandidat sudah dari wilayah itu. Kata wilayah hanya mengunggulkan tabel
   yang kebetulan menyebutnya di atas bab dan tabel yang tidak menyebutnya.

Efek sampingnya: untuk nama lengkap, peringkat bergeser ke entri pendek. Untuk
"penduduk tanah laut", yang teratas kini bab "Penduduk" (96,7), bukan
"Piramida Penduduk Kabupaten Tanah Laut" (86,7).

Perbandingan lengkap (a) sekarang, (b) filter dengan kata wilayah tetap
dinilai, dan (c) rancangan baru, untuk 6 kueri, ada di
`filter-wilayah-20261110/bukti-kata-wilayah.txt`.

## Syarat 2: "Juga ada di publikasi provinsi"
Untuk "penduduk tanah laut", "inflasi bjm", dan "luas panen padi kotabaru",
bagian provinsi:
- hanya berisi entri domain 6300;
- sama persis (entri_id dan urutannya) dengan 10 teratas
  `cari(<kueri tanpa kata wilayah>, domain="6300")`.

Bagian ini tidak tampil kalau filternya provinsi sendiri. Untuk kueri satu
kata ("penduduk"), kesepuluh entri teratasnya judul bab. Itu perilaku skor
yang sudah ada sejak sebelum filter wilayah (entri pendek menang), bukan
akibat filternya.

## Syarat 3: regresi
| Uji | Hasil |
|---|---|
| 10 kueri uji tanpa nama wilayah, "Semua wilayah": mesin sebelum perubahan vs jalur baru | **identik 10/10** di setiap medan lama (urutan, skor, jumlah, publikasi). Medan baru hanya tambahan: `domain`, `wilayah`, `provinsi`, `filter`, `hanya_wilayah` |
| Pembanding mampu mendeteksi beda | ya: urutan `ditemukan` yang dibalik terdeteksi di 8/10 (2 kueri tanpa `ditemukan`) |
| 2 kueri uji bernama wilayah ("penduduk tanah laut", "luas panen padi kotabaru") | otomatis memasang 6301 / 6302. Sesudah **Batalkan**: **identik** dengan sekarang |

## Syarat 4: kasus wajib
| Kueri | Filter |
|---|---|
| penduduk banjar | Kab. Banjar (kata utuh) |
| penduduk banjarmasin / banjarbaru | Kota Banjarmasin / Kota Banjarbaru, bukan Kab. Banjar |
| penduduk banjar baru | Kota Banjarbaru (frasa terpanjang) |
| penduduk kotabaru / kota baru | Kab. Kotabaru, keduanya |
| penduduk tala, pdrb hss, inflasi bjm | Tanah Laut, HSS, Banjarmasin |
| penduduk miskin, jumlah hotel kabupaten kota 2024 | tanpa filter ("kota" tanpa "baru" tidak dideteksi) |
| tanah laut | publikasi Tanah Laut saja (17), terbaru dulu |
| penduduk tanah laut dan kotabaru | tanpa filter + pita info "lebih dari satu wilayah" |

Risiko yang diketahui:
- "banjar" juga nama suku ("penduduk suku banjar" akan memasang Kab. Banjar).
  Pita dan tombol Batalkan ada untuk kasus seperti ini.
- Singkatan belum dikonfirmasi tim PST.

## Syarat 5 dan 6: halaman, URL, log
`test_client` tanpa JavaScript: **37 pemeriksaan, 0 gagal**. Yang diperiksa:
- dropdown 15 pilihan, `?w=` memilih dropdown;
- pita dan tombol Batalkan, `wo`/`abaikan` di form;
- deteksi ulang saat form dikirim ulang dengan kueri baru;
- `w` tidak valid diabaikan;
- kueri di-escape;
- tautan "di semua wilayah" saat hasil kosong;
- notice BPS di beranda dan halaman hasil.

Halaman admin (beranda, log, periksa) dan `/api/saran` tetap 200.

**Log:** 5 pencarian uji berpenanda unik tercatat dengan `wilayah_filter`
yang benar:
- 6301 otomatis;
- 6372 dropdown;
- NULL semua wilayah;
- NULL sesudah dibatalkan;
- 6301 untuk kueri wilayah saja.

Barisnya lalu dihapus: log kembali 51 baris, max id 53, dan ke-51 baris lama
bernilai NULL.

**Tangkapan layar** (`filter-wilayah-20261110/`):
- `beranda.png`;
- `hasil-atas.png` (kueri "penduduk tanah laut");
- `hasil-bawah-provinsi.png` (bagian provinsi dan footer);
- `ponsel-390px.png`.

Edge headless memaksa viewport minimal 504 px. Karena itu tampilan ponsel
dipotret lewat iframe 390 px, dan potret langsung pada 390 px menyesatkan
(terlihat terpotong).

## Syarat 7: waktu
Pengukuran bergantian dalam satu proses, 10 kueri tanpa wilayah, 20 ulangan:

| | Rata-rata median | Terlambat |
|---|---|---|
| jalur baru, Semua wilayah | 84,6 / 84,7 ms | 189 ms |
| mesin sebelum perubahan | 83,7 ms | 189 ms |

`ukur_kinerja.py` resmi (`data/ukur_kinerja/20261110-1340-filter-wilayah.json`)
kini juga memuat bagian `per_kueri_wilayah`:
- 12 kueri lama: rata-rata 81 ms, terlambat 192 ms;
- 9 kueri berfilter, termasuk bagian provinsi: **terlambat 59 ms**. Contohnya
  "penduduk tanah laut" 21 ms, "jumlah penduduk menurut kecamatan" di
  Banjarmasin 59 ms, kueri wilayah saja 1 ms.
