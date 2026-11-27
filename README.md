# Sistem Pencarian Publikasi BPS Kalsel
Aplikasi ini dikembangkan sebagai bagian dari project magang di BPS Provinsi
Kalimantan Selatan. Kode dipublikasikan sebagai portofolio. Data publikasi,
berkas PDF, dan seluruh kredensial tidak disertakan.

Mesin pencari internal untuk petugas Pelayanan Statistik Terpadu (PST) BPS
Provinsi Kalimantan Selatan. Petugas mengetik kata kunci; sistem menunjukkan
publikasi mana DAN bagian mana (tabel, gambar, lampiran, bab) yang memuat
data tersebut, lengkap dengan tombol membuka PDF di halaman yang tepat.

**Versi 1.0.0 (serah terima, 27 November 2026)** — ringkasan perubahan dan
utang teknis yang masih terbuka: [CHANGELOG.md](CHANGELOG.md).

Cakupan: publikasi Provinsi Kalimantan Selatan, 13 kabupaten/kota, dan
"Kecamatan … Dalam Angka" yang dirilis 2025–2026, dengan filter wilayah dan
pilihan kecamatan di halaman pencarian. Keadaan data 27 November 2026:

- 622 publikasi, 312 di antaranya kecamatan;
- 44.649 bagian terindeks;
- 88,9% bagian bisa dibuka langsung di halaman PDF-nya.

- **Panduan operasional** (pemasangan, menjalankan, memperbarui data,
  mengelola kamus dan wilayah, OCR, cara menguji, pemecahan masalah,
  kebutuhan deploy, keterbatasan dan utang teknis): [PANDUAN.md](PANDUAN.md)
- **Konteks teknis dan riwayat keputusan** (untuk pengembang):
  [CLAUDE.md](CLAUDE.md)

## Struktur

- `app/` — aplikasi Flask (models, services, routes, templates, static)
- `data/` — pengaturan wilayah (`wilayah.json`), kamus sinonim, laporan
  pemeriksaan (`regresi/`); PDF unduhan, cache OCR, dan log tidak masuk Git
- `scripts/` — pipeline data (`perbarui.py`) serta utilitas
- `tests/` — `uji_pipeline.py`, uji pipeline ujung ke ujung di database uji
  (PANDUAN.md bagian 9); berkas `test_*.py` masih kerangka kosong
- `jalankan-aplikasi.bat`, `perbarui-data.bat` — pintu masuk klik-dua-kali
  (Windows); padanannya untuk Linux `jalankan-aplikasi.sh`, `perbarui-data.sh`

## Menjalankan (ringkas)

```
python -m venv venv
venv\Scripts\pip.exe install -r requirements.txt
copy .env.example .env      # lalu isi semua nilainya - lihat PANDUAN.md bagian 2
```

Lalu isi datanya, dengan salah satu dari dua jalur di PANDUAN.md bagian 2:

- **dari berkas serah terima** (disarankan):
  - pulihkan cadangan database;
  - salin folder PDF, sampul, dan cache OCR tanpa ZIP (tanggal ubah berkas
    harus tetap);
  - periksa dengan `scripts/periksa_sidik.py`.

  Paket serah terima `data/serah_terima/` (tidak masuk Git) memuat
  `BACA-DULU.txt`; caranya ada di PANDUAN.md bagian 2 dan 7.4;
- **dari nol** (butuh internet ke WebAPI BPS, beberapa jam):

  ```
  venv\Scripts\python.exe scripts\perbarui.py --hanya-periksa
  perbarui-data.bat
  ```

Sesudah itu `jalankan-aplikasi.bat` membuka `http://localhost:5000/`.

Mode pengembangan (debugger + auto-reload, jangan di jaringan kantor):
`venv\Scripts\python.exe run.py --dev`

Di Linux (teruji di Ubuntu 22.04, Python 3.12, MySQL 8.0): `python3 -m venv
venv`, `venv/bin/pip install -r requirements.txt`, lalu `./perbarui-data.sh`
dan `./jalankan-aplikasi.sh`.
Pemasangan di server Windows atau Linux, termasuk layanan systemd dan paket
serah terima: PANDUAN.md bagian 7.4.

OCR untuk PDF tanpa lapisan teks bersifat opsional
(`requirements-ocr.txt`, PANDUAN.md bagian 7.2).

Aplikasi menolak berjalan kalau `SECRET_KEY` atau `ADMIN_PASSWORD_HASH` di
`.env` kosong. Halaman `/admin/` dilindungi satu kata sandi bersama; halaman
pencarian terbuka tanpa login.

## Catatan Term of Use WebAPI BPS

Setiap halaman wajib mencantumkan "Layanan ini menggunakan API Badan Pusat
Statistik (BPS)" — sudah dipasang di footer `app/templates/base.html` dan
tidak boleh dihapus. API key hanya di `.env` (tidak masuk Git). Penarikan
data memberi jeda 1 detik antar request.
