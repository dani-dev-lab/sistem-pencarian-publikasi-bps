/* Kotak centang + dropdown kecamatan di form cari (18 Nov 2026).
 *
 * Tanpa JavaScript form tetap berfungsi: dropdown kecamatan dirender server
 * untuk wilayah yang aktif, dan memilih kecamatan berarti kec=1.
 * Dengan JavaScript:
 *   - isi dropdown kecamatan diganti saat dropdown wilayah diganti (data dari
 *     #data-kecamatan, domain -> [[kunci, nama], ...]); disembunyikan kalau
 *     wilayah itu tidak punya publikasi kecamatan;
 *   - dropdown kecamatan nonaktif (tidak ikut terkirim) selama kotak centang
 *     mati, supaya "Semua kecamatan"/pilihan lama tidak menyalakan kec diam-diam.
 */
(function () {
  "use strict";
  var data = document.getElementById("data-kecamatan");
  var form = data && data.closest("form");
  if (!form) return;
  var semua = JSON.parse(data.textContent || "{}");
  var wilayah = form.querySelector("select[name=w]");
  var pilih = form.querySelector("select[name=kc]");
  var centang = form.querySelector("input[name=kec]");
  if (!wilayah || !pilih || !centang) return;

  function isi() {
    var daftar = semua[wilayah.value] || [];
    var lama = pilih.value;
    pilih.textContent = "";
    var o = document.createElement("option");
    o.value = ""; o.textContent = "Semua kecamatan";
    pilih.appendChild(o);
    daftar.forEach(function (k) {
      var op = document.createElement("option");
      op.value = k[0]; op.textContent = k[1];
      if (k[0] === lama) op.selected = true;
      pilih.appendChild(op);
    });
    pilih.hidden = daftar.length === 0;
    atur();
  }
  function atur() {
    pilih.disabled = pilih.hidden || !centang.checked;
  }
  wilayah.addEventListener("change", isi);
  centang.addEventListener("change", atur);
  atur();
})();
