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
main.py          ← Entry point, game loop, input handling
├── player.py    ← Player movement (keyboard + A* pathfinding)
├── npc.py       ← NPC follow behavior (A* recompute periodically)
├── pathfinding.py ← Core A* & UCS implementation
├── map.py       ← Grid system, collision detection, viewport
├── debug_overlay.py ← Visualisasi visited nodes & path
└── settings_menu.py ← Konfigurasi heuristic & parameter
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
- Kecepatan NPC lebih lambat dari player (600 px/s vs 750 px/s)
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

### 5. Settings Menu
- Tekan `ESC` untuk buka/tutup menu
- Konfigurasi heuristic player & NPC
- Toggle NPC follow, debug overlay, HUD
- Reset posisi, fullscreen

## Kendali

| Key | Fungsi |
|-----|--------|
| `W/A/S/D` atau `Arrow Keys` | Gerak manual |
| `Mouse Click` | A* pathfinding ke target |
| `E` | Toggle grid editor |
| `M` | Toggle debug grid |
| `1/2/3` | Toggle debug layers |
| `ESC` | Settings menu |
| `F` | Toggle fullscreen |
| `R` | Reset posisi |
| `G` | Toggle NPC follow |
| `H` | Toggle HUD |

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

## Author

**Ian Octori** - [GitHub](https://github.com/ianorii)
