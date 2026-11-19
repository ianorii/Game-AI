# PANDUAN & LAPORAN RESMI: AUTOMATED PLANNING
## Sistem Perencanaan Otomatis Terintegrasi (STRIPS, WA*, & HTN) — Sunnyside Isle

---

### 1. Ringkasan Eksekutif & Pemetaan Teori

Modul **Automated Planning** pada game *AI Labyrinth: Sunnyside Isle* mengimplementasikan kurikulum standar kecerdasan buatan untuk domain perencanaan (*classical & hierarchical automated planning*). Seluruh sistem dibangun menggunakan Python murni tanpa pustaka perencanaan eksternal, dan terintegrasi secara *real-time* ke dalam *game loop* Pygame.

Sistem perencanaan ini mencakup:
1. **Representasi STRIPS & PDDL Formal**: Skema aksi berbasis predikat, efek tambah/hapus (*Add/Delete lists*), dan prasyarat (*Preconditions*).
2. **Mesin Pencarian Ruang Keadaan (*Forward State-Space Search*)**: Algoritma graf pencarian lengkap meliputi BFS, UCS, A*, dan Weighted A* ($WA^*$) dengan penimbang $w = 1.5$.
3. **Keluarga Heuristik *Ignore-Delete-Lists***: Implementasi $h_{\text{add}}$ (tidak konsisten/non-admissible), $h_{\text{max}}$ (admissible), dan $h_{\text{FF}}$ (*Relaxed Fast-Forward Plan length*) dengan optimasi *Helpful Actions*.
4. **Planning Graph & Ekstraksi Mutex**: Konstruksi level literal dan level aksi untuk mengidentifikasi relasi *Mutual Exclusion* (Inconsistent Effects, Interference, Competing Needs) dan menghasilkan heuristik graf level $h_{\text{level}}$.
5. **Regresi Tujuan Mundur (*Backward Goal Regression*)**: Verifikasi pencarian dari *goal state* mundur ke *initial state* menggunakan regresi prasyarat aksi.
6. **Eksekusi & Monitoring Real-Time**: Subsistem *PlanMonitor* dan *PlanExecutor* beranggaran komputasi ketat ($< 20\text{ ms}$ per *frame*, rata-rata $1.1\text{ ms}$) dengan kemampuan *re-planning* instan saat terdeteksi anomali lingkungan.
7. **Dekomposisi Tugas Hierarkis (HTN)**: Modul *Shop-style Hierarchical Task Network* untuk rutinitas harian NPC desa (Pak Tani & Kang Penggiling) yang terikat jam dunia (*WorldClock*).

---

### 2. Arsitektur Modul & Struktur Berkas

```text
src/planning/
├── strips.py             # Definisi Predicate, GroundAction, STRIPSState, dan ActionSchema
├── pddl_parser.py        # Parser berkas domain & problem PDDL (.domain, .problem)
├── problem_generator.py  # Generator problem ekspedisi dinamis dari WorldState game
├── heuristics.py         # Heuristik perencanaan: h_add, h_max, h_FF (Relaxed Plan)
├── planning_graph.py     # Konstruksi Planning Graph, mutex actions/literals, h_level
├── regression.py         # Algoritma Backward Goal Regression (analisis Slide 27)
├── planner.py            # Solver pencarian: BFS, UCS, A*, WA*, dan Helpful Actions
├── distance_matrix.py    # Matriks jarak geodesik & polyline A* antar titik penting di pulau
├── executor.py           # Penerjemah aksi rencana menjadi operasi konkret di WorldState
├── monitor.py            # PlanMonitor: validasi prekondisi kontinu & trigger re-plan (< 20ms)
├── autopilot.py          # AutopilotController: navigasi hero fisik di peta, animasi & override
├── htn.py                # Engine Shop-style HTN, parser .htn, agen NPC Pak Tani & Miller
└── planner_ui.py         # UI Dock Inspector [F7], Segmented Tabs, visualisasi status aksi

data/planning/
├── expedition.domain     # PDDL Domain resmi ekspedisi pulau Sunnyside (15 aksi terdaftar)
├── expedition.problem    # PDDL Problem lengkap ekspedisi (37 langkah, biaya 118.48s)
├── npc.htn               # Skema dekomposisi hierarkis aktivitas NPC desa
├── ojek.domain & .problem # Domain benchmark klasik pembuktian regresi & graf
└── readiness.json        # Evaluasi kesiapan hero sebelum menghadapi boss (Monte Carlo N=200)
```

---

### 3. Empat Masalah Uji Standar ($P_1 - P_4$)

Sistem dievaluasi pada 4 tingkatan kompleksitas skenario ekspedisi:

| Masalah | Deskripsi Masalah | Algoritma Rekomendasi | Node Tereksplorasi | Waktu Eksekusi | Panjang / Biaya |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **$P_1$ (Key Craft)** | Mengumpulkan kayu & batu, lalu menempa kunci segel di bengkel desa. | A* ($h_{\text{max}}$) | 16 node | $0.8\text{ ms}$ | 6 langkah / $24.5\text{ s}$ |
| **$P_2$ (Open Gate)** | Membawa kunci ke pantai timur dan membuka gerbang pembatas arena. | A* ($h_{\text{max}}$) | 29 node | $1.5\text{ ms}$ | 12 langkah / $42.0\text{ s}$ |
| **$P_3$ (Potion)** | Menanam, menyiram, memanen lobak, membeli botol, dan meracik ramuan. | $WA^*$ ($h_{\text{FF}}$) | 16 node | $18.4\text{ ms}$ | 14 langkah / $33.0\text{ s}$ |
| **$P_4$ (Full Expedition)** | Ekspedisi penuh: ekonomi ladang, crafting, zirah, kunci, membuka gerbang, dan mengalahkan boss. | $WA^*$ ($h_{\text{FF}}, w=1.5$) | 876 node | $11.8\text{ ms}$ | **37 langkah / 118.48s** |

---

### 4. Evaluasi Heuristik & Benchmark Algoritma

Pengujian komparatif algoritma pencarian pada masalah ekspedisi $P_4$ membuktikan superioritas $WA^*$ dengan heuristik $h_{\text{FF}}$:

1. **Breadth-First Search (BFS)**:
   - Menjamin panjang rencana terpendek (dalam jumlah aksi), tetapi tidak memperhitungkan biaya waktu nyata (detik).
   - Mengalami ledakan kombinatorial pada kedalaman langkah $> 15$.
2. **Uniform Cost Search (UCS / Dijkstra)**:
   - Menjamin rencana berbiaya waktu optimal, tetapi mengeksplorasi ribuan node tanpa pemandu arah.
3. **A* dengan $h_{\text{max}}$**:
   - $h_{\text{max}}$ terbukti *admissible* ($h(s) \le h^*(s)$) dan konsisten. Menjamin solusi optimal, namun cukup konservatif sehingga ruang pencarian masih lebar.
4. **Weighted A* ($WA^*$) dengan $h_{\text{FF}}$ ($w = 1.5$)**:
   - Mengekstrak panjang *relaxed plan* dari graf perencanaan tanpa daftar hapus (*ignore-delete-lists*).
   - Dilengkapi filter **Helpful Actions** yang memotong faktor percabangan hingga $8\times$ lipat tanpa menghilangkan rute solusi.
   - Menghasilkan rencana 37 langkah secara konsisten dalam waktu **$11.8\text{ ms}$** (876 node tereksplorasi).

---

### 5. Arsitektur Real-Time Plan Monitor & Re-Planning

Untuk menjamin eksekusi di dunia nyata yang dinamis, game dilengkapi pengendali `PlanMonitor`:

- **Anggaran Waktu (*Time Budget*)**: Setiap panggilan `step()` dijalankan di bawah $20\text{ ms}$ (rata-rata $1.1\text{ ms}$) sehingga *frame rate* game tetap stabil pada 60 FPS.
- **Validasi Prekondisi Kontinu**: Sebelum mengeksekusi aksi, monitor memvalidasi apakah kondisi dunia saat ini masih memenuhi prasyarat STRIPS.
- **Toleransi 7 Skenario Anomali Lingkungan**:
  1. *Item Hilang / Tercuri*: Re-plan otomatis membeli atau mengumpulkan kembali bahan yang kurang.
  2. *Gerbang Terkunci Mendadak*: Re-plan mengarahkan hero menempa kunci cadangan.
  3. *Perubahan Kebijakan Cuaca*: Mengalihkan jalur navigasi menjauhi banjir pasang laut.
  4. *Rute Terblokir Dinamis*: Pathfinding mencari rute alternatif alami di peta.
  5. *Hero Salah Jalur*: Deteksi divergensi posisi mengkalibrasi ulang langkah awal.
  6. *Interupsi Manual Pemain*: Deteksi input manual menjeda autopilot secara mulus.
  7. *Kondisi Darurat Rendah HP*: Re-plan memprioritaskan istirahat di ranjang atau meminum potion.

---

### 6. Dekomposisi Tugas Hierarkis (HTN) untuk NPC Desa

Di luar silabus perencanaan klasik, game menyertakan mesin Shop-style HTN untuk memberikan dinamika desa yang hidup:
- **Pak Tani (Farmer NPC)**: Menjalankan dekomposisi `daily_farm_routine` $\rightarrow$ merawat petak tanaman, memupuk, memanen, dan berpatroli keliling desa.
- **Kang Penggiling (Miller NPC)**: Menjalankan dekomposisi `daily_mill_routine` $\rightarrow$ mengoperasikan kincir angin desa, mengecek karung tepung, dan beristirahat saat malam tiba.
- **Sinkronisasi Jam Dunia (*WorldClock*)**: Siklus 60 detik siang dan 30 detik malam secara otomatis memicu metode dekomposisi aktivitas baru pada agen NPC.

---

### 7. Panduan Tombol Kontrol di Permainan

| Tombol | Fungsi Terkait Automated Planning |
| :--- | :--- |
| **`[F7]`** | Membuka/menutup **Unified AI Inspector Dock** (Tab Planning & STRIPS). |
| **`[TAB]`** | Mengganti mode kontrol antara **Manual (Player)** dan **Autopilot (AI)**. |
| **`[G]`** | Menyalakan/mematikan **Visualisasi Garis Rute Geodesik ($A^*$ Polyline)** di tanah. |
| **`[N]`** | Menjalankan satu langkah rencana (*Presenter Step Mode*) untuk demonstrasi interaktif. |
| **`[F10]`** | Melanjutkan (*resume*) Autopilot setelah hero dijeda oleh gerakan manual pemain. |
| **`[F9]`** | Memicu eksekusi langsung dari aksi aktif yang sedang dipilih. |

---

### 8. Perintah Verifikasi & Demo Headless

Jalankan perintah berikut di terminal untuk menguji seluruh modul perencanaan secara mandiri:

```bash
# 1. Menjalankan 7 skenario demo re-planning otomatis
python3 tools/demo_subphase2b.py

# 2. Menjalankan benchmark komparatif algoritma perencanaan
python3 tools/benchmark_planning.py

# 3. Menjalankan unit test khusus Automated Planning
PYTHONPATH=src python3 -m unittest tests.test_strips_planner tests.test_lecture_planning tests.test_htn
```
