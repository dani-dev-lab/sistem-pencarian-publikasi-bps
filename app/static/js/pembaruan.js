/* Halaman /admin/perbarui: tampilkan keluaran pembaruan secara langsung.
 *
 * Peningkatan opsional. Tanpa berkas ini halaman tetap berfungsi: proses
 * berjalan di server, dan <meta refresh> di <noscript> memuat ulang halaman
 * tiap 5 detik sampai ringkasan akhir tampil.
 *
 * Dua mode, dipilih dari atribut data-* elemen #log-pembaruan:
 *   data-berjalan="1"  -> tarik /admin/perbarui/aliran dan tempelkan tiap
 *                         potongan yang datang; begitu aliran habis (proses
 *                         selesai), muat ulang supaya ringkasan dirender server.
 *   data-poll="N"      -> pembaruan dijalankan dari terminal/.bat, keluarannya
 *                         tidak bisa dibaca dari sini; cukup muat ulang tiap N
 *                         detik sampai kuncinya lepas.
 */
(function () {
  "use strict";

  var log = document.getElementById("log-pembaruan");
  if (!log) return;

  if (log.dataset.poll) {
    setTimeout(function () { location.reload(); },
               parseInt(log.dataset.poll, 10) * 1000);
    return;
  }
  if (log.dataset.berjalan !== "1" || !window.fetch || !window.TextDecoder) return;

  var url = log.dataset.url + "?dari=" + encodeURIComponent(log.dataset.dari || "0");
  var decoder = new TextDecoder();

  fetch(url, { cache: "no-store" })
    .then(function (r) {
      if (!r.ok || !r.body) throw new Error("aliran tidak tersedia");
      var reader = r.body.getReader();
      function baca() {
        return reader.read().then(function (bagian) {
          if (bagian.done) {
            // Proses selesai: server yang merender ringkasannya.
            location.reload();
            return;
          }
          var ikutiBawah = log.scrollTop + log.clientHeight >= log.scrollHeight - 24;
          log.textContent += decoder.decode(bagian.value, { stream: true });
          if (ikutiBawah) log.scrollTop = log.scrollHeight;
          return baca();
        });
      }
      return baca();
    })
    .catch(function () {
      // Koneksi terputus (mis. laptop tidur): coba lagi dengan memuat ulang.
      setTimeout(function () { location.reload(); }, 3000);
    });
})();
