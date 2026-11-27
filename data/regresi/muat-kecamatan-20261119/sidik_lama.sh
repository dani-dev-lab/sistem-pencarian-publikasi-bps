# Sidik kolom LAMA log_pencarian & publikasi (tanpa kolom baru) + semua entri produksi per id.
B="C:/laragon/bin/mysql/mysql-8.0.30-winx64/bin"; DB=${1:-db_pencarian_bps}
"$B/mysql" -uroot -N $DB -e "
SELECT 'log_lama', COUNT(*), BIT_XOR(CRC32(CONCAT_WS('|', id, keyword, IFNULL(keyword_ternormalisasi,'~'), jumlah_hasil, IFNULL(skor_tertinggi,'~'), IFNULL(durasi_ms,'~'), IFNULL(wilayah_filter,'~'), waktu_pencarian))) FROM log_pencarian;
SELECT 'publikasi_lama', COUNT(*), BIT_XOR(CRC32(CONCAT_WS('|', id, domain, judul, IFNULL(abstrak,'~'), IFNULL(tanggal_rilis,'~'), IFNULL(url_pdf,'~'), IFNULL(teks_ternormalisasi,'~'), IFNULL(halaman_ocr,'~'), IFNULL(updt_date_api,'~'), IFNULL(updt_date_diproses,'~'), IFNULL(sidik_ukuran,'~'), IFNULL(sidik_mtime,'~'), wilayah, IFNULL(diekstrak_pada,'~')))) FROM publikasi WHERE judul NOT REGEXP '^Kecamatan .* Dalam Angka [0-9]{4}\$';
SELECT 'entri_non_kec_per_id', COUNT(*), BIT_XOR(CRC32(CONCAT_WS('|', e.id, e.publikasi_id, e.tipe, IFNULL(e.nomor,'~'), e.judul, IFNULL(e.halaman,'~'), IFNULL(e.halaman_fisik,'~'), e.halaman_fisik_perkiraan, e.sumber, IFNULL(e.teks_ternormalisasi,'~')))) FROM entri_dokumen e JOIN publikasi p ON p.id=e.publikasi_id WHERE p.judul NOT REGEXP '^Kecamatan .* Dalam Angka [0-9]{4}\$';
SELECT 'versi', versi FROM versi_data;
CHECKSUM TABLE kategori, publikasi_kategori;"
