/* Formulir pilihan penarikan di /admin/perbarui (24 Nov 2026).
 *
 * Peningkatan opsional. Tanpa berkas ini formulir tetap berfungsi penuh dan
 * pilihan tetap diperiksa di server; yang hilang hanya:
 *   - tombol "Pilih semua" / "Hapus semua" wilayah (disembunyikan tanpa JS);
 *   - kelompok "Jenis publikasi" yang dinonaktifkan selama tidak ada
 *     kabupaten/kota yang dicentang (pilihan itu hanya berlaku untuk kab/kota;
 *     server mengabaikannya kalau hanya provinsi yang dipilih).
 */
(function () {
  "use strict";

  var form = document.getElementById("form-pembaruan");
  if (!form) return;

  var wilayah = form.querySelectorAll('input[name="wilayah"]');
  var kabkota = form.querySelectorAll('input[name="wilayah"][data-kabkota]');
  var jenis = document.getElementById("pilihan-jenis");

  function aturJenis() {
    if (!jenis) return;
    var ada = false;
    for (var i = 0; i < kabkota.length; i++) ada = ada || kabkota[i].checked;
    jenis.disabled = !ada;
    jenis.classList.toggle("tidak-berlaku", !ada);
  }

  var aksi = form.querySelector(".aksi-centang");
  if (aksi) {
    aksi.hidden = false;
    aksi.addEventListener("click", function (e) {
      var tombol = e.target.closest("button[data-centang]");
      if (!tombol) return;
      var nilai = tombol.getAttribute("data-centang") === "semua";
      for (var i = 0; i < wilayah.length; i++) wilayah[i].checked = nilai;
      aturJenis();
    });
  }

  form.addEventListener("change", function (e) {
    if (e.target && e.target.name === "wilayah") aturJenis();
  });
  aturJenis();
})();
