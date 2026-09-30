# Game AI - Pathfinding & Adversarial Search

Proyek ini berisi dua topik search AI, masing-masing untuk satu tahap tubes:

- **Tahap 1** - pathfinding di grid 2D: A\* dan UCS (Uniform Cost Search)
  dengan beberapa heuristic, dipakai untuk pergerakan Player dan NPC.
- **Tahap 2** - adversarial search: duel turn-based melawan NPC. Mode battle
  aktif otomatis saat Player mendekatinya, lalu diselesaikan dengan Minimax,
  alpha-beta pruning, move ordering, dan early stop.

Fokus tubes tahap 2 adalah komponen AI, bukan game design. Penjelasan
komplitnya ada di bagian **Adversarial Search (Tahap 2)** di bawah.

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
termasuk di repository. Musuh muncul di lokasi acak yang cukup jauh, lalu
langsung mengejar Player (mode follow aktif, bisa dimatikan dengan `F`).
Duel dimulai otomatis saat jarak Manhattan Player dan NPC <= 1 ubin
(`BATTLE_TRIGGER_DIST = 1` di `main.py`). Game **tidak langsung** masuk menu
pertarungan saat baru dinyalakan: musuh pertama baru muncul setelah
`INITIAL_ENEMY_SPAWN_DELAY = 8` detik, jadi ada waktu jalan-jalan dulu. Setelah
duel selesai ada jeda `ENEMY_RESPAWN_DELAY = 5` detik (di `main.py`) sebelum
musuh baru muncul, lalu langsung mengejar lagi.

Setiap pertarungan selesai — menang, kalah, seri, maupun keluar paksa dengan
`ESC` — darah Player selalu di-reset penuh (100 = `MAX_HP`).

Posisi Player selalu dipertahankan: setelah duel selesai — maupun setelah
tombol `R` / tombol **Reset Duel** di menu ESC — permainan dilanjutkan dari
titik yang sama persis seperti saat war dimulai, tanpa kembali ke posisi awal
peta.

| Tombol (saat duel) | Fungsi |
|-----|--------|
| `1` / `2` / `3` / `4` | Pilih ATTACK / DEFEND / POTION / SPECIAL |
| `W` `S` atau `↑` `↓` | Geser pilihan aksi |
| `Enter` / `Space` | Konfirmasi aksi |
| `D` | Tampilkan / sembunyikan debug overlay AI |
| `-` / `=` | Kurangi / tambah kedalaman pencarian AI (1–7); overlay langsung dihitung ulang pada state yang sama |
| `ESC` | Keluar dari Battle Mode walaupun duel belum selesai |

Overlay menampilkan skor evaluasi tiap aksi yang dipertimbangkan NPC, jumlah
node minimax versus alpha-beta, node terpangkas, efisiensi pruning, jumlah
cutoff, evaluasi daun, waktu kalkulasi, fungsi evaluasi, dan urutan aksi.

Panel selalu ditempatkan di **sisi kanan layar duel**: lebarnya mengikuti area
aman (di antara panel NPC dan battle log) sehingga tetap tampil di pinggir untuk
semua resolusi umum (1920x1080, 1600x900, 1440x900, 1366x768, 1280x720, dst.),
dengan tinggi baris minimum 9 px. Mode modal (panel di tengah layar + tirai
gelap) hanya dipakai sebagai cadangan untuk layar sangat sempit (di bawah
sekitar 1152 px lebar) yang teksnya sudah tidak terbaca bila disusutkan.

## Eksperimen

```bash
python experiments.py                            # E0-E7, hasil dicetak ke stdout
python experiments.py --log-csv data/duel_log.csv   # + log per giliran NPC
python experiments.py --only E7                  # hanya perbandingan branching 3 vs 4
python experiments.py --quick                    # iterasi cepat dengan lebih sedikit state
python adversarial_ai.py                         # self-test: alpha-beta harus = minimax
```

`experiments.py` menjalankan E0 sampai E7: horizon dan kondisi early stop,
perbandingan algoritma, fungsi evaluasi, urutan aksi, kedalaman, perilaku NPC
terhadap tiga lawan, dan branching 3 versus 4. Semua angka yang
dikutip pada bagian **Adversarial Search (Tahap 2)** berasal dari perintah di
atas, tanpa diedit tangan.

| Berkas | Isi |
|--------|-----|
| `data/duel_log.csv` | Log per giliran NPC untuk 60 duel (deterministik, seed tetap) |

## Struktur Proyek

```text
Game AI/
├── main.py                        game loop, input, pemicu duel
├── player.py                      pergerakan Player + A* + UCS
├── npc.py                         NPC follow dengan A*
├── battle_system.py               duel: giliran, aksi, UI panel
├── adversarial_ai.py              Tubes 2: state, eval, minimax, alpha-beta
├── debug_overlay.py               DebugOverlay (pathfinding) + BattleDebugOverlay (AI duel)
├── settings_menu.py               menu pengaturan
├── experiments.py                 harness E0-E7
├── requirements.txt               dependensi: pygame, pygbag
├── Readme.md                      dokumen yang sedang Anda baca
├── .gitignore                     abaikan __pycache__, venv, build
│
├── game/                          paket inti game
│   ├── __init__.py
│   ├── map/
│   │   ├── __init__.py
│   │   ├── core.py                grid, collision, viewport, deteksi obstacle
│   │   └── utils.py               utilitas koordinat & kamera
│   ├── pathfinding/
│   │   ├── __init__.py
│   │   └── core.py                implementasi inti A* dan UCS
│   └── adv_search/
│       ├── __init__.py
│       └── core.py                facade ke adversarial_ai.py
│
├── docs/
│   └── screenshots/                     screenshot README (diisi manual)
│
├── data/                          data yang dibaca/ditulis saat bermain
│   ├── grid_override.txt          hasil simpan grid dari editor
│   └── duel_log.csv               log per giliran NPC, 60 duel (seed tetap)
│
├── assets/
│   └── images/                    sprite peta: terrain, air, bangunan, karakter, dll.
│
└── .github/
    └── workflows/
        └── deploy.yml             build pygbag + deploy ke GitHub Pages
```

`__pycache__/`, `venv/`, dan `build/` (output pygbag) di-ignore lewat
`.gitignore`, jadi tidak muncul di atas.

## Tangkapan Layar

Taruh screenshot di `docs/screenshots/` dengan nama persis seperti di tabel,
gambar di bawah akan tampil otomatis — tidak perlu file `.md` tambahan.

| Berkas | Isi singkat |
|--------|-------------|
| `tahap1-overworld-debug.png` | Overworld + debug overlay A\* (layer `1`–`4` + panel A\* DEBUGGER) |
| `tahap1-heuristic-manhattan.png` | Panel A\* DEBUGGER, heuristic Manhattan, `Expanded` kecil |
| `tahap1-heuristic-ucs.png` | Titik sama, heuristic UCS (h=0), `Expanded` jauh lebih besar |
| `tahap1-grid-obstacle.png` | Grid editor (tombol `M`), petak obstacle merah |
| `tahap2-menu-duel.png` | Layar duel: HP, 4 aksi, battle log |
| `tahap2-overlay-minimax.png` | Debug overlay AI (tombol `D`): skor aksi + statistik node |
| `tahap2-overlay-pruning.png` | Overlay giliran lain: node alpha-beta < minimax, pruning > 0% |

### Tahap 1 — Pathfinding

<!-- TODO: drop file di docs/screenshots/ dengan nama yang sama, gambar tampil otomatis -->
![Tahap 1 — overworld dengan debug overlay A* (visited, path, label g/h/f, panel A* DEBUGGER)](docs/screenshots/tahap1-overworld-debug.png)
![Tahap 1 — heuristic Manhattan: jumlah node expanded](docs/screenshots/tahap1-heuristic-manhattan.png)
![Tahap 1 — heuristic UCS pada titik yang sama: node expanded lebih banyak](docs/screenshots/tahap1-heuristic-ucs.png)
![Tahap 1 — grid editor: air, atap, pagar, dan vegetasi ditandai obstacle](docs/screenshots/tahap1-grid-obstacle.png)

### Tahap 2 — Adversarial Search

<!-- TODO: drop file di docs/screenshots/ dengan nama yang sama, gambar tampil otomatis -->
![Tahap 2 — layar duel dengan empat pilihan aksi dan battle log](docs/screenshots/tahap2-menu-duel.png)
![Tahap 2 — debug overlay AI: skor aksi, node minimax vs alpha-beta, pruning](docs/screenshots/tahap2-overlay-minimax.png)
![Tahap 2 — debug overlay AI pada giliran lain: node alpha-beta lebih sedikit](docs/screenshots/tahap2-overlay-pruning.png)

## Pathfinding (Tahap 1)

### Formulasi masalah

| Unsur | Representasi |
|-------|--------------|
| State | `(baris, kolom)` pada grid 96 x 64 |
| Aksi | 4 arah: atas, kanan, bawah, kiri — tanpa diagonal (`allow_diagonal=False`) |
| Cost langkah `g` | 1 per ubin |
| Start | Posisi Player saat klik, atau posisi NPC saat recompute |
| Goal | Ubin yang diklik (Player) atau posisi target (NPC) |
| Selesai | `goal` keluar dari frontier = FOUND; frontier kosong = NO PATH |

Graf yang ditelusuri bukan gambar peta mentah, melainkan grid hasil deteksi
obstacle (`0` = bisa dilewati, `1` = terblokir), sehingga jalur tidak pernah
menyeberangi air, atap, pagar, maupun vegetasi gelap.

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

### Perbandingan ketiga varian

| Varian | Optimal | Rata-rata node di-expand | Karakter |
|--------|---------|--------------------------|----------|
| A\* + Manhattan | ya (admissible & consistent) | **568** | Paling sedikit node, jadi paling cepat |
| A\* + Euclidean | ya (admissible) | **774** | Lebih banyak node karena menganggap gerak diagonal mungkin |
| UCS (`h = 0`) | ya | **1758** | Menjelajah ke segala arah, ± 3x node Manhattan |

Angka di atas diukur pada peta asli dengan 56 pasang titik acak (seed 7),
gerak 4 arah; ketiganya menghasilkan panjang jalur yang identik. Di permainan,
perbandingan ini terlihat langsung pada angka `Expanded` di panel
**A\* DEBUGGER** — tekan `E`/`Q` untuk mengganti heuristic Player dan `T`/`G`
untuk heuristic NPC.

### Kompleksitas

Worst case ketiga algoritma O(b^d), dengan `b = 4` arah (8 bila diagonal
diaktifkan) dan `d` = kedalaman solusi. UCS dapat membuka hampir seluruh
simpul pada radius `d`, sementara A\* hanya membuka simpul dengan
`f(n) ≤ f*` — makin dekat `h(n)` ke jarak sesungguhnya, makin sedikit simpul
yang dibuka.

### Alur kerja di dalam game

1. Input (klik kiri atau gerak manual) menentukan start dan goal.
2. `game/pathfinding/core.py` menjalankan pencarian; hasilnya disimpan di
   `Player.debug_visited`, `Player.debug_path`, dan `Player.debug_node_data`
   (nilai g/h/f tiap simpul).
3. `DebugOverlay` menggambar layer sesuai tombol `1`–`4`, lalu Player bergerak
   menyusuri path dengan interpolasi (tanpa snap).
4. NPC memanggil fungsi yang sama setiap kali targetnya berubah. Default
   heuristic: Player `manhattan` (`player.py`), NPC `ucs` (`npc.py`).

### Kecepatan Gerak

| Karakter | `move_speed` | Setara |
|----------|--------------|--------|
| **Player** (`player.py`) | `650` px/s | ≈ 40,6 ubin/detik |
| **NPC** (`npc.py`) | `250` px/s | ≈ 15,6 ubin/detik |

NPC sengaja dibuat lebih lambat dari player supaya player masih bisa menjaga
jarak, sementara interpolasi NPC tanpa *snap* tiap recompute membuat
kecepatan efektifnya persis sesuai `move_speed`.

## Adversarial Search (Tahap 2)

Duel bergiliran: Player memilih satu dari empat aksi (`ATTACK`, `DEFEND`,
`POTION`, `SPECIAL`), NPC menjawab dengan aksi hasil pencarian adversarial.
Asumsi pemodelan, perbandingan algoritma, dan pembahasan eksperimen dirangkum
di bagian ini; semua angkanya dihasilkan oleh `experiments.py`.

### Formulasi masalah

| Unsur | Representasi |
|-------|--------------|
| State | `BattleState`: HP Player, HP NPC, sisa potion, status buff/armor, giliran |
| Pemain | Dua: NPC (maximizer) dan Player (minimizer) |
| Aksi | `ATTACK`, `DEFEND`, `POTION`, `SPECIAL` → branching maksimum 4 (`POTION`/`SPECIAL` hanya bila legal) |
| Kedalaman | 4 ply per giliran (`DEFAULT_DEPTH = 4`) |
| Terminal | `BattleState.is_terminal()`: `player_hp ≤ 0` atau `npc_hp ≤ 0`, lalu skor terminal `± WIN_SCORE` |
| Utilitas | `eval_balanced` (default): selisih HP + selisih potion × 10 + bonus defend ± 15 + bonus terminal |

### Algoritma yang diimplementasikan

| Algoritma | Ide singkat | Tempat |
|-----------|-------------|--------|
| **Minimax** | NPC memaksimalkan skor, Player meminimalkan; jadi patokan tanpa pruning | `adversarial_ai.py` |
| **Alpha-beta pruning** | Memangkas subtree yang mustahil mengalahkan skor terbaik yang sudah diketahui | `adversarial_ai.py` |
| **Move ordering** | Aksi yang kemungkinan terbaik dicoba lebih dulu sehingga window menutup lebih cepat | `MOVE_ORDERS` |
| **Early stop** | Pemangkasan tambahan bila `is_decided(state)` — satu pihak pasti mati, pihak lain tidak, jadi hasil akhir tidak berubah lagi | `is_decided()` |

**Alpha-beta bukan algoritma baru — ia hanya minimax yang lebih hemat.**
Yang dipotong adalah bagian pohon yang **mustahil mengubah keputusan akhir**,
sehingga skor dan aksi yang dipilih **dijamin identik dengan minimax**; yang
berbeda hanya jumlah node yang dihitung. Bukti empirisnya ada di self-test
`python adversarial_ai.py` (aksi sama pada kedalaman 1-6, node lebih sedikit).

Konfigurasi yang dipakai saat duel berlangsung: `algorithm = "alphabeta"`,
`eval = "balanced"`, `order = "default"`, `depth = 4`, dengan `early_stop`
**nonaktif** (hasil eksperimennya tetap dilaporkan di bawah). Statistik tiap
giliran (node, cutoff, terpangkas, waktu) ditampilkan lewat
`BattleDebugOverlay` dengan tombol `D`.

Kedalaman bisa diubah **saat duel berjalan** dengan `-` / `=` (rentang 1–7,
mengikuti rentang eksperimen E1/E4). Setiap kali diubah, overlay **langsung
dihitung ulang pada state yang sama**, jadi angka node minimax vs alpha-beta
bisa dibandingkan antar kedalaman dalam satu tangkapan layar. Kedalaman terakhir
dipertahankan untuk duel berikutnya.

### Hasil eksperimen (ringkas)

Semua angka di bawah berasal dari `experiments.py` (600 state acak, seed tetap):

**Penghematan node alpha-beta terhadap minimax (E1)**

| Kedalaman | Node minimax | Node alpha-beta | Hemat | + early stop |
|-----------|-------------|-----------------|-------|--------------|
| 4 | 140,3 | 101,9 | 27,4% | 32,9% |
| 5 | 454,6 | 217,3 | 52,2% | 56,6% |
| 6 | 1455,0 | 494,5 | 66,0% | 69,1% |
| 7 | 4628,7 | 982,1 | 78,8% | 81,1% |

Titik potong alpha-beta mulai terasa sejak kedalaman 3, dan keuntungannya
makin besar seiring bertambahnya kedalaman.

**Optimasi lain**

- **Move ordering (E3):** urutan `aggressive` memangkas **37,2%** node dibanding
  urutan default, dengan skor tetap identik di 100% state (beda aksi hanya
  karena skor seri).
- **Early stop (E1):** pada kedalaman 7 menambah penghematan dari 78,8% menjadi
  **81,1%** dengan 16,6 kasus cutoff per 100 state.
- **Branching 3 vs 4 (E7):** menambah aksi `SPECIAL` menaikkan kemenangan NPC
  dari 40,0% (tanpa SPECIAL) menjadi **93,3%**, dengan distribusi aksi root
  ATTACK 61,3% / DEFEND 3,8% / POTION 24,2% / SPECIAL 10,7%.

## Kendali (Overworld)

| Tombol | Fungsi |
|-----|--------|
| `W` `A` `S` `D` / `↑` `↓` `←` `→` | Gerak manual 1 cell |
| Klik kiri | A\* pathfinding ke target |
| `E` / `Q` | Ganti heuristic Player (next / previous) |
| `T` / `G` | Ganti heuristic NPC (next / previous) |
| `F` | Toggle NPC mengikuti Player |
| `R` | Reset status duel + respawn musuh (posisi player tetap di tempat) |
| `M` | Toggle grid editor |
| `P` / `L` | Simpan / muat grid (`data/grid_override.txt`) |
| `1` `2` `3` `4` | Toggle layer debug pathfinding |
| `ESC` | Buka / tutup settings menu (saat duel: keluar dari Battle Mode) |
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
