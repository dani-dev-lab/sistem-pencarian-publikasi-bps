/* Posisi gulir halaman pencarian/hasil saat kembali dari admin (26 Nov 2026).
 *
 * Setiap halaman pencarian menyimpan posisi gulirnya di sessionStorage
 * (per alamat: path + query) saat ditinggalkan. Halaman yang dibuka lewat
 * tombol "Kembali ke Pencarian" ditandai server (body[data-pulihkan-gulir],
 * dari penanda sekali pakai /kembali); hanya halaman seperti itu yang
 * memulihkan posisinya. Pencarian biasa tetap mulai dari atas.
 *
 * Tanpa JavaScript, atau kalau sessionStorage tidak bisa dipakai (mode
 * privat, diblokir), tombol Kembali tetap menuju hasil yang sama; hanya
 * posisi gulirnya yang tidak pulih.
 */
(function () {
  "use strict";
  var kunci = "gulir:" + location.pathname + location.search;

  function simpan() {
    try {
      sessionStorage.setItem(kunci, String(Math.round(window.pageYOffset || 0)));
    } catch (e) { /* sessionStorage tidak tersedia */ }
  }
  window.addEventListener("pagehide", simpan);
  var tombolAdmin = document.querySelector(".tombol-admin");
  if (tombolAdmin) tombolAdmin.addEventListener("click", simpan);

  if (!document.body.hasAttribute("data-pulihkan-gulir")) return;
  var y = null;
  try { y = sessionStorage.getItem(kunci); } catch (e) { return; }
  y = parseInt(y, 10);
  if (!(y > 0)) return;

  // Gulir sekarang, lalu lagi setiap kali tinggi halaman berubah dalam 3
  // detik pertama (sampul termuat, kotak info kecamatan disembunyikan
  // kecamatan.js) dan saat load - kecuali petugas sudah menggulir sendiri.
  var disentuh = false;
  ["wheel", "touchstart", "keydown", "mousedown"].forEach(function (nama) {
    window.addEventListener(nama, function () { disentuh = true; }, { passive: true, once: true });
  });
  function pulihkan() { if (!disentuh) window.scrollTo(0, y); }
  pulihkan();
  if (window.ResizeObserver) {
    var pengamat = new ResizeObserver(pulihkan);
    pengamat.observe(document.body);
    setTimeout(function () { pengamat.disconnect(); }, 3000);
  }
  if (document.readyState !== "complete") window.addEventListener("load", pulihkan);
})();
