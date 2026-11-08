# AI LABYRINTH: THE DUNGEON OVERSEER

Game 2D top-down (Pygame) bertema *Dungeon Overseer* vs *Hero AI* dengan
**dunia open-world 96x72 tile** (3072x2304 px, sekitar 9 layar), bukan lagi satu
ruangan labirin.  
Peran pemain adalah **Dungeon Overseer**: menempatkan jebakan & monster untuk menghambat Hero.  
Hero bisa dikendalikan **manual** (WASD / tombol panah) atau **otomatis** oleh AI
(A* + rencana **STRIPS**) — mode-nya ditukar dengan **SPACE / TAB**.  
Kamera mengikuti Hero, dan HUD menampilkan **minimap dunia**, nama wilayah, serta
tujuan perjalanan menuju Core.  
Ketika Hero menyentuh Boss, masuk ke **turn-based battle** yang menggunakan **Minimax + Alpha-Beta Pruning**.

Semua algoritma AI yang diminta sudah diintegrasikan dan bisa diamati lewat overlay debug.

Dunia dibangkitkan secara deterministik dari `seed`:
- **Desa Meadowbrook** — titik spawn, rumah, sumur, pagar, lentera, jalan,
  ladang sayur berpagar, dan kandang hewan (sapi/domba/babi/ayam).
- **Hutan Whisperwood** — pepohonan rapat, semak, batu, dan monster patroli.
- **Sungai Emberflow** — aliran air, jembatan kayu, dan jalur penyeberangan.
- **Danau Kristal** — danau luas dengan air dangkal/dalam dan lili air.
- **Reruntuhan Obsidian Keep** — pelataran batu, pilar, brazier, Gerbang, Core, dan Boss.
- **Padang Liar Eldoria** — hamparan rumput terbuka yang menghubungkan semua wilayah.

## 1) Struktur Proyek

```text
DungeonGame/
├── assets/
│   ├── tilesets/
│   │   ├── sunnyside_world.png     # atlas utama 1280x1280 (64x64 sel, pitch 20)
│   │   ├── sunnyside_forest.png    # atlas kanopi hutan
│   │   └── CREDITS_sunnyside_world.txt
│   ├── sprites/
│   │   ├── hero/                   # hero_idle / hero_run / hero_attack / hero_hurt / hero_cast
│   │   └── monsters/               # zombie (Goblin), ice_zombie (Skeleton), big_demon (Boss)
│   ├── props/                      # pohon, jamur, hewan, batu, peti, tanaman
│   └── vfx/                        # api, kilau, ikon hati
├── src/
│   ├── main.py
│   ├── config.py
│   ├── asset_loader.py
│   ├── ai/
│   │   ├── pathfinding.py      # A*, Dijkstra + tracking open/closed
│   │   ├── csp.py              # Constraint Satisfaction (PlacementCSP)
│   │   ├── local_search.py     # Simulated Annealing (auto-optimise)
│   │   ├── adversarial.py      # Minimax + Alpha-Beta (battle Boss)
│   │   └── planning.py         # STRIPS planner + PlanMonitor
│   └── core/
│       ├── worldgen.py         # generator dunia: biome, jalan, sungai, desa, ladang, ruins
│       ├── world_art.py        # tile atlas + prop aset + rumah prosedural
│       ├── map.py              # chunk renderer, kamera, minimap, ambient
│       ├── entity.py           # Hero/Monster/Boss + controller manual
│       ├── battle_ui.py        # layar Battle Mode
│       └── debug_overlay.py    # Overlay F1–F5 & F12 (panel pojok)
├── tools/
│   └── import_sunnyside.py     # impor ulang aset dari paket sumber (--pack)
├── setup_structure.py
└── requirements.txt
```

> Aset tileset, karakter, prop, dan VFX berasal dari **Sunnyside World Asset Pack V2.1**
> (Daniel Diggle / Pixel Boy — lihat `assets/tilesets/CREDITS_sunnyside_world.txt`).
> Paket sumber **tidak disimpan** di proyek; folder `assets/` sudah berisi hasil impor
> yang siap dipakai. Rumah, sumur, pilar, gerbang, dan Core tetap digambar prosedural
> dengan palet Sunnyside.

### Regenerasi aset (opsional)

```bash
# Butuh salinan paket Sunnyside World V2.1 di luar proyek
python tools/import_sunnyside.py --pack /path/ke/Sunnyside_World_ASSET_PACK_V2.1
# atau set env var
SUNNYSIDE_PACK=/path/ke/paket python tools/import_sunnyside.py
```

Script impor bersifat idempoten: menghapus lalu membangun ulang isi `assets/`
dengan struktur & pola nama yang dibaca `src/asset_loader.py`.

## 2) Instalasi & Menjalankan

### Kebutuhan
- Python 3.10+ (sudah diuji di lingkungan ini)
- `pygame`
- `networkx` & `python-constraint` **opsional**. Jika tidak ada, kode tetap berjalan dengan fallback internal.

### Langkah
```bash
# 1) Masuk ke folder proyek
cd /mnt/kuliah/smt3/AI/DungeonGame

# 2) Buat lingkungan (opsional tapi disarankan)
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 3) Install dependencies
pip install -r requirements.txt

# 4) Jalankan game
python src/main.py
```

### Mode Headless / Selftest
```bash
# Selftest selama ~120 frame tanpa jendela (berguna untuk pengecekan cepat)
SDL_VIDEODRIVER=dummy python src/main.py --selftest 120

# Jalankan dengan seed tertentu (untuk reproduksi level/layout)
python src/main.py --seed 123

# Mulai langsung dalam Mode AI Auto-Pilot (A*) alih-alih Manual
python src/main.py --autopilot
```

## 3) Kontrol

### Player Controller (Mode Explore)

| Tombol | Fungsi |
|---|---|
| **W / A / S / D** atau **UP / DOWN / LEFT / RIGHT** | Gerak manual Hero (ditekan = berjalan terus, satu tile demi satu tile) |
| **SPACE** / **TAB** | Tukar **Mode Manual** ⇄ **Mode AI Auto-Pilot** (A* + STRIPS) |
| **LMB** | Pasang item terpilih (`1/2/3`) di tile kosong |
| **RMB** | Hapus item/jebakan/monster yang dipasang Overseer |
| **1** | Pilih `Fire Trap` (energi 2) |
| **2** | Pilih `Ice Trap` (energi 2) |
| **3** | Pilih `Ice Monster` (energi 5) |
| **O** | **SA auto-optimise** layout (Simulated Annealing) |
| **F5** | Simpan state game ke `data/savegame.json` |
| **F6** | Muat state game dari `data/savegame.json` |
| **F7** | Toggle Unified Planner Panel (Tab 0: Ekspedisi STRIPS) |
| **F8** | Toggle Unified Planner Panel (Tab 2: HTN - opsional, belum aktif) |
| **F9** | Toggle Mode Perencana: `OFF` -> `AUTO` -> `ADVISOR` -> `OFF` |
| **F10** | Jeda / Lanjut Autopilot (`PAUSED` ⇄ `NAVIGATING`). Bila Hero digerakkan manual dengan WASD, Autopilot otomatis terjeda dan **tetap terjeda** hingga ditekan F10 |
| **P** | Pause/Resume Game |
| **R** | Reset dunia & state (seed sama — layout identik) |
| **N** | Generate dunia baru dengan seed acak |
| **F11** / **Alt+Enter** | Toggle fullscreen / windowed (kanvas 1024x768 di-scale ke layar) |
| **ESC** | Keluar game |

- Indikator **CONTROL MODE** tampil di pojok kiri atas area peta:
  `CONTROL MODE: [MANUAL - WASD]` atau `CONTROL MODE: [AI AUTO-PILOT - A*]`.

> [!NOTE] Catatan Modul HTN (Hierarchical Task Network)
> Engine dekomposisi hierarkis SHOP-style (`src/planning/htn.py`), file domain (`data/planning/npc.htn`), dan 9 test unit (`tests/test_htn.py`) telah diimplementasikan secara mandiri. Namun, **belum ada NPC HTN yang diaktifkan di dunia permainan nyata** (ditandai sebagai materi pengayaan opsional di luar 35 slide silabus utama Automated Planning). Seluruh ekspedisi game dan misi autopilot dijalankan secara otonom oleh STRIPS forward planner dan Planning Graph.

- **Kamera open-world** mengikuti Hero secara halus dengan *look-ahead* ke arah gerak.
  Minimap di HUD menunjukkan posisi Hero, monster, Boss, Core, desa, dan viewport kamera.
- **Collision Detection presisi:** Hero tidak pernah menembus air/tebing/dinding, keluar
  peta, atau memasuki sel Boss selama Boss masih hidup (dicek tiap frame sebelum langkah).
- Pada mode Manual, sprite Hero memiliki 3 set animasi arah (depan / belakang / samping);
  gerak ke **kiri** memakai frame samping yang dicerminkan.
- **Monster tidak menyerang seketika.** Saat pertama melihat Hero, monster berhenti
  sejenak (`ALERT`, tanda `?`), lalu mengejar (`CHASE`). Saat sudah bersebelahan,
  monster melakukan *wind-up* (`!` + bar merah) selama ±0.55 detik sebelum damage
  masuk. Pemain masih punya waktu untuk kabur dan membatalkan serangan.

### Mode Battle (Turn-based vs Boss)
Boss menggunakan **Minimax + Alpha-Beta depth 3** untuk memilih aksinya.

| Tombol | Fungsi |
|---|---|
| **1** | Physical Attack (damage biasa, tanpa biaya) |
| **2** | Cast Magic / Shield (BUFF bila ada mana, otomatis jadi GUARD bila mana habis) |
| **3** | Use Item (Shield Potion: pulih HP + blok 60% damage) |
| **↑** | Physical Attack (alternatif tombol angka) |
| **→** | Cast Magic / Shield |
| **↓** | Use Item / Defend |
| **←** | Physical Attack |
| **A / H / G / B** | Shortcut lama: Attack / Heavy Strike / Guard / Cast Magic |

> Jika pemain diam saat giliran Hero di battle, Hero akan menjalankan aksi otomatis
> mengikuti strategi `BUFF -> GUARD(darurat) -> HEAVY -> ATTACK`.

### Debug Overlay
| Tombol | Tampilan |
|---|---|
| **F1** | **Pathfinding** - jalur A* Hero, `OPEN` (kuning), `CLOSED` (merah), jalur patroli monster (oranye) |
| **F2** | **CSP** - grid audit aturan R1-R3 (valid/invalid), energi Core, daftar constraint |
| **F3** | **SA** - progres Simulated Annealing (T, accept/reject, best score) |
| **F4** | **Minimax** - pohon nilai Boss + alpha/beta + skor tiap cabang aksi |
| **F5** | **STRIPS** - aksi aktif, plan saat ini, status re-plan |
| **F12** | Toggle semua overlay |

#### Layout Panel Overlay (semua semi-transparan, tidak menutupi map)

```text
+--------------------------------------------------------------+
| [CONTROL MODE]  ......                                  [LEGEND]|   pojok kiri atas = mode + log
| [LOG PESAN]                                            [CSP F2]|   pojok kanan atas = legenda + CSP
|                                                              |
|                        AREA PETA (1024 x 640)                 |
|                                                              |
| [STRIPS F5]                                              [MINIMAX F4]
| [LOCAL SEARCH F3]           [RINGKASAN A* F1]                   |
+--------------------------------------------------------------+
```

- Semua panel digambar di dalam kotak berlatar semi-transparan (`PANEL_BG`) supaya map tetap terbaca.
- Banner nama wilayah muncul singkat di kanan-atas; log pesan tetap di kiri-atas.
- Panel di kolom kiri bawah diisi dari bawah ke atas sehingga **tidak pernah saling tumpang tindih**.
- Pada Battle Mode, panel debug ditumpuk rapi di kolom kanan layar battle
  (legenda di atas, lalu Minimax → STRIPS → Local Search).

## 4) Algoritma AI yang Diimplementasikan

| Modul | Algoritma | Kegunaan |
|---|---|---|
| `ai/pathfinding.py` | **A\*** (utama), **Dijkstra** (alternatif) | Hero menavigasi spawn -> Core, menghindari dinding/monster dinamis, *repath* otomatis. Menampilkan `open/closed` di F1. |
| `ai/csp.py` | **Constraint Satisfaction (backtracking)** | Validasi penempatan Overseer. Aturan: (R1) jalur spawn→Core tidak boleh sepenuhnya diblokir, (R2) `fire trap` tidak boleh bersebelahan dengan `ice monster`, (R3) total energi ≤ kapasitas Core. Panel F2 menampilkan hasil audit/saran. |
| `ai/local_search.py` | **Simulated Annealing** | Tombol **O** mengoptimasi layout Overseer untuk memaksimalkan kesulitan. Progres ditampilkan di F3. |
| `ai/adversarial.py` | **Minimax + Alpha-Beta Pruning** | Boss menghitung aksi terbaik dengan kedalaman 3. Evaluasi dari sudut pandang Boss. Skor tiap aksi & pohon pencarian ditampilkan di F4. |
| `src/planning/` | **Automated Planning (STRIPS, Regression, Planning Graph)** | Ekspedisi otonom: Forward Search (BFS, UCS, A* $h_{\max}$, WA* $h_{\text{FF}}$, A* $h_{\text{level}}$), Backward Subgoal Regression (Slide 27), Planning Graph dengan Mutex (Slide 31–35), Plan Monitor & Adaptive Replan. Panel F7 & F8, Mode F9 (OFF/AUTO/ADVISOR). |

### CLI Demonstrasi Automated Planning (Materi Kuliah 35 Slide)
Tersedia opsi CLI interaktif untuk verifikasi cepat:
```bash
python3 src/main.py --demo-ojek        # Demo 1: Ojek Delivery, Forward Search, State Trace, Plan Checker (Slide 1-26, 30)
python3 src/main.py --demo-regression  # Demo 2: Backward Search Subgoal Regression & Dual Goal (Slide 27, 30)
python3 src/main.py --demo-graph       # Demo 3: Planning Graph, Aksi & Fakta Mutex, h_level, GraphPlan (Slide 31-35)
python3 src/main.py --demo-detour      # Demo 4: Detour Jembatan A -> B, A* rerouting, frame time IncrementalPlanner
python3 tools/demo_subphase2b.py       # Demonstrasi Empiris 7 Skenario Headless (Sub-fase 2B)
```

## 5) Rendering & Aset

- **Dunia:** `96x72` tile (`WORLD_W` / `WORLD_H` di `config.py`), viewport tetap
  `1024x640` + HUD `128` px. Dunia digeser oleh kamera, bukan dimuat penuh ke layar.
- **Tileset:** `assets/tilesets/sunnyside_world.png` (atlas Sunnyside 1280x1280,
  grid 64x64 sel; tile logis 16x16 px dengan *pitch* 20 dan *inset* 2).
  `sunnyside_forest.png` disimpan sebagai atlas sekunder (kanopi hutan).
  Medan open-world memakai tile atlas langsung; rumah, sumur, pilar, gerbang,
  dan Core tetap prosedural dengan palet Sunnyside.
- **Chunk renderer** (`src/core/map.py`):
  1. Tanah dirender per chunk **8x8 tile** secara *lazy* dan di-cache.
  2. Chunk di sekitar kamera **dibangun lebih awal satu per frame** agar perpindahan
     kamera tidak memicu lonjakan beban tepat saat chunk baru terlihat.
  3. **Ambient occlusion** dari dinding/tebing/air + bayangan pohon.
  4. Prop pendek (semak, batu, puing, peti) **dibakar ke chunk** agar hemat
     draw call; pohon, rumah, pilar, pagar, papan, brazier, dan lentera tetap
     dinamis agar kedalaman tetap benar.
  5. **Y-sorting** menyatukan prop tinggi dengan Hero/monster/Boss sehingga karakter
     bisa berjalan di depan atau di belakang objek dengan benar.
  6. Air beranimasi (kilau), partikel ambient (pollen/daun/firefly/debu), vignette
     tepi yang ringan, marker Core, dan rune spawn.
  7. **Minimap** dunia di-cache; hanya marker dinamis yang digambar tiap frame.
- **Sprite:** strip Sunnyside satu arah (96x64 px per frame) dipotong otomatis
  berdasarkan lebar strip, lalu diratakan ke kanvas 24x24. Hero/monster tampil
  48x48 dan Boss 72x72 di layar. Karena pack hanya menyediakan satu arah,
  arah kiri dicerminkan saat render; arah atas/bawah memakai frame yang sama.
- **Prop:** pohon, jamur, hewan, batu, peti, dan tanaman matang dimuat dari
  `assets/props/` (skala 2x–3x sesuai ukuran sumber).
- **Bayangan tanah** oval di bawah tiap karakter dan objek agar tidak terlihat "melayang".

## 6) Keseimbangan Battle (Minimax)

Battle bersifat turn-based dan bergantung pada strategi pemain.

Nilai saat ini (bisa dilihat di `src/config.py` & `src/ai/adversarial.py`):
- Hero: `ATTACK (14-22)`, `HEAVY (22-32, -1 mana)`, `GUARD (+14 HP, -60% dmg, cd 2)`, `BUFF (+16 dmg, 3 ronde, -1 mana)`
- Boss: `HEAVY_STRIKE (11-21)`, `AREA_MAGIC (7-16 AoE, -30% guard, buang 1 Buff)`, `GUARD (+4 HP, -60% dmg, cd 2)`, `RAGE (+2 dmg) saat HP ≤ 50%`

**Hasil pengukuran (200 seed/belok, headless):**

| Strategi Hero | HP100 | HP95 | HP85 | HP80 | HP70 |
|---|---|---:|---:|---:|---:|
| **Pintar** (BUFF -> HEAVY -> GUARD saat darurat) | 95% | 91% | 50% | 31% | 3% |
| **Auto** (mengikuti rencana game) | 97% | 93% | 63% | 43% | 14% |
| **Asal** (hanya ATTACK) | 41% | 24% | 10% | 2% | 0% |

**Kesimpulan:** Perintah pemain benar-benar menentukan hasil battle. Hero yang sehat &
menerapkan taktik yang tepat hampir selalu menang, tetapi kerusakan yang diterima Hero
sebelum battle (jebakan/monster) sangat besar pengaruhnya. Kedua ujung kemenangan
(`HERO` menang mencuri Core, atau `OVERSEER` menang membuat Hero tewas) tetap terjangkau.

## 7) Catatan Teknis

- **Aset fallback:** Jika sprite/tileset tidak lengkap, `asset_loader.py` akan menampilkan
  persegi berwarna agar game tidak crash.
- **Dependency opsional:** `networkx` dan `python-constraint` tidak wajib. Jika tidak
  terinstall, `pathfinding` dan `csp` memakai implementasi internal.
- **Battle state:** Saat battle, HP Hero di-sync dari `battle["state"]`. Boss entity
  `game.boss.hp` bisa tertinggal, sehingga status akhir sebaiknya dilihat dari state battle / log game.
- **Display & fullscreen:** kanvas game tetap `1024x768`, tetapi display dibuat
  dengan `pygame.SCALED` agar SDL men-scale ke window/fullscreen dan surface
  tidak memiliki kanal alpha. Ini mencegah sprite transparan meninggalkan
  lubang hitam pada compositor X11/Wayland. Jika `SCALED` tidak tersedia,
  game memakai surface render opaque sebagai fallback. **F11** men-toggle
  fullscreen tanpa mengubah koordinat kamera/mouse.
- **Performansi:** Tanah memakai chunk *lazy* 8x8; prop pendek dibakar ke chunk;
  sprite/bayangan objek digabung menjadi satu blit; panel debug, teks HUD, dan
  fade log memakai cache; pita vignette dipersempit agar tetap ringan. Pada
  pengujian headless (tanpa VSync) frame biasa berada di sekitar **9–13 ms**
  (p50 ≈ 9 ms, rata-rata ≈ 11–12 ms saat Auto-Pilot berjalan), dengan lonjakan
  singkat saat chunk pertama kali dibangun. Pada window/fullscreen nyata,
  presentasi/scaling SDL menambah sekitar 1–4 ms tergantung driver; angka juga
  dapat naik bila CPU sedang sibuk karena renderer memakai permukaan software
  Pygame.
- **Dunia:** 96x72 tile dibangkitkan prosedural dan deterministik dari `seed`.
  Spawn→Core selalu dicek *reachability*-nya, dan monster/ruins ditempatkan pada
  sel yang valid. `[R]` mereproduksi dunia yang sama; `[N]` membuat dunia baru.
- **Aksesibilitas:** semua aset sudah ada di folder `assets/`; paket sumber
  Sunnyside tidak diperlukan untuk bermain. Jika atlas hilang, `asset_loader.py`
  tetap menyediakan fallback berwarna agar game tidak crash.

## 8) Troubleshooting

| Masalah | Solusi |
|---|---|
| Jendela hitam / crash saat start | Pastikan `pygame` terinstall. Coba `SDL_VIDEODRIVER=dummy` untuk debug. |
| "TileSheet" error / aset hilang | Jalankan `python tools/import_sunnyside.py --pack /path/ke/paket`, atau biarkan fallback berjalan (game tetap bisa dimainkan). |
| Hero tidak bergerak | Mode default adalah **MANUAL** — tekan WASD/panah, atau tekan **SPACE** untuk beralih ke AI Auto-Pilot. |
| Battle langsung dimenangkan/dikalahkan | Atur strategi battle (gunakan BUFF + HEAVY, GUARD saat HP rendah). Lihat overlay F4. |
| FPS rendah dengan semua overlay | Matikan beberapa overlay (F1–F5) atau biarkan F12 off; caching sudah diterapkan. |

**Mulai bermain:** `python src/main.py`  
Amati AI bekerja lewat **F1–F5** untuk melihat perbedaan nyata tiap algoritma.
