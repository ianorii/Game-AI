# ROADMAP & SPESIFIKASI PROYEK: AI LABYRINTH (THE DUNGEON OVERSEER)

Dokumen ini memuat seluruh rencana kerja, urutan fase pengerjaan, checklist fitur, aturan desain, dan spesifikasi verifikasi yang disepakati langsung dari ruang kerja arsitektur utama (`chat/5edab99b-6887-47c6-9f3c-58538dd79984`). Dokumen ini berfungsi sebagai acuan tunggal (*single source of truth*) dalam pengembangan dan evaluasi.

---

## 1. ATURAN DESAIN & BATASAN ARSITEKTUR

1. **Mandiri Penuh (*From Scratch*)**:
   - Seluruh modul AI (A*, Dijkstra, CSP, Local Search, Minimax/Alpha-Beta, STRIPS, HTN, Bayes, MDP) **wajib diimplementasikan mandiri tanpa library AI/MDP eksternal**.
2. **Isolasi & Kemandirian Modul**:
   - Pengerjaan fase/putaran baru dilarang merusak (*break*) atau mengubah modul yang sudah stabil dan lulus uji (kontrol manual hero, sistem battle Minimax, CSP solver, local search).
3. **Integritas Pelaporan & Angka Mentah**:
   - Seluruh angka ringkasan (persentase cakupan, luas hilang, jumlah pelanggaran, selisih piksel) **wajib dihitung langsung oleh skrip/alat uji dari data mentah**, bukan diketik manual. Disimpan di `docs/report_data/`.
   - Laporan harus memuat tabel (poin | status | bukti) dan wajib menyertakan bagian "Hal yang bermasalah" (tidak boleh dikosongkan).
4. **Kebijakan Tampilan & Tombol**:
   - **Dilarang menambah tombol F baru** (seluruh F1–F12 sudah terpakai). Tampilan baru diintegrasikan sebagai **Tab baru di Panel F7**.
   - Teks UI minimal 14 px dan tidak boleh tumpang tindih (*no overlapping*).
   - Dilarang mengubah peta asli (`Room1.yy` / `sunnyside_isle.json`). Jika perlu detour atau rute alternatif, gunakan koridor alami.
5. **Kebijakan Pengujian**:
   - Semua operasi berkas pengujian wajib menggunakan folder sementara (`tempfile.TemporaryDirectory`).
   - Semua algoritma probabilistik/RNG wajib menggunakan `seed` deterministik.
6. **Kebijakan Git**:
   - **DILARANG KERAS melakukan `git commit` otomatis**. Seluruh modifikasi kode harus tetap dalam status *unstaged/uncommitted* hingga pengguna sendiri yang menginstruksikannya.

---

## 2. URUTAN FASE & STATUS IMPLEMENTASI

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ FASE 0: Pondasi Game, Aset Sunnyside, Minimax & CSP (SELESAI)                │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────────────────┐
│ FASE 1: Automated Planning STRIPS & HTN (SELESAI)                             │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────────────────┐
│ FASE 2: Putaran 1 & 2 - Collision Audit & Modul Decision Inti (SELESAI)      │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────────────────┐
│ FASE 3: Putaran 3 & Penutup - Decisions Under Uncertainty & Verifikasi (LULUS)│
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. CHECKLIST DETAIL FITUR PUTARAN 3 & PUTARAN PENUTUP

### BAGIAN 0: Perbaikan Kecil Sisa Putaran 1
- [x] **0.a. Validasi Visual Tile Gerbang**:
  - Potong tile pilar batu Sunnyside (`c=49..50, r=28..30`) dan daun pintu kayu (`c=35, 37, r=24`) dengan perbesaran 4x ke PNG (`docs/figures/tile_debug/gate_tiles_used_4x.png`).
  - Gerbang terbaca jelas: lengkung batu + daun pintu kayu tertutup vs terlipat saat terbuka (`docs/screenshots/gate_closeup_side_by_side.png`).
- [x] **0.b. Klarifikasi & Kesejajaran Obstacle Gerbang**:
  - Obstacle disesuaikan menjadi 96x32 di tapak daratan (`y=832..864`), 100% di daratan kering dengan clearance 2 tile ke garis air. Flood-fill membuktikan: tertutup = Boss unreachable; terbuka = Boss reachable; 12 LOCATIONS tetap reachable.
- [x] **0.c. Penataan & Klasifikasi Inventaris Entitas**:
  - Tepat 14 entitas bergerak (1 Hero, 2 NPC: Pak Tani & Kang Penggiling, 11 Hewan: 4 Domba, 2 Sapi, 3 Ayam, 2 Bebek air) + 1 Boss Statis (Skeleton Overlord di `2464, 448`) = 15 total entitas di dunia aktif.
- [x] **0.d. Tabel Detail Footprint Per Bangunan**:
  - Tabel per bangunan tersimpan di `docs/report_data/footprint_audit.csv` & `footprint_audit.json`. Rata-rata area terbuang 5.52% disebabkan oleh perhitungan alpha masking non-transparan pada atap miring (bukan bounding box kasar).
- [x] **0.e. Simulasi 20 Menit Game Loop pada 60 FPS**:
  - Simulasi 20 menit (72.000 langkah, 1.080.000 cek tabrakan entitas) di `tools/simulate_game_loop_20min.py` mencatat 0 pelanggaran. Versi simulasi 60 detik (3.600 langkah) berjalan langsung di test suite `tests/test_collision_and_decor_fixes.py`.
- [x] **0.f. Perbaikan Jam Simulasi HTN**:
  - WorldClock menampilkan fase diurnal akurat: `PAGI (0.1s / 90.0s)` pada awal hari, menghindari anomali "SIANG pada 0.1s". Hubungan multi-timescale dengan siklus cuaca 240s didokumentasikan.
- [x] **0.g. Cetak Bukti Verifikasi**:
  - Log unittest 207 test OK di `docs/report_data/unittest.json`, selftest 120 frame di `docs/report_data/selftest.txt`, dan checksums SHA256 di `docs/report_data/checksums.sha256`.

---

### BAGIAN 1: Model Cuaca & Zona Rawan Banjir
- [x] **1.1. Siklus Cuaca Probabilistik**:
  - Siklus hari cuaca (240 detik di `src/config.py` atau saat hero `Rest`).
  - Kondisi banjir tersembunyi dibangkitkan dari prior $P(\text{Banjir}) = 0.10$ tanpa bisa diintip langsung oleh pemain/AI.
- [x] **1.2. Pemetaan Zona Rawan Banjir & Dua Rute**:
  - Zona rawan: area walkable pesisir pantai (`(2016, 864, 352, 96)`).
  - Rute Pintas: $168.2 \text{ px} \implies 1.14 \text{ s}$ (Full corridor: $480 \text{ px} \implies 3.26 \text{ s}$).
  - Rute Aman: $220.4 \text{ px} \implies 1.50 \text{ s}$ (Full corridor: $608 \text{ px} \implies 4.13 \text{ s}$, +31% jarak).
- [x] **1.3. Konsekuensi Fisik Banjir & Nearest Dry Tile**:
  - Hero di zona rawan saat banjir dievakuasi ke tile kering terdekat (`(2096, 848)`) via algoritma `find_nearest_dry_tile`.
  - Memicu animasi asli `swimming` (12 frame `base_swimming_strip12.png`), penalti waktu fisik terkalibrasi $2.70 \text{ s}$. NPC & hewan tidak terpengaruh.

---

### BAGIAN 2: Sistem Bukti Bayes (Bayesian Belief Update)
- [x] **2.1. Papan Pengumuman Cuaca Desa (Weather Notice Board)**:
  - Prop papan petunjuk di alun-alun desa (`(1504, 1024)`), tombol `[E]` (maksimal 1x per hari cuaca).
  - Likelihood resmi: $P(\text{Berita} \mid \text{Banjir}) = 0.90$, $P(\text{Berita} \mid \text{NoBanjir}) = 0.10$.
  - Pembaruan posterior via `bayes_update()`: Berita -> $0.50$, Cerah -> $0.0122$.
- [x] **2.2. Bukti Sekunder (Opsional / Rumor NPC)**:
  - Rumor cuaca terintegrasi dalam modul probabilistik.

---

### BAGIAN 3: MDP Rute & Penentuan Titik Belok $f^*$
- [x] **3.1. Konstruksi Model MDP Rute**:
  - State space: Rumah, Warung, Jalan Raya, Kampus (+10), Banjir (-20).
  - Step reward: $-2.0$, diskon $\gamma = 0.8$.
- [x] **3.2. Evaluasi Kebijakan Dinamis & Kalibrasi Opsi (b)**:
  - Value iteration sinkron konvergen dalam $< 5$ iterasi.
  - Titik potong indiferen analitik: $f^* = \frac{4}{30} = \frac{2}{15} \approx 0.1333$.
  - Policy: $f < f^* \implies \text{Pintas}$, $f \ge f^* \implies \text{Raya}$.
  - Terkalibrasi dengan delay fisik $2.70 \text{ s}$ sehingga prior normal ($10\%$) memilih Pintas dan Berita Banjir ($50\%$) memilih Raya.

---

### BAGIAN 4: Integrasi Planner & Autopilot
- [x] **4.1. Seleksi Aksi `goto` Berbasis Kebijakan**:
  - Rekomendasi rute berdasarkan $\pi^*(s)$.
- [x] **4.2. Monitor Pemicu Replanning (`TRIGGER_BELIEF_UPDATE`)**:
  - Memicu evaluasi ulang rencana saat keyakinan banjir melampaui $f^*$.
- [x] **4.3. Banner Rekomendasi Mode ADVISOR**:
  - Menampilkan rekomendasi rute dan EU: Pintas vs Raya di HUD banner.

---

### BAGIAN 5: Tampilan Antarmuka (UI Panel F7 & Efek Visual)
- [x] **5.1. Tab "Ketidakpastian" di Panel F7**:
  - Menggunakan Tab 3 tanpa menambah hotkey baru.
  - Menampilkan bar visual $P(\text{Banjir})$ dengan garis $f^*$, rumus Bayes, $Q$-values, dan komparasi plan vs policy.
  - Font $\ge 14$ px / linesize $\ge 12-16$ px tanpa overlap.
- [x] **5.2. Visualisasi Banjir Sederhana**:
  - Efek puddle genangan air bergelombang di zona rawan pantai saat banjir aktif.

---

### BAGIAN 6: Evaluasi Empiris (Simulasi Monte Carlo $N \ge 10.000$)
- [x] **6.1. Dual Benchmark Monte Carlo**:
  - Model Slide Abstrak: Fast = $7.06$, Safe = $6.00$, Blind = $7.06$, Adaptive = $9.03$ (Teori: $8.98$, 95% CI: $[8.967, 9.090]$).
  - Model Game Nyata (Detik): Fast = $1.4046\text{ s}$, Safe = $1.5000\text{ s}$, Blind = $1.4046\text{ s}$, Adaptive = $1.2274\text{ s}$ (Teori: $1.2318\text{ s}$, 95% CI: $[1.2219, 1.2330]$).
  - Penghematan waktu nyata: $+0.1772 \text{ s}$ (~$0.18\text{ s}$). VPI $= +1.98$ (dilabeli ekstensi).

---

### BAGIAN 7: Dokumentasi & Pelaporan
- [x] **7.1. Dokumen Teknis `docs/DECISION_UNCERTAINTY.md`**:
  - Dokumen teknis komprehensif memetakan slide 3-23, konsistensi model, opsi kalibrasi (a) vs (b), multi-timescale, dual Monte Carlo, dan evaluasi keterbatasan jujur.
- [x] **7.2. Integrasi ke Generator Laporan (`tools/make_report_data.py`)**:
  - Menghasilkan seluruh 10 tahap laporan data mentah secara otomatis.

---

### BAGIAN 8: Verifikasi & Test Otomatis
- [x] **8.1. Test Suite Komprehensif**:
  - 14 berkas test, 213 unit test total: 100% lulus (`Ran 213 tests in ~85s. OK`).
- [x] **8.2. Pengujian Sistem Menyeluruh**:
  - Selftest 120 frame lolos. Demo CLI ojek, regression, dan graph lolos. Demo CLI decision lolos.
