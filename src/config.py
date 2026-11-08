"""
config.py - Konfigurasi sentral game "AI LABYRINTH: THE DUNGEON OVERSEER"

Semua konstanta (ukuran tile, FPS, warna, parameter AI, bindings tombol)
didefinisikan di sini agar mudah di-tweak tanpa menyentuh logika game.
"""

import os

# ==============================================================================
# PATH DASAR
# ==============================================================================
# src/config.py  ->  folder src  ->  root proyek
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
SUNNYSIDE_DIR = os.path.join(ASSETS_DIR, "sunnyside_world")
MAPS_DIR = os.path.join(ASSETS_DIR, "maps")

# Peta Pulau Baru (Sunnyside HD Map dari Aset Tileset)
MAP_IMAGE_PATH = os.path.join(MAPS_DIR, "island_map.png")
MAP_COLLISION_PATH = os.path.join(MAPS_DIR, "collision.json")
WALKABLE_MASK_PATH = os.path.join(MAPS_DIR, "walkable_mask.png")
OVERRIDES_PATH = os.path.join(MAPS_DIR, "overrides.json")
DEBUG_PREVIEW_PATH = os.path.join(MAPS_DIR, "debug_mask_preview.png")

# Direktori Data Runtime & Collision Overrides
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
COLLISION_OVERRIDES_PATH = os.path.join(DATA_DIR, "collision_overrides.json")
COLLISION_BACKUP_PATH = os.path.join(DATA_DIR, "collision_overrides.json.bak")
VERBOSE_SPRITE_LOGS: bool = True

MAP_SCALE = 2                      # Skala integer (1x: 1376x768, 2x HD: 2752x1536)
MAP_RAW_W = 1376                   # 86 tile x 16 px
MAP_RAW_H = 768                    # 48 tile x 16 px
DEFAULT_SPAWN_1X = (720, 528)      # Titik awal player di alun-alun desa Meadowbrook (tile 45, 33)

# ==============================================================================
# LAYAR & GRID
# ==============================================================================
WINDOW_SIZE = (1024, 768)          # spesifikasi tugas
TITLE = "AI LABYRINTH: THE DUNGEON OVERSEER"
FPS = 60                           # spesifikasi tugas

# Ukuran tile render - Sunnyside World 16x16 dirender x2 (32x32)
TILE_SIZE = 32                     # ukuran tile di layar (px)
SOURCE_TILE = 16                   # ukuran tile sumber di tileset PNG
SCALE_FACTOR = TILE_SIZE // SOURCE_TILE   # scaling 16x16 -> 32x32 (factor 2)
RENDER_SCALE = SCALE_FACTOR
USE_TINY_DUNGEON = False           # warisan nama; True hanya untuk Kenney lama

# ---------------------------------------------------------------------------
# VIEWPORT vs OPEN WORLD
#   MAP_PIXEL_W/H = area pandang (viewport) game, tetap 1024 x 640 agar HUD
#   dan panel debug tidak berubah. Dunia sesungguhnya jauh lebih luas dan
#   digeser oleh CAMERA yang mengikuti Hero.
# ---------------------------------------------------------------------------
MAP_W = 32                         # lebar viewport dalam tile (legacy)
MAP_H = 20                         # tinggi viewport dalam tile (legacy)
MAP_PIXEL_W = MAP_W * TILE_SIZE    # 1024 (viewport)
MAP_PIXEL_H = MAP_H * TILE_SIZE    # 640 (viewport)
HUD_H = WINDOW_SIZE[1] - MAP_PIXEL_H    # 128 px panel bawah

#: ukuran dunia open-world pulau Sunnyside.
WORLD_W = 86
WORLD_H = 48
WORLD_PIXEL_W = WORLD_W * TILE_SIZE
WORLD_PIXEL_H = WORLD_H * TILE_SIZE

MAP_WORLD_PIXEL_W = MAP_RAW_W * MAP_SCALE
MAP_WORLD_PIXEL_H = MAP_RAW_H * MAP_SCALE

#: ukuran chunk cache render tanah (tile per sisi). Chunk dibuat lazy saat
#: kamera mendekat supaya start tetap cepat dan memori hemat.
CHUNK_TILES = 8

#: kecepatan kamera mengikuti Hero (makin besar = makin responsif)
CAMERA_LERP = 8.0
CAMERA_LOOKAHEAD = 1.1             # geser kamera ke arah hadap Hero (tile)

#: tile yang dianggap "dalam ruangan" untuk pencahayaan/ambient
OPEN_WORLD_LIGHT = (255, 236, 186, 14)   # lapisan hangat tipis (RGBA)

# ==============================================================================
# WARNA
# ==============================================================================
WHITE = (245, 245, 245)
BLACK = (12, 12, 16)
LIGHT_GREY = (200, 200, 210)
GREY = (150, 150, 160)
DARK_GREY = (60, 60, 70)
RED = (230, 60, 60)
GREEN = (80, 220, 100)
BLUE = (70, 130, 240)
YELLOW = (240, 210, 60)
ORANGE = (240, 140, 40)
CYAN = (90, 210, 240)
PURPLE = (190, 90, 230)
PINK = (240, 100, 170)
GOLD = (255, 200, 60)

PANEL_BG = (14, 14, 20, 205)       # rgba untuk panel debug
GRID_LINE = (28, 28, 36)

# Warna PLACEHOLDER bila file aset PNG tidak ditemukan
# (merah = hero, biru = core, abu-abu = dinding - sesuai spesifikasi)
FALLBACK_COLORS = {
    "hero": RED,
    "core": BLUE,
    "wall": (125, 125, 135),
    "floor": (46, 46, 56),
    "spawn": GREEN,
    "monster": (95, 200, 95),
    "monster_ice": (120, 190, 240),
    "boss": PINK,
    "fire_trap": ORANGE,
    "ice_trap": CYAN,
    "magic": PURPLE,
}

# ==============================================================================
# ASET - Sunnyside World Asset Pack V2.1
#   Atlas utama: tilesets/sunnyside_world.png (1280x1280)
#     * 64 x 64 sel, tile logis 16x16 px
#     * jarak antar sel (pitch) 20 px, konten dimulai 2 px dari tepi sel
#   Atlas sekunder: tilesets/sunnyside_forest.png (autotile kanopi hutan)
# ==============================================================================
TILESET_CANDIDATES = [
    os.path.join(SUNNYSIDE_DIR, "Tileset", "sunnyside_world.png"),
    os.path.join(SUNNYSIDE_DIR, "Tileset", "spr_tileset_sunnysideworld_16px.png"),
    os.path.join(SUNNYSIDE_DIR, "Tileset", "sunnyside_forest.png"),
    os.path.join(ASSETS_DIR, "tilesets", "sunnyside_world.png"),
]

#: jarak antar sel atlas (px) dan inset konten di dalam sel
TILESET_PITCH = 20
TILESET_INSET = 2

# ---------------------------------------------------------------------------
# ATLAS - daftar koordinat (kolom, baris) per jenis permukaan.
# Semua koordinat sudah diverifikasi manual dari contact-sheet atlas:
#   * rumput  : hijau polos dengan bintik daun
#   * hutan   : hijau gelap (kanopi lembap)
#   * tanah   : cokelat kemerahan
#   * jalan   : pasir/beige setapak
#   * batu    : lempeng batu abu-abu (dipakai juga untuk dinding & dungeon)
#   * air     : cyan terang (dangkal) vs biru tua (dalam)
# Variasi dipilih deterministik per sel supaya tekstur tidak berulang.
# ---------------------------------------------------------------------------
TILE_ATLAS = {
    "grass":      [(1, 1), (2, 1), (1, 2), (2, 2), (0, 3), (1, 3),
                   (2, 3), (3, 3), (5, 3), (7, 3), (2, 4), (3, 4)],
    "meadow":     [(0, 3), (1, 3), (2, 3), (3, 3), (5, 3), (7, 3)],
    "forest":     [(14, 4), (15, 4), (16, 4), (17, 4), (14, 5)],
    "dirt":       [(10, 4), (11, 4), (12, 4), (14, 2)],
    "path":       [(9, 7), (10, 7), (11, 7), (12, 7)],
    "sand":       [(5, 1), (7, 1), (8, 1), (9, 1), (42, 7), (43, 7)],
    "stone":      [(2, 15), (3, 15), (9, 15), (1, 16)],
    "dungeon":    [(2, 15), (3, 15), (9, 15), (1, 16)],
    "cliff":      [(1, 15), (2, 15), (3, 15), (9, 15)],
    "water":      [(30, 6), (31, 6), (32, 6), (33, 6)],
    # air dalam memakai tile air dangkal yang digelapkan di world_art
    # (atlas tidak punya tile "deep water" polos sendiri).
    "deep_water": [(30, 6), (31, 6), (32, 6), (33, 6)],
    # ---- lantai indoor (dipakai UI/latar battle) -------------------------
    "floor_wood":  (8, 5),
    "floor_dirt":  (10, 4),
    "floor_stone": (2, 15),
    # ---- tekstur dinding batu --------------------------------------------
    "wall_block": (2, 15),
}

#: ukuran kanvas sprite karakter hasil impor (px sumber)
CHAR_CANVAS = 24
#: skala sprite karakter di layar: hero/monster 24 -> 48, boss 24 -> 72
HERO_SCREEN_SIZE = (CHAR_CANVAS * 2, CHAR_CANVAS * 2)
MONSTER_SCREEN_SIZE = (CHAR_CANVAS * 2, CHAR_CANVAS * 2)
BOSS_SCREEN_SIZE = (CHAR_CANVAS * 3, CHAR_CANVAS * 3)
#: skala aset prop (pohon 32x34 -> 64x68, batu 10x10 -> 30x30)
PROP_SCALE = 2

# Gaya lantai per wilayah (dipakai bila latar battle/ruangan digambar)
FLOOR_STYLE_ROOM = "wood"       # lantai kayu di dalam ruangan
FLOOR_STYLE_CORRIDOR = "dirt"    # lantai tanah di koridor
FLOOR_STYLE_CORE = "stone"      # lantai batu di ruangan Core

# Proporsi tinggi "front face" dinding 2.5D (dalam piksel render)
WALL_FACE_RATIO = 3             # 1/3 tinggi tile

# ==============================================================================
# PLAYER CONTROLLER - mode manual (default) & auto-pilot AI
# ==============================================================================
CONTROL_MANUAL = "MANUAL"       #mode default: keyboard WASD / panah
CONTROL_AUTOPILOT = "AUTOPILOT"  #mode AI: A* Pathfinding + STRIPS Planning

#: nama tombol -> arah gerak hero pada mode MANUAL ("up"/"down"/"left"/"right").
#: Dipetakan ke konstanta pygame di src/main.py (KEY_DIRECTION).
MOVE_KEYS = {
    "W": "up", "S": "down", "A": "left", "D": "right",
    "UP": "up", "DOWN": "down", "LEFT": "left", "RIGHT": "right",
}

#: tombol untuk berpindah mode kontrol
CONTROL_TOGGLE_KEYS = ("SPACE", "TAB")

#: label indikator mode kontrol (pojok atas layar)
CONTROL_MODE_LABEL = {
    CONTROL_MANUAL: "CONTROL MODE: [MANUAL - WASD]",
    CONTROL_AUTOPILOT: "CONTROL MODE: [AI AUTO-PILOT - A*]",
}

# ==============================================================================
# GAME STATES
# ==============================================================================
STATE_EXPLORATION = "EXPLORE"         # Hero menelusuri peta 2D (A* Pathfinding)
STATE_BATTLE_PREP = "BATTLE_PREP"     # Layar Persiapan Loadout Hero (CSP)
STATE_BATTLE = "BATTLE"               # Battle Mode (Minimax + Alpha-Beta)
STATE_GAME_OVER = "GAME_OVER"         # Battlefield selesai (kalah/menang)


# ==============================================================================
# GAMEPLAY - HERO
# ==============================================================================
# Kustomisasi Rambut Hero (Sunnyside World: spikeyhair, bowlhair, curlyhair, longhair, mophair, shorthair)
HERO_HAIR_STYLE = "spikeyhair"   # Gaya rambut (default: spikeyhair merah seperti di Battle Mode)
HERO_HAIR_COLOR = (228, 59, 68)  # Warna rambut otentik merah Sunnyside World, atau None untuk palet asli

HERO_SPEED_TPS = 4.6        # tile per detik saat menjelajah
HERO_MAX_HP = 100
HERO_MAX_MANA = 2
HERO_SLOW_MULT = 0.45       # factor kecepatan saat kena es
HERO_SLOW_TIME = 2.2        # detik
HERO_INVULN_TIME = 0.55     # i-frame setelah kena damage

# ==============================================================================
# GAMEPLAY - MONSTER & BOSS
# ==============================================================================
MONSTER_SPEED_TPS = 2.7
MONSTER_CHASE_SPEED_TPS = 4.0
MONSTER_CHASE_RADIUS = 7    # jarak deteksi hero (manhattan)
MONSTER_DAMAGE = 10
ICE_MONSTER_DAMAGE = 8      # + efek lambat
ICE_MONSTER_SLOW = True
MONSTER_ATTACK_COOLDOWN = 1.0
# NPC tidak langsung menyerang: ada jeda "menyadari" lalu "wind-up" sebelum
# damage benar-benar masuk. Memberi pemain kesempatan menghindar.
MONSTER_ALERT_TIME = 0.75   # detik berhenti & waspada saat pertama melihat Hero
MONSTER_ATTACK_WINDUP = 0.55  # detik ancang-ancang sebelum memukul

BOSS_SPEED_TPS = 2.2
BOSS_MAX_HP = 100
BOSS_DAMAGE = 12            # baseline; tiap aksi punya range sendiri
BOSS_POS = (2464, 448)      # Koordinat Boss di dunia (Obsidian Keep Ruins)
BOSS_TRIGGER_RADIUS = 64    # Radius trigger interaksi (2 tile x 32 px)
BOSS_NAME = "SKELETON OVERLORD"

# Keseimbangan TURN-BASED BATTLE (dipakai ai/adversarial.py)
# Spesifikasi:
#   Player actions (strictly 3):
#     1. ATTACK: 18-24 dmg (expected average 21)
#     2. POTION: +30 HP, starts at 3, disabled at 0
#     3. DEFEND: reduces incoming dmg on next opponent turn by 60%
#   Boss actions:
#     1. ATTACK: 20-26 dmg (expected average 23)
#     2. HEAVY_ATTACK: 36 dmg (3-turn cooldown, defend only cuts 30%)
#     3. DEFEND: cuts player damage by 50%
#     4. HEAL: +20 HP, max 2 uses
HERO_ATTACK_DMG = (18, 24)
HERO_ATTACK_EXPECTED = 21
HERO_INITIAL_POTIONS = 3
HERO_POTION_HEAL = 30
HERO_DEFEND_REDUCE = 0.60
GUARD_DAMAGE_REDUCE = 0.60    # alias kompatibilitas

# --- Aksi Boss (dikerjakan oleh Minimax + Alpha-Beta) ----------------------
BOSS_ATTACK_DMG = (20, 26)
BOSS_ATTACK_EXPECTED = 23
BOSS_HEAVY_DMG = 36
BOSS_HEAVY_CD = 3
BOSS_HEAVY_GUARD_REDUCE = 0.30
BOSS_DEFEND_REDUCE = 0.50
BOSS_HEAL_AMOUNT = 20
BOSS_MAX_HEALS = 2
BATTLE_MAX_TURNS = 50

# Kesiapan Pertarungan Ekspedisi (Automated Planning)
# Ambang tunggal jujur win rate minimal agar loadout berstatus SIAP (ready_loadout)
READY_MIN_WIN_RATE = 0.50             # Ambang tunggal (50%): hanya loadout win rate >= 50% yang siap tempur
READY_MIN_POTIONS = 1                 # Syarat wajib potion: minimal membawa 1 potion untuk status SIAP (ekspedisi aman)
PLANNER_PAUSE_KEY = "F10"             # Tombol eksplisit jeda/lanjut planner (tidak lagi memakai Spasi)

# Fallback alias untuk kode lama bila ada yang mengakses
BOSS_HEAVY_STRIKE_DMG = (20, 28)
BOSS_AREA_MAGIC_DMG = (15, 25)
BOSS_GUARD_HEAL = 20
BOSS_GUARD_CD = 2
BOSS_RAGE_HP_GATE = 0.5
BOSS_RAGE_BUFF = 2
HERO_HEAVY_DMG = (22, 32)
HERO_BUFF_DMG = 16
HERO_BUFF_TURNS = 3
HERO_GUARD_HEAL = 30

# --- Fungsi evaluasi Minimax ----------------------------------------------
EVAL_WIN_SCORE = 1000         # nilai terminal (kalah/menang mutlak)

# --- Menu aksi Hero di Battle Mode ---------------------------------------
BATTLE_MENU = [
    {"key": "1", "name": "ATTACK", "action": "ATTACK",
     "hint": "Serang musuh (-21 HP)"},
    {"key": "2", "name": "POTION", "action": "POTION",
     "hint": "Pulihkan +30 HP (tersisa 3)"},
    {"key": "3", "name": "DEFEND", "action": "DEFEND",
     "hint": "Tahan serangan lawan (-60% damage)"},
]

#: pemetaan tombol panah -> indeks menu battle (0=Attack, 1=Potion, 2=Defend)
BATTLE_ARROW_KEYS = {
    "LEFT": 0,
    "UP": 0,
    "DOWN": 2,
    "RIGHT": 1,
}

#: label tombol panah yang ditampilkan di menu Battle Mode
BATTLE_ARROW_LABEL = {
    0: "panah KIRI/ATAS",
    1: "panah KANAN",
    2: "panah BAWAH",
}

# ==============================================================================
# JEBAKAN & ENERGI (Constraint Satisfaction)
# ==============================================================================
TRAP_REARM_TIME = 2.6       # detik sampai jebakan aktif lagi
FIRE_TRAP_DAMAGE = 15
ICE_TRAP_DAMAGE = 9
ICE_TRAP_SLOW = True

CORE_ENERGY_CAPACITY = 20   # kapasitas energi Core
ITEM_ENERGY = {             # konsumsi energi tiap item yang dipasang overseer
    "fire_trap": 2,
    "ice_trap": 2,
    "ice_monster": 5,
}
ITEM_LABEL = {
    "fire_trap": "Fire Trap",
    "ice_trap": "Ice Trap",
    "ice_monster": "Ice Monster",
}

# ==============================================================================
# SIMULATED ANNEALING (Local Search - auto optimise layout)
# ==============================================================================
SA_START_TEMP = 600.0
SA_MIN_TEMP = 1.0
SA_ALPHA = 0.995            # factor pendinginan per iterasi
SA_ITERS_PER_FRAME = 4      # kecepatan animasi optimisasi

# ==============================================================================
# ADVERSARIAL SEARCH (Minimax + Alpha-Beta)
# ==============================================================================
MINIMAX_DEPTH = 3           # kedalaman pencarian boss default (Normal)
MINIMAX_DEPTH_EASY = 1      # Level Easy: 1-ply search (cepat/greedy)
MINIMAX_DEPTH_NORMAL = 3    # Level Normal: 3-ply minimax + alpha-beta
MINIMAX_DEPTH_HARD = 5      # Level Hard: 5-ply minimax + alpha-beta + planner
DEFAULT_DIFFICULTY = "NORMAL"

BATTLE_HERO_TURN_TIME = 2.4 # detik window input pemain sebelum hero auto-main
BATTLE_BOSS_DELAY = 1.0     # jeda "Boss berpikir" 0.8 - 1.2 detik (spesifikasi 1.0s)
BATTLE_LOG_SIZE = 14        # jumlah baris battle log yang disimpan

# Layout Battle Mode (1024x768 - 4 Zona Fullscreen Tanpa Tumpang Tindih)
BATTLE_ARENA_RECT = (0, 0, 1024, 430)             # Zona 1: Arena (56% tinggi)
BATTLE_MENU_RECT = (20, 440, 520, 316)            # Zona 3: Menu Aksi (bawah kiri)
BATTLE_LOG_RECT = (560, 440, 444, 316)            # Zona 4: Battle Log (bawah kanan)
BATTLE_AI_PANEL_RECT = (650, 14, 360, 140)        # Zona AI Thinking (F3 overlay kanan)

# Posisi Karakter & Elemen HUD Arena (Dihitung dari posisi sprite agar seimbang)
BATTLE_HERO_POS = (230, 395)                      # Anchor kaki Hero di arena
BATTLE_BOSS_POS = (790, 395)                      # Anchor kaki Boss di arena
BATTLE_HERO_HP_RECT = (120, 185, 220, 22)         # Bar HP Hero tepat di atas kepala sprite
BATTLE_BOSS_HP_RECT = (680, 165, 220, 22)         # Bar HP Boss tepat di atas kepala sprite
BATTLE_TURN_PILL_RECT = (382, 14, 260, 32)        # Pill indikator giliran di tengah atas
BATTLE_BOSS_TITLE_RECT = (382, 48, 260, 20)       # Judul nama boss kecil

# Tombol Aksi di dalam Menu (Presisi di dalam BATTLE_MENU_RECT)
BATTLE_BUTTON_1_RECT = (36, 482, 488, 48)
BATTLE_BUTTON_2_RECT = (36, 536, 488, 48)
BATTLE_BUTTON_3_RECT = (36, 590, 488, 48)
BATTLE_DESC_RECT = (36, 646, 488, 54)
BATTLE_HINT_RECT = (36, 708, 488, 24)

# ==============================================================================
# CSP HERO LOADOUT CONFIGURATION (Persiapan Sebelum Battle)
# ==============================================================================
CSP_BUDGET = 10               # Batas total poin cost
CSP_WEIGHT_LIMIT = 10         # Batas total bobot weight
CSP_SOLVER_SEED = 42          # Seed deterministik untuk CSP solver

CSP_SLOTS = ["WEAPON", "ARMOR", "CHARM", "CONSUMABLE"]

CSP_ITEMS = {
    "WEAPON": [
        {"name": "Pedang Biasa", "cost": 2, "weight": 3, "desc": "Pedang seimbang standar (+0 DMG)", "effects": {"attack_bonus": 0}, "locked": False, "is_defensive": False},
        {"name": "Kapak Berat", "cost": 4, "weight": 6, "desc": "Kapak penghancur (+6 DMG, berat)", "effects": {"attack_bonus": 6}, "locked": False, "is_defensive": False},
        {"name": "Belati Cepat", "cost": 3, "weight": 2, "desc": "Belati lincah tebasan cepat (+3 DMG)", "effects": {"attack_bonus": 3}, "locked": False, "is_defensive": False},
        {"name": "Tongkat Api", "cost": 5, "weight": 3, "desc": "Tongkat magis semburan api (+7 DMG)", "effects": {"attack_bonus": 7}, "locked": False, "is_defensive": False},
    ],
    "ARMOR": [
        {"name": "Kain", "cost": 1, "weight": 1, "desc": "Jubah kain ringan (+0 HP, mobilitas tinggi)", "effects": {"max_hp_bonus": 0, "defend_bonus": 0.0}, "locked": False, "is_defensive": False},
        {"name": "Kulit", "cost": 3, "weight": 3, "desc": "Zirah kulit tangguh (+10 HP, +5% defend)", "effects": {"max_hp_bonus": 10, "defend_bonus": 0.05}, "locked": False, "is_defensive": True},
        {"name": "Besi", "cost": 5, "weight": 6, "desc": "Baju pelat besi (+20 HP, +10% defend, berat)", "effects": {"max_hp_bonus": 20, "defend_bonus": 0.10}, "locked": False, "is_defensive": True},
    ],
    "CHARM": [
        {"name": "Kosong", "cost": 0, "weight": 0, "desc": "Tanpa jimat tambahan", "effects": {}, "locked": False, "is_defensive": False},
        {"name": "Jimat Vitalitas", "cost": 3, "weight": 1, "desc": "Jimat penambah daya tahan (+25 HP)", "effects": {"max_hp_bonus": 25}, "locked": False, "is_defensive": True},
        {"name": "Jimat Kritikal", "cost": 4, "weight": 1, "desc": "Jimat tebasan mematikan (+4 avg DMG)", "effects": {"attack_bonus": 4}, "locked": False, "is_defensive": False},
        {"name": "Jimat Penawar", "cost": 2, "weight": 1, "desc": "Ramuan lebih manjur (+10 HP per potion)", "effects": {"potion_heal_bonus": 10}, "locked": False, "is_defensive": False},
    ],
    "CONSUMABLE": [
        {"name": "Kosong", "cost": 0, "weight": 0, "desc": "Tanpa perbekalan ekstra", "effects": {}, "locked": False, "is_defensive": False},
        {"name": "Potion Ekstra", "cost": 3, "weight": 2, "desc": "Bawa +2 botol potion tambahan", "effects": {"potion_count_bonus": 2}, "locked": False, "is_defensive": False},
        {"name": "Perisai Kertas", "cost": 2, "weight": 1, "desc": "Mulai battle dengan DEFEND aktif", "effects": {"start_defending": True}, "locked": False, "is_defensive": True},
        {"name": "Bom Asap", "cost": 3, "weight": 1, "desc": "Ledakan awal kurangi HP Boss sebesar -15 HP", "effects": {"boss_hp_penalty": 15}, "locked": False, "is_defensive": False},
    ]
}

CSP_DEFAULT_LOADOUT = {
    "WEAPON": "Pedang Biasa",
    "ARMOR": "Kulit",
    "CHARM": "Jimat Vitalitas",
    "CONSUMABLE": "Kosong"
}

# ==============================================================================
# LOCAL SEARCH (Boss Adaptive Tuning)
# ==============================================================================
LOCAL_SEARCH_SEED = 42
LOCAL_SEARCH_ALGORITHM = "SA"        # "HC" (Hill Climbing) atau "SA" (Simulated Annealing)
LOCAL_SEARCH_INTERVAL = 3           # Setel bobot setiap 3 giliran boss
LOCAL_SEARCH_SIM_COUNT = 20         # Jumlah simulasi rollouts per evaluasi fitness (resolusi tinggi & cepat)
LOCAL_SEARCH_MAX_TIME_MS = 250.0    # Batas komputasi maksimum per tuning (150-300 ms)
LOCAL_SEARCH_STEP = 1.2             # Step ukuran perturbasi bobot
LOCAL_SEARCH_HC_RESTARTS = 3        # Jumlah random restarts untuk Hill Climbing

# Batas bobot evaluasi Minimax w = (w_hp, w_defend, w_heavy, w_resource)
# Batas diperluas agar ruang pencarian tidak terjepit di batas sempit
BOSS_WEIGHT_BOUNDS = [
    (0.5, 10.0),  # w1: HP diff
    (2.0, 30.0),  # w2: Defend stance
    (4.0, 40.0),  # w3: Heavy attack readiness
    (1.0, 25.0),  # w4: Resource / Potion threat
]
BOSS_DEFAULT_WEIGHTS = (2.0, 8.0, 12.0, 6.0)
BOSS_WEIGHTS_EASY = (1.0, 15.0, 4.0, 2.0)     # Easy: 1-ply greedy + defensif pasif
BOSS_WEIGHTS_NORMAL = (2.0, 8.0, 12.0, 6.0)   # Normal: 3-ply balanced
BOSS_WEIGHTS_HARD = (2.0, 2.0, 32.0, 12.0)    # Hard: 5-ply taktis agresif (anti defensive stalling)

# Batas ketat untuk skenario benchmark CSP
CSP_TIGHT_BUDGET = 6
CSP_TIGHT_WEIGHT = 6

# Parameter Simulated Annealing Tuning
SA_TUNING_T0 = 40.0
SA_TUNING_ALPHA = 0.90
SA_TUNING_MIN_T = 0.2

# Layout Layar Persiapan (1024x768 Fullscreen Opaque)
PREP_TITLE_RECT = (32, 24, 960, 48)
PREP_SUMMARY_RECT = (32, 80, 960, 44)
PREP_SLOT_RECTS = [
    (32, 136, 464, 180),   # Slot 0: WEAPON (kiri atas)
    (528, 136, 464, 180),  # Slot 1: ARMOR (kanan atas)
    (32, 330, 464, 180),   # Slot 2: CHARM (kiri bawah)
    (528, 330, 464, 180),  # Slot 3: CONSUMABLE (kanan bawah)
]
PREP_BUDGET_BAR_RECT = (48, 524, 432, 24)
PREP_WEIGHT_BAR_RECT = (544, 524, 432, 24)
PREP_ACTIONS_RECT = (32, 560, 960, 64)
PREP_F4_PANEL_RECT = (160, 80, 704, 560)  # Modal inspeksi F4 di layar persiapan/battle

# Kompatibilitas lama (bila ada komponen lain yang membaca)
BATTLE_PANEL_RECT = (0, 0, 1024, 768)
BATTLE_SIDE_RECT = (692, 8, 324, 752)

# ==============================================================================
# DEBUG OVERLAY
# ==============================================================================
OVERLAY_LABELS = {
    "path": "F1 PATHFINDING (A*)",
    "csp": "F2 CONSTRAINT SATISFACTION",
    "local": "F3 LOCAL SEARCH (SA)",
    "minimax": "F4 ADVERSARIAL (MINIMAX)",
    "plan": "F5 AUTOMATED PLANNING (STRIPS)",
}

# ---------------------------------------------------------------------------
# Layout panel overlay (semua di dalam area peta 1024x640).
# Setiap panel digambar di dalam kotak semi-transparan supaya tidak menutupi
# tampilan map, dan tidak saling tumpang tindih.
# ---------------------------------------------------------------------------
OVERLAY_CONTROL_RECT = (8, 8, 268, 26)        # indikator CONTROL MODE (kiri atas)
OVERLAY_LEGEND_RECT = (750, 8, 266, 30)       # daftar overlay aktif (kanan atas)
OVERLAY_LOCAL_RECT = (8, 42, 330, 168)        # F3 Local Search (kiri bawah)
OVERLAY_CSP_X = 548                           # F2 CSP (kanan atas, di bawah legenda)
OVERLAY_CSP_W = 470
OVERLAY_CSP_Y = 44
OVERLAY_PLAN_X = 8                            # F5 STRIPS (kiri bawah)
OVERLAY_PLAN_W = 340
OVERLAY_PATH_RECT = (356, 586, 330, 46)       # F1 ringkasan A* (bawah tengah)
OVERLAY_MINIMAX_RECT = (694, 406, 322, 226)   # F4 Minimax (kanan bawah)

# ==============================================================================
# LEVEL - layout dungeon (ruangan simetris + koridor penghubung)
#   '#' dinding  |  '.' lantai  |  'S' spawn hero  |  'C' core (+Boss)
#   'M' monster patroli  |  'o' pilar (dinding dekoratif)
# ==============================================================================
LEVEL = [
    "################################",
    "################################",
    "##.......##############.......##",
    "##.S.....##############.......##",
    "##..........................M.##",
    "##.......#######.######.......##",
    "##.......#######.######.......##",
    "#####.##########.###############",
    "#####.##########.###############",
    "##.....#................#.....##",
    "##.....########..########.....##",
    "##.M..........................##",
    "##.....########.#########.....##",
    "##.......######.#######.......##",
    "##.......######.#######.......##",
    "##............................##",
    "##.......##############.....C.##",
    "##.......##############.......##",
    "################################",
    "################################",
]

LEVEL_SEED_DEFAULT = 20261021     # dipakai untuk RNG patrol monster, dst.

# ==============================================================================
# COLLISION EDITOR (F1)
# ==============================================================================
EDITOR_MODE_OFF = "OFF"
EDITOR_MODE_VIEW = "VIEW"
EDITOR_MODE_EDIT = "EDIT"

# Warna & Alpha Overlay Collision
EDITOR_BLOCKED_BASE_COLOR = (220, 40, 40, 90)        # Merah semi-transparan (data map asli)
EDITOR_BLOCKED_BASE_BORDER = (255, 60, 60, 180)
EDITOR_BLOCKED_OVERRIDE_COLOR = (245, 140, 30, 115)  # Oranye semi-transparan (override manual blocked)
EDITOR_BLOCKED_OVERRIDE_BORDER = (255, 170, 50, 210)
EDITOR_WALKABLE_OVERRIDE_COLOR = (50, 220, 90, 115)  # Hijau semi-transparan (override manual walkable)
EDITOR_WALKABLE_OVERRIDE_BORDER = (80, 255, 120, 210)
EDITOR_WALKABLE_BASE_COLOR = (60, 220, 100, 25)      # Hijau sangat tipis jika diaktifkan

EDITOR_GRID_COLOR = (200, 200, 230, 40)              # Garis grid tile tipis
EDITOR_HOVER_COLOR = (255, 255, 255, 140)            # Highlight kotak di kursor
EDITOR_SELECT_BOX_COLOR = (60, 170, 255, 95)         # Kotak area Shift+drag
EDITOR_SELECT_BOX_BORDER = (90, 200, 255, 220)

EDITOR_BRUSH_SIZES = [1, 2, 3]                       # Ukuran kuas (1x1, 2x2, 3x3)
EDITOR_MAX_UNDO = 100                                # Batas riwayat Undo/Redo
EDITOR_CAMERA_SPEED = 650.0                          # Kecepatan geser kamera bebas (px/dtk)

# ==============================================================================
# DEKORASI DESA SUNNYSIDE (KINCIR ANGIN & ASAP CEROBONG)
# ==============================================================================
# Menara Kincir Angin (Bangunan tinggi kayu beratap merah di dekat sungai & jembatan utara)
WINDMILL_TOWER_RECT = (1280, 448, 96, 192)       # (x, y, w, h) Bounding box menara di peta HD (gx=40..42, gy=14..19)
WINDMILL_HUB_POS = (1328, 526)                   # (x, y) Titik poros / hub bilah kincir angin di puncak menara
WINDMILL_SORT_Y = 448.0                          # Y-sorting atap menara agar hero di samping/depan menara tidak tertutup bilah
WINDMILL_SCALE = 2                               # Skala bilah 2x mencocokkan densitas piksel dunia HD
WINDMILL_FPS = 8.0                               # Kecepatan putaran bilah kincir

# Zona Aman Desa Sunnyside (Village Safe Zone: area permukiman, toko, dan ladang)
# Musuh/Goblin dilarang berkeliaran, mengejar, atau spawn di dalam zona aman ini
VILLAGE_SAFE_ZONE_RECT = (800, 420, 1150, 700)   # (x, y, w, h) melingkupi seluruh desa damai
WORLD_GOBLINS_ACTIVE = False                     # Dinonaktifkan di dunia petualangan desa (audit: patroli musuh ditunda)

# Titik Keluar Asap Cerobong Desa (Ujung Atas Cerobong Rumah yang Memiliki Cerobong Nyata)
# Disimpan dalam koordinat dunia HD (2x). Hanya rumah yang benar-benar memiliki cerobong.
CHIMNEY_ANCHORS = [
    (948, 142),    # North Farm House (building_28_2)
    (1742, 230),   # North-East Manor (building_50_6)
    (1070, 614),   # Central-West Village House (building_32_19)
    (1388, 812),   # Village House near River (building_39_24)
    (1774, 838),   # Village Central Manor (building_50_20)
    (1900, 1036),  # East Village House (building_55_31)
    (814, 1070),   # South-West Farm House (building_17_33)
]

# ==============================================================================
# SISTEM GAME MINIMAL FASE 1A: INTERAKSI DUNIA & LOKASI
# ==============================================================================
STARTING_COINS = 20                       # Koin awal hero (Game Baru)
INTERACT_SHOP_POS = (1600, 944)           # Toko desa (Alun-alun pasar)
INTERACT_WORKSHOP_POS = (1712, 944)       # Meja bengkel / anvil crafting (Potion & Kunci)
INTERACT_BED_POS = (1344, 960)            # Ranjang istirahat hero di rumah warga
INTERACT_FARM_POS = (528, 448)            # Ladang pertanian luas barat laut
FARM_BASE_STAGE_DURATION = 5.0            # Detik per tahap pertumbuhan tanaman (5 tahap = 25s unwatered, 12.5s watered)

INTERACT_GATE_POS = (2384, 880)           # Posisi berdiri depan Gerbang Besi koridor chokepoint
INTERACT_CHICKEN_POS = (1344, 992)        # Kandang ayam desa (Telur, samping ayam riil di alun-alun)
INTERACT_COW_POS = (704, 480)              # Padang rumput sapi perah (Susu, samping sapi riil barat laut)
INTERACT_FISHING_POS = (1424, 688)        # Dermaga kayu pancingan sungai (Ikan)
INTERACT_TREE_POS = (1488, 592)           # Pohon tebang desa (Kayu)
INTERACT_ROCK_POS = (1904, 656)           # Vena tambang tebing (Batu)
INTERACTION_RADIUS = 52.0                 # Jarak deteksi interaksi tombol [E]

# Kamus Lokasi Terverifikasi A* Reachable untuk Automated Expedition Planner
LOCATIONS = {
    "spawn": (1440, 1056),
    "shop": INTERACT_SHOP_POS,
    "workshop": INTERACT_WORKSHOP_POS,
    "bed": INTERACT_BED_POS,
    "farm": INTERACT_FARM_POS,
    "gate": INTERACT_GATE_POS,
    "chicken_coop": INTERACT_CHICKEN_POS,
    "cow_pasture": INTERACT_COW_POS,
    "river_fishing": INTERACT_FISHING_POS,
    "forest_wood": INTERACT_TREE_POS,
    "quarry_rock": INTERACT_ROCK_POS,
    "boss": BOSS_POS,
}

