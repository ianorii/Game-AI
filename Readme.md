# Game AI - Pathfinding & Heuristic Analysis

Proyek implementasi algoritma **A\*** dan **UCS (Uniform Cost Search)** dalam lingkungan game 2D. Proyek ini memvisualisasikan bagaimana algoritma pencarian jalur bekerja dengan berbagai heuristic, termasuk perbandingan efisiensi dan perilaku NPC (Non-Player Character).

## Algoritma yang Diimplementasikan

### 1. A\* (A-Star)

A\* adalah algoritma pencarian jalur terpendek yang menggabungkan **g(n)** (cost dari start ke node saat ini) dan **h(n)** (heuristic estimate dari node saat ini ke goal).

```
f(n) = g(n) + h(n)
```

**Karakteristik:**
- Menggunakan priority queue (min-heap) untuk memilih node dengan f(n) terkecil
- Optimal jika heuristic **admissible** (tidak pernah overestimate)
- Efisiensi tergantung pada kualitas heuristic yang digunakan

### 2. UCS (Uniform Cost Search)

UCS adalah special case dari A\* di mana **h(n) = 0** untuk semua node.

```
f(n) = g(n)
```

**Karakteristik:**
- Menjelajahi semua node secara uniform berdasarkan cost g(n)
- Selalu optimal untuk graf dengan non-negative edge weights
- Lebih lambat dari A\* karena tidak ada panduan heuristic

## Heuristic Functions

| Heuristic | Formula | Keterangan |
|-----------|---------|------------|
| **Manhattan** | `\|dx\| + \|dy\|` | Best untuk grid 4-directional (atas, bawah, kiri, kanan). Admissible dan consistent. |
| **Euclidean** | `√(dx² + dy²)` | Admissible, tapi kurang informed untuk grid karena mengasumsikan gerakan diagonal. |
| **UCS** | `0` | Tidak ada heuristic guidance, menjelajahi semua arah secara uniform. |

### Perbandingan Heuristic

- **Manhattan** → Paling efisien untuk grid 4-directional. Jumlah node expanded paling sedikit.
- **Euclidean** → Lebih banyak node expanded karena underestimate jarak aktual pada grid.
- **UCS** → Paling banyak node expanded karena tidak ada heuristic guidance.

[foto: screenshot perbandingan debug overlay saat menggunakan Manhattan vs Euclidean vs UCS pada jalur yang sama]

## Arsitektur Sistem

```
main.py              ← Entry point, game loop, input handling
├── player.py        ← Player movement (keyboard + A* pathfinding)
├── npc.py           ← NPC follow behavior (A* recompute periodically)
├── debug_overlay.py ← Visualisasi visited nodes & path
├── settings_menu.py ← Konfigurasi heuristic & parameter
└── game/
    ├── pathfinding/ ← Core A* & UCS implementation
    ├── map/         ← Grid system, collision detection, viewport
    └── adv_search/  ← Battle turn-based: Min-Max + Alpha-Beta
        ├── core.py  ← GameState, evaluate, minimax, iterative deepening
        └── battle.py← Battle UI overlay (HP bar, tombol aksi, battle log)
```

### Flow Algoritma A\* pada Player

```
Mouse Click → set_target(row, col)
                ↓
         astar(grid, start, goal, heuristic)
                ↓
         Return: { path, visited, expanded, found }
                ↓
         Player bergerak mengikuti path dengan smooth interpolation
```

### Flow Algoritma A\* pada NPC

```
Every 0.1 detik → recomput path
                ↓
         astar(grid, npc_pos, player_pos, heuristic)
                ↓
         NPC bergerak mengikuti path (kecepatan lebih lambat dari player)
```

## Fitur Utama

### 1. Dual Movement Mode (Player)
- **Manual**: WASD / Arrow keys untuk bergerak 1 cell per input
- **A\* Pathfinding**: Klik mouse untuk menghitung jalur otomatis

### 2. NPC Follow Behavior
- NPC secara periodik menghitung ulang jalur ke player (setiap 0.1 detik)
- Kecepatan NPC lebih lambat dari player (250 px/s vs 650 px/s)
- NPC akan berhenti jika sudah dekat dengan player (Manhattan distance ≤ 1)

### 3. Debug Overlay
Visualisasi komponen A\*:
- **Visited nodes** (kotak biru) → Node-node yang sudah diekspansi oleh algoritma
- **Path nodes** (kotak merah) → Jalur terpendek yang ditemukan
- **Info panel** → Jumlah node expanded dan heuristic yang digunakan

**Toggle debug layer:**
| Key | Fungsi |
|-----|--------|
| `1` | Toggle visited nodes |
| `2` | Toggle path nodes |
| `3` | Toggle info panel |

[foto: screenshot debug overlay dengan visited nodes (biru) dan path (merah) terlihat jelas]

### 4. Grid Editor
- Tekan `E` untuk masuk edit mode
- Klik kiri → tutup cell (obstacle)
- Klik kanan → buka cell (walkable)
- Tekan `S` untuk simpan grid, `L` untuk muat grid

### 5. Settings Menu (Pause)
- Tekan `ESC` untuk buka/tutup menu
- **Saat menu terbuka game dianggap pause**: player & NPC dibekukan
  (tidak ada gerakan) dan battle **tidak akan terpicu** meski NPC
  bersebelahan dengan player
- Konfigurasi heuristic player & NPC
- Toggle NPC follow, debug overlay, HUD
- Reset posisi, fullscreen

### 6. Battle Mode (Adversarial Search)

Saat player bersebelahan dengan NPC, pertarungan turn-based dimulai.
Inilah bagian yang memakai **adversarial search**.

**Alur giliran:**
```
Player pilih aksi → resolve → jeda 0.4s → NPC (Min-Max) → resolve → giliran player
```

**4 aksi (Rock-Paper-Scissors ringan):**

| Aksi | Efek | Dihukum oleh |
|------|------|--------------|
| `ATTACK` | Damage dasar `atk - 0.4 × def` (variasi ±10%) | musuh yang `DEFEND` |
| `DEFEND` | `guard`: serangan berikutnya masuk hanya 40% | musuh yang `CHARGE` (tetap lumayan) |
| `POTION` | Heal, tapi status `open` (+80% damage diterima) sampai giliran berikutnya | musuh yang menyerang di giliran berikutnya |
| `CHARGE` | Serangan berikutnya damage ×2.4 | musuh yang `DEFEND` |

**Cara AI memilih aksi (di `game/adv_search/core.py`):**
1. **Min-Max** dengan **Alpha-Beta Pruning** + move ordering (aksi fatal diprioritaskan)
2. **Iterative deepening** depth 1 → 4 dengan budget waktu 0.15 s (anytime algorithm)
3. **Evaluation function**: selisih HP ternormalisasi, kesadaran lethal window,
   ekonomi potion, nilai status (guard/charge/open), keuntungan giliran
4. **Personalitas musuh**: bobot evaluation function berbeda per arketipe
   (`brute`, `guardian`, `alchemist`, `assassin`) sehingga gaya bertarung beda
5. **Wave/threat scaling**: tiap kemenangan naik level ancaman dan musuh
   berganti arketipe (HP +4, ATK +1 tiap 3 wave, DEF +1 tiap 6 wave)

**Yang ditampilkan di UI:** HP bar, jumlah potion, battle log, dan statistik
pencarian AI (`depth`, `nodes`, `pruned`, waktu ms) tiap giliran musuh.

Tekan `H` saat giliran player untuk meminta saran dari algoritma yang sama
(`get_player_hint`) - bukti bahwa search yang sama bisa dipakai kedua pihak.

**Debug overlay keputusan AI (tekan `F3`):**

Panel di samping panel battle yang menampilkan *proses pengambilan
keputusan NPC*, bukan hanya hasilnya:

| Bagian | Isi |
|--------|-----|
| Status | `AI BERPIKIR...` / aksi terpilih + giliran & ronde |
| Peluang menang | estimasi peluang NPC vs player dari skor eval |
| Statistik pencarian | `depth`, `nodes`, `pruned` (+%), waktu vs budget |
| Skor Min-Max per aksi | bar skor tiap aksi legal di root → aksi mana yang dipilih |
| Principal variation | jalur main terbaik beberapa ply ke depan |
| Evaluation function (live) | rincian tiap komponen skor: HP diff, lethal, potion, charge/guard/open, giliran |
| Statistik pertarungan | damage keluar/masuk, heal, jumlah pemakaian tiap aksi, status aktif |

Pencarian dijalankan **saat jeda 0.4 s dimulai**, sehingga panel sudah
menampilkan keputusan dan statistik pencarian selama jeda berlangsung
(bukan setelah NPC bergerak).

> Catatan: "peluang menang" adalah **estimasi heuristik** (fungsi logistik
> `1 / (1 + e^(-skor/60))` dari skor evaluation), bukan probabilitas pasti.
> Angkanya dipakai untuk memvisualkan seberapa yakin pencarian, bukan untuk
> pengambilan keputusan.

## Kendali

### Overworld

| Key | Fungsi |
|-----|--------|
| `W/A/S/D` atau `Arrow Keys` | Gerak manual |
| `Mouse Click` | A* pathfinding ke target |
| `M` | Toggle grid editor |
| `P` / `L` | Simpan / muat collision grid |
| `1/2/3/4` | Toggle debug layers |
| `Q` / `E` | Cycle heuristic A* player |
| `T` / `G` | Cycle heuristic A* NPC |
| `F` | Toggle NPC follow |
| `F11` | Toggle fullscreen |
| `ESC` | Settings menu |
| `R` | Reset posisi player & NPC |

### Saat Battle

| Key | Fungsi |
|-----|--------|
| `←` / `→` atau `A` / `D` | Pilih tombol aksi |
| `1/2/3/4` | Langsung pilih ATTACK / DEFEND / POTION / CHARGE |
| `ENTER` / `SPACE` | Konfirmasi aksi (atau tutup layar hasil) |
| `H` | Saran aksi dari Min-Max (hint untuk player) |
| `F3` / `TAB` | Toggle panel debug keputusan AI |
| `Mouse Click` | Klik tombol aksi |

## Instalasi

```bash
# Clone repository
git clone https://github.com/ianorii/Game-AI.git
cd Game-AI

# Install dependencies
pip install -r requirements.txt

# Jalankan game
python main.py
```

**Dependencies:**
- Python 3.10+
- pygame 2.6.1

## Struktur Grid

- Ukuran peta: **1536 x 1024** piksel
- Cell size: **8 x 8** piksel
- Grid: **192 x 128** cells
- Representasi: `0` = walkable, `1` = obstacle

Deteksi obstacle menggunakan **pixel-level color analysis** untuk mengidentifikasi:
- Air (biru)
- Atap (merah)
- Stone/fence (abu-abu)
- vegetasi gelap

## Visualisasi Debug

[foto: screenshot game yang menunjukkan NPC mengejar player dengan path terlihat]

**Penjelasan visual:**
- **Kotak biru transparan**: Node-node yang sudah diekspansi algoritma (visited)
- **Kotak merah**: Jalur terpendek dari start ke goal (path)
- **Info di atas**: Jumlah node expanded dan heuristic yang digunakan

## Analisis Kompleksitas

| Komponen | Kompleksitas |
|----------|--------------|
| **Time** | O(b^d) di worst case, dimana b = branching factor, d = depth solusi |
| **Space** | O(b^d) untuk menyimpan semua node di memory |
| **A\*** | Lebih cepat dari UCS karena heuristic memandu pencarian |
| **UCS** | O(b^d) tanpa pruning dari heuristic |

**Branching Factor pada Grid:**
- 4-directional: b = 4 (atas, bawah, kiri, kanan)
- 8-directional: b = 8 (+ diagonal)

## Referensi

- Russell, S. & Norvig, P. (2020). *Artificial Intelligence: A Modern Approach*. 4th Edition. Chapter 3: Solving Problems by Searching.
- Hart, P.E., Nilsson, N.J., & Raphael, B. (1968). A Formal Basis for the Heuristic Determination of Minimum Cost Paths. *IEEE Transactions on Systems Science and Cybernetics*.
