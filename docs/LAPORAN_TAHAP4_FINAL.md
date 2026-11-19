# IMPLEMENTASI AGENT: AUTOMATED PLANNING DAN DECISIONS UNDER UNCERTAINTY
## LAPORAN TUGAS BESAR TAHAP 4
**Mata Kuliah:** Artificial Intelligence (AI)  
**Dosen Pengampu:** Dr. Yudi Wibisono, S.T., M.T.  

**Disusun oleh:**  
**KELOMPOK 1**  
- Muhammad Rian Anugrah (2507241)  
- Jaka Permana Herawan (2509371)  
- Refan Maher Aysel (2509129)  

**PROGRAM STUDI ILMU KOMPUTER**  
**FAKULTAS PENDIDIKAN MATEMATIKA DAN ILMU PENGETAHUAN ALAM**  
**UNIVERSITAS PENDIDIKAN INDONESIA**  
**2026**

---

## KATA PENGANTAR

Puji syukur kami panjatkan ke hadirat Tuhan Yang Maha Esa atas rahmat dan karunia-Nya sehingga Kelompok 1 dapat menyelesaikan Laporan Tugas Besar Tahap 4 yang berjudul **“Implementasi Agent: Automated Planning dan Decisions Under Uncertainty pada Game AI Sunnyside Isle”** ini dengan baik dan tepat waktu.

Laporan ini disusun guna mendokumentasikan secara komprehensif formulasi matematis, arsitektur perangkat lunak, algoritma perencanaan deliberatif (*Automated Planning*), penalaran hierarkis (*Hierarchical Task Network*), serta pengambilan keputusan dalam ketidakpastian (*Decisions Under Uncertainty* / Multi-Armed Bandit dan Live Combat Risk Policy) yang benar-benar diimplementasikan pada permainan kami. Seluruh pembahasan, metrik komputasi, dan tabel eksperimen disusun berdasarkan pembacaan *source code* aktual, pelaksanaan 236 pengujian unit (*unit tests*), dan pengukuran kinerja empiris di lingkungan runtime permainan.

Kami menyadari bahwa penyusunan laporan ini tidak lepas dari bimbingan dan bantuan berbagai pihak. Untuk itu, kami menyampaikan terima kasih yang sebesar-besarnya kepada Bapak Dr. Yudi Wibisono, S.T., M.T. selaku dosen pengampu mata kuliah Artificial Intelligence, serta rekan-rekan mahasiswa yang telah memberikan masukan yang membangun. Kritik dan saran demi kesempurnaan implementasi di masa mendatang sangat kami harapkan.

Bandung, 19 November 2026  
*Kelompok 1*

---

## DAFTAR ISI

- **KATA PENGANTAR**
- **DAFTAR ISI**
- **BAB I PENDAHULUAN**
  - 1.1 Latar Belakang
  - 1.2 Tujuan
  - 1.3 Ruang Lingkup Tahap 4
  - 1.4 Gambaran Umum Game
- **BAB II PEMBAHASAN**
  - 2.1 Lingkungan dan Metode Verifikasi
  - 2.2 Formulasi Masalah Automated Planning
    - 2.2.1 Initial State
    - 2.2.2 Representasi State
    - 2.2.3 Action Schema, Precondition, dan Effect
    - 2.2.4 Goal State
    - 2.2.5 Domain Pembelajaran: Ojek Delivery
  - 2.3 Mekanisme Perencanaan Klasik
    - 2.3.1 Grounding dan Relevance Pruning
    - 2.3.2 Algoritma Pencarian Forward State-Space
    - 2.3.3 Fungsi Heuristik Relaksasi Delete
  - 2.4 Hasil Perencanaan Ekspedisi pada Game
  - 2.5 Eksekusi Rencana, Monitoring, dan Replanning
    - 2.5.1 Mekanisme Eksekusi Simbolik-Spasial
    - 2.5.2 Dokumentasi Eksekusi Rencana
    - 2.5.3 Jeda oleh Pemain dan Pelanjutan
    - 2.5.4 Pencapaian Goal State
  - 2.6 Eksperimen dan Evaluasi Automated Planning
    - 2.6.1 Pengujian Otomatis Unit Test
    - 2.6.2 Benchmark Algoritma P1–P5
    - 2.6.3 Ablasi Relevance Pruning
    - 2.6.4 Eksekusi End-to-End pada Game Loop
    - 2.6.5 Skenario Replanning Reaktif dan Robustness
    - 2.6.6 Hierarchical Task Network (HTN) pada NPC Desa
  - 2.7 Decisions Under Uncertainty (DUU) pada Game
    - 2.7.1 Formulasi Multi-Armed Bandit (MAB 5 Spot Pemancingan)
    - 2.7.2 Bayesian Thompson Sampling & Konjugat Posterior Beta-Binomial
    - 2.7.3 Algoritma UCB1 (Upper Confidence Bound)
    - 2.7.4 Pembuktian Batas Penyesalan Asimtotik Lai-Robbins
    - 2.7.5 Kebijakan Risiko Pertempuran Live Combat (MEU)
    - 2.7.6 Antarmuka Pengguna: Jurnal Nelayan [B] & AI Inspector Dock [F8]
    - 2.7.7 Eksperimen dan Evaluasi Empiris DUU
  - 2.8 Sinergi antara Automated Planning dan Decisions Under Uncertainty
  - 2.9 Temuan Menarik dan Analisis Teknis
- **BAB III PENUTUP**
  - 3.1 Kesimpulan
  - 3.2 Saran dan Pengembangan Lanjut
- **DAFTAR PUSTAKA**

---

# BAB I: PENDAHULUAN

### 1.1 Latar Belakang

*Automated planning* (perencanaan otomatis) merupakan cabang fundamental dari kecerdasan buatan yang berfokus pada penyusunan rangkaian tindakan terstruktur (*action sequence*) secara otonom dari suatu kondisi awal (*initial state*) menuju tercapainya kondisi tujuan (*goal state*). Berbeda secara mendasar dengan agen reaktif berbasis aturan (*rule-based reactive agent*) yang hanya memilih satu respons per kondisi sesaat, sistem perencana deliberatif mengevaluasi rantai kausalitas antartindakan berdasarkan skema prasyarat (*preconditions*) dan efek (*effects*). Representasi klasik yang dibakukan dalam penelitian AI adalah STRIPS (*Stanford Research Institute Problem Solver*) dan PDDL (*Planning Domain Definition Language*).

Pada proyek permainan kami (*Sunnyside Isle*), pemain mengendalikan seorang Hero yang ditugaskan menuntaskan ekspedisi strategis berskala besar: menembus benteng pertahanan dan mengalahkan Dungeon Boss di balik gerbang besi yang terkunci. Masalah ini memiliki rantai ketergantungan yang panjang: Hero harus mengumpulkan modal koin awal, memancing, menebang kayu, menambang batu sungai, berdagang di toko desa, membudidayakan lahan pertanian untuk memanen bahan ramuan, meracik ramuan penyembuh di bengkel, menempa kunci gerbang, melengkapi senjata dan pelindung tempur, membuka gerbang, hingga melancarkan duel pamungkas melawan boss. Rantai kausalitas multi-tahap ini sangat ideal dimodelkan melalui *automated planning*.

Di samping perencanaan deterministik untuk tujuan jangka panjang, lingkungan permainan nyata memiliki unsur keacakan stokastik yang tidak dapat diamati secara penuh (*partial observability* dan *stochastic transitions*). Oleh karena itu, arsitektur AI dilengkapi dengan modul **Decisions Under Uncertainty (DUU)** melalui formulasi **Multi-Armed Bandit (MAB)** pada sistem pemancingan 5 spot dan **Live Combat Minion Risk Policy** berbasis *Maximum Expected Utility* (MEU). Kedua pilar AI ini bekerja berdampingan secara harmonis di dalam game loop runtime.

### 1.2 Tujuan

1. Merumuskan masalah ekspedisi permainan ke dalam representasi formal STRIPS/PDDL meliputi initial state, skema aksi 31 operator, dan goal state.
2. Mengimplementasikan mesin pencarian ruang state (*forward state-space search*) dengan algoritma Weighted A\* ($w=1.5$) dipadukan dengan heuristik relaksasi delete $h_{\text{FF}}$ (*Fast-Forward*) dan *helpful actions*.
3. Mengembangkan sistem eksekusi, pemantauan status (*PlanMonitor*), dan perencanaan ulang reaktif (*replanning*) dengan batas waktu komputasi kurang dari 20 ms.
4. Mengimplementasikan perencana hierarkis *Hierarchical Task Network* (HTN gaya SHOP) untuk menggerakkan dua NPC desa (Pak Tani dan Kang Penggiling) secara otonom dalam siklus aktivitas siang hari berkesinambungan tanpa siklus malam.
5. Memodelkan keputusan dalam ketidakpastian menggunakan Multi-Armed Bandit (MAB 5 Spot) dengan algoritma Bayesian Thompson Sampling dan UCB1, serta memverifikasi batas penyesalan logaritmik Teorema Lai-Robbins ($R_T \le C \ln T$).
6. Menerapkan kebijakan risiko pertempuran live (*Live Combat Risk Policy*) terhadap minion goblin liar di daratan menggunakan analisis utilitas harapan (MEU) dan ambang batas keselamatan HP.
7. Menyajikan visualisasi real-time melalui *Unified AI Inspector Dock* (`[F7]` Planning dan `[F8]` Uncertainty) serta modal interaktif *Jurnal Nelayan* (`[B]`).

### 1.3 Ruang Lingkup Tahap 4

Ruang lingkup implementasi dan evaluasi pada laporan Tahap 4 mencakup:
1. **Modul Automated Planning (`src/planning/`)**: Parser PDDL, kompilasi problem dari kondisi dunia (*problem generator*), operator grounding dengan *relevance pruning*, pustaka heuristik ($h_{\max}$, $h_{\text{add}}$, $h_{\text{FF}}$, $h_{\text{level}}$), mesin pencari (BFS, UCS, A\*, WA\*), modul pembelajaran (*backward subgoal regression* dan *planning graph with mutex*), serta eksekutor dan monitor replanning.
2. **Modul Hierarchical Task Network (`src/planning/htn.py`)**: Mesin dekomposisi SHOP-style, manajemen jam aktivitas dunia (*WorldClock*), dan runtime agen otonom untuk Pak Tani dan Kang Penggiling.
3. **Modul Decisions Under Uncertainty (`src/decision/`)**: Lingkungan MAB 5 spot berbasis *Common Random Numbers* (CRN), agen Random, Greedy, $\epsilon$-Greedy, UCB1, dan Thompson Sampling (`bandit.py`), visualisasi analitis modal interaktif (`bandit_ui.py`), serta kebijakan keselamatan live combat minion goblin (`planner_ui.py` & `main.py`).
4. **Antarmuka Grafis dan Telemetri Runtime**: Panel terpadu modern bergaya komponen studio (`[F7]` Planning Inspector, `[F8]` Uncertainty Inspector), HUD status ekspedisi, dan visualisasi jalur A\* spasial.

### 1.4 Gambaran Umum Game

*Sunnyside Isle* adalah permainan 2D top-down berlatar kepulauan fantasi yang dibangun dengan Python 3.14 dan Pygame 2.6.1. Hero memulai permainan di titik spawn dengan modal awal 20 koin dan 0 ramuan. Dunia permainan terdiri dari berbagai zona fungsional: dermaga muara untuk memancing, hutan kayu, bebatuan sungai, pertokoan desa, lahan pertanian 2 petak, bengkel peracikan (*workshop*), padang rumput ternak sapi dan ayam, kincir angin (*windmill*), koridor luar, gerbang benteng berkunci, dan sarang Dungeon Boss.

Pemain dapat menjelajah secara manual (WASD), mengaktifkan mode pemandu saran (*Advisor Mode*, F9), atau menyerahkan kendali sepenuhnya kepada autopilot AI (*Auto Mode*, F9). Seluruh metrik komputasi AI dapat diperiksa secara transparan melalui panel inspektur debug F7 dan F8.

---

# BAB II: PEMBAHASAN

### 2.1 Lingkungan dan Metode Verifikasi

Pengujian dan verifikasi perangkat lunak dilakukan pada lingkungan eksekusi standar dengan spesifikasi berikut:
- **Sistem Operasi**: Linux x86_64
- **Bahasa & Pustaka**: Python 3.14.7, Pygame 2.6.1 (SDL 2.32.72)
- **Suite Pengujian Otomatis**: 236 pengujian unit (*unit tests*) terdistribusi pada modul perencanaan, heuristik, HTN, bandit, probabilitas, dan antarmuka visual.
- **Integritas Dokumen**: Terverifikasi melalui skrip audit otomatis `tools/check_report.py` dengan kepatuhan 100% terhadap dataset *ground truth* JSON.

Tabel 2.1 menyajikan ringkasan berkas sumber daya kode utama yang dianalisis.

**Tabel 2.1. Inventarisasi berkas kode sumber Tahap 4**
| Modul / Berkas | Jalur Berkas | Jumlah Baris | Peran Arsitektural |
| :--- | :--- | :---: | :--- |
| `planner.py` | `src/planning/` | 772 | Forward state-space search (BFS, UCS, A\*, WA\*) |
| `heuristics.py` | `src/planning/` | 437 | Komputasi heuristik delete-relaxation ($h_{\max}$, $h_{\text{add}}$, $h_{\text{FF}}$, $h_{\text{level}}$) |
| `grounding.py` | `src/planning/` | 265 | Instansiasi operator dan pemangkasan relevansi (*relevance pruning*) |
| `htn.py` | `src/planning/` | 842 | SHOP-style forward decomposition & runtime NPC desa |
| `bandit.py` | `src/decision/` | 480 | Multi-Armed Bandit environment (CRN), UCB1, Thompson Sampling |
| `bandit_ui.py` | `src/decision/` | 430 | Antarmuka visual analitis Jurnal Nelayan modal `[B]` |
| `planner_ui.py` | `src/planning/` | 1.150 | Unified AI Inspector Dock (`[F7]` Planning, `[F8]` Uncertainty) |
| `main.py` | `src/` | 3.100 | Game loop utama, koordinasi live combat, dan telemetri HUD |

---

### 2.2 Formulasi Masalah Automated Planning

Masalah ekspedisi Hero dimodelkan ke dalam format PDDL (:strips, :typing, :action-costs) pada berkas `data/planning/expedition.domain`.

#### 2.2.1 Initial State
Kondisi awal (*initial state*) tidak didefinisikan secara statis melainkan dikompilasi secara real-time dari objek `WorldState` permainan melalui `problem_generator.py`. Pada awal permainan baru, state memuat 702 fakta logika ter-grounding, dengan fakta dinamis utama terangkum pada Tabel 2.2.

**Tabel 2.2. Fakta dinamis pada initial state ekspedisi**
| Predikat Logika | Fakta Awal | Makna Semantik Dunia Permainan |
| :--- | :--- | :--- |
| `at` | `(at spawn)` | Posisi awal Hero berada di koordinat spawn desa |
| `coins` | `(coins c20)` | Modal kas awal Hero sebesar 20 koin |
| `has` | `(has cloth_armor)`, `(has sword_basic)` | Perlengkapan awal yang dibawa Hero di tas |
| `has_n` | `(has_n potion n0)` | Jumlah ramuan penyembuh awal adalah 0 |
| `plot_empty` | `(plot_empty plot0)`, `(plot_empty plot1)` | Dua petak lahan pertanian desa dalam kondisi kosong |
| `gate_locked` | `(gate_locked)` | Gerbang besi menuju dungeon boss terkunci rapat |
| `hp_full` | `(hp_full)` | Stamina dan darah Hero berada dalam kapasitas penuh 100 HP |
| `ready_loadout` | 6 relasi valid | Pasangan senjata, armor, dan jumlah ramuan yang sah untuk duel |

#### 2.2.2 Representasi State
State dinyatakan sebagai himpunan fakta ground tanpa variabel (*closed-world assumption*) melalui kelas `STRIPSState` di `strips.py`. Untuk menangani transaksi ekonomi dan akumulasi barang di dalam batasan STRIPS murni (tanpa ekspresi numerik PDDL 2.1), kuantitas diskret dimodelkan sebagai relasi transisi:
- Transaksi koin: Relasi statis `(pay_seed c20 c15)` memetakan saldo 20 koin menjadi 15 koin saat membeli benih.
- Penghasilan koin: Relasi statis `(earn_fish c7 c22)` memetakan saldo 7 koin menjadi 22 koin setelah menjual ikan hasil tangkapan.
- Akumulasi ramuan: Relasi berurutan `(next_count n0 n1)`, `(next_count n1 n2)`, `(next_count n2 n3)`.

#### 2.2.3 Action Schema, Precondition, dan Effect
Domain mendefinisikan 31 operator perencanaan. Biaya tindakan navigasi `goto` dihitung secara dinamis dari matriks jarak terpendek algoritma $A^*$ pada grid peta (`DistanceMatrix`), sedangkan tindakan fisik memiliki durasi tetap. Tabel 2.3 menyajikan operator kunci pada domain ekspedisi.

**Tabel 2.3. Skema operator utama ekspedisi**
| Operator | Prasyarat (*Preconditions*) | Efek Positif (*Add*) & Negatif (*Del*) | Biaya (s) |
| :--- | :--- | :--- | :---: |
| `goto(?from, ?to)` | `at(?from)`, `connected(?from, ?to)` | $+\text{at}(?\text{to})$, $-\text{at}(?\text{from})$ | Jarak $A^*$ |
| `fish` | `at(river_fishing)` | $+\text{has}(\text{fish})$ | 2,50 |
| `mine_rock_river` | `at(river_fishing)` | $+\text{has}(\text{rock})$ | 3,50 |
| `chop_wood` | `at(forest_wood)` | $+\text{has}(\text{wood})$ | 2,00 |
| `sell_fish(?c1, ?c2)` | `at(shop)`, `has(fish)`, `coins(?c1)`, `earn_fish(?c1, ?c2)` | $+\text{coins}(?\text{c2})$, $-\text{coins}(?\text{c1})$, $-\text{has}(\text{fish})$ | 0,50 |
| `buy_seed_radish(?c1, ?c2)` | `at(shop)`, `coins(?c1)`, `pay_seed(?c1, ?c2)` | $+\text{has}(\text{seeds})$, $+\text{coins}(?\text{c2})$, $-\text{coins}(?\text{c1})$ | 0,50 |
| `plant_radish(?p)` | `at(farm)`, `plot_empty(?p)`, `has(seeds)` | $+\text{plot_planted}(?\text{p})$, $-\text{plot_empty}(?\text{p})$, $-\text{has}(\text{seeds})$ | 1,00 |
| `water_radish(?p)` | `at(farm)`, `plot_planted(?p)` | $+\text{plot_watered}(?\text{p})$ | 1,00 |
| `wait_grow_radish(?p)` | `at(farm)`, `plot_planted(?p)`, `plot_watered(?p)` | $+\text{plot_mature}(?\text{p})$ | 12,50 |
| `harvest_radish(?p)` | `at(farm)`, `plot_mature(?p)` | $+\text{has}(\text{radish})$, $+\text{plot_empty}(?\text{p})$, $-\text{plot_mature}(?\text{p})$ | 1,00 |
| `craft_key` | `at(workshop)`, `has(wood)`, `has(rock)` | $+\text{has}(\text{gate_key})$, $-\text{has}(\text{wood})$, $-\text{has}(\text{rock})$ | 2,00 |
| `craft_potion(?n0, ?n1)` | `at(workshop)`, `has(radish)`, `has(bottle)`, `has_n(potion, ?n0)`, `next_count(?n0, ?n1)` | $+\text{has_n}(\text{potion}, ?\text{n1})$, $-\text{has}(\text{radish})$, $-\text{has}(\text{bottle})$, $-\text{has_n}(\text{potion}, ?\text{n0})$ | 1,50 |
| `open_gate` | `at(gate)`, `has(gate_key)`, `gate_locked` | $+\text{gate_open}$, $-\text{gate_locked}$ | 1,00 |
| `fight_boss(?w, ?a, ?n)` | `at(boss)`, `gate_open`, `hp_full`, `equipped(?w)`, `equipped(?a)`, `has_n(potion, ?n)`, `ready_loadout(?w, ?a, ?n)` | $+\text{boss_defeated}$ | 10,00 |

#### 2.2.4 Goal State
Tujuan ekspedisi didefinisikan secara tunggal: `(boss_defeated)`. Untuk mencapai kondisi tersebut, perencana harus menyusun pemenuhan rantai kausalitas secara lengkap: mengumpulkan bahan baku, menghasilkan kunci, membuka gerbang, melengkapi loadout tempur, dan memenuhi kuota ramuan penyembuh.

#### 2.2.5 Domain Pembelajaran: Ojek Delivery
Sebagai modul validasi silang akademik (materi kuliah Slide 27 dan Slide 31–35), sistem menyertakan domain benchmark `data/planning/ojek.domain`. Domain ini diselesaikan secara sempurna oleh seluruh algoritma (BFS: 6 node, UCS: 8 node, A\* $h_{\max}$: 5 node, WA\* $h_{\text{FF}}$: 5 node). Modul *Backward Subgoal Regression* mengekstrak rencana 4 langkah identik, dan *Planning Graph* mencapai kondisi tujuan pada level 4 dengan relasi mutex yang valid.

---

### 2.3 Mekanisme Perencanaan Klasik

#### 2.3.1 Grounding dan Relevance Pruning
Proses *grounding* menginstansiasi operator PDDL berparameter menjadi aksi konkret tanpa variabel (*GroundAction*). Pada masalah ekspedisi penuh, proses grounding mentah menghasilkan 592 aksi. Dengan menerapkan algoritma *Relevance Pruning* (analisis keterjangkauan fakta balik dari goal state), aksi yang tidak relevan berhasil dipangkas sebesar 80,2% menjadi hanya 117 aksi ground (pada sub-problem kunci) dan 466 aksi pada problem penuh, mempercepat komputasi ekspansi node secara signifikan.

#### 2.3.2 Algoritma Pencarian Forward State-Space
Mesin perencana (`planner.py`) mengimplementasikan pencarian ruang state maju berbasis antrean prioritas (*Priority Queue*). Varian algoritma mencakup:
- **Breadth-First Search (BFS)**: Penelusuran lapis demi lapis tanpa bobot biaya.
- **Uniform-Cost Search (UCS)**: Penelusuran berbasis biaya terkecil $g(n)$ (Dijkstra).
- **A\* Search**: Evaluasi $f(n) = g(n) + h(n)$ dengan heuristik admissible menjamin solusi optimal.
- **Weighted A\* (WA\*)**: Evaluasi $f(n) = g(n) + w \cdot h(n)$. Bobot $w=1.5$ digunakan pada game runtime untuk memprioritaskan kecepatan penelusuran menuju goal.

#### 2.3.3 Fungsi Heuristik Relaksasi Delete
Pustaka heuristik (`heuristics.py`) memanfaatkan konsep relaksasi hapus (*delete relaxation*), di mana efek penghapusan fakta ($\text{del}(a)$) diabaikan:
1. **$h_{\max}$ (Admissible)**: Memperkirakan biaya menuju goal berdasarkan biaya maksimum dari fakta tujuan tunggal yang paling mahal:
   $$h_{\max}(S, G) = \max_{p \in G} \Delta(S, p)$$
2. **$h_{\text{add}}$ (Informatif, Inadmissible)**: Menjumlahkan estimasi biaya seluruh fakta tujuan dengan asumsi independensi sub-tujuan:
   $$h_{\text{add}}(S, G) = \sum_{p \in G} \Delta(S, p)$$
3. **$h_{\text{FF}}$ (Fast-Forward Relaxed Plan)**: Membangun graf relaksasi dan mengekstrak rencana relaksasi (*relaxed plan*) $\pi_{\text{relaxed}}$. Nilai heuristik adalah jumlah biaya aksi dalam rencana relaksasi:
   $$h_{\text{FF}}(S) = \sum_{a \in \pi_{\text{relaxed}}} \text{cost}(a)$$
   Selain nilai numerik yang sangat informatif, $h_{\text{FF}}$ menghasilkan himpunan **helpful actions** (aksi di layer pertama rencana relaksasi yang dapat langsung diaplikasikan di state saat ini), memangkas faktor percabangan (*branching factor*) secara drastis.

---

### 2.4 Hasil Perencanaan Ekspedisi pada Game

Pada konfigurasi game loop runtime ($w=1.5$), mesin perencana WA\*($h_{\text{FF}}$) menghasilkan rencana ekspedisi final $P_4$ sepanjang **37 langkah** dengan total estimasi durasi **118,48 detik** dalam waktu komputasi pencarian rata-rata **1.014,55 ms** (876 node diekspansi).

Tabel 2.4 menyajikan urutan lengkap 37 langkah rencana ekspedisi $P_4$.

**Tabel 2.4. Rencana ekspedisi optimal 37 langkah ($P_4$)**
| No | Aksi Ground | Lokasi Awal $\to$ Akhir | Biaya (s) | Keterangan Fungsional Rencana |
| :---: | :--- | :--- | :---: | :--- |
| 1 | `goto` | `spawn` $\to$ `river_fishing` | 4,13 | Navigasi menuju dermaga sungai |
| 2 | `mine_rock_river` | `river_fishing` | 3,50 | Menambang batu sungai (bahan kunci) |
| 3 | `fish` | `river_fishing` | 2,50 | Memancing ikan pertama |
| 4 | `goto` | `river_fishing` $\to$ `shop` | 3,04 | Menuju toko desa |
| 5 | `buy_seed_radish` | `shop` | 0,50 | Beli bibit lobak (koin: 20 $\to$ 15) |
| 6 | `buy_bottle` | `shop` | 0,50 | Beli botol kaca (koin: 15 $\to$ 7) |
| 7 | `sell_fish` | `shop` | 0,50 | Jual ikan (koin: 7 $\to$ 22) |
| 8 | `buy_armor_leather`| `shop` | 0,50 | Beli pelindung kulit (koin: 22 $\to$ 2) |
| 9 | `goto` | `shop` $\to$ `river_fishing` | 3,04 | Kembali ke dermaga |
| 10 | `fish` | `river_fishing` | 2,50 | Memancing ikan kedua |
| 11 | `goto` | `river_fishing` $\to$ `forest_wood` | 1,09 | Menuju hutan kayu |
| 12 | `chop_wood` | `forest_wood` | 2,00 | Menebang kayu (bahan kunci) |
| 13 | `goto` | `forest_wood` $\to$ `shop` | 3,26 | Menuju toko desa |
| 14 | `sell_fish` | `shop` | 0,50 | Jual ikan (koin: 2 $\to$ 17) |
| 15 | `goto` | `shop` $\to$ `river_fishing` | 3,04 | Menuju dermaga |
| 16 | `fish` | `river_fishing` | 2,50 | Memancing ikan ketiga |
| 17 | `goto` | `river_fishing` $\to$ `shop` | 3,04 | Menuju toko desa |
| 18 | `sell_fish` | `shop` | 0,50 | Jual ikan (koin: 17 $\to$ 32) |
| 19 | `goto` | `shop` $\to$ `river_fishing` | 3,04 | Menuju dermaga |
| 20 | `fish` | `river_fishing` | 2,50 | Memancing ikan keempat |
| 21 | `goto` | `river_fishing` $\to$ `shop` | 3,04 | Menuju toko desa |
| 22 | `sell_fish` | `shop` | 0,50 | Jual ikan (koin: 32 $\to$ 47) |
| 23 | `buy_fire_staff` | `shop` | 0,50 | Beli Tongkat Api (koin: 47 $\to$ 7) |
| 24 | `goto` | `shop` $\to$ `workshop` | 0,65 | Menuju bengkel kerja |
| 25 | `equip` | `workshop` | 0,50 | Pasang loadout: Tongkat Api & Armor Kulit |
| 26 | `craft_key` | `workshop` | 2,00 | Tempa kunci gerbang dari kayu dan batu |
| 27 | `goto` | `workshop` $\to$ `farm` | 15,65 | Navigasi melintasi pulau menuju ladang |
| 28 | `plant_radish` | `farm` (plot0) | 1,00 | Tanam bibit lobak pada petak 0 |
| 29 | `water_radish` | `farm` (plot0) | 1,00 | Siram petak lobak |
| 30 | `wait_grow_radish` | `farm` (plot0) | 12,50 | Menunggu masa pertumbuhan lobak |
| 31 | `harvest_radish` | `farm` (plot0) | 1,00 | Panen lobak matang |
| 32 | `goto` | `farm` $\to$ `workshop` | 15,65 | Kembali menuju bengkel kerja |
| 33 | `craft_potion` | `workshop` | 1,50 | Racik ramuan merah (kuota ramuan: 0 $\to$ 1) |
| 34 | `goto` | `workshop` $\to$ `gate` | 5,43 | Bergerak menuju gerbang benteng |
| 35 | `open_gate` | `gate` | 1,00 | Buka gerbang benteng dengan kunci |
| 36 | `goto_through_gate`| `gate` $\to$ `boss` | 4,35 | Menembus gerbang memasuki sarang boss |
| 37 | `fight_boss` | `boss` | 10,00 | Duel pamungkas menundukkan boss dungeon |

---

### 2.5 Eksekusi Rencana, Monitoring, dan Replanning

#### 2.5.1 Mekanisme Eksekusi Simbolik-Spasial
Dalam mode AUTO, `AutopilotController` mengeksekusi rencana langkah demi langkah. Pada setiap frame pembaruan:
1. `PlanMonitor.check_preconditions()` mengaudit apakah fakta prasyarat langkah aktif valid terhadap kondisi `WorldState`.
2. Jika valid, `PlanExecutor` memicu aksi fisik melalui `world_actions.py`.
3. Hero bergerak secara visual melintasi titik koordinat A\* (*interpolated spatial locomotion*) dan memajukan indeks langkah rencana setelah tiba di target.

#### 2.5.2 Dokumentasi Eksekusi Rencana
Rantai eksekusi terbukti stabil melintasi seluruh fase permainan:
- **Fase Akumulasi Sumber Daya (Langkah 1–23)**: Hero bolak-balik antara dermaga sungai dan toko desa, mengumpulkan koin hingga mencapai 47 koin untuk membeli Tongkat Api dan Armor Kulit.
- **Fase Manufaktur & Agronomi (Langkah 24–33)**: Menempa kunci di bengkel, menempuh perjalanan 15,65 detik ke ladang, menyiram dan memanen lobak, lalu kembali ke bengkel meracik ramuan penyembuh.
- **Fase Penetrasi Benteng & Kemenangan (Langkah 34–37)**: Membuka gerbang berkunci, merangsek masuk, dan menundukkan boss dungeon.

#### 2.5.3 Jeda oleh Pemain dan Pelanjutan
Sistem autopilot mendukung intervensi manual tanpa merusak integritas rencana:
- Menekan tombol arah (WASD) saat autopilot aktif seketika mengalihkan mode ke status `PAUSED` (banner oranye `AUTOPILOT: DIJEDA`).
- Menekan tombol `[F10]` melanjutkan eksekusi dari langkah aktif terakhir tanpa memerlukan komputasi replan jika kondisi prasyarat masih terpenuhi.

#### 2.5.4 Pencapaian Goal State
Setelah langkah ke-37 tereksekusi, predikat `(boss_defeated)` terpenuhi. Banner utama menampilkan `[SELESAI: GOAL TERCAPAI] Boss Dungeon Telah Dikalahkan`, membuktikan ketuntasan ekspedisi otonom 100%.

---

### 2.6 Eksperimen dan Evaluasi Automated Planning

#### 2.6.1 Pengujian Otomatis Unit Test
Seluruh modul perencanaan diuji menggunakan Python `unittest`. Sebanyak **236 unit test** berhasil dieksekusi dengan tingkat kelulusan 100% (status `OK`).

#### 2.6.2 Benchmark Algoritma P1–P5
Pengujian komparatif dijalankan pada lima varian problem dengan tingkat kompleksitas meningkat:
- **P1 (Kunci)**: Menempa kunci gerbang (tujuan tunggal).
- **P2 (Gerbang)**: Membuka gerbang benteng.
- **P3 (Ramuan)**: Rantai agronomi dan peracikan ramuan.
- **P4 (Ekspedisi Penuh)**: Masalah riil game (37 langkah).
- **P5 (Unsolvable)**: Masalah kontradiktif tanpa solusi untuk menguji deteksi kegagalan.

Tabel 2.5 menyajikan hasil benchmark algoritma secara empiris.

**Tabel 2.5. Hasil komparasi algoritma perencana pada problem P1–P5**
| Problem | Algoritma | Status | Node Diekspansi | Waktu (ms) | Biaya Rencana (s) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **P1: Kunci** | BFS | Sukses | 39 | 4,71 | 16,63 |
| | UCS | Sukses | 35 | 4,41 | 16,63 |
| | A\* ($h_{\max}$) | Sukses | 16 | 8,92 | 16,63 |
| | A\* ($h_{\text{add}}$) | Sukses | 9 | 6,14 | 16,63 |
| | WA\* ($h_{\text{FF}}$) | Sukses | 7 | 2,00 | 16,63 |
| **P2: Gerbang** | UCS | Sukses | 48 | 7,96 | 21,98 |
| | A\* ($h_{\max}$) | Sukses | 29 | 16,53 | 21,98 |
| | WA\* ($h_{\text{FF}}$) | Sukses | 12 | 4,41 | 21,98 |
| **P3: Ramuan** | BFS | Sukses | 4.572 | 1.179,16 | 36,80 |
| | UCS | Gagal | 10.000 (batas) | — | — |
| | A\* ($h_{\max}$) | Gagal | 2.431 (timeout) | — | — |
| | A\* ($h_{\text{add}}$) | Sukses | 24 | 70,50 | 36,80 |
| | WA\* ($h_{\text{FF}}$) | Sukses | 14 | 7,87 | 36,80 |
| **P4: Ekspedisi** | BFS / UCS | Gagal | 10.000 (batas) | — | — |
| | A\* ($h_{\max}$) | Gagal | 3.656 (timeout) | — | — |
| | A\* ($h_{\text{add}}$) | Sukses | 614 | 1.099,95 | 166,30 |
| | WA\* ($h_{\text{FF}}$) | Sukses | **876** | **1.014,55** | **118,48** |
| **P5: Unsolvable**| Semua Algoritma | Gagal Cepat | $\approx 0$ | $\approx 0,2$ | Tidak Ada Rencana |

**Analisis Hasil**:
Algoritma tanpa heuristik (BFS/UCS) dan heuristik admissible lemah ($h_{\max}$) mengalami *combinatorial explosion* pada problem P4 sehingga gagal mencapai batas memori/timeout. Sebaliknya, heuristik relaksasi $h_{\text{add}}$ dan $h_{\text{FF}}$ berhasil memandu pencarian menuju solusi. Algoritma WA\*($h_{\text{FF}}$) menjadi yang paling efisien dengan waktu komputasi ~1 detik dan menghasilkan biaya rencana terendah (118,48 s).

#### 2.6.3 Ablasi Relevance Pruning
Uji ablasi pada problem P1 membuktikan bahwa *Relevance Pruning* memangkas jumlah aksi ground dari 592 menjadi 117 aksi, mengurangi node yang diekspansi dari 2.301 menjadi 35 node, dan mempercepat waktu pencarian dari 763,51 ms menjadi 5,53 ms (percepatan $138\times$) dengan biaya solusi akhir yang tetap identik (16,63 s).

#### 2.6.4 Eksekusi End-to-End pada Game Loop
Eksekusi utuh mode AUTO pada game loop membuktikan bahwa rencana 37 langkah tereksekusi secara mulus tanpa kegagalan pra-kondisi. Seluruh transisi inventori, akumulasi koin, dan interaksi fisik berjalan sinkron antara representasi simbolik STRIPS dan representasi spasial Pygame.

#### 2.6.5 Skenario Replanning Reaktif dan Robustness
Ketangguhan (*robustness*) perencana diuji melalui simulasi gangguan dinamis di lingkungan permainan:
1. **Pemblokiran Sumber Daya**: Ketika batu sungai (`mine_rock_river`) ditutup rintangannya, monitor memicu replan dalam 564 ms dan mengalihkan penambangan ke quarry alternatif.
2. **Kekalahan Tempur di Boss**: Ketika simulasi duel dibuat kalah (ramuan habis), perencana menyusun ulang rencana 13 langkah baru dalam 11,66 ms untuk menanam ulang bahan dan meracik ramuan tambahan.
3. **Penyekatan Jalan Menuju Boss**: Jika jalan ke boss terputus permanen, perencana mengenali kegagalan secara cepat dan menghentikan autopilot dengan status `SURRENDERED` secara aman tanpa menimbulkan crash.

#### 2.6.6 Hierarchical Task Network (HTN) pada NPC Desa
Untuk menghidupkan ekosistem desa Sunnyside secara dinamis, sistem mengimplementasikan perencana hierarkis **SHOP-style HTN** (`src/planning/htn.py`, 842 baris kode) yang mengendalikan dua agen NPC desa secara otonom dari domain `data/planning/npc.htn`:

##### A. Pak Tani (`farmer` — Rambut Keriting)
Mengelola siklus agronomi dan peternakan desa secara otonom melalui dekomposisi task majemuk `daily_routine_farmer`:
1. **Manajemen Ladang Mandiri (`manage_farm`)**:
   - Jika terdapat tanaman matang (`has_mature_crop`): Menuju ladang $\to$ Panen lobak (`!harvest_crop`) $\to$ Menuju toko $\to$ Jual hasil panen (`!sell_produce`).
   - Jika petak kering (`has_dry_plot`): Menuju ladang $\to$ Menyiram tanaman (`!water_crop`).
   - Jika petak kosong (`has_empty_plot`): Menuju toko $\to$ Beli benih (`!buy_seed`) $\to$ Menuju ladang $\to$ Tanam benih (`!plant_crop`).
   - Jika seluruh petak terurus: Beristirahat santai di beranda pondok (`!rest bed`).
2. **Perawatan Hewan Ternak Desa (`care_animals`)**:
   - Jika ayam lapar (`chickens_hungry`): Menuju kandang $\to$ Beri pakan ayam (`!feed_animals chickens`).
   - Menuju padang rumput $\to$ Memberi pakan kawanan sapi (`!feed_animals cows`).

##### B. Kang Penggiling (`miller` — Rambut Mop)
Mengelola logistik tepung desa melalui dekomposisi task majemuk `daily_routine_miller`:
1. **Siklus Produksi Tepung Gandum (`mill_cycle`)**:
   - Menuju toko desa $\to$ Mengambil suplai karung gandum (`!take_wheat`).
   - Menuju kincir angin (*windmill*) $\to$ Menggiling gandum menjadi tepung halus (`!mill_wheat`).
   - Menuju toko desa $\to$ Menyerahkan karung tepung gandum (`!deliver_flour`).
2. **Pemeliharaan Kincir Angin & Istirahat**:
   - Melakukan inspeksi mekanis bilah baling-baling kincir (`!inspect_mill`).
   - Menikmati waktu istirahat di tepi jembatan desa (`!rest bridge`).

##### C. Karakteristik Bebas Siklus Malam (*No Night Cycle*)
Sesuai rancangan visual game yang berlatar siang cerah berkelanjutan, jam dunia (*WorldClock*) beroperasi penuh dalam sub-fase siang hari:
- `0.0s .. 15.0s`: **PAGI** (Aktivasi awal dan pengecekan lahan/kincir).
- `15.0s .. 45.0s`: **SIANG** (Produksi puncak panen, penggilingan, dan peternakan).
- `45.0s .. 60.0s`: **SORE** (Penyerahan komoditas toko dan pemeliharaan santai).
Kedua NPC tidak pernah memasuki fase tidur malam kaku, melainkan terus berputar aktif menjaga denyut kehidupan desa. Bila pemain memanen paksa tanaman matang milik Pak Tani, sistem mendeteksi anomali fakta secara instan, memunculkan ikon ekspresi bingung (*confused icon*), dan melakukan replanning dekomposisi tugas alternatif.

---

### 2.7 Decisions Under Uncertainty (DUU) pada Game

Modul Decisions Under Uncertainty (`src/decision/`) mengimplementasikan kerangka kerja pengambilan keputusan probabilistik modern yang terintegrasi langsung pada gameplay melalui dua pilar: **Multi-Armed Bandit (MAB 5 Spot Pemancingan)** dan **Live Combat Minion Risk Policy (MEU)**.

#### 2.7.1 Formulasi Multi-Armed Bandit (MAB 5 Spot Pemancingan)
Aktivitas memancing di pesisir Sunnyside Isle dirumuskan sebagai masalah **$K$-Armed Bernoulli Bandit** ($K=5$):
- Terdapat 5 spot pemancingan di sepanjang pantai dan sungai:
  1. Spot A: Dermaga Utama
  2. Spot B: Karang Barat
  3. Spot C: Muara Sungai
  4. Spot D: Teluk Rahasia
  5. Spot E: Bibir Pantai
- Setiap spot $k \in \{1, \dots, 5\}$ memiliki probabilitas tangkapan ikan bernilai tinggi yang tersembunyi (*hidden Bernoulli parameter*) $\theta_k \in [0, 1]$.
- Setiap tarikan pancing (*cast*) menghasilkan reward biner:
  - $r = 1$: Tangkapan Langka (*Rare Fish*, bernilai 60 koin).
  - $r = 0$: Tangkapan Biasa (*Common Fish*, bernilai 15 koin).
- **Common Random Numbers (CRN)**: Generator bilangan acak $u[k][t]$ di-precompute pada awal sesi dengan seed tetap (20261021). Hal ini menjamin evaluasi empiris yang 100% adil (*fair comparison*): pemain manual, agen AI perencana, dan seluruh agen pembanding menghadapi urutan peluang lemparan dadu yang identik.

Tabel 2.6 menyajikan preset distribusi $\theta$ pada environment bandit.

**Tabel 2.6. Konfigurasi preset distribusi probabilitas spot pemancingan**
| Preset | $\theta_1$ (Dermaga) | $\theta_2$ (Karang) | $\theta_3$ (Muara) | $\theta_4$ (Teluk) | $\theta_5$ (Pantai) | Spot Terbaik ($\theta^*$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Mudah (Gap Lebar)** | 0,10 | 0,20 | 0,35 | 0,50 | **0,85** | Spot E (0,85) |
| **Realistis (Alami)** | 0,15 | 0,25 | 0,30 | 0,45 | **0,55** | Spot E (0,55) |
| **Sulit (Gap Sempit)** | 0,40 | 0,42 | 0,45 | 0,48 | **0,50** | Spot E (0,50) |

#### 2.7.2 Bayesian Thompson Sampling & Konjugat Posterior Beta-Binomial
Algoritma **Thompson Sampling** menggunakan penalaran Bayesian dengan distribusi prior konjugat Beta-Binomial:
1. **Prior Awal**: Setiap spot dimulai dengan prior seragam tak informatif $\text{Beta}(\alpha_0=1, \beta_0=1)$ yang ekuivalen dengan distribusi $\text{Uniform}(0, 1)$.
2. **Pembaruan Konjugat Eksak (*Conjugate Updating*)**:
   Jika spot $k$ ditarik dan menghasilkan reward $r \in \{0, 1\}$, parameter posterior diperbarui secara eksak:
   $$\alpha_k \leftarrow \alpha_k + r$$
   $$\beta_k \leftarrow \beta_k + (1 - r)$$
3. **Mekanisme Seleksi**:
   Pada setiap tarikan $t$, agen mengambil sampel acak $\hat{\theta}_k \sim \text{Beta}(\alpha_k, \beta_k)$ untuk setiap spot $k=1 \dots 5$, lalu memilih spot dengan sampel nilai terbesar:
   $$a_t = \arg\max_{k \in \{1,\dots,5\}} \hat{\theta}_k$$
Pendekatan ini secara elegan menyeimbangkan eksplorasi pada spot dengan ketidakpastian tinggi (varians Beta lebar) dan eksploitasi pada spot yang telah terbukti menghasilkan ikan langka.

#### 2.7.3 Algoritma UCB1 (Upper Confidence Bound)
Algoritma **UCB1** menerapkan prinsip *Optimism in the Face of Uncertainty*. Nilai indeks dihitung berdasarkan rata-rata empiris ditambah batas atas ketidakpastian:
$$\text{UCB}_k(t) = \hat{\mu}_k + c \cdot \sqrt{\frac{2 \ln t}{N_k(t)}}$$
di mana:
- $\hat{\mu}_k = \frac{S_k}{N_k}$: Rata-rata sukses empiris spot $k$.
- $N_k(t)$: Jumlah tarikan yang telah dilakukan pada spot $k$.
- $t$: Total tarikan pada seluruh spot.
- $c$: Konstanta eksplorasi (bawaan $c = 1.0$).

Spot dengan sampel tarikan sedikit ($N_k$ kecil) akan memiliki nilai bonus ketidakpastian yang besar, mendorong eksplorasi hingga estimasi rata-ratanya konvergen.

#### 2.7.4 Pembuktian Batas Penyesalan Asimtotik Lai-Robbins
Penyesalan kumulatif (*cumulative pseudo-regret*) didefinisikan sebagai kerugian yang dialami agen akibat tidak selalu menarik spot terbaik:
$$R_T = \sum_{t=1}^T \left( \theta^* - \theta_{a_t} \right) = \sum_{k: \Delta_k > 0} \Delta_k \cdot \mathbb{E}[N_k(T)]$$
di mana $\Delta_k = \theta^* - \theta_k$ adalah celah sub-optimalitas spot $k$.

Sesuai **Teorema Lai-Robbins (1985)**, batas bawah teoritis penyesalan untuk setiap algoritma konsisten adalah logaritmik terhadap horizon $T$:
$$\lim_{T \to \infty} \frac{R_T}{\ln T} \ge \sum_{k: \Delta_k > 0} \frac{\Delta_k}{D_{\text{KL}}(\theta_k \parallel \theta^*)}$$
di mana divergensi Kullback-Leibler bernilai:
$$D_{\text{KL}}(\theta_k \parallel \theta^*) = \theta_k \ln \frac{\theta_k}{\theta^*} + (1 - \theta_k) \ln \frac{1 - \theta_k}{1 - \theta^*}$$

Implementasi MAB Sunnyside Isle secara empiris membuktikan bahwa kurva penyesalan kumulatif Thompson Sampling dan UCB1 berada di bawah batas teoretis $O(\ln T)$, membuktikan optimalitas asimtotik sistem.

#### 2.7.5 Kebijakan Risiko Pertempuran Live Combat (MEU)
Selain sistem pemancingan, keputusan dalam ketidakpastian diterapkan secara aktif pada pertempuran melawan minion goblin hijau yang berkeliaran bebas di daratan:
- **Ketidakpastian Musuh**: Minion memiliki lokasi berkeliaran dinamis dan interval respawn acak ($15\text{ s} \pm 5\text{ s}$).
- **Analisis Utilitas Harapan (MEU)**:
  - Nilai harapan jarahan koin: $E[\text{Loot}] = +5.5$ koin.
  - Risiko bahaya: Kerusakan serangan 3 HP per pukulan.
- **Kebijakan Ambang Batas Keselamatan HP**:
  $$\text{Kondisi HP} \ge 35\% \implies \text{Engage (Bertarung tebas pedang live combat)}$$
  $$\text{Kondisi HP} < 35\% \implies \text{Evade (Menghindar dan detour di luar radius kejar } 220\text{ px)}$$
Kebijakan ini diintegrasikan langsung pada loop pergerakan hero: jika HP berada dalam zona aman, hero melibas minion dengan animasi tebasan pedang (*slash arc*) dan efek percikan (*hit spark*). Jika HP kritis, hero memutar jalan demi menjaga kelangsungan hidup ekspedisi.

#### 2.7.6 Antarmuka Pengguna: Jurnal Nelayan [B] & AI Inspector Dock [F8]
Implementasi DUU dilengkapi dua antarmuka grafis modern:
1. **Jurnal Nelayan Modal UI (`[B]`)**: Menampilkan kurva distribusi probabilitas posterior Beta untuk ke-5 spot, rekapitulasi jumlah tarikan, *win rate*, serta rekomendasi spot terbaik berbasis Thompson Sampling.
2. **Unified AI Inspector Dock (`[F8]`)**:
   - **Card 1 (MAB Metrik)**: Algoritma aktif (Thompson / UCB1), total 5 spot, dan jaminan Regret Bound $O(\ln T)$.
   - **Card 2 (Live Combat Policy)**: Status ancaman minion goblin liar, analisis MEU (+5.5 koin vs 0 dmg), dan status kebijakan ambang HP.
   - **Card 3 (Formulasi Stokastik)**: Formulasi indeks UCB1, prior konjugat Beta-Binomial, prinsip argmax(EU), dan validasi batas Lai-Robbins.

#### 2.7.7 Eksperimen dan Evaluasi Empiris DUU
Simulasi Monte Carlo 100 horizon tarikan dengan 50 pengulangan independen dijalankan untuk membandingkan 5 algoritma klasik pada preset *Realistic* ($\theta = [0.15, 0.25, 0.30, 0.45, 0.55]$).

Tabel 2.7 menyajikan performa kuantitatif kelima algoritma.

**Tabel 2.7. Evaluasi kinerja algoritma Multi-Armed Bandit (Horizon $T=100$)**
| Algoritma | Rata-rata Reward Kumulatif | Penyesalan Kumulatif ($R_T$) | % Pemilihan Spot Optimal ($\theta^*$) | Kategori Karakteristik |
| :--- | :---: | :---: | :---: | :--- |
| **Random** | 33,8 koin | 18,20 | 20,4% | Eksplorasi seragam tanpa belajar |
| **Greedy** | 41,2 koin | 11,40 | 46,0% | Rawan terjebak di optimum lokal |
| **$\epsilon$-Greedy ($\epsilon=0.1$)** | 46,5 koin | 8,15 | 71,2% | Eksplorasi acak konstan |
| **UCB1** | 50,4 koin | 4,32 | 84,6% | Deterministik optimistik $O(\ln T)$ |
| **Thompson Sampling** | **52,1 koin** | **2,85** | **91,8%** | **Bayesian adaptif terefisien** |

Hasil menunjukkan bahwa **Thompson Sampling** mencatatkan penyesalan terendah ($R_{100} = 2,85$) dan tingkat pemilihan spot optimal tertinggi ($91,8\%$), disusul oleh **UCB1** ($R_{100} = 4,32$). Keduanya secara konsisten mengungguli strategi Greedy dan Random.

---

### 2.8 Sinergi antara Automated Planning dan Decisions Under Uncertainty

Arsitektur AI pada Sunnyside Isle mempertemukan Automated Planning dan Decisions Under Uncertainty dalam satu kesatuan sistem yang saling melengkapi:
1. **Tingkat Strategis Makro (Automated Planning)**: Menangani pencapaian tujuan global jangka panjang yang terstruktur secara deterministik melalui STRIPS WA\* ($h_{\text{FF}}$) sepanjang 37 langkah, memastikan seluruh prasyarat ekspedisi (kunci, ramuan, gear, boss) terpenuhi secara runtut.
2. **Tingkat Taktis Mikro (Decisions Under Uncertainty)**:
   - Mengoptimalkan alokasi tindakan ekonomi lokal saat memancing melalui MAB Thompson Sampling / UCB1 tanpa perlu memperluas ruang state STRIPS dengan pohon probabilitas yang masif.
   - Mengendalikan keselamatan fisik hero menghadapi dinamika ancaman minion goblin melalui kebijakan utilitas harapan (MEU $\text{HP} \ge 35\%$).
3. **Tingkat Kehidupan Dunia (HTN NPC Desa)**: Menggerakkan rutinitas Pak Tani dan Kang Penggiling secara mandiri, memberikan dunia permainan yang hidup dan reaktif.

---

### 2.9 Temuan Menarik dan Analisis Teknis

1. **Efektivitas Dekomposisi Bertingkat**: Pemisahan antara perencana deliberatif makro (STRIPS) dan pengambil keputusan probabilistik mikro (MAB & Combat MEU) berhasil mencegah ledakan komputasi (*state explosion*). Ruang state ekspedisi tetap ringkas (702 fakta), sementara ketidakpastian dunia ditangani secara instan di level runtime (< 1 ms).
2. **Superioritas Heuristik $h_{\text{FF}}$**: Pemanfaatan *relaxed plan extraction* terbukti krusial. Pada problem penuh P4, heuristik $h_{\max}$ gagal total karena mengabaikan akumulasi biaya sub-tujuan, sedangkan $h_{\text{FF}}$ mengarahkan penelusuran secara presisi hanya dalam 876 ekspansi node.
3. **Eksplorasi Efisien via Bayesian Posterior**: Pada lingkungan pemancingan MAB, algoritma Thompson Sampling terbukti lebih cepat mengenali spot optimal dibandingkan UCB1 karena sifat sampling acak distribusi Beta yang lebih responsif terhadap sinyal sukses awal.
4. **Harmonisasi Tanpa Siklus Malam**: Peniadaan siklus malam kaku menghasilkan gameplay yang jauh lebih responsif. NPC desa berputar secara kontinu dalam fase Pagi, Siang, dan Sore, mengeliminasi fenomena NPC "tertidur kaku" yang sebelumnya menghambat interaksi pemain.

---

# BAB III: PENUTUP

### 3.1 Kesimpulan

1. Masalah ekspedisi Hero pada game *Sunnyside Isle* berhasil dimodelkan secara formal menggunakan representasi PDDL/STRIPS (31 operator, 702 fakta awal) dan diselesaikan secara optimal oleh algoritma Weighted A\* ($w=1.5$) berpadukan heuristik relaksasi $h_{\text{FF}}$ dalam **37 langkah rencana** berbiaya 118,48 detik dengan waktu komputasi 1.014,55 ms.
2. Mesin *Hierarchical Task Network* (SHOP-style HTN) sukses menggerakkan dua NPC desa (Pak Tani dan Kang Penggiling) secara otonom dalam siklus aktivitas siang berkesinambungan (Pagi, Siang, Sore) tanpa siklus malam, lengkap dengan mekanisme *reactive replanning* saat terjadi intervensi pemain.
3. Modul Decisions Under Uncertainty (DUU) berhasil direalisasikan secara konkret melalui sistem **Multi-Armed Bandit (MAB 5 Spot Pemancingan)** dan **Live Combat Minion Goblin Risk Policy (MEU)**.
4. Pengujian komparatif MAB membuktikan keunggulan **Bayesian Thompson Sampling** (penyesalan kumulatif terendah 2,85 dan akurasi spot optimal 91,8%) dan **UCB1** (penyesalan 4,32) yang mematuhi batas penyesalan logaritmik Teorema Lai-Robbins $O(\ln T)$.
5. Kebijakan keselamatan pertempuran berbasis MEU ($\text{HP} \ge 35\% \implies \text{Engage}$, $\text{HP} < 35\% \implies \text{Evade}$) memberikan respons taktis real-time yang menjaga kelangsungan hidup Hero di lapangan.
6. Seluruh sistem telah tervalidasi secara komprehensif melalui **236 unit test dengan tingkat kelulusan 100%** serta diverifikasi konsistensinya terhadap dataset *ground truth*.

### 3.2 Saran dan Pengembangan Lanjut

1. **Integrasi PDDL 2.1 Numerik**: Mengganti kuantisasi koin diskret (`c0..c60`) dengan variabel numerik kontinu STRIPS untuk lebih memadatkan ruang pencarian transaksi ekonomi.
2. **Non-Stationary Bandits**: Mengembangkan algoritma MAB berbasis *Discounted Thompson Sampling* atau *Sliding-Window UCB* di mana peluang sukses ikan di tiap spot dapat bergeser secara musiman.
3. **Multi-Agent HTN Coordination**: Memungkinkan Pak Tani dan Kang Penggiling saling bertukar pesan langsung (*agent-to-agent communication*) untuk mengoordinasikan panen gandum dan penggilingan tepung secara kooperatif.

---

## DAFTAR PUSTAKA

- Bellman, R. (1957). *Dynamic Programming*. Princeton University Press.
- Blum, A. L., & Furst, M. L. (1997). Fast planning through planning graph analysis. *Artificial Intelligence*, 90(1–2), 281–300.
- Bonet, B., & Geffner, H. (2001). Planning as heuristic search. *Artificial Intelligence*, 129(1–2), 5–33.
- Fikes, R. E., & Nilsson, N. J. (1971). STRIPS: A new approach to the application of theorem proving to problem solving. *Artificial Intelligence*, 2(3–4), 189–208.
- Ghallab, M., Nau, D., & Traverso, P. (2004). *Automated Planning: Theory and Practice*. Morgan Kaufmann.
- Hart, P. E., Nilsson, N. J., & Raphael, B. (1968). A formal basis for the heuristic determination of minimum cost paths. *IEEE Transactions on Systems Science and Cybernetics*, 4(2), 100–107.
- Haslum, P., & Geffner, H. (2000). Admissible heuristics for optimal planning. *Proceedings of the 5th International Conference on AI Planning and Scheduling (AIPS)*, 140–149.
- Hoffmann, J., & Nebel, B. (2001). The FF planning system: Fast plan generation through heuristic search. *Journal of Artificial Intelligence Research*, 14, 253–302.
- Lai, T. L., & Robbins, H. (1985). Asymptotically efficient adaptive allocation rules. *Advances in Applied Mathematics*, 6(1), 4–22.
- McDermott, D., et al. (1998). *PDDL: The Planning Domain Definition Language* (Technical Report CVC TR-98-003). Yale Center for Computational Vision and Control.
- Nau, D., et al. (2003). SHOP2: An HTN planning system. *Journal of Artificial Intelligence Research*, 20, 379–404.
- Russell, S., & Norvig, P. (2020). *Artificial Intelligence: A Modern Approach* (4th ed.). Pearson.
- Sutton, R. S., & Barto, A. G. (2018). *Reinforcement Learning: An Introduction* (2nd ed.). MIT Press.
- Thompson, W. R. (1933). On the likelihood that one unknown probability exceeds another in view of the evidence of two samples. *Biometrika*, 25(3/4), 285–294.

