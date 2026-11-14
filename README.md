# Sistem Pencarian Publikasi BPS Kalsel
Aplikasi ini dikembangkan sebagai bagian dari project magang di BPS Provinsi
Kalimantan Selatan. Kode dipublikasikan sebagai portofolio. Data publikasi,
berkas PDF, dan seluruh kredensial tidak disertakan.

Mesin pencari internal untuk petugas Pelayanan Statistik Terpadu (PST) BPS
Provinsi Kalimantan Selatan. Petugas mengetik kata kunci; sistem menunjukkan
publikasi mana DAN bagian mana (tabel, gambar, lampiran, bab) yang memuat
data tersebut, lengkap dengan tombol membuka PDF di halaman yang tepat.

Cakupan: publikasi Provinsi Kalimantan Selatan dan 13 kabupaten/kota yang
dirilis 2 tahun terakhir, dengan filter wilayah di halaman pencarian.

- **Panduan operasional** (pemasangan, menjalankan, memperbarui data,
  mengelola kamus dan wilayah, OCR, cara menguji, pemecahan masalah,
  kebutuhan deploy): [PANDUAN.md](PANDUAN.md)
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

## Menjalankan (ringkas)

```
python -m venv venv
venv\Scripts\pip.exe install -r requirements.txt
copy .env.example .env      # lalu isi semua nilainya - lihat PANDUAN.md bagian 2
```

Lalu isi datanya, dengan salah satu dari dua jalur di PANDUAN.md bagian 2:

- **dari berkas serah terima** (disarankan): pulihkan cadangan database, salin
  folder PDF dan cache OCR;
- **dari nol** (butuh internet ke WebAPI BPS, beberapa jam):

  ```
  venv\Scripts\python.exe scripts\perbarui.py --hanya-periksa
  perbarui-data.bat
  ```

Sesudah itu `jalankan-aplikasi.bat` membuka `http://localhost:5000/`.

Mode pengembangan (debugger + auto-reload, jangan di jaringan kantor):
`venv\Scripts\python.exe run.py --dev`

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
