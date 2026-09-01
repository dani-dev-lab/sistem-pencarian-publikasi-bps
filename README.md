# Sistem Pencarian Publikasi BPS

Sistem pencarian entri dokumen (Daftar Isi, Daftar Tabel, Daftar Gambar, Lampiran)
dari publikasi BPS Kalimantan Selatan, untuk membantu petugas PST menjawab
permintaan data secara cepat.

## Struktur

- `app/` — aplikasi Flask (models, services, routes, templates, static)
- `data/` — sampel PDF, PDF hasil unduhan, dan kamus sinonim
- `scripts/` — utilitas sekali-jalan (spike, unduhan massal, analisis frekuensi)
- `tests/` — pengujian ekstraksi PDF dan mesin pencari

## Menjalankan

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # lalu isi BPS_API_KEY
python run.py
```

## Catatan Terms of Use WebAPI BPS

Setiap halaman wajib mencantumkan sumber data BPS dan pernyataan bahwa aplikasi
ini bukan produk resmi BPS — sudah dipasang di footer `app/templates/base.html`.
