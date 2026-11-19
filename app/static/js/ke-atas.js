/* Tombol "Kembali ke atas" (19 Nov 2026).
 *
 * - Muncul hanya setelah halaman digulir lebih dari satu layar.
 * - Diklik: gulir halus ke atas; kalau pengguna memilih "kurangi animasi"
 *   (prefers-reduced-motion), langsung lompat.
 * - Sesudahnya fokus dipindah ke kop, supaya pengguna keyboard melanjutkan
 *   dari atas halaman (tombolnya sendiri lalu tersembunyi).
 * Tanpa JavaScript tombol tetap tersembunyi (atribut hidden).
 */
(function () {
  "use strict";
  var tombol = document.querySelector(".ke-atas");
  if (!tombol) return;
  var kurangiGerak = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;

  function periksa() {
    var tampil = window.scrollY > window.innerHeight;
    if (tombol.hidden === tampil) tombol.hidden = !tampil;
  }

  tombol.addEventListener("click", function () {
    var halus = !(kurangiGerak && kurangiGerak.matches);
    window.scrollTo({ top: 0, left: 0, behavior: halus ? "smooth" : "auto" });
    var kop = document.querySelector(".kop-identitas");
    if (kop && kop.focus) kop.focus({ preventScroll: true });
  });
  window.addEventListener("scroll", periksa, { passive: true });
  window.addEventListener("resize", periksa);
  periksa();
})();
