"""Isi database dari metadata BPS dan PDF: yang menulis ke MySQL ada di sini.

Dipanggil scripts/perbarui.py, di dalam app context. Tidak ada berkas perantara:
database adalah satu-satunya catatan tentang apa yang sudah diproses.

Dua jaminan yang dijaga:
  - Satu domain, satu transaksi metadata. Metadata domain yang gagal ditarik
    tidak pernah disentuh.
  - Satu publikasi, satu transaksi entri. Entri lama dihapus dan entri baru
    beserta normalisasinya masuk bersamaan, jadi pencarian yang berjalan
    melihat versi lama atau versi baru, tidak pernah keadaan setengah jadi.
"""

import re
from collections import Counter
from datetime import date, datetime, timezone

from app.models import EntriDokumen, Kategori, Publikasi, db
from app.services.ekstraksi_pdf import ekstrak_lengkap
from app.services.normalisasi_data import teks_publikasi
from app.services.preprocessing import normalisasi
from app.services import versi_data
from app.services.sumber_bps import berkas_pdf_valid, path_pdf, samarkan, sidik_pdf

PANJANG_GALAT = 1000


def tanggal(teks):
    """rl_date / updt_date -> date. Return None kalau kosong atau tidak terbaca."""
    if not teks:
        return None
    cocok = re.match(r"\s*(\d{4})-(\d{2})-(\d{2})", str(teks))
    if not cocok:
        return None
    try:
        return date(*(int(g) for g in cocok.groups()))
    except ValueError:
        return None


def daftar_subjek(p):
    """subject_csa bisa list, null, atau string. Selalu kembalikan list str.

    Sejak ~Nov 2026 API selalu mengembalikan [] (lihat CLAUDE.md), tapi kode ini
    tetap menanganinya supaya otomatis terisi kalau API memulihkannya.
    """
    nilai = p.get("subject_csa")
    if not nilai:
        return []
    if isinstance(nilai, list):
        return [str(s).strip() for s in nilai if str(s).strip()]
    return [str(nilai).strip()]


def simpan_metadata(kode, nama_wilayah, daftar):
    """Upsert metadata satu domain dalam SATU transaksi.

    Pub_id yang sudah menjadi milik domain lain TIDAK ditimpa, hanya dilaporkan.
    Menimpanya akan memindahkan publikasi itu ke wilayah lain tanpa jejak.

    Return dict {baru, diperbarui, tabrakan, tidak_di_daftar}.
    """
    hasil = {"baru": [], "diperbarui": 0, "tabrakan": [], "tidak_di_daftar": []}

    try:
        kategori = {k.nama: k for k in Kategori.query.all()}
        for nama in sorted({s for p in daftar for s in daftar_subjek(p)}):
            if nama not in kategori:
                kategori[nama] = Kategori(nama=nama)
                db.session.add(kategori[nama])
        db.session.flush()

        for p in daftar:
            pid = p["pub_id"]
            judul = (p.get("title") or "").strip()
            pub = db.session.get(Publikasi, pid)

            if pub is not None and pub.domain != kode:
                hasil["tabrakan"].append({"pub_id": pid, "domain_lain": pub.domain,
                                          "judul_tersimpan": pub.judul, "judul_api": judul})
                continue

            if pub is None:
                pub = Publikasi(id=pid, domain=kode)
                db.session.add(pub)
                hasil["baru"].append(pid)
            else:
                hasil["diperbarui"] += 1

            # Teks ternormalisasi hanya dihitung ulang kalau sumbernya berubah.
            abstrak = p.get("abstract")
            if (pub.teks_ternormalisasi is None or pub.judul != judul
                    or pub.abstrak != abstrak):
                pub.teks_ternormalisasi = teks_publikasi(judul, abstrak)

            rilis = tanggal(p.get("rl_date"))
            pub.judul = judul
            pub.abstrak = abstrak
            pub.tanggal_rilis = rilis
            pub.tahun_terbit = rilis.year if rilis else None
            pub.url_pdf = p.get("pdf")
            pub.url_cover = p.get("cover")
            pub.issn = p.get("issn")
            pub.wilayah = nama_wilayah

            # Nilai kosong dari API bukan perubahan: pertahankan yang terakhir.
            updt = tanggal(p.get("updt_date"))
            if updt is not None:
                pub.updt_date_api = updt

            # Ganti seluruh kaitan kategori, bukan menambah - supaya perubahan
            # subjek di sumber tidak meninggalkan kaitan lama.
            pub.kategori = [kategori[n] for n in daftar_subjek(p)]

        di_daftar = {p["pub_id"] for p in daftar}
        hasil["tidak_di_daftar"] = [
            {"pub_id": pid, "judul": judul}
            for pid, judul in db.session.query(Publikasi.id, Publikasi.judul)
            .filter(Publikasi.domain == kode).all()
            if pid not in di_daftar
        ]
        versi_data.naikkan()        # korpus pencarian di memori perlu dimuat ulang
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return hasil


def susun_rencana(kode, di_daftar=None, paksa=False):
    """Publikasi yang perlu dikerjakan, ditentukan dari DATABASE.

    `di_daftar`: himpunan pub_id dari API. None berarti mode lokal - tidak ada
    jaringan, jadi tidak ada yang bisa diunduh.

    Aturannya:
      unduh + ekstrak : updt_date berubah, atau PDF hilang/rusak
      ekstrak saja    : belum pernah berhasil diekstrak, atau PDF berubah
    Publikasi yang tidak lagi ada di daftar API tidak diunduh (URL-nya tidak
    bisa dipercaya), tapi tetap ikut kalau --paksa.

    Return (tugas, menunggu_unduhan). Isinya nilai biasa, bukan objek ORM, dan
    transaksi baca ditutup di sini: ekstraksi bisa makan beberapa menit, dan
    transaksi tidak boleh terbuka selama itu.
    """
    lokal = di_daftar is None
    tugas = []
    menunggu = []

    for pub in Publikasi.query.filter_by(domain=kode).order_by(Publikasi.id).all():
        ada_di_api = not lokal and pub.id in di_daftar
        if not lokal and not ada_di_api and not paksa:
            continue

        path = path_pdf(kode, pub.id)
        utuh = berkas_pdf_valid(path)
        updt_berubah = (pub.updt_date_api is not None
                        and pub.updt_date_api != pub.updt_date_diproses)
        sidik_berubah = utuh and sidik_pdf(path) != (pub.sidik_ukuran, pub.sidik_mtime)

        alasan = []
        if pub.diekstrak_pada is None:
            alasan.append("belum pernah diekstrak")
        if updt_berubah and ada_di_api:
            alasan.append("updt_date berubah")
        if not utuh:
            alasan.append("PDF hilang/rusak")
        if sidik_berubah:
            alasan.append("PDF berubah")
        if paksa:
            alasan.append("--paksa")

        # Mode lokal tidak bisa mengambil versi terbaru. Dicatat supaya tetap
        # terlihat, dan updt_date_diproses tidak disentuh sehingga pembaruan
        # online berikutnya masih mengunduhnya.
        if lokal and updt_berubah:
            menunggu.append({"pub_id": pub.id, "judul": pub.judul,
                             "updt_date_api": pub.updt_date_api.isoformat()})
        if not alasan:
            continue

        tugas.append({
            "pub_id": pub.id,
            "judul": pub.judul,
            "url_pdf": pub.url_pdf,
            "path": path,
            "unduh": ada_di_api and (updt_berubah or not utuh),
            "updt_date_api": pub.updt_date_api,
            "belum_pernah": pub.diekstrak_pada is None,
            "alasan": alasan,
        })

    db.session.commit()
    return tugas, menunggu


def ekstrak_berkas(path, pub_id):
    """Jalankan parser. Tidak menyentuh database. Return (entri, catatan)."""
    # Heading dicatat supaya bisa membedakan "daftarnya memang tidak ada" dari
    # "daftarnya ada tapi gagal dibaca". Diambil dari dalam ekstrak_lengkap(),
    # bukan dicari ulang: mencarinya dua kali menambah sekitar 16% waktu.
    heading = {}
    jejak = []
    entri, n_daftar, n_badan, n_lengkap, n_isi = ekstrak_lengkap(
        path, pub_id, jejak, heading_keluar=heading)

    catatan = {
        "heading_ditemukan": sorted(heading),
        "jumlah_entri": len(entri),
        "per_tipe": dict(Counter(e["tipe"] for e in entri)),
        "per_sumber": dict(Counter(e["sumber"] for e in entri)),
        "tanpa_halaman": sum(1 for e in entri if not e["halaman"]),
        "mode_tanpa_label": jejak,
        "dari_daftar": n_daftar,
        "dari_badan": n_badan,
        "halaman_fisik_dilengkapi": n_lengkap,
        "halaman_fisik_isi": n_isi,
    }
    return entri, catatan


def simpan_entri(pub_id, entri, sidik, catatan, updt_diproses=None):
    """Ganti seluruh entri satu publikasi dalam SATU transaksi.

    `updt_diproses` diisi HANYA kalau PDF benar-benar diunduh pada run ini.
    Mengekstrak ulang PDF lama (--paksa, mode lokal) tidak boleh menandai
    publikasi itu sudah mengikuti versi terbaru dari BPS.
    """
    try:
        EntriDokumen.query.filter_by(publikasi_id=pub_id).delete(
            synchronize_session=False)
        for e in entri:
            db.session.add(EntriDokumen(
                publikasi_id=pub_id,
                tipe=e["tipe"],
                nomor=e.get("nomor"),
                judul=e["judul"],
                halaman=e.get("halaman"),
                halaman_fisik=e.get("halaman_fisik"),
                sumber=e.get("sumber", "daftar"),
                teks_ternormalisasi=normalisasi(e["judul"]),
            ))

        pub = db.session.get(Publikasi, pub_id)
        pub.sidik_ukuran, pub.sidik_mtime = sidik
        pub.diekstrak_pada = datetime.now(timezone.utc)
        pub.galat_ekstraksi = None
        pub.catatan_ekstraksi = catatan
        if updt_diproses is not None:
            pub.updt_date_diproses = updt_diproses
        versi_data.naikkan()        # korpus pencarian di memori perlu dimuat ulang
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def catat_galat(pub_id, pesan):
    """Simpan pesan galat. Entri lama dan diekstrak_pada sengaja tidak disentuh."""
    try:
        pub = db.session.get(Publikasi, pub_id)
        pub.galat_ekstraksi = samarkan(pesan)[:PANJANG_GALAT]
        db.session.commit()
    except Exception:  # noqa: BLE001 - gagal mencatat galat tidak boleh menghentikan proses
        db.session.rollback()


def perlu_diperiksa(catatan):
    """Alasan hasil ekstraksi ini layak diperiksa manual, atau None."""
    jumlah = catatan["jumlah_entri"]
    per_tipe = catatan["per_tipe"]
    if jumlah == 0:
        return "0 entri sama sekali"
    buntu = [t for t in catatan["heading_ditemukan"] if not per_tipe.get(t)]
    if buntu:
        return f"heading {', '.join(buntu)} ada tapi 0 entri"
    if set(per_tipe) == {"isi"}:
        return "hanya Daftar Isi, tidak ada tabel/gambar/lampiran"
    if catatan["tanpa_halaman"] > jumlah * 0.25:
        return f"{catatan['tanpa_halaman']}/{jumlah} entri tanpa nomor halaman"
    return None
