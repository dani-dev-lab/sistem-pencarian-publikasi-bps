/* Saran judul entri saat mengetik.
 *
 * Peningkatan opsional (progressive enhancement): kolom pencarian adalah form
 * biasa yang sudah berfungsi tanpa JavaScript. Kalau berkas ini gagal dimuat,
 * endpoint /api/saran error, atau JavaScript dimatikan, form tetap bisa
 * dikirim seperti biasa. Fitur tambahan tidak boleh mematikan fitur utama.
 */
(function () {
  "use strict";

  var MIN_KARAKTER = 3;
  var JEDA_MS = 250;

  function pasang(input) {
    var form = input.form;
    if (!form) return;

    var kotak = document.createElement("ul");
    kotak.className = "saran-kotak";
    kotak.setAttribute("role", "listbox");
    kotak.hidden = true;

    var pembungkus = document.createElement("div");
    pembungkus.className = "saran-pembungkus";
    input.parentNode.insertBefore(pembungkus, input);
    pembungkus.appendChild(input);
    pembungkus.appendChild(kotak);

    input.setAttribute("autocomplete", "off");
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-autocomplete", "list");

    var daftar = [];
    var aktif = -1;
    var timer = null;
    var permintaan = 0;

    function tutup() {
      kotak.hidden = true;
      kotak.innerHTML = "";
      daftar = [];
      aktif = -1;
      input.setAttribute("aria-expanded", "false");
    }

    function tandai() {
      var item = kotak.children;
      for (var i = 0; i < item.length; i++) {
        var ini = i === aktif;
        item[i].classList.toggle("aktif", ini);
        item[i].setAttribute("aria-selected", ini ? "true" : "false");
      }
    }

    function pilih(i) {
      if (i < 0 || i >= daftar.length) return;
      input.value = daftar[i].judul;
      tutup();
      form.submit();
    }

    function gambar(hasil) {
      kotak.innerHTML = "";
      daftar = hasil;
      aktif = -1;

      if (!hasil.length) {
        tutup();
        return;
      }

      hasil.forEach(function (s, i) {
        var li = document.createElement("li");
        li.className = "saran-item";
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", "false");

        var tipe = document.createElement("span");
        tipe.className = "saran-tipe tipe-" + s.tipe;
        tipe.textContent = s.tipe;

        var judul = document.createElement("span");
        judul.className = "saran-judul";
        judul.textContent = s.judul;

        var pub = document.createElement("span");
        pub.className = "saran-pub";
        pub.textContent = s.publikasi;

        li.appendChild(tipe);
        li.appendChild(judul);
        li.appendChild(pub);

        // mousedown, bukan click: blur pada input tidak boleh menutup daftar
        // sebelum pilihan sempat terbaca.
        li.addEventListener("mousedown", function (e) {
          e.preventDefault();
          pilih(i);
        });
        li.addEventListener("mouseenter", function () {
          aktif = i;
          tandai();
        });

        kotak.appendChild(li);
      });

      kotak.hidden = false;
      input.setAttribute("aria-expanded", "true");
    }

    function ambil() {
      var q = input.value.trim();
      if (q.length < MIN_KARAKTER) {
        tutup();
        return;
      }

      var nomor = ++permintaan;
      fetch("/api/saran?q=" + encodeURIComponent(q))
        .then(function (r) {
          if (!r.ok) throw new Error("status " + r.status);
          return r.json();
        })
        .then(function (data) {
          // Abaikan jawaban yang datang terlambat, supaya daftar tidak
          // menampilkan hasil dari ketikan sebelumnya.
          if (nomor !== permintaan) return;
          gambar(data.saran || []);
        })
        .catch(function () {
          // Endpoint gagal bukan alasan mengganggu pencarian. Diam saja.
          tutup();
        });
    }

    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(ambil, JEDA_MS);
    });

    input.addEventListener("keydown", function (e) {
      if (kotak.hidden || !daftar.length) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        aktif = (aktif + 1) % daftar.length;
        tandai();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        aktif = aktif <= 0 ? daftar.length - 1 : aktif - 1;
        tandai();
      } else if (e.key === "Enter") {
        // Enter tanpa pilihan aktif dibiarkan mengirim form seperti biasa.
        if (aktif >= 0) {
          e.preventDefault();
          pilih(aktif);
        }
      } else if (e.key === "Escape") {
        tutup();
      }
    });

    document.addEventListener("click", function (e) {
      if (!pembungkus.contains(e.target)) tutup();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var kolom = document.querySelectorAll(".kotak-cari input[type=search]");
    for (var i = 0; i < kolom.length; i++) pasang(kolom[i]);
  });
})();
