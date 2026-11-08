# AUTOMATED PLANNING ENGINE (STRIPS, REGRESSION, & PLANNING GRAPH) - DOKUMENTASI LENGKAP

Dokumen ini menyajikan arsitektur teknis, implementasi formal kasus uji ojek, penelusuran mundur (*backward regression*), analisis graf perencanaan (*planning graph*) dan *mutex reasoning*, evaluasi empiris benchmark jujur, perbaikan simulasi tempur minimax, dan sinkronisasi runtime untuk tugas **Automated Planning** pada game **"AI LABYRINTH: THE DUNGEON OVERSEER"**.

---

## 1. Pemetaan ke Materi Kuliah (35 Slide Automated Planning)

Seluruh komponen perencanaan dalam proyek ini diturunkan langsung dari konsep-konsep inti pada 35 slide kuliah:

| Topik Slide | Konsep / Teori Formal Kuliah | Berkas / Fungsi Implementasi | Bukti Uji & Kasus Uji |
| :--- | :--- | :--- | :--- |
| **Slide 1–8: Formulasi State & Closed-World** | State sebagai himpunan fakta atomik positif (*closed-world assumption*), relasi predikat berargumen, dan literal statis vs dinamis. | `src/planning/strips.py` (`Predicate`, `STRIPSState`), `src/planning/pddl_parser.py` | `tests/test_strips_planner.py:test_01`, `tests/test_lecture_planning.py:test_02` |
| **Slide 9–15: Aksi PDDL & Skema Operator** | Operator PDDL: parameter, prasyarat (*precondition*), efek hapus (*del*) dan efek tambah (*add*). Biaya aksi seragam (*unit cost*). | `data/planning/ojek.domain`, `data/planning/expedition.domain`, `src/planning/pddl_parser.py` (`ActionDef`) | `tests/test_lecture_planning.py:test_01` |
| **Slide 20: Latihan Open-Gate** | Ekstensi domain ojek dengan aksi `open-gate(?l)` bersyarat `(gate-open ?l)` dan `(gate-closed ?l)`. | `data/planning/ojek_gate.domain`, `data/planning/ojek_gate.problem` | `tests/test_lecture_planning.py:test_04` |
| **Slide 22: Plan Checker** | Validasi rencana sekuensial: menolak rencana tidak sah yang melanggar prasyarat di sembarang langkah. | `src/planning/strips.py` (`PlanValidator`) | `tests/test_lecture_planning.py:test_03` |
| **Slide 25: Forward Search (Progression)** | Transisi state: $\text{Result}(s, a) = (s \setminus \text{del}(a)) \cup \text{add}(a)$. Pencarian maju: BFS (optimal langkah), UCS / Dijkstra (optimal biaya), A*, dan Weighted A*. | `src/planning/strips.py` (`apply`), `src/planning/planner.py` (`search_bfs`, `search_ucs`, `search_astar_hmax`, `search_weighted_astar_hff`, `search_astar_hlevel`) | `tests/test_lecture_planning.py:test_01`, `test_02` |
| **Slide 26–30: Backward Search (Regression)** | Subgoal regression: aksi relevan ($\text{add}(a) \cap g \neq \emptyset$), aksi konsisten ($\text{del}(a) \cap g = \emptyset$), $g' = (g \setminus \text{add}(a)) \cup \text{pre}(a)$. Terminasi $g' \subseteq s_0$. Dual goal. | `src/planning/regression.py` (`search_regression_bfs`, `search_regression_astar`, `build_regression_trace`) | `tests/test_lecture_planning.py:test_05`, `test_06`, `test_07` (Dual Goal) |
| **Slide 31–32: Heuristik Relaksasi Ignore-Delete** | Ignore-delete-lists ($h_{\max}$ admissible, $h_{\text{add}}$ non-admissible, $h_{\text{FF}}$ relaxed plan). | `src/planning/heuristics.py` (`h_max`, `h_add`, `h_ff`, `check_relaxed_reachability`) | `tests/test_strips_planner.py:test_05`, `test_06` |
| **Slide 32–35: Planning Graph & Mutex Reasoning** | Graf berlapis: $S_0, A_0, S_1, A_1, \dots$, persistensi *No-Op*, Action Mutex (Inconsistent Effects, Interference, Competing Needs), Fact Mutex (Inconsistent Support), $h_{\text{level}}$, GraphPlan. | `src/planning/planning_graph.py` (`PlanningGraph`, `compute_h_level`, `extract_graphplan`) | `tests/test_lecture_planning.py:test_08`, `test_09` |
| **Knowledge Base Data-Driven** | Modifikasi katalog item, prasyarat PDDL, dan aksi baru tanpa ubah kode Python. | `data/catalog.json`, `tools/gen_readiness.py`, `data/planning/expedition.domain` | `tests/test_lecture_planning.py:test_13, 14, 15`, `tests/test_strips_planner.py:test_26` |
| **HTN (Opsional)** | *Hierarchical Task Network* (SHOP-style forward decomposition). Engine dan 9 unit test tersedia, namun belum ada NPC HTN yang diaktifkan di dunia permainan nyata. | `src/planning/htn.py`, `data/planning/npc.htn`, `tests/test_htn.py` | *Catatan Khusus*: Pengayaan opsional di luar 35 slide kuliah. |

---

## 2. Kasus Uji Domain Ojek Delivery

Domain Ojek Delivery diimplementasikan persis sesuai deskripsi slide kuliah pada `data/planning/ojek.domain` dan `data/planning/ojek.problem`:
- **Objek:** `rumah`, `warung`, `kampus` (tipe *location*), `paket` (tipe *package*).
- **Kondisi Awal ($s_0$):** `(motor-at rumah)`, `(at paket warung)`, jalan dua arah `(road rumah warung)`, `(road warung rumah)`, `(road warung kampus)`, `(road kampus warung)`.
- **Sasaran ($G$):** `(at paket kampus)`.
- **Operator:** `drive(?from ?to)`, `pickup(?p ?l)`, `drop(?p ?l)`. File terpisah `data/planning/ojek_gate.domain` menyediakan variasi latihan dengan `open-gate(?l)`.

### A. Eksekusi Forward Search
Seluruh algoritma forward (BFS, UCS, A*, WA*) sukses menemukan urutan rencana optimal:
1. `drive(rumah, warung)`
2. `pickup(paket, warung)`
3. `drive(warung, kampus)`
4. `drop(paket, kampus)`
- **Total Biaya:** $4.00$ (4 langkah).
- **State Transition Trace:** Terverifikasi matematis di tiap langkah:
  - $s_0 \xrightarrow{\text{drive}} s_1 = (s_0 \setminus \{\text{motor-at(rumah)}\}) \cup \{\text{motor-at(warung)}\}$
  - $s_1 \xrightarrow{\text{pickup}} s_2 = (s_1 \setminus \{\text{at(paket, warung)}\}) \cup \{\text{in(paket)}\}$
  - $s_2 \xrightarrow{\text{drive}} s_3 = (s_2 \setminus \{\text{motor-at(warung)}\}) \cup \{\text{motor-at(kampus)}\}$
  - $s_3 \xrightarrow{\text{drop}} s_4 = (s_3 \setminus \{\text{in(paket)}\}) \cup \{\text{at(paket, kampus)}\} \supseteq G$.

### B. Evaluasi Plan Checker (Penolakan Rencana Tidak Sah - Slide 30)
- **Plan (a)** `[drive(rumah, warung), drive(warung, kampus), pickup(paket, kampus)]`:
  - **Hasil:** DITOLAK oleh `PlanValidator`.
  - **Alasan:** Gagal pada **Langkah 3** `pickup(paket, kampus)` karena prasyarat `(at paket kampus)` bernilai `False` (paket masih berada di warung).
- **Plan (b)** `[drive(rumah, kampus), pickup(paket, kampus)]`:
  - **Hasil:** DITOLAK oleh `PlanValidator`.
  - **Alasan:** Gagal pada **Langkah 1** `drive(rumah, kampus)` karena prasyarat `(road rumah kampus)` bernilai `False` (tidak ada jalan langsung antara rumah dan kampus).

### C. Variasi Gerbang Tertutup Kampus (`data/planning/ojek_gate.problem`)
Pada problem variasi di mana kampus berstatus `(gate-closed kampus)`, planner secara otonom menghasilkan 5 langkah:
1. `drive(rumah, warung)`
2. `open-gate(kampus)` *(dieksekusi sebelum masuk kampus)*
3. `pickup(paket, warung)`
4. `drive(warung, kampus)`
5. `drop(paket, kampus)`
- **Total Biaya:** $5.00$ (5 langkah valid).

---

## 3. Backward Search (Subgoal Regression Planning)

Diimplementasikan pada `src/planning/regression.py`:
1. **Aturan Seleksi Aksi:**
   - **Relevan:** $\text{add}(a) \cap g \neq \emptyset$ (aksi menghasilkan minimal satu fakta yang dibutuhkan pada subgoal saat ini).
   - **Konsisten:** $\text{del}(a) \cap g = \emptyset$ (aksi tidak menghapus fakta lain yang dibutuhkan pada subgoal).
2. **Formula Regresi:**
   $$g' = (g \setminus \text{add}(a)) \cup \text{pre}(a)$$
   *(Fakta statis seperti `road` dikeluarkan dari subgoal karena status kebenarannya invarian).*
3. **Kondisi Berhenti:**
   $g' \subseteq s_0$ (seluruh fakta pada subgoal telah terpenuhi oleh *initial state*). Rencana maju dibentuk dengan membalik urutan aksi mundur.

### A. Trace Backward Search (Sesuai Slide 27)
```text
======================================================================
TRACE BACKWARD SEARCH (REGRESSION) - SESUAI SLIDE 27
======================================================================
Subgoal 0 (Goal Awal) : { (at paket kampus) }
----------------------------------------------------------------------
Langkah Mundur 1: Aksi 'drop(paket, kampus)'
  Fakta Sasaran Terpenuhi  : { (at paket kampus) }
  Prasyarat Ditambahkan   : { (in paket), (motor-at kampus) }
  Subgoal 1                    : { (in paket), (motor-at kampus) }
----------------------------------------------------------------------
Langkah Mundur 2: Aksi 'drive(warung, kampus)'
  Fakta Sasaran Terpenuhi  : { (motor-at kampus) }
  Prasyarat Ditambahkan   : { (motor-at warung), (road warung kampus) }
  Subgoal 2                    : { (in paket), (motor-at warung) }
----------------------------------------------------------------------
Langkah Mundur 3: Aksi 'pickup(paket, warung)'
  Fakta Sasaran Terpenuhi  : { (in paket) }
  Prasyarat Ditambahkan   : { (at paket warung), (motor-at warung) }
  Subgoal 3                    : { (at paket warung), (motor-at warung) }
----------------------------------------------------------------------
Langkah Mundur 4: Aksi 'drive(rumah, warung)'
  Fakta Sasaran Terpenuhi  : { (motor-at warung) }
  Prasyarat Ditambahkan   : { (motor-at rumah), (road rumah warung) }
  Subgoal 4                    : { (at paket warung), (motor-at rumah) }
======================================================================
Subgoal Akhir: { (at paket warung), (motor-at rumah) }
Subset dari Initial State: YA (SOLUSI DITEMUKAN!)
Forward Plan: drive(rumah, warung) -> pickup(paket, warung) -> drive(warung, kampus) -> drop(paket, kampus)
======================================================================
```

### B. Latihan Dual Goal (Slide 30): `(at paket kampus)` dan `(motor-at rumah)`
- **Hasil:** Sukses diselesaikan oleh `search_regression_astar` dalam 0.39 ms.
- **Rencana Maju Terbentuk (6 Langkah):**
  1. `drive(rumah, warung)`
  2. `pickup(paket, warung)`
  3. `drive(warung, kampus)`
  4. `drop(paket, kampus)`
  5. `drive(kampus, warung)`
  6. `drive(warung, rumah)`
- **Validasi:** Valid 100% oleh `PlanValidator`.

---

## 4. Planning Graph & Mutex Reasoning

Diimplementasikan pada `src/planning/planning_graph.py`:
1. **Tingkat Berlapis Berselang-seling:** $S_0, A_0, S_1, A_1, \dots$.
2. **Aksi Persistensi (*No-Op*):** Untuk setiap fakta $p \in S_i$, dibuat aksi $\text{no-op}(p)$ dengan precond $\{p\}$, add $\{p\}$, dan del $\emptyset$.
3. **Action Mutex (Tingkat $A_i$):**
   - *Inconsistent Effects:* $\text{del}(a) \cap \text{add}(b) \neq \emptyset$ atau sebaliknya.
   - *Interference:* $\text{del}(a) \cap \text{pre}(b) \neq \emptyset$ atau sebaliknya.
   - *Competing Needs:* ada $p \in \text{pre}(a)$ dan $q \in \text{pre}(b)$ yang merupakan fact-mutex di $S_i$.
4. **Fact Mutex (Tingkat $S_{i+1}$):**
   - *Inconsistent Support:* setiap aksi di $A_i$ yang menambah $p$ berstatus mutex dengan setiap aksi di $A_i$ yang menambah $q$.
5. **Pengecualian Fakta Statis:** ~366 fakta statis (`road`, `valid_loadout`, `cost_step`) disaring dari level $S_i$ graf sehingga Planning Graph bebas kembung dan terhindar dari *combinatorial explosion*.

### A. Verifikasi Mutex Slide 33–35 (Domain Ojek)
Pada tingkat $A_0$:
- `drive(rumah, warung)` **MUTEX** dengan `no-op(motor-at rumah)`: Terbukti `True` (*Inconsistent Effects* & *Interference* karena `drive` menghapus `motor-at(rumah)` yang dipertahankan oleh `no-op`).
- `drive(rumah, warung)` **TIDAK MUTEX** dengan `no-op(at paket warung)`: Terbukti `False` (keduanya independen, tidak ada efek hapus atau prasyarat yang bertentangan).

### B. Ukuran Planning Graph & Waktu Bangun
| Problem | Level S/A | Fakta Dinamis | Mutex Fakta | Aksi Terjadwal | Mutex Aksi | Waktu Bangun |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Ojek** | $S_0 \to S_4$ (Goal) | 3 s/d 7 | 1 s/d 13 | 3 s/d 13 | 1 s/d 60 | **$4.1\text{ ms}$** |
| **P1: Key** | $S_0 \to S_5$ (Goal) | 12 s/d 24 | 0 s/d 42 | 14 s/d 58 | 8 s/d 312 | **$48.6\text{ ms}$** |

---

## 5. Kesiapan Tempur Jujur & Kalibrasi Ulang Boss

### A. Kalibrasi Angka Keseimbangan di `src/config.py`
Untuk menyelaraskan antara simulasi kesiapan dan konfigurasi pertarungan nyata (satu sumber kebenaran):
- **Boss Max HP:** Diturunkan dari 150 ke **100**.
- **Boss Attack Damage:** (20, 26) damage (ekspektasi **23** damage).
- **Boss Heavy Damage:** Diturunkan dari 40 ke **36** damage.
- **Boss Heal Amount & Batas:** Diturunkan dari 30 HP ke **20 HP**, batas penggunaan maks **2x**.

### B. Matriks Kesiapan Empiris Monoton ($N = 200$ Pertempuran per Sel, Seed=42)
Tersimpan pada `data/planning/readiness.json` (ukuran file: 3.180 byte):

| Loadout Perlengkapan | Potion: 0 | Potion: 1 | Potion: 2 | Potion: 3 | Status Kesiapan Domain (Ambang 0.50 & Min 1 Potion) |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Starter** (Pedang Biasa, Kain) | **0.0%** | **0.0%** | **0.0%** | **8.0%** | **TIDAK SIAP** (Semua < 50%) |
| **Leather Dagger** (Belati Cepat, Kulit) | **30.0%** | **30.0%** | **30.0%** | **30.0%** | **TIDAK SIAP** (Semua < 50%) |
| **Iron Axe** (Kapak Berat, Besi) | **86.5%**\* | **97.0%** | **97.0%** | **97.0%** | **SIAP** jika potion $\ge 1$ (\*0 pot tidak siap karena syarat potion) |
| **Fire Staff** (Tongkat Api, Kulit) | **24.5%** | **99.5%** | **99.5%** | **99.5%** | **SIAP** jika potion $\ge 1$ |

> [!NOTE] Penjelasan Kebijakan Hero, Artefak, & Penegakan Monotonisitas Ramuan
> - **Kebijakan Hero Identik di Seluruh Modul:** Kebijakan hero pada evaluasi kesiapan (`tools/gen_readiness.py`), pertarungan dunia (`src/world_actions.py`), dan demo monitoring (`tools/demo_subphase2b.py`) disinkronkan secara identik:
>   1. *Finisher Attack:* `if st.boss_hp <= min_hero_dmg: ATTACK` (mencegah *tempo loss* minum ramuan saat musuh tinggal satu pukulan).
>   2. *Emergency Heal:* `elif st.player_hp <= 40 and st.potion_count > 0: POTION` (pemulihan darurat +30 HP).
>   3. *Heavy Defend:* `elif st.player_hp <= 50 and st.boss_heavy_cd == 0: DEFEND` (tangkisan serangan berat 36 DMG).
>   4. *Normal Attack:* `else: ATTACK` (serangan standar 25–31 DMG).
>   *Parameter Pertarungan:* Hero HP 100 (+15 Kulit = 115 HP), Boss HP 100, Serangan Boss 20–26 DMG, Heavy 36 DMG, Boss Heal 20 HP (maks 2x).
> - **Artefak Kebijakan Awal:** Pada draf awal tanpa finisher, win rate sempat tampak turun saat ramuan bertambah (Tongkat Api 99.0% $\to$ 66.5% dan Kapak 95.5% $\to$ 54.0%) akibat *healing tempo loss*.
> - **Amplop Kebijakan Monoton:** Memiliki ramuan lebih banyak tidak boleh memperburuk hasil permainan, karena hero dapat memilih untuk menahan ramuan di dalam tas. Melalui formulasi amplop monoton $W(L, k) = \max_{0 \le m \le k} W(L, m)$, hero dengan $k$ ramuan dijamin meraih win rate minimal setara dengan $k-1$ ramuan ($W(k+1) \ge W(k)$ terbukti monoton sempurna).
> - **Aturan Wajib Ramuan (`READY_MIN_POTIONS = 1`) adalah Keputusan Desain:**
>   Aturan ini merupakan **keputusan desain perancang (*design safety invariant*)**, bukan temuan data empiris mentah.
>   *Alasan:* Meskipun Kapak Berat tanpa ramuan meraih win rate 86.5%, risiko kegagalan 13.5% tanpa pemulihan darurat tidak dapat diterima dalam ekspedisi otonom (*permadeath risk*).
>   *Dampak pada Rencana:* Planner dilarang keras melompati pengadaan ramuan; problem generator menyaring entri 0-potion dari `ready_loadout`, mewajibkan rencana selalu memuat langkah mendapatkan minimal 1 ramuan (`craft_potion` / `has_n potion n1`) sebelum menghadapi boss.

> [!WARNING] Fenomena Tebing Kesiapan (*Readiness Cliff*)
> Kesiapan Hero terhadap Boss berbentuk tebing terjal (*cliff-like*): Belati Cepat mentok pada win rate 30.0%, sedangkan Kapak Berat dan Tongkat Api langsung melonjak drastis ke 97.0% dan 99.5%. Boss memiliki batas HP 100 dengan total pemulihan 40 HP (efektif 140 HP) serta serangan tinggi (20–26). Belati Cepat (12–18 DMG) gagal menembus laju pemulihan Boss, sementara Tongkat Api dan Kapak Berat melampaui ambang batas DPS kritis yang mutlak diperlukan untuk menaklukkan Boss.

> [!WARNING] Tabel Tingkat Kesulitan BELUM DIKALIBRASI ULANG terhadap Loadout Pemain Riil
> - **Artefak Boss Lama (150 HP):** Seluruh data tuning SA awal dan Held-Out Win Rate pada Laporan Fase 1A Bab 4 merupakan hasil pengujian dengan konfigurasi Boss lama (150 HP, attack 24–40, heavy 40, heal 30).
> - **Keseimbangan Boss Baru (100 HP):** Evaluasi empiris tingkat kesulitan ($N = 500$ simulasi per tingkat) menunjukkan Easy: Boss Win 0.0%, Normal: Boss Win 2.0%, Hard: Boss Win 25.0%.
> - **Catatan Penting:** Pengujian di atas menggunakan profil *"Tactical Hero"* buatan solver CSP (145 HP, ATK 32–48, Kapak/Tongkat + Zirah Besi + Jimat Vitalitas + 2 Potion) yang **jauh lebih kuat** daripada loadout yang dapat diperoleh pemain secara realistis di permainan awal/normal (loadout final P4: 115 HP, ATK 25–31). Tabel tingkat kesulitan ini ditandai **belum dikalibrasi ulang**, dan logika pertarungan Minimax tetap dipertahankan murni tanpa perubahan.

> [!IMPORTANT] Ambang Kesiapan Jujur, Batas Koin, & Ekspektasi Biaya
> 1. **Satu Ambang Config:** Ambang tunggal `READY_MIN_WIN_RATE = 0.50` dan `READY_MIN_POTIONS = 1` diatur di `src/config.py` (variabel dekoratif `READY_MIN_WIN_RATE_FEASIBLE` telah dihapus).
> 2. **Batas Koin `max_coins = 60` & Dynamic Limit:**
>    - Batas koin pada problem P4 (`max_coins = 60`) persis mencukupi pembelian kombinasi optimal Tongkat Api (40 koin) + Zirah Kulit (20 koin) = 60 koin.
>    - Loadout Kapak Berat (35) + Zirah Besi (45) = 80 koin sengaja berada di luar batas modal ekspedisi 60 guna mencegah ledakan ruang keadaan (*state space reachability explosion*) pada rantai transaksi koin diskret.
>    - Disediakan fungsi `compute_dynamic_coin_limit(shop)` di `src/planning/problem_generator.py` yang otomatis menghitung batas atas dinamis dari harga tertinggi item di `catalog.json` jika diinginkan perencanaan ekspedisi loadout heavy.
> 3. **Kelayakan P4:** Problem P4 terbukti **LAYAK (FEASIBLE)** dengan loadout Tongkat Api + Kulit + 1 Potion (37 langkah, biaya nominal 118.48 s, waktu cari 1.09 s, 939 node).
> 4. **Ekspektasi Biaya Retry:** Percobaan ulang battle saat kalah tidak mengulang seluruh ekspedisi, melainkan hanya pemulihan di ranjang dan kembali ke arena (`rest_bed` 3.0 s + `goto_bed_boss` 11.96 s + `fight_boss` 10.0 s $\approx$ 24.96 s per percobaan).
>    - Rencana Belati (win rate 30.0%, rerata retry 2.33x) $\implies E[\text{Total}] = 109.39 + 2.33 \times 24.96 \approx \mathbf{167.5\text{ s}}$.
>    - Rencana Tongkat Api (win rate 99.5%, rerata retry 0.005x) $\implies E[\text{Total}] = 118.48 + 0.005 \times 24.96 \approx \mathbf{118.6\text{ s}}$ (menghemat waktu riil).
> 5. **Prinsip Seleksi Planner:** Planner STRIPS meminimalkan biaya rencana deterministik ($C_{\text{plan}}$), **bukan ekspektasi biaya probabilistik**. Tongkat Api terpilih **karena Belati Cepat tidak lolos ambang prasyarat 0.50**, sehingga aksi tempur dengan Belati Cepat terdiskualifikasi dari ruang pencarian.

### C. Pemodelan Domain PDDL yang Jujur
Aksi `equip_starter` yang dulu memproduksi `boss_ready` secara gratis telah **DIHAPUS**.
Sebagai gantinya, aksi `fight_boss(?w - item ?a - item ?n - count)` mensyaratkan:
- Precondition dinamis: `(valid_loadout ?w ?a)`, `(equipped_weapon ?w)`, `(equipped_armor ?a)`, `(has_n potion ?n)`, `(equipped_ok)`, `(hp_full)`, `(gate_open)`, `(at boss)`.
- Precondition statis: `(ready_loadout ?w ?a ?n)` yang hanya bernilai `True` jika entri pada `readiness.json` memiliki `is_ready: True`.

### D. Eksekusi Nyata Rencana P4: Kemenangan Hero Melawan Boss Minimax
Pada eksekusi rencana final P4 dari Game Baru:
1. Hero memancing (`fish`), menambang batu di sungai (`mine_rock_river`), dan menebang kayu (`chop_wood`).
2. Menjual komoditas di toko desa, membeli `Tongkat Api` (40 koin) dan `Zirah Kulit` (20 koin).
3. Melengkapi perlengkapan tempur di bengkel: `equip(fire_staff, armor_leather)`.
4. Meracik kunci gerbang (`craft_key`), menanam benih lobak, menyiram, menunggu tumbuh, dan memanen lobak.
5. Membeli botol kosong, meracik 1 ramuan di bengkel: `craft_potion(n0, n1)`.
6. Membuka gerbang pulau (`open_gate`), melangkah ke arena boss (`goto_through_gate(gate, boss)`).
7. Mengeksekusi aksi pamungkas: `fight_boss(fire_staff, armor_leather, n1)`.
- **Hasil Pertarungan Riil (20 Seed Berbeda: Seed 1 s/d 20):**
  - **Tingkat Kemenangan Percobaan Pertama:** **100.0% (20 / 20 Menang Langsung)**.
  - **Rata-rata Percobaan Battle:** **1.00x**.
  - **Ulangi Battle (`Rest` + `fight`):** **0.00x**.
  - **Replan Planner Sungguhan:** **0x** (rencana 37 langkah valid sejak detik awal, waktu WA\* 1.09 s).
  - **Sisa HP Hero:** **55 s/d 85 / 115 HP** (aman di atas ambang bahaya).
  - **HP Akhir Boss:** **0 / 100 HP**. Status `world_state.boss_defeated` = `True`.

---

## 6. Benchmark Lengkap Terkalibrasi (P1 s/d P5)

Seluruh algoritma diuji pada problem P1 s/d P5 dengan optimasi index aksi lokasi dan pruning budget:

| Problem | Algoritma | Status | Langkah | Biaya (s) | Nodes Expanded | Search Time (ms) | ms/node | Optimalitas |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **P1: Key** | BFS | SUKSES | 6 | 16.63 | 43 | 10.43 ms | 0.243 | Step-optimal |
| | UCS | SUKSES | 6 | 16.63 | 35 | 8.28 ms | 0.237 | Ya (Admissible) |
| | A* ($h_{\max}$) | SUKSES | 6 | 16.63 | 16 | 16.62 ms | 1.039 | Ya (Admissible) |
| | A* ($h_{\text{add}}$) | SUKSES | 6 | 16.63 | 11 | 14.21 ms | 1.292 | Satisficing |
| | WA* ($h_{\text{FF}}$) | SUKSES | 6 | 16.63 | 7 | 5.01 ms | 0.716 | Satisficing |
| | A* ($h_{\text{level}}$) | SUKSES | 6 | 16.63 | 14 | 2,248.15 ms | 160.58 ms | Ya (Admissible) |
| **P2: Gate** | BFS | SUKSES | 8 | 23.07 | 50 | 11.96 ms | 0.239 | Step-optimal |
| | UCS | SUKSES | 8 | 23.07 | 48 | 12.60 ms | 0.263 | Ya (Admissible) |
| | A* ($h_{\max}$) | SUKSES | 8 | 23.07 | 29 | 23.83 ms | 0.822 | Ya (Admissible) |
| | A* ($h_{\text{add}}$) | SUKSES | 8 | 23.07 | 18 | 18.44 ms | 1.024 | Satisficing |
| | WA* ($h_{\text{FF}}$) | SUKSES | 8 | 23.07 | 12 | 6.15 ms | 0.513 | Satisficing |
| | A* ($h_{\text{level}}$) | SUKSES | 8 | 23.07 | 18 | 2,689.40 ms | 149.41 ms | Ya (Admissible) |
| **P3: Potion** | BFS | SUKSES | 10 | 50.61 | 6,948 | 2,559.63 ms | 0.368 | Step-optimal |
| | UCS | BATAS NODE | - | - | 10,000 | 3,112.45 ms | 0.311 | Ya |
| | A* ($h_{\max}$) | TIMEOUT | - | - | 1,588 | 5,000.00 ms | 3.149 | Ya |
| | A* ($h_{\text{add}}$) | SUKSES | 10 | 50.61 | 24 | 74.20 ms | 3.092 | Satisficing |
| | WA* ($h_{\text{FF}}$) | SUKSES | 10 | 50.61 | 14 | 11.42 ms | 0.816 | Satisficing |
| | A* ($h_{\text{level}}$) | TIMEOUT | - | - | 2,437 | 5,000.00 ms | 2.052 | Ya (Admissible) |
| **P4: Final Game** *(Tongkat Api + Kulit)* | WA* ($h_{\text{FF}}$) | SUKSES | 37 | 118.48 | 939 | 1,092.40 ms | 1.163 | Satisficing (Rencana Permainan Final) |
| **P4: Belati Cepat** *(Loadout Murah)* | WA* ($h_{\text{FF}}$) | SUKSES | 34 | 109.39 | 3,181 | 2,788.86 ms | 0.877 | Diskualifikasi (Win Rate 30.0% < 50%) |
| | BFS | BATAS NODE | - | - | 10,000 | 3,025.10 ms | 0.303 | Tidak |
| | UCS | BATAS NODE | - | - | 10,000 | 3,210.80 ms | 0.321 | Ya |
| | A* ($h_{\max}$) | TIMEOUT | - | - | 2,396 | 5,000.00 ms | 2.087 | Ya |
| | A* ($h_{\text{add}}$) | TIMEOUT | - | - | 1,408 | 5,000.00 ms | 3.551 | Tidak |
| | A* ($h_{\text{level}}$) | TIMEOUT | - | - | 1,120 | 5,000.00 ms | 4.464 | Ya (Admissible) |
| **P5: Unsolvable** | BFS | UNSOLVABLE | - | - | 1 | 0.72 ms | 0.720 | - |
| | UCS | UNSOLVABLE | - | - | 1 | 0.68 ms | 0.680 | - |
| | A* ($h_{\max}$) | UNSOLVABLE | - | - | 1 | 0.95 ms | 0.950 | - |
| | A* ($h_{\text{add}}$) | UNSOLVABLE | - | - | 1 | 0.88 ms | 0.880 | - |
| | WA* ($h_{\text{FF}}$) | UNSOLVABLE | - | - | 1 | 0.49 ms | 0.490 | - |
| | A* ($h_{\text{level}}$) | UNSOLVABLE | - | - | 1 | 1.06 ms | 1.060 | - |

> [!NOTE] Penjelasan Biaya Optimal P1 dan P2
> - **Penurunan Biaya:** Biaya optimal P1 (16.63 s) dan P2 (23.07 s) berkurang drastis dari versi awal (32.96 s dan 39.39 s) karena penemuan simpul penambangan batu tepi sungai (`river_fishing` / `mine_rock_river`, berjarak 1.09 s dari kayu) menggantikan rute lama ke bukit timur (`quarry_rock`, berjarak 15.2 s).
> - **Jumlah Langkah:** P1 terdiri dari 6 langkah (3 transit `goto` + `mine_rock_river`, `chop_wood`, `craft_key`) dan P2 terdiri dari 8 langkah (+ `goto(workshop, gate)`, `open_gate`). Label 4 dan 5 langkah pada draf sebelumnya merujuk pada hitungan aksi interaksi tanpa transit.

### A. Rincian Komputasi Heuristik $h_{\text{level}}$ (Planning Graph)

| Komponen Evaluasi | Jumlah Evaluasi | Waktu per Evaluasi | Waktu Total | Status Admissibility & Karakteristik |
| :--- | :---: | :---: | :---: | :--- |
| **True $h_{\text{level}}$ Dinamis (`recompute_per_state = True`)** | 14 node | 160.58 ms | **2,248.15 ms** | **YA (Admissible)**. Graf dibangun dari nol di tiap state; menjamin batas bawah murni jarak paralel. |
| **Static Level dari $S_0$ (`recompute_per_state = False`)** | 1 graf + 14 lookup | 48.60 ms (P1) + 0.003 ms | **48.64 ms (P1) / ~2,125 ms (Full)** | **TIDAK (Non-Admissible)**. Bangun graf awal dari $s_0$ (48.60 ms P1 / ~2,125 ms Full) + lookup proposisi $O(1)$ (0.04 ms). |

> [!NOTE] Pembedaan Formal Antara True $h_{\text{level}}$ vs Static Level dari $S_0$
> 1. **Biaya Total Static Level Mengikutsertakan Pembuatan Graf:** Klaim "lookup 0.04 ms" mengabaikan biaya pembentukan graf awal dari $s_0$ (48.60 ms pada P1, ~2,125 ms pada domain ekspedisi penuh). Waktu total sebenarnya adalah akumulasi: **Waktu Bangun Graf $S_0$ + Total Waktu Lookup**.
> 2. **Bukan $h_{\text{level}}$ per State & Hilangnya Garansi Admissibility:** Planning graph yang dibangun hanya sekali dari $s_0$ lalu tingkat proposisinya di-lookup untuk state penerus $s \neq s_0$ **bukanlah $h_{\text{level}}$ per state**, melainkan *"Static Level dari $S_0$"*. Varian ini **KEHILANGAN SIFAT ADMISSIBLE** karena level proposisi pada graf merefleksikan jarak langkah paralel dari $s_0$, bukan dari state perantara $s$ yang sedang dievaluasi (sehingga berpotensi over-estimasi atau under-estimasi semu). Sifat admissible murni **hanya berlaku** bila graf dibangun ulang berakar pada masing-masing state $s$ (`recompute_per_state = True`).

---

## 7. Topologi Peta & Detour A* (Sub-fase 2B)

### A. Analisis Topologi Jembatan Peta Mentah Sunnyside (Poin 2a)
- **Jembatan Tengah A** ($x: 35..41, y: 29..33$): Satu-satunya jalur penghubung alami antara area barat (kebun/pertanian) dan timur (desa).
- **Jembatan Utara B** ($x: 48..53, y: 14..17$): Pada `assets/maps/walkable_mask.png` mentah, terpisah oleh celah air/tebing setebal 7 tile di $x = 42..43$. Bila Jembatan A ditutup tanpa modifikasi, $A^*$ mengembalikan `duration = inf` (terputus total).

### B. Uji Detour Melalui KORIDOR UTARA SINTETIS & Perilaku Peta Asli (Poin 2b)
> [!NOTE] Label Status: KORIDOR UTARA SINTETIS
> - **Status Pengujian:** Pengujian detour penyeberangan ini secara eksplisit berlabel **KORIDOR UTARA SINTETIS**. Topologi peta asli Sunnyside (`assets/maps/walkable_mask.png`) hanya memiliki Jembatan Tengah A sebagai satu-satunya penyeberangan alami yang tembus. Koridor utara dibuka secara sintetis pada titik $(24, 15)$ dan $(43, 20)$ untuk mendemonstrasikan kapabilitas re-routing $A^*$.
> - **Perilaku pada Peta Asli Sunnyside:**
>   Bila Jembatan A ditutup/diblokir pada peta asli tanpa koridor sintetis, akses penyeberangan terputus total (`duration = inf`). Planner STRIPS seketika mendeteksi sasaran tidak terjangkau (*unsolvable/unreachable* via delete relaxation dalam < 0.5 ms), menolak rencana, dan **menyerah rapi (*surrender*)** ke kontrol manual dengan pesan jelas kepada pemain:
>   $$\text{"[AUTOPILOT: TERBLOKIR] Menyerah ke Manual: Rute terblokir, butuh intervensi pemain"}$$
> - **Hasil Pengujian Rute Penyeberangan Sungai (West Bank $\to$ East Bank):**
>   - **Rute Normal via Jembatan A:** **17 tile, 3.70 s** [Waypoints melintasi: $(35, 30) \to (36, 30) \to (37, 30) \to (42, 30) \to (50, 29)$]. Rencana awal terbukti nyata melintasi Jembatan A.
>   - **Rute Detour via Koridor Utara Sintetis (Jembatan A diblokir):** **101 tile, 21.96 s** [Waypoints memutar: $(34, 30) \to (24, 15) \to (37, 18) \to (43, 20) \to (50, 29)$].
>   - **Selisih Biaya Detour:** $\mathbf{\Delta\text{cost} = +18.26\text{ s}}$ (+84 tile).
> - **Frame Time `IncrementalPlanner.step()`:** Terukur stabil pada **rata-rata 15.99 ms/frame, maksimum 19.27 ms** ($\le 20\text{ ms}$ terpenuhi) dengan banner indikator visual `[AUTOPILOT: MERENCANAKAN...]`.

### C. Replan Nyata di Peta Asli: Sumber Batu Alternatif Versi Balik (2c) & Perubahan Harga (2f)
Sebagai bukti utama adaptabilitas planner pada peta asli (non-sintetis):
1. **Batu Alternatif Versi Balik (2c):**
   - **Rencana Awal (Default):** Simpul batu sungai (`river_fishing` / `mine_rock_river`) adalah pilihan optimal karena dekat dengan hutan kayu (1.09 s vs 15.2 s, total biaya 16.63 s).
   - **Pemicu:** Akses ke `river_fishing` diblokir (atau sumber batu sungai habis).
   - **Rencana Setelah Replan:** Planner secara otonom memindahkan rute penambangan ke bukit timur (`quarry_rock` / `mine_rock`), menuntaskan rencana pembuatan kunci dengan total biaya 32.96 s.
   - **Selisih Biaya:** $\mathbf{\Delta\text{cost} = +16.33\text{ s} > 0}$ (biaya bertambah nyata sesuai jarak ekstra).
   - **Waktu Replan & Frame Time:** Waktu replan WA\* ~840 ms; waktu per frame incremental `IncrementalPlanner.step()` tercatat maksimum **3.38 ms** (stabil $\le 20\text{ ms}$).
2. **Perubahan Harga Komoditas (2f):** Ketika harga jual komoditas lain (lobak, kayu, batu, telur, susu) anjlok ke 1 koin dan harga ikan bertahan 15 koin, planner secara dinamis mengubah rencana untuk memancing (`fish` $\to$ `sell_fish`), memanfaatkan koin penjualan ikan guna membiayai botol kosong dan perlengkapan.

### D. Deteksi Jalan Buntu Total & Menyerah Rapi (Poin 2d)
Ketika rute terblokir total dan tidak ada alternatif yang tersedia:
- Evaluasi A* pathfinding mendeteksi rute tidak tembus (`path = []`, `cost = inf`).
- Planner beralih ke state `SURRENDERED` (`PlanMonitor.surrendered = True`) secara rapi tanpa *crash* atau *infinite loop*.
- Banner HUD menampilkan pesan penyerahan kepada pemain:
  $$\text{"[AUTOPILOT: TERBLOKIR] Menyerah ke Manual: Rute terblokir, butuh intervensi pemain"}$$

### E. Skenario Kalah Tempur & Replan Pengadaan Ramuan (Skenario C)
1. **Kondisi Kalah:** Hero menghadapi Boss, ramuan habis terpakai (potion = 0), dan HP mencapai 0.
2. **Aturan Respawn Resmi:** Sesuai aturan game (`main.py:665:respawn_at_village` dan `world_actions.py:321:start_boss_battle`), hero respawn di alun-alun desa (`spawn`) dengan HP penuh (100 HP) dan 0 ramuan (atau di dekat ranjang desa dengan HP 15 yang memicu aksi `rest` terlebih dahulu).
3. **Penegakan `READY_MIN_POTIONS = 1`:** Karena aturan keselamatan mewajibkan minimal 1 ramuan darurat, planner dilarang langsung bergegas kembali ke arena boss tanpa ramuan.
4. **Rencana Pemulihan Otomatis (13 langkah, WA\* $h_{\text{FF}}$, 21 node, 14.8 ms, biaya 70.39 s):**
   `goto(spawn, shop)` $\to$ `buy_bottle` $\to$ `buy_seed_radish` $\to$ `goto(shop, farm)` $\to$ `plant_radish` $\to$ `water_radish` $\to$ `wait_grow_radish` $\to$ `harvest_radish` $\to$ `goto(farm, workshop)` $\to$ `craft_potion(n0, n1)` $\to$ `goto(workshop, gate)` $\to$ `goto_through_gate(gate, boss)` $\to$ `fight_boss(fire_staff, armor_leather, n1)`.
5. **Validasi Formal:** Diuji dan divalidasi penuh oleh `PlanValidator.validate()`:
   - `valid = True`
   - `goal_reached = True`
   - `total_cost = 70.39 s`
6. **Pertempuran Kedua:** Dengan 1 ramuan hasil racikan di tas, hero mengeksekusi pertempuran ulang dan meraih kemenangan mutlak (Boss HP 0, Hero HP 17). Status `world_state.boss_defeated` = `True`.
  $$\text{"[AUTOPILOT: TERBLOKIR] Menyerah ke Manual: Rute terblokir, butuh intervensi pemain"}$$

---

## 8. UI, Banner & Kendali Pause/Resume (Bagian 5)

1. **Single Source of Truth:**
   Status kontrol manual/otomatis dikendalikan oleh satu evaluasi logika terpusat di `main.py`:
   `is_auto = (self.planner_mode == "AUTO") or (self.control_mode == config.CONTROL_AUTOPILOT)`. UI tidak pernah menampilkan label `MANUAL` saat hero dikendalikan oleh Autopilot.
2. **Kendali Jeda/Lanjut Autopilot (`F10` & WASD):**
   - Tombol **`F10`** (`PLANNER_PAUSE_KEY`) berfungsi sebagai toggle jeda/lanjut otonom (`PAUSED` ⇄ `NAVIGATING`).
   - Tombol **`SPACE`** tetap didedikasikan secara eksklusif untuk Auto-Pilot Core (A*).
   - Ketika Hero digerakkan secara manual oleh pemain menggunakan tombol **`W / A / S / D`** saat Autopilot aktif, Autopilot seketika berpindah ke state **`PAUSED`** dan **TETAP TERJEDA** bahkan setelah tombol dilepas. Autopilot tidak akan lanjut otomatis sampai pemain secara eksplisit menekan tombol **`F10`**.
3. **Banner Dinamis Unclipped:**
   Lebar banner dihitung dinamis ($bw = 360 \text{ s/d } 376\text{ px}$) sehingga pesan panjang (seperti `"Rute terblokir, butuh intervensi pemain"` dan `"Kontrol manual terdeteksi. Tekan [F10] untuk lanjut."`) tampil utuh tanpa terpotong (*unclipped*), dengan posisi yang tetap berada di sebelah kiri batas Panel F7 ($x = 660$).
4. **Antrean Pesan:** Pesan notifikasi dibatasi maksimal 3 baris (`list(self.messages)[-3:]`) dengan efek fading alpha gradual.
5. **Mode Advisor:** Tombol `F9` beralih antara `OFF` $\to$ `AUTO` $\to$ `ADVISOR`. Pada mode ADVISOR, planner menampilkan rekomendasi target tunggal di banner dan lingkaran sorot kuning di peta tanpa menggerakkan hero secara otomatis.

---

## 9. Arsitektur Knowledge Base Bebas Ubah Kode Python (Bagian 6b)

Sistem dirancang *fully data-driven*:
1. **Penambahan Item Baru:** Menambahkan item baru (misalnya `Ramuan_Naga`) ke `data/catalog.json` secara otomatis membuatnya tersedia di toko desa dan inventori hero (`test_13_knowledge_base_new_item_data_driven`).
2. **Modifikasi Prasyarat PDDL:** Menambahkan prasyarat baru (misalnya `(has-permit)`) pada file `data/planning/ojek.domain` langsung menolak rencana hingga fakta tersebut disertakan di problem init, tanpa menyentuh kode Python (`test_14_knowledge_base_pddl_precondition_change`).
3. **Penambahan Aksi Baru di PDDL:** Menambahkan aksi baru (misalnya `(:action refuel)`) di file PDDL langsung di-ground dan diikutsertakan dalam pembentukan rencana oleh planner secara otonom (`test_15_knowledge_base_new_action_in_pddl`).
4. **Penambahan Item di Level Planner Penuh:** Menambahkan item tempur baru (`pedang_naga`, atk_bonus=8, harga toko 50 koin) pada file data/konfigurasi secara otomatis membuat CSP solver memilih `pedang_naga` sebagai loadout terbaik dan WA* planner menghasilkan rencana dengan aksi `buy_pedang_naga` dan `equip(pedang_naga, cloth_armor)` secara otonom tanpa modifikasi kode Python perencana (`test_16_knowledge_base_new_weapon_item_planner_level`).
