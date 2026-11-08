# Panduan Kompilasi Dokumen Laporan ke PDF

Dokumen laporan utama perencanaan otomatis tersedia di `docs/LAPORAN_AUTOMATED_PLANNING.md`. Dokumen ini disusun menggunakan Markdown standar yang bersih dari tag HTML non-standar, callout GitHub khusus, dan tautan absolut, sehingga sepenuhnya kompatibel untuk dikonversi menjadi dokumen PDF formal berkualitas publikasi.

Berikut adalah opsi dan instruksi lengkap untuk mengonversi dokumen laporan ke berkas PDF:

---

## Opsi 1: Menggunakan Pandoc dan XeLaTeX (Direkomendasikan untuk Hasil Akademis Formal)

Pandoc yang dipadukan dengan mesin `xelatex` memberikan hasil typesetting tipografi terbaik untuk tabel, rumus matematika LaTeX, dan perataan gambar.

### Perintah Kompilasi Dasar
Jalankan perintah berikut dari direktori akar proyek:

```bash
pandoc docs/LAPORAN_AUTOMATED_PLANNING.md -o docs/LAPORAN_AUTOMATED_PLANNING.pdf \
  --toc \
  --toc-depth=3 \
  --number-sections \
  --pdf-engine=xelatex \
  --resource-path=docs \
  -V geometry:margin=2.5cm \
  -V papersize=a4 \
  -V colorlinks=true \
  -V linkcolor=blue \
  -V urlcolor=blue \
  -V mainfont="DejaVu Sans"
```

### Rekomendasi Font Sistem
Gunakan font Unicode lengkap yang mendukung karakter matematis dan simbol, antara lain:
- **DejaVu Sans** / **DejaVu Serif** (tersedia luas di Linux dan Windows)
- **Noto Sans** / **Noto Serif** (paket font Google multilingual)
- **Liberation Sans** / **Liberation Serif**

Contoh opsi font Pandoc:
```bash
  -V mainfont="Noto Sans" \
  -V monofont="DejaVu Sans Mono"
```

### Paket LaTeX yang Diperlukan (Bila Menggunakan Instalasi Minimal TeX Live)
Pastikan paket TeX berikut telah terpasang di sistem operasi:
- `texlive-xetex`
- `texlive-latex-extra`
- `texlive-fonts-recommended`
- `texlive-lang-other` (bila diperlukan)

---

## Opsi 2: Ekstensi VS Code (Markdown PDF / Marp / Markdown Preview Enhanced)

Bagi pengembang yang menggunakan Visual Studio Code atau Codium, konversi dapat dilakukan langsung melalui antarmuka grafis:

1. Buka berkas `docs/LAPORAN_AUTOMATED_PLANNING.md` di VS Code.
2. Pasang ekstensi **Markdown PDF** (`yzane.markdown-pdf`) dari VS Code Marketplace.
3. Buka Command Palette (`Ctrl+Shift+P`) lalu ketik dan pilih:
   `Markdown PDF: Export (pdf)`.
4. Berkas PDF otomatis tersimpan di folder `docs/` dengan seluruh styling CSS tabel dan gambar yang terintegrasi.

---

## Opsi 3: Menggunakan Editor Typora

1. Buka berkas `docs/LAPORAN_AUTOMATED_PLANNING.md` menggunakan editor Typora.
2. Masuk ke menu **File** $\to$ **Export** $\to$ **PDF**.
3. Pastikan opsi *Header & Footer* menyertakan nomor halaman dan *Include Table of Contents* dicentang.
4. Klik **Save**.

---

## Opsi 4: Menggunakan Chromium Headless / Weasyprint

Bila Pandoc dipadukan dengan mesin HTML-to-PDF:
```bash
pandoc docs/LAPORAN_AUTOMATED_PLANNING.md -o docs/LAPORAN_AUTOMATED_PLANNING.pdf \
  --toc \
  --number-sections \
  --pdf-engine=weasyprint \
  --resource-path=docs
```

---

## Verifikasi Mandiri Sebelum Ekspor

Sebelum melakukan ekspor atau penyerahan laporan, jalankan script cek integritas:
```bash
python3 tools/check_report.py
```
Script tersebut akan memvalidasi bahwa seluruh gambar lokal tersedia, tidak ada tautan `file://` atau path absolut, semua tabel bernomor dan memiliki sumber data, serta angka kunci di laporan konsisten dengan berkas mentah di `docs/report_data/`.

