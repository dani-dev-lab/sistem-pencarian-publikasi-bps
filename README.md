# Sistem Pencarian Publikasi BPS Kalsel
Aplikasi ini dikembangkan sebagai bagian dari project magang di BPS Provinsi
Kalimantan Selatan. Kode dipublikasikan sebagai portofolio. Data publikasi,
berkas PDF, dan seluruh kredensial tidak disertakan.

Mesin pencari internal untuk petugas Pelayanan Statistik Terpadu (PST) BPS
Provinsi Kalimantan Selatan. Petugas mengetik kata kunci; sistem menunjukkan
publikasi mana DAN bagian mana (tabel, gambar, lampiran, bab) yang memuat
data tersebut, lengkap dengan tombol membuka PDF di halaman yang tepat.

- **Panduan operasional** (menjalankan, memperbarui data, mengelola kamus,
  mengganti sandi admin, kebutuhan deploy): [PANDUAN.md](PANDUAN.md)
- **Konteks teknis dan riwayat keputusan** (untuk pengembang):
  [CLAUDE.md](CLAUDE.md)

## Struktur

- `app/` — aplikasi Flask (models, services, routes, templates, static)
- `data/` — metadata publikasi, hasil ekstraksi, kamus sinonim, PDF unduhan
- `scripts/` — pipeline data (`perbarui.py` dan tahap-tahapnya) serta utilitas
- `tests/` — pengujian ekstraksi PDF dan mesin pencari
- `jalankan-aplikasi.bat`, `perbarui-data.bat` — pintu masuk klik-dua-kali

## Menjalankan (ringkas)

```
python -m venv venv
venv\Scripts\pip.exe install -r requirements.txt
copy .env.example .env      # lalu isi semua nilainya - lihat PANDUAN.md bagian 2
perbarui-data.bat           # isi database (butuh jaringan "BPS - Pegawai")
jalankan-aplikasi.bat       # buka http://localhost:5000/
```

Mode pengembangan (debugger + auto-reload, jangan di jaringan kantor):
`venv\Scripts\python.exe run.py --dev`

Aplikasi menolak berjalan kalau `SECRET_KEY` atau `ADMIN_PASSWORD_HASH` di
`.env` kosong. Halaman `/admin/` dilindungi satu kata sandi bersama; halaman
pencarian terbuka tanpa login.

## Catatan Term of Use WebAPI BPS

Setiap halaman wajib mencantumkan "Layanan ini menggunakan API Badan Pusat
Statistik (BPS)" — sudah dipasang di footer `app/templates/base.html` dan
tidak boleh dihapus. API key hanya di `.env` (tidak masuk Git). Penarikan
data memberi jeda 1 detik antar request.
