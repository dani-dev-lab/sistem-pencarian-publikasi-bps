/* Hitung mundur login yang terkunci (26 Nov 2026).
 *
 * Sisa waktu dihitung SERVER (data-sisa, detik); skrip ini hanya
 * menampilkannya sebagai mm:ss dan, saat habis, mengaktifkan kotak sandi dan
 * tombol Masuk tanpa memuat ulang. Penguncian tetap ditegakkan server: kiriman
 * yang masuk sebelum waktunya ditolak (HTTP 429), apa pun keadaan tombolnya.
 *
 * Pembaca layar: hitung mundur per detik disembunyikan (aria-hidden), dan
 * wilayah aria-live (#pesan-kunci) hanya berubah sekali, saat selesai.
 * Kalimat sisa waktu dari server tetap terbaca di awal, tetapi tidak lagi
 * terlihat (diganti hitung mundur).
 */
(function () {
  "use strict";
  var kotak = document.getElementById("kotak-kunci");
  if (!kotak || !kotak.dataset.sisa) return;
  var akhir = Date.now() + parseInt(kotak.dataset.sisa, 10) * 1000;
  var pesan = document.getElementById("pesan-kunci");
  var statis = kotak.querySelector(".sisa-statis");
  var hitung = kotak.querySelector(".hitung-mundur");
  var angka = kotak.querySelector(".sisa-waktu");
  var masukan = document.querySelector('form.form-admin input[name="sandi"]');
  var tombol = document.querySelector('form.form-admin button[type="submit"]');

  function duaAngka(n) { return (n < 10 ? "0" : "") + n; }

  function selesai() {
    hitung.hidden = true;
    kotak.classList.remove("kabar-gagal");
    kotak.classList.add("kabar-sukses");
    pesan.textContent = "Silakan coba lagi.";
    if (masukan) { masukan.disabled = false; masukan.focus(); }
    if (tombol) tombol.disabled = false;
  }

  function detak() {
    var sisa = Math.ceil((akhir - Date.now()) / 1000);
    if (sisa <= 0) { selesai(); return; }
    angka.textContent = duaAngka(Math.floor(sisa / 60)) + ":" + duaAngka(sisa % 60);
    // Tepat di pergantian detik berikutnya, supaya tampilan tidak melompat.
    var tunggu = (akhir - Date.now()) % 1000;
    setTimeout(detak, tunggu > 0 ? tunggu : 1000);
  }

  if (statis) statis.classList.add("hanya-pembaca-layar");
  hitung.hidden = false;
  detak();
})();
