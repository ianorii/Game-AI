# Game AI - Pathfinding & Adversarial Search

Proyek ini berisi dua topik search AI, masing-masing untuk satu tahap tubes:

- **Tahap 1** - pathfinding di grid 2D: A\* dan UCS (Uniform Cost Search)
  dengan beberapa heuristic, dipakai untuk pergerakan Player dan NPC.
- **Tahap 2** - adversarial search: duel turn-based melawan NPC. Mode battle
  aktif otomatis saat Player mendekatinya, lalu diselesaikan dengan Minimax,
  alpha-beta pruning, early stop, move ordering, dan Expectimax.

Fokus tubes tahap 2 adalah komponen AI, bukan game design. Seluruh analisis,
eksperimen, dan dokumentasinya ada di `Laporan_Adversarial_Search.md`.

## Instalasi

```bash
pip install -r requirements.txt   # pygame 2.6.1, pygbag
python main.py                    # jalankan game
```

Python 3.10+. Paket `pygame` (bukan `pygame-ce`) yang dipakai; versi 2.6.1
sudah termasuk dukungan Python 3.13. Yang terpasang di environment penulis
adalah `pygame-ce 2.5.8` dan kode tetap berjalan di sana, jadi
pengganti `pygame-ce` juga aman kalau `pygame` gagal terpasang.

## Menjalankan duel dan melihat AI-nya

Tidak perlu menyetel apa pun untuk melihat AI-nya bekerja; aset dan peta sudah
termasuk di repository. Duel dimulai otomatis saat jarak Manhattan Player dan
NPC <= 1 ubin (`BATTLE_TRIGGER_DIST = 1` di `main.py`).

| Tombol (saat duel) | Fungsi |
|-----|--------|
| `1` / `2` / `3` / `4` | Pilih ATTACK / DEFEND / POTION / SPECIAL |
| `W` `S` atau `↑` `↓` | Geser pilihan aksi |
| `Enter` / `Space` | Konfirmasi aksi |
| `D` | Tampilkan / sembunyikan debug overlay AI |
| `C` | Nyalakan tabel perbandingan minimax vs alpha-beta vs early stop |

Overlay menampilkan skor evaluasi tiap aksi yang dipertimbangkan NPC, node
count, jumlah cutoff, dan (saat `C` aktif) perbandingan ketiga algoritma pada
state yang sama.

## Eksperimen dan laporan

```bash
python experiments.py --out hasil_eksperimen.md --log-csv duel_log.csv
python experiments.py --only E7      # hanya perbandingan branching 3 vs 4
python experiments.py --quick       # iterasi cepat dengan lebih sedikit state
python adversarial_ai.py            # self-test: alpha-beta harus = minimax
```

`experiments.py` menjalankan E0 sampai E7: horizon dan kondisi early stop,
perbandingan algoritma, fungsi evaluasi, urutan aksi, kedalaman, perilaku NPC
terhadap tiga lawan, Expectimax, dan branching 3 versus 4. Semua angka pada
laporan dihasilkan oleh perintah pertama, tanpa diedit tangan.

| Berkas | Isi |
|--------|-----|
| `Laporan_Adversarial_Search.md` | Laporan tubes tahap 2: asumsi, formulasi formal, algoritma, dan pembahasan semua eksperimen |
| `hasil_eksperimen.md` | Output mentah `experiments.py` |
| `duel_log.csv` | Log per giliran NPC untuk 60 duel (deterministik, seed tetap) |

## Struktur Proyek

```
main.py                   game loop, input, pemicu duel
adversarial_ai.py         Tubes 2: state, eval, minimax, alpha-beta, expectimax
experiments.py            harness E0-E7
battle_system.py          duel: giliran, aksi, UI panel
debug_overlay.py          DebugOverlay (pathfinding) + BattleDebugOverlay (AI duel)
player.py                 pergerakan Player + A* + UCS
npc.py                    NPC follow dengan A*
settings_menu.py          menu pengaturan
grid_override.txt         hasil simpan grid dari editor
game/
  map/core.py             grid, collision, viewport
  map/utils.py            utilitas koordinat
  pathfinding/core.py     implementasi inti A* dan UCS
  adv_search/core.py      facade ke adversarial_ai.py
```

## Pathfinding (Tahap 1)

### A\* (A-Star)

Menggabungkan `g(n)` (cost dari start ke node sekarang) dan `h(n)` (estimasi
ke goal):

```
f(n) = g(n) + h(n)
```

Memakai priority queue min-heap dan optimal bila `h` **admissible**.
Efisiensinya bergantung pada kualitas heuristic.

### UCS (Uniform Cost Search)

Special case dari A\* dengan `h(n) = 0` untuk semua node, jadi hanya
`f(n) = g(n)`. Selalu optimal untuk graf berbobot non-negatif, tapi lebih lambat
karena tidak ada panduan heuristic.

### Heuristic

| Heuristic | Formula | Keterangan |
|-----------|---------|------------|
| **Manhattan** | `abs(dx) + abs(dy)` | Paling efisien untuk grid 4-arah. Admissible dan consistent. |
| **Euclidean** | `sqrt(dx^2 + dy^2)` | Admissible, tapi kurang informatif untuk grid 4-arah. |
| **UCS** | `0` | Tanpa panduan heuristic, expands paling banyak node. |

## Kendali (Overworld)

| Tombol | Fungsi |
|-----|--------|
| `W` `A` `S` `D` / `↑` `↓` `←` `→` | Gerak manual 1 cell |
| Klik kiri | A\* pathfinding ke target |
| `E` / `Q` | Ganti heuristic Player (next / previous) |
| `T` / `G` | Ganti heuristic NPC (next / previous) |
| `F` | Toggle NPC mengikuti Player |
| `R` | Reset posisi Player dan NPC, serta status duel |
| `M` | Toggle grid editor |
| `P` / `L` | Simpan / muat grid |
| `1` `2` `3` `4` | Toggle layer debug pathfinding |
| `ESC` | Buka / tutup settings menu |
| `F11` | Toggle fullscreen |

## Struktur Grid

Ukuran peta 1536 x 1024 piksel, cell size 16 x 16, sehingga grid 96 x 64 cells.
Representasi `0` = walkable, `1` = obstacle. Deteksi obstacle memakai
analisis warna di level piksel untuk air, atap, stone/fence, dan vegetasi gelap.

## Referensi

- Russell, S. & Norvig, P. (2020). *Artificial Intelligence: A Modern
  Approach*. 4th Edition. Chapter 3: Solving Problems by Searching.
- Hart, P.E., Nilsson, N.J., & Raphael, B. (1968). A Formal Basis for the
  Heuristic Determination of Minimum Cost Paths. *IEEE Transactions on Systems
  Science and Cybernetics*.
