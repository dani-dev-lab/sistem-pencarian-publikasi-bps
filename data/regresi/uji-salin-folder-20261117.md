# Uji menyalin folder PDF + cache OCR (17 Nov 2026)

Pertanyaannya: cara menyalin mana yang mempertahankan sidik PDF (ukuran,
`int(mtime)`), yang dipakai `sumber_bps.sidik_pdf` dan `ocr._sidik`.
Kalau sidik berubah:
- pembaruan berikutnya menganggap semua PDF berganti, lalu membaca ulang;
- cache OCR yang sidiknya tidak cocok dibuang.

## Bahan

Disalin dari proyek ke folder sementara di drive yang sama (laptop
pengembang, NTFS):
- 5 PDF domain 6305: 4 bertekst dan `f338cd99` (publikasi OCR);
- folder cache OCR `f338cd99`: 99 berkas halaman + `_meta.json`;
- total 105 berkas.

Folder asal dibuat dengan `Copy-Item`, lalu dibuktikan sama sidiknya dengan
berkas proyek (105/105).

## Hasil

| Cara | Sidik PDF berubah | Waktu berkas cache berubah | Cache OCR masih sah (`_meta.json` = sidik PDF salinan) |
|---|---|---|---|
| robocopy `/E` | 0/5 | 0/100 | ya |
| File Explorer (`Shell.Application.CopyHere`, mesin salin yang sama dengan salin–tempel Explorer) | 0/5 | 0/100 | ya |
| `Copy-Item -Recurse` | 0/5 | 0/100 | ya |
| `tar -cf` lalu `tar -xf` (bsdtar 3.8.9 bawaan Windows) | 0/5 | 0/100 | ya |
| ZIP PowerShell (`Compress-Archive` / `Expand-Archive`) | **3/5** (−1 detik) | **50/100** | **tidak** |
| ZIP Explorer (CopyHere ke .zip, lalu CopyHere isinya keluar) | **5/5** (+1 s.d. +2 detik) | **100/100** | **tidak** |

Penyebabnya: format ZIP menyimpan waktu DOS dengan ketelitian 2 detik.
Pergeseran 1-2 detik itu pasti, bukan kebetulan, dan sudah cukup untuk
mengubah `int(mtime)`.

## Akibat kalau folder dipindah lewat ZIP

Mengikuti perilaku yang sudah tercatat di CLAUDE.md, bagian "Jebakan serah
terima":
- semua PDF dianggap berubah, sehingga pembaruan berikutnya membaca ulang
  306 PDF (±75 menit);
- cache OCR 8 publikasi dihapus. Membuatnya ulang butuh ±5 jam OCR. Kalau
  EasyOCR tidak terpasang di server, publikasi OCR kehilangan entri hasil
  OCR-nya.

## Tidak diuji

- Penyimpanan awan (unduh ulang dari OneDrive/Drive).
- Flashdisk FAT32 (ketelitian 2 detik, jadi kemungkinan besar sama dengan
  ZIP).
- Exfat.
- Salin lintas komputer lewat jaringan (SMB).

## Tindak lanjut

PANDUAN bagian 2 (catatan "Penting saat menyalin folder PDF") diganti dengan
tabel hasil ini.
