/* Menu kop di layar sempit (25 Nov 2026).
 *
 * Tanpa JavaScript menu selalu terbuka (tombol "Menu" tetap tersembunyi).
 * Dengan JavaScript, kop diberi kelas "menu-js"; CSS lalu melipat menu di
 * layar <= 640 px dan memunculkan tombol "Menu". Di layar lebar tombol tetap
 * tidak tampil dan menu selalu terbuka. Esc menutup menu yang terbuka.
 */
(function () {
  "use strict";
  var kop = document.querySelector(".kop");
  var tombol = document.querySelector(".tombol-menu");
  var menu = document.getElementById("menu-utama");
  if (!kop || !tombol || !menu) return;

  kop.classList.add("menu-js");
  tombol.hidden = false;

  function setel(buka) {
    tombol.setAttribute("aria-expanded", buka ? "true" : "false");
    kop.classList.toggle("menu-terbuka", buka);
  }

  tombol.addEventListener("click", function () {
    setel(tombol.getAttribute("aria-expanded") !== "true");
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && kop.classList.contains("menu-terbuka")) {
      setel(false);
      tombol.focus();
    }
  });
})();
