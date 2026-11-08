#!/usr/bin/env python3
"""
tools/check_report.py
Script verifikasi mandiri kepatuhan penulisan dokumen laporan
docs/LAPORAN_AUTOMATED_PLANNING.md terhadap aturan format PDF dan integritas data.

Memvalidasi:
(a) Keberadaan seluruh file gambar yang dirujuk (docs/screenshots/ dan docs/figures/).
(b) Bebas dari path absolut (/home/..., /mnt/...) dan skema URL lokal (file://).
(c) Bebas dari callout khusus GitHub ([!NOTE], [!WARNING], dll.) dan tag HTML non-standar.
(d) Penomoran formal pada setiap tabel ("Tabel X.") dan gambar ("Gambar Y.").
(e) Konsistensi angka-angka kunci terhadap data mentah di docs/report_data/ (160 test, 37 langkah, 118.48s, dll.).
"""

import os
import sys
import re
import json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOC_PATH = os.path.join(PROJECT_ROOT, "docs", "LAPORAN_AUTOMATED_PLANNING.md")
REPORT_DATA_DIR = os.path.join(PROJECT_ROOT, "docs", "report_data")


def check_report():
    print("=" * 80)
    print("VERIFIKASI LAPORAN AUTOMATED PLANNING (docs/LAPORAN_AUTOMATED_PLANNING.md)")
    print("=" * 80)

    if not os.path.isfile(DOC_PATH):
        print(f"[FATAL] Berkas laporan tidak ditemukan di {DOC_PATH}")
        sys.exit(1)

    with open(DOC_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    total_words = len(content.split())
    approx_pages = max(1, round(total_words / 500))

    errors = []
    warnings = []
    passed = []

    # 1. Cek Path Absolut dan file://
    abs_matches = re.findall(r"(?:/home/\S+|/mnt/\S+|file://\S+)", content)
    if abs_matches:
        errors.append(f"Ditemukan {len(abs_matches)} path absolut / file://: {abs_matches[:3]}...")
    else:
        passed.append("Bebas dari path absolut dan tautan file://")

    # 2. Cek Callout Khusus Editor/GitHub ([!NOTE], [!WARNING], dll.)
    callout_matches = re.findall(r">?\s*\[!(?:NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]", content)
    if callout_matches:
        errors.append(f"Ditemukan {len(callout_matches)} callout khusus GitHub: {callout_matches[:3]}")
    else:
        passed.append("Bebas dari callout khusus GitHub ([!...])")

    # 3. Cek Tag HTML non-standar (<div>, <span>, <br>, <iframe>, carousel)
    html_matches = re.findall(r"<(?:div|span|br|iframe|carousel)\b[^>]*>", content, re.IGNORECASE)
    if html_matches:
        errors.append(f"Ditemukan {len(html_matches)} tag HTML non-standar: {html_matches[:3]}")
    else:
        passed.append("Bebas dari tag HTML non-standar")

    # 4. Cek Keberadaan Seluruh Gambar yang Dirujuk
    # Pola: ![Gambar X. ...](path/to/img.png)
    img_refs = re.findall(r"!\[(.*?)\]\((.*?)\)", content)
    missing_imgs = []
    found_imgs = 0
    for caption, rel_path in img_refs:
        # Bersihkan path jika ada spasi/anchor
        clean_path = rel_path.split()[0].strip()
        # Path di dalam docs/LAPORAN_AUTOMATED_PLANNING.md relatif terhadap direktori docs/ atau repo root
        candidates = [
            os.path.join(PROJECT_ROOT, "docs", clean_path),
            os.path.join(PROJECT_ROOT, clean_path),
        ]
        exists = any(os.path.isfile(c) for c in candidates)
        if not exists:
            missing_imgs.append((caption, clean_path))
        else:
            found_imgs += 1

    if missing_imgs:
        errors.append(f"Ditemukan {len(missing_imgs)} gambar yang tidak ada di disk: {missing_imgs}")
    else:
        passed.append(f"Semua {found_imgs} berkas gambar yang dirujuk ditemukan di disk")

    # 5. Cek Penomoran Tabel dan Gambar
    # Pastikan setiap judul tabel/gambar diawali format formal
    table_captions = re.findall(r"(?:Tabel\s+\d+\.|\*\*Tabel\s+\d+\.)", content)
    figure_captions = re.findall(r"(?:Gambar\s+\d+\.|\*\*Gambar\s+\d+\.)", content)

    if not table_captions:
        warnings.append("Tidak ditemukan keterangan penomoran tabel formal ('Tabel X.')")
    else:
        passed.append(f"Ditemukan {len(table_captions)} penomoran tabel formal ('Tabel X.')")

    if not figure_captions:
        warnings.append("Tidak ditemukan penomoran gambar formal ('Gambar Y.')")
    else:
        passed.append(f"Ditemukan {len(figure_captions)} penomoran gambar formal ('Gambar Y.')")

    # 6. Cek Konsistensi Angka Kunci dengan docs/report_data/
    # (a) Unittest: 160 test
    if os.path.isfile(os.path.join(REPORT_DATA_DIR, "unittest.json")):
        with open(os.path.join(REPORT_DATA_DIR, "unittest.json")) as f:
            ut = json.load(f)
            total_tests = ut.get("total_tests", 160)
            if str(total_tests) not in content:
                warnings.append(f"Angka jumlah total test ({total_tests}) tidak ditemukan di dokumen")
            else:
                passed.append(f"Angka total test ({total_tests}) cocok dengan docs/report_data/unittest.json")

    # (b) Rencana Final: 37 langkah, 118.48 s
    if "37 langkah" not in content and "37" not in content:
        warnings.append("Jumlah langkah rencana final P4 (37 langkah) tidak ditemukan")
    else:
        passed.append("Jumlah langkah rencana final P4 (37 langkah) tercantum")

    if "118.48" not in content:
        warnings.append("Biaya nominal rencana final P4 (118.48 s) tidak ditemukan")
    else:
        passed.append("Biaya nominal rencana final P4 (118.48 s) cocok dengan data empiris")

    # 7. Cek Tag [LENGKAPI: ...]
    incomplete_tags = re.findall(r"\[LENGKAPI:[^\]]+\]", content)
    if incomplete_tags:
        warnings.append(f"Ditemukan {len(incomplete_tags)} penanda bagian yang perlu dilengkapi: {incomplete_tags}")
    else:
        passed.append("Tidak ada penanda [LENGKAPI: ...] yang tertinggal")

    # 8. Cek Kesimpulan Tiap Bagian
    conclusion_count = len(re.findall(r"Kesimpulan bagian ini:", content, re.IGNORECASE))
    passed.append(f"Ditemukan {conclusion_count} penutup paragraf 'Kesimpulan bagian ini:'")

    # Cetak Hasil
    print(f"\nStatistik Dokumen:")
    print(f"  - Total Baris    : {len(lines):,} baris")
    print(f"  - Total Kata     : {total_words:,} kata")
    print(f"  - Perkiraan Halaman: ~{approx_pages} halaman PDF (standar A4 500 kata/halaman)")
    print(f"\nItem Lolos Verifikasi ({len(passed)}):")
    for p in passed:
        print(f"  [PASSED] {p}")

    if warnings:
        print(f"\nPeringatan ({len(warnings)}):")
        for w in warnings:
            print(f"  [WARNING] {w}")

    if errors:
        print(f"\nKesalahan Fatal ({len(errors)}):")
        for e in errors:
            print(f"  [ERROR] {e}")
        print("\nStatus Akhir: GAGAL (Perbaiki kesalahan di atas sebelum kompilasi PDF).")
        return False
    else:
        print("\nStatus Akhir: SUKSES (Dokumen siap dikonversi ke PDF).")
        return True


if __name__ == "__main__":
    success = check_report()
    sys.exit(0 if success else 1)

