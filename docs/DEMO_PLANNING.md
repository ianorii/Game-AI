# NASKAH DEMO PRESENTASI 3–5 MENIT: AUTOMATED PLANNING

Dokumen ini merupakan panduan presentasi interaktif di hadapan dosen/evaluator untuk mendemonstrasikan implementasi materi kuliah **Automated Planning (35 Slide)** pada game **"AI LABYRINTH: THE DUNGEON OVERSEER"**.

---

## Ringkasan Perintah CLI Cepat

Setiap modul dapat dijalankan secara instan dari terminal workspace:

```bash
# 1. Kasus Uji Domain Ojek, Forward Search, State Trace, & Plan Checker (Slide 1–26, 30)
python3 src/main.py --demo-ojek

# 2. Backward Search / Subgoal Regression & Dual Goal (Slide 27, 30)
python3 src/main.py --demo-regression

# 3. Planning Graph, Deteksi Relasi Mutex, & h_level (Slide 31–35)
python3 src/main.py --demo-graph

# 4. Detour Rerouting Jembatan & Frame Time IncrementalPlanner (Sub-fase 2B)
python3 src/main.py --demo-detour

# 5. Demonstrasi Empiris 7 Skenario Headless (Execution, Replan, Boss Battle)
python3 tools/demo_subphase2b.py
```

---

## Naskah Presentasi Langkah Demi Langkah (3–5 Menit)

### Menit 0:00 – 01:15: Domain Ojek Delivery & Forward Search (Slide 1–26, 30)
**Perintah:**
```bash
python3 src/main.py --demo-ojek
```

**Poin Penjelasan untuk Dosen:**
1. *"Selamat pagi/siang Bapak/Ibu Dosen, sistem Automated Planning kami dibangun murni berbasis kaidah STRIPS dan PDDL klasik."*
2. *"Pada demonstrasi pertama, kami mereplikasi Domain Ojek Delivery persis sesuai slide kuliah: objek `rumah`, `warung`, `kampus`, dan `paket`. State direpresentasikan sebagai himpunan fakta atomik di bawah Closed-World Assumption."*
3. *"Seluruh algoritma forward—BFS, UCS, A* ($h_{\max}$), dan WA* ($h_{\text{FF}}$)—menghasilkan rencana optimal 4 langkah:*
   $$\text{drive(rumah, warung)} \to \text{pickup(paket, warung)} \to \text{drive(warung, kampus)} \to \text{drop(paket, kampus)}$$
4. *"Transisi state dihitung matematis menggunakan formula:*
   $$\text{Result}(s, a) = (s \setminus \text{del}(a)) \cup \text{add}(a)$$
   *dan dicetak trace fakta dinamisnya di tiap langkah."*
5. *"Plan Checker kami menguji dua rencana salah dari Slide 30:*
   - *Plan (a) ditolak pada Langkah 3 `pickup` karena prasyarat `(at paket kampus)` belum terpenuhi.*
   - *Plan (b) ditolak pada Langkah 1 `drive` karena `(road rumah kampus)` tidak ada di peta jalan."*
6. *"Variasi `ojek_gate` membuktikan kemampuan adaptasi ketika kampus terkunci: planner menyisipkan `open-gate(kampus)` secara otonom sebelum masuk."*

---

### Menit 01:15 – 02:30: Backward Search (Subgoal Regression) (Slide 27, 30)
**Perintah:**
```bash
python3 src/main.py --demo-regression
```

**Poin Penjelasan untuk Dosen:**
1. *"Berikutnya adalah Backward Search menggunakan Subgoal Regression sesuai Slide 24–30."*
2. *"Pencarian mundur menerapkan aturan ketat:*
   - *Aksi relevan: $\text{add}(a) \cap g \neq \emptyset$.*
   - *Aksi konsisten: $\text{del}(a) \cap g = \emptyset$.*
   - *Formula regresi: $g' = (g \setminus \text{add}(a)) \cup \text{pre}(a)$, di mana fakta statis seperti jalan invarian dikeluarkan dari subgoal."*
3. *"Output trace di layar mencocokkan persis 4 tahapan subgoal pada Slide 27:*
   - *Subgoal 0 (Goal): `{(at paket kampus)}`*
   - *Subgoal 1: `{(in paket), (motor-at kampus)}` via `drop`*
   - *Subgoal 2: `{(in paket), (motor-at warung)}` via `drive`*
   - *Subgoal 3: `{(at paket warung), (motor-at warung)}` via `pickup`*
   - *Subgoal 4: `{(at paket warung), (motor-at rumah)}` via `drive`*
   *Karena Subgoal 4 adalah subset dari Initial State, pencarian sukses."*
4. *"Kami juga menyelesaikan latihan Dual Goal dari Slide 30: `(at paket kampus)` dan `(motor-at rumah)`. Planner mundur menghasilkan rute pulang-pergi 6 langkah yang terbukti valid."*

---

### Menit 02:30 – 03:45: Planning Graph & Mutex Reasoning (Slide 31–35)
**Perintah:**
```bash
python3 src/main.py --demo-graph
```

**Poin Penjelasan untuk Dosen:**
1. *"Pada Slide 31–35, graf perencanaan (Planning Graph) dibangun secara berselang-seling $S_0, A_0, S_1, A_1, \dots$ lengkap dengan persistensi No-Op."*
2. *"Sistem kami mendeteksi tiga relasi Action Mutex:*
   - *Inconsistent Effects & Interference: `drive(rumah, warung)` berstatus mutex dengan `no-op(motor-at rumah)` karena aksi drive menghapus fakta yang dipertahankan oleh no-op.*
   - *Competing Needs: aksi dengan prasyarat yang saling mutex di tingkat state sebelumnya.*
   - *Fact Mutex: Inconsistent Support pada tingkat proposisi."*
3. *"Pengecualian fakta statis (~366 fakta) diterapkan agar Planning Graph tidak bengkak (leveling-off tercapai dalam 4.1 ms pada ojek dan 48.6 ms pada P1)."*
4. *"Heuristik $h_{\text{level}}$ dievaluasi (bernilai 4.0), dan algoritma GraphPlan berhasil mengekstrak rencana tanpa menggunakan heuristik numerik."*

---

### Menit 03:45 – 05:00: Detour Rerouting, Frame Time & Pertempuran Boss
**Perintah:**
```bash
python3 src/main.py --demo-detour
```

**Poin Penjelasan untuk Dosen:**
1. *"Terakhir, integrasi perencanaan ke dalam lingkungan game sesungguhnya (Sub-fase 2B):*
   - *Topologi Peta: Kami menganalisis bahwa Jembatan Tengah A adalah satu-satunya penyeberangan alami pada mask mentah. Ketika Jembatan A ditutup, A* membuktikan bahwa jalur terputus total.*
   - *Detour Reroute: Dengan membuka koridor Jembatan B utara di collision override sementara, A* memutar secara sempurna dengan waypoints di koridor utara tanpa menabrak sungai.*
   - *Anggaran Frame Time: Mesin `IncrementalPlanner.step()` mengalokasikan waktu maksimal **18.24 ms per siklus frame**, memenuhi batas $\le 20\text{ ms}$ sehingga game loop tidak mengalami lag/stutter."*
2. *"Keseimbangan Boss & Kesiapan Jujur:*
   - *Kami mengkalibrasi ulang konfigurasi Boss di `src/config.py` (HP 100, damage 20–26, heal 20) sebagai satu sumber kebenaran bersama battle engine.*
   - *Berdasarkan matriks empiris $N = 200$ di `data/planning/readiness.json`, starter gear memiliki win rate 0%, sedangkan Belati Cepat + Zirah Kulit + 1 Ramuan mencapai win rate 22.5% (status SIAP).*
   - *Pada problem P4, planner secara otonom merencanakan pembelian Belati Cepat dan Zirah Kulit, meracik potion dan kunci gerbang, serta memenangkan pertarungan riil melawan AI Minimax (HP Hero 20, Boss 0)."*

---

## Tanya-Jawab Kunci (Antisipasi Pertanyaan Dosen)

| Pertanyaan Dosen | Jawaban Singkat Berdasarkan Data |
| :--- | :--- |
| **Q: Kenapa tidak memakai HTN?** | *HTN adalah materi pengayaan di luar 35 slide kuliah. Kami telah mengimplementasikannya sebagai modul opsional desa (`src/planning/htn.py` pada tab F8), namun fokus utama evaluasi kami pusatkan 100% pada materi wajib: STRIPS, Forward/Backward Search, dan Planning Graph.* |
| **Q: Kenapa win rate starter gear dulu 0% tapi planner tetap memilihnya?** | *Sebelumnya domain memiliki aksi `equip_starter` yang memproduksi efek `boss_ready` secara cuma-cuma. Kami telah merevisi domain tersebut: aksi dummy dihapus, dan `fight_boss` kini mensyaratkan `ready_loadout` yang terverifikasi empiris dari simulasi pertempuran nyata.* |
| **Q: Apakah A* $h_{\text{level}}$ admissible? Mengapa lebih lambat dari $h_{\max}$?** | *$h_{\text{level}}$ terbukti admissible karena relaksasi planning graph tidak pernah melebih-lebihkan biaya langkah. Namun, komputasi pasangan mutex $O(\|A\|^2)$ pada domain ratusan aksi membutuhkan overhead waktu yang lebih besar dibanding evaluasi ignore-delete-list.* |
| **Q: Bagaimana memastikan penambahan item baru tidak mengubah kode Python?** | *Arsitektur dirancang data-driven. Cukup menambahkan entri item di `catalog.json` atau skema di `expedition.domain`, modul `problem_generator.py` dan parser PDDL langsung meng-ground dan menyusun rencananya secara dinamis (terbukti di unit test 13, 14, dan 15).* |

