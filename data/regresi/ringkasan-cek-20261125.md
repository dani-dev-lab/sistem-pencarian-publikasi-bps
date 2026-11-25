# Kartu ringkasan "Cek dulu" dan hasil pembaruan, /admin/perbarui (25 Nov 2026)

Tujuannya agar hasil cek mudah dibaca orang non-IT. Hanya database uji yang
dipakai; produksi tidak disentuh; belum di-push.

## Yang berubah

| Berkas | Isi |
|---|---|
| `app/services/ringkasan_pembaruan.py` (baru) | Aturan di satu tempat, berupa fungsi murni: `format_ukuran`, `format_durasi`, `ambang()` (dari wilayah.json), `penarikan_besar`, `ringkas_cek` (4 status + kalimat + 4 angka), `ringkas_pembaruan`, `sisa_ruang_mb` (`shutil.disk_usage` folder PDF) |
| `data/wilayah.json` | `"ambang_penarikan": {"besar_menit": 30, "besar_gb": 1, "cadangan_disk_persen": 20}` + catatan. Tanpa nilai cadangan di kode: kunci hilang/salah = SystemExit berpesan |
| `app/routes/admin.py` | Kartu dihitung saat halaman dibuka (sisa disk dibaca saat itu). **Penjaga server**: POST Mulai pembaruan dengan pilihan SAMA dengan cek sesi ini yang statusnya merah -> HTTP 409, tidak ada proses |
| `app/templates/admin/perbarui.html` | Macro `kartu_ringkasan`, dipakai hasil cek dan ringkasan sesudah pembaruan. Tabel per wilayah dilipat di `<details>` "Lihat rincian per wilayah". Tombol Mulai `disabled` + `aria-describedby` alasan. Kalau ada hasil cek, ringkasan pembaruan terakhir dilipat, supaya tidak ada dua kartu berwarna bersaing |
| `app/static/css/style.css` | Ditambah di akhir, semua pemilih diawali `.panel-ringkasan`. 4 kolom; <= 640 px menjadi 2x2 |
| `scripts/perbarui.py` | Peringatan "Penarikan besar" `--cek-dulu` memakai ambang yang sama (dulu konstanta >= 50 publikasi / 1000 MB / 1 jam) |
| `tests/uji_pipeline.py` | Bagian J (baru); Q5 disesuaikan dengan aturan baru |
| `PANDUAN.md` bagian 4 | "Membaca hasil cek", tabel 4 angka dan 4 warna, ambang di wilayah.json, ringkasan sesudah pembaruan |

**Status (diperiksa berurutan):**

| Status | Syarat |
|---|---|
| abu-abu **Semua sudah terbaru** | 0 publikasi yang akan diproses |
| merah **Ruang disk tidak cukup** | unduhan x (1 + 20%) > sisa ruang disk |
| kuning **Penarikan besar, sebaiknya jalankan malam hari** | perkiraan > 30 menit ATAU unduhan > 1 GB |
| hijau **Siap ditarik** | selain itu |

- Merah didahulukan dari kuning. Sisa disk yang tidak terbaca tidak pernah
  menghasilkan merah.
- Satuan: MB/GB satu desimal dengan koma (1 GB = 1024 MB, sama dengan
  `sumber_bps.ukuran_mb`); detik/menit/jam, perkiraan bertanda ±.
- Kalimat ringkasan menyebut nama wilayah kalau tiga atau kurang; selebihnya
  "dari N wilayah".
- **Perubahan perilaku di CLI:** jumlah publikasi tidak lagi menjadi alasan
  "penarikan besar". Ambangnya kini lebih dari 30 menit (dulu >= 1 jam) atau
  lebih dari 1 GB (dulu >= 1000 MB).

## Uji (`uji_pipeline.py` bagian J, 10 uji)

| Uji | Isi |
|---|---|
| J1 | Satuan: 9 kasus ukuran ("tidak diketahui", "0 MB", "< 0,1 MB", ... "1.023,9 MB", "1,0 GB", "402,7 GB") dan 9 kasus waktu ("59 detik", "1 menit", "59 menit", "1,0 jam", "2,5 jam", "±9 menit") |
| J2 | Empat status beserta batasnya: tepat 30 menit/1 GB/disk pas = belum; +1 detik/+0,1 MB/-0,1 MB = berubah. Merah mengalahkan kuning. Kalimat untuk 1, 3, dan 5 wilayah, revisi, cek gagal, disk, terbaru. Ambang benar-benar dibaca dari wilayah.json (diubah ke 4 menit -> kuning); kunci hilang ditolak |
| J3 | Halaman dengan keadaan cek buatan: 4 status -> `data-status`, judul, 4 kotak angka, tabel di dalam `<details>`. Tombol Mulai `disabled` + penjelasan HANYA pada status merah |
| J4 | Server: pilihan sama + disk kurang -> 409, 0 proses. "Cek dulu", disk cukup, atau pilihan lain -> tetap dimulai |
| J5 | Sesudah pembaruan: hijau/abu-abu/kuning/merah, label 4 angka, "1,3 GB", "13 menit", judul publikasi baru tampil, publikasi gagal tampil, rincian dilipat |
| J6 | "Cek dulu" sungguhan lewat test_client + WebAPI tiruan. Tanpa perubahan = abu-abu; 1 publikasi baru = hijau, "Ada 1 publikasi baru dari Kab. Tapin.", 12,5 MB, sisa disk terbaca |

- **Alatnya diuji dulu:** dua cacat sengaja ditanam di salinan kode (ambang
  `>` menjadi `>=`, atribut `disabled` dibuang). Hasilnya J2 dan J3 GAGAL
  (`uji-pipeline-J-uji-alat.txt`, 16 lulus 2 gagal), lalu berkas dikembalikan.
- Tanpa cacat: `--hanya J` 18 lulus, 0 gagal (`uji-pipeline-J-1.txt`).

**Run penuh tanpa argumen: 152 lulus, 0 gagal, 0 dilewati, kode keluar 0,
3.485 detik** (`uji-pipeline-penuh.txt`). Termasuk J1-J6 (10), R5 (tanpa
perubahan ekspektasi: teks lama tetap ada, sebagian kini di dalam
`<details>`), Q5, Z1, dan Z2.

Q5 disesuaikan. Dulu ekspektasinya 3 alasan (>= 50 publikasi, >= 1 GB,
>= 1 jam); untuk 60 publikasi, 2.000 MB, ±69 menit kini 2 alasan
(> 30 menit, > 1 GB), karena jumlah publikasi tidak lagi menjadi ambang.

## Tangkapan layar (`ringkasan-cek-20261125/layar-ringkasan/`)

Server: database uji + WebAPI tiruan (`form-pembaruan-20261124/tiruan_tangkapan.py`,
simulasi Tanah Laut 3 baru + 2 direvisi, provinsi seluruhnya direvisi). Tombol
Mulai tidak pernah diklik. Sisa disk merah dipalsukan HANYA di proses server
tangkapan (`SISA_DISK_MB.txt`), tidak di kode aplikasi.

| Berkas (1280 dan 375) | Status | Angka |
|---|---|---|
| `1-sesudah-pembaruan` | hijau Pembaruan selesai (tarik kecil Tanah Laut 24 Nov, data asli) | 27 publikasi, 0, 221,7 MB, 13 menit |
| `2-cek-terbaru` | abu-abu (Kota Banjarmasin) | 0, 0 MB, ±3 detik, 31,4 GB |
| `3-cek-siap` (+ `3b` rincian dibuka) | hijau (Tanah Laut 2024-2026) | 5, 68,0 MB, ±3 menit, 31,4 GB |
| `4-cek-disk-kurang` | merah (sisa palsu 40 MB), Mulai nonaktif + alasan | 5, 68,0 MB, ±3 menit, 40,0 MB |
| `5-cek-semua-wilayah` | kuning (semua, rilis 2024-2026) | 84, 813,3 MB, ±32 menit, 31,4 GB |
| `0375-3c-tanpa-js-rincian-dibuka` | `<details>` dibuka di browser dengan JavaScript MATI: tabel tersembunyi -> terlihat | |

Dari `catatan.json`:
- 1280 px: 4 kolom; 375 px: 2 kolom x 2 baris;
- setiap angka muat satu baris;
- 0/12 halaman bergulir mendatar.

Satu perbaikan dari potret pertama: di 375 px angka terpotong ("68,0 / MB").
Penyebabnya, ruang kanan 38 px untuk tombol "Kembali ke atas" terpasang dua
kali (kotak hasil cek dan kartu di dalamnya). Kini hanya kotak luar yang
memakainya.

Catatan: cek semua wilayah rilis 2025-2026 menghasilkan "±30 menit" berstatus
hijau. Perkiraannya <= 1.800 detik, dan ambangnya "lebih dari 30 menit". Itu
sesuai aturan, tetapi angka bulat di batas bisa terlihat janggal.

## Halaman pencarian tidak berubah

- **HTML:** `tests/potret_tampilan.py`, 28 URL di database uji. "Sebelum" =
  kode HEAD (perubahan disimpan sementara dengan `git stash`, lalu
  dikembalikan); "sesudah" = kode baru. **IDENTIK 28/28.**
- **Piksel:** 6 halaman x 2 lebar. CSS HEAD (diganti lewat intersepsi request)
  vs CSS final, server sama: **12 sama, 0 beda**
  (`banding-layar-pencarian.txt`).

## CHECKSUM produksi

`checksum-produksi-awal.json` (sebelum semua uji) = `checksum-produksi-akhir.json`
(sesudah semua uji, tangkapan layar, dan run penuh): 6/6 tabel, jumlah baris
dan CHECKSUM sama. Z2 di run penuh juga lulus.
