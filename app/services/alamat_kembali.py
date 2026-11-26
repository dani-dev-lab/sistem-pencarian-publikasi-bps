"""Alamat "Kembali ke Pencarian" dari halaman admin (26 Nov 2026).

Tombol "Halaman Admin" di halaman pencarian/hasil membawa alamat halaman itu
(path + query) sebagai `?dari=` ke /admin/*. Admin menyimpannya di session
(KUNCI_ALAMAT) dan menyimpannya terus selama di admin, termasuk melewati
login. Tombol "Kembali ke Pencarian" menuju /kembali, yang memasang penanda
SEKALI PAKAI (KUNCI_DARI_ADMIN) lalu mengalihkan ke alamat itu. Halaman
pencarian yang dibuka dengan penanda itu:
  - tidak menulis log_pencarian (kueri yang sama sudah tercatat saat dicari);
  - meminta posisi gulir dipulihkan (js/gulir-kembali.js, sessionStorage).

Alamat datang dari URL, jadi bisa diisi siapa saja. Satu aturan di sini
(`alamat_aman`) mencegah open redirect: hanya path relatif berawalan "/"
ke halaman pencarian aplikasi ini.
"""
from urllib.parse import urlsplit

# Session: alamat halaman pencarian terakhir sebelum masuk admin.
KUNCI_ALAMAT = "kembali_pencarian"
# Session: alamat yang baru dibuka lewat tombol Kembali (dipakai sekali).
KUNCI_DARI_ADMIN = "dari_admin_sekali"

# Path halaman pencarian (relatif terhadap akar aplikasi, seperti
# request.full_path). Selain ini, misalnya /admin/..., /pdf/..., /api/...,
# alamat ditolak.
JALUR_PENCARIAN = ("/", "/hasil")
# Session Flask disimpan di cookie (batas ±4 KB); kueri wajar jauh lebih
# pendek.
PANJANG_MAKS = 1000


def alamat_aman(alamat):
    """Kembalikan `alamat` kalau aman sebagai tujuan Kembali, selain itu None.

    Aman = teks, <= PANJANG_MAKS, berawalan satu "/" (bukan "//"), tanpa "\\",
    tanpa karakter kendali, tanpa skema/host/fragmen, dan path-nya PERSIS
    "/" atau "/hasil". Contoh ditolak: "//evil.com", "/\\evil.com",
    "http://evil.com/", "/admin/log", "/hasil/../admin", "hasil?q=a".
    """
    if not isinstance(alamat, str):
        return None
    a = alamat.strip()
    if not a or len(a) > PANJANG_MAKS:
        return None
    if not a.startswith("/") or a.startswith("//") or "\\" in a:
        return None
    if any(ord(c) < 32 or ord(c) == 127 for c in a):
        return None
    bagian = urlsplit(a)
    if bagian.scheme or bagian.netloc or bagian.fragment:
        return None
    if bagian.path not in JALUR_PENCARIAN:
        return None
    return a
