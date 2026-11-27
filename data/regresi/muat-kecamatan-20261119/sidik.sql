-- Sidik isi (tanpa id entri) untuk membandingkan produksi dan database uji per ISI baris.
-- @db diganti oleh pemanggil. Kolom publikasi tanpa kolom yang hanya ada di satu sisi.
SELECT 'kec_publikasi', COUNT(*), BIT_XOR(CRC32(CONCAT_WS('|', id, domain, judul, IFNULL(abstrak,'~'), IFNULL(tanggal_rilis,'~'),
       IFNULL(url_pdf,'~'), IFNULL(teks_ternormalisasi,'~'), IFNULL(halaman_ocr,'~'), IFNULL(kecamatan,'~'),
       IFNULL(updt_date_api,'~'), IFNULL(updt_date_diproses,'~'), IFNULL(sidik_ukuran,'~'), IFNULL(sidik_mtime,'~'), wilayah)))
  FROM publikasi WHERE judul REGEXP '^Kecamatan .* Dalam Angka [0-9]{4}$';
SELECT 'kec_entri', COUNT(*), BIT_XOR(CRC32(CONCAT_WS('|', e.publikasi_id, e.tipe, IFNULL(e.nomor,'~'), e.judul, IFNULL(e.halaman,'~'),
       IFNULL(e.halaman_fisik,'~'), e.halaman_fisik_perkiraan, e.sumber, IFNULL(e.teks_ternormalisasi,'~'))))
  FROM entri_dokumen e JOIN publikasi p ON p.id = e.publikasi_id WHERE p.judul REGEXP '^Kecamatan .* Dalam Angka [0-9]{4}$';
