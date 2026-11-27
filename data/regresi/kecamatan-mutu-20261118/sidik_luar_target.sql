SET @t = '289e7b7ffea9212fd954d849,e3eb7975c2d3d43a1144ddf2,9d9fc69a6340558366cdd51b,b0d3817c3ae3788048ad8c87,d774eb0b6f130968ae3b5c50,abf5e6920511b575b8859ea7,4ce13f41bb7314220ba6525e';
SELECT 'entri_luar', COUNT(*), BIT_XOR(CRC32(CONCAT_WS('|',id,publikasi_id,tipe,IFNULL(nomor,'~'),judul,IFNULL(halaman,'~'),IFNULL(halaman_fisik,'~'),halaman_fisik_perkiraan,sumber,IFNULL(teks_ternormalisasi,'~')))) FROM entri_dokumen WHERE FIND_IN_SET(publikasi_id,@t)=0;
SELECT 'pub_luar', COUNT(*), BIT_XOR(CRC32(CONCAT_WS('|',id,judul,IFNULL(diekstrak_pada,'~'),IFNULL(halaman_ocr,'~'),IFNULL(sidik_ukuran,'~'),IFNULL(updt_date_diproses,'~'),IFNULL(galat_ekstraksi,'~')))) FROM publikasi WHERE FIND_IN_SET(id,@t)=0;
SELECT 'target', COUNT(*) FROM entri_dokumen WHERE FIND_IN_SET(publikasi_id,@t)>0;
CHECKSUM TABLE log_pencarian, kategori, publikasi_kategori;
