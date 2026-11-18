# Tampilan publikasi Kecamatan Dalam Angka: pengerjaan hari 1 (18 Nov 2026)

Rancangan: `rancangan-tampilan-kecamatan-20261118.md`, disetujui TANPA deteksi
nama kecamatan dari kata kunci (saran pengembangan sesudah presentasi). Semua
uji di database uji, salinan produksi `db_pencarian_bps_salinan_uji`, dan
salinan sementara. Produksi tidak disentuh dan tidak di-push.

## Commit (berurutan, satu bagian per commit)
| Commit | Bagian |
|---|---|
| `b6683b9` | `tests/potret_tampilan.py`: 28 URL lewat test_client, PYTHONHASHSEED=0 |
| `f3fef32` | 1. kolom `publikasi.kecamatan` + `pola_kecamatan` + `sinkron_kecamatan` |
| `9189f93` | 2. korpus dipisah (`entri_kec`, `publikasi_kec`, `daftar_kecamatan`) |
| `758bef8` | 3. `/api/saran` tanpa kecamatan kecuali `kec=1` |
| `42e768e` | 4. backend `cari_kecamatan` / `publikasi_kecamatan`, parameter `kec`/`kc`/`semua_kec` |
| `7ef7a71` | 5. kotak centang + dropdown kecamatan (`kecamatan.js`, `saran.js` mengirim `kec=1`) |
| `a8e3649` | 6. seksi hasil "Dari publikasi Kecamatan Dalam Angka" |
| `69de203` | 7. kotak info + `/api/kecamatan/jumlah` |
| `51a0a07` | urutan korpus eksplisit (lihat temuan 2) |
| `9060429` | `uji_pipeline.py` bagian V |

## Jaminan "tanpa centang identik"
1. **Salinan produksi (tanpa kecamatan), sebelum vs sesudah setiap bagian:**
   potret 28/28 byte-identik (beranda, 21 kueri `/hasil`, 5 awalan
   `/api/saran`). Selama database tidak berisi publikasi kecamatan,
   kotak centang, dropdown, dan kotak info tidak dirender.
2. **Database uji (berkecamatan) vs salinan sementara tanpa kecamatan**
   (`uji_pipeline.py` bagian V, bisa diulang kapan saja):
   - 23/23 halaman byte-identik sesudah ketiga widget kecamatan dibuang;
   - saran tanpa `kec=1` memuat 0 kecamatan;
   - waktu 85 vs 84 ms;
   - angka kotak info = jumlah di seksi bercentang.
3. **`uji_pipeline.py` penuh:** lihat bagian akhir.

## Temuan
1. **Potret tidak deterministik tanpa PYTHONHASHSEED.** Dua potret dari kode
   dan data yang SAMA berbeda di 4/28 halaman, karena urutan entri berskor
   sama ikut urutan iterasi set string yang diacak per proses. Alat potret dan
   bagian V kini mengunci `PYTHONHASHSEED=0`.
2. **Urutan seri skor bergantung pada rencana kueri MySQL** (diperbaiki,
   `51a0a07`).
   - `_ambil_korpus` tidak punya ORDER BY. EXPLAIN menunjukkan produksi
     memakai indeks `publikasi_id`, sedangkan salinannya yang isinya identik
     memakai `(publikasi_id, tipe)`.
   - Memuat kecamatan juga mengubah rencana, sehingga entri berskor sama
     bertukar tempat (4/21 halaman). Ini terjadi apa pun kodenya.
   - Urutan kini eksplisit, meniru rencana produksi: publikasi
     `(tahun_terbit, id)`, entri `(tahun_terbit, publikasi.id, entri.id)`.
     Salinan produksi tetap 28/28 identik.
3. **`/api/saran`: seri edisi juga bergantung pada rencana kueri. MENUNGGU
   KEPUTUSAN.**
   - `ORDER BY char_length LIMIT 32` memakai filesort yang tidak stabil untuk
     seri. Edisi mana yang tampil di antara judul sepanjang sama bisa berubah
     begitu ada klausa WHERE atau isi tabel berubah.
   - Saat ini filter kecamatan hanya dipasang kalau database berisi kecamatan,
     sehingga produksi sekarang identik.
   - Sesudah kecamatan dimuat ke produksi, label edisi di saran BISA berubah;
     daftar judulnya kebanyakan sama.
   - Usulan: pemecah seri eksplisit, edisi TERBARU dulu (`tanggal_rilis
     DESC, id`). Ini mengubah saran sekarang satu kali (label edisi), lalu
     stabil. Mencoba `tahun_terbit ASC` mengubah 5/5 awalan (memilih edisi
     2024 alih-alih 2025), jadi tidak dipakai.
4. Saran dengan `kec=1`: "penduduk" hanya memberi 4 saran, karena batas 32
   baris habis oleh judul kecamatan kembar yang lalu dideduplikasi. Bisa
   diperbaiki dengan batas lebih besar kalau `kec=1`.

## Titik berhenti (18 Nov 2026)
- **Selesai dan lulus:** bagian 1-7 rancangan, serta jaminan identik di
  `uji_pipeline.py` (V).
- **Belum:**
  - kolom opsional `log_pencarian.sertakan_kecamatan`;
  - keputusan pemecah seri saran (temuan 3);
  - cek tampilan dan JavaScript di browser sungguhan (sejauh ini hanya
    test_client: HTML, URL, angka). Termasuk tata letak kotak centang di
    layar kecil dan perilaku dropdown saat wilayah diganti;
  - PANDUAN.md (fitur kecamatan, parameter URL);
  - memuat kecamatan ke produksi (`kecualikan_judul.aktif` = false, lalu
    pembaruan) - keputusan pemilik project.
- `db_pencarian_bps_salinan_uji` (salinan produksi 18 Nov) masih ada, dipakai
  sebagai pembanding potret. Hapus kalau sudah tidak perlu.
