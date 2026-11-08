"""
worldgen.py - Generator dunia OPEN WORLD untuk "AI LABYRINTH".

Dunia tidak lagi berupa satu ruangan labirin 32x20. Generator ini menyusun
peta 96x72 tile (sekitar 9 layar) yang memiliki:

    * padang rumput, hutan, perbukitan batu, sungai, dan danau,
    * jalan tanah yang menghubungkan desa dengan reruntuhan Core,
    * Desa Meadowbrook (spawn) + rumah, sumur, pagar, dan lentera,
    * Reruntuhan Obsidian Keep (Core & Boss) dengan gerbang, pilar, brazier,
    * dekorasi runtime: pohon, batu, semak, bunga, alang-alang, lili air,
    * titik patroli monster yang tersebar di seluruh wilayah.

Modul ini HANYA menghasilkan data (grid + daftar prop). Semua penggambaran
ada di core/world_art.py dan core/map.py. Pembangkitan bersifat deterministik
terhadap `seed`, sehingga tombol [R] mengulang dunia yang sama sedangkan [N]
membuat dunia baru.
"""

from __future__ import annotations

import json
import math
import os
import random
from dataclasses import dataclass, field

import pygame

import config


# ==============================================================================
# JENIS TERRAIN
# ==============================================================================
T_GRASS = "grass"
T_MEADOW = "meadow"
T_FOREST = "forest_floor"
T_DIRT = "dirt"
T_PATH = "path"
T_SAND = "sand"
T_STONE = "stone"
T_DUNGEON = "dungeon"
T_WATER = "water"
T_DEEP = "deep_water"
T_BRIDGE = "bridge"
T_CLIFF = "cliff"
T_WALL = "wall"

WATER_KINDS = {T_WATER, T_DEEP}
HARD_KINDS = {T_WATER, T_DEEP, T_CLIFF, T_WALL}


# ==============================================================================
# STRUKTUR DATA
# ==============================================================================
@dataclass
class PropData:
    """Satu objek tinggi yang ikut di-sort bersama Hero/monster (y-sort)."""
    kind: str
    gx: int
    gy: int
    variant: int = 0
    w: int = 1
    h: int = 1
    solid: bool = False
    base_y: int | None = None

    @property
    def cell(self):
        return (self.gx, self.gy)


@dataclass
class Zone:
    name: str
    subtitle: str
    x: int
    y: int
    radius: int
    color: tuple


@dataclass
class WorldData:
    width: int
    height: int
    terrain: list                 # list[list[str]]
    solid: list                   # list[list[bool]]
    spawn: tuple
    core: tuple
    monster_spawns: list
    props: list = field(default_factory=list)       # list[PropData]
    houses: list = field(default_factory=list)      # list[PropData]
    animals: list = field(default_factory=list)     # list[tuple[str, int, int, int]]
    road: set = field(default_factory=set)
    water: set = field(default_factory=set)
    bridge: set = field(default_factory=set)
    zones: list = field(default_factory=list)
    village_rect: tuple = (0, 0, 1, 1)
    ruin_rect: tuple = (0, 0, 1, 1)
    world_name: str = "ELDORIA"

    def zone_at(self, x, y):
        best, best_score = None, 10 ** 9
        for z in self.zones:
            d = math.hypot(x - z.x, y - z.y)
            score = d - z.radius * 0.35
            if d <= z.radius and score < best_score:
                best, best_score = z, score
        return best


# ==============================================================================
# NOISE
# ==============================================================================
def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def _value_noise(rng, width, height, cell):
    """Value noise halus dengan interpolasi smoothstep."""
    gw = width // cell + 3
    gh = height // cell + 3
    lattice = [[rng.random() for _ in range(gw)] for _ in range(gh)]
    out = [[0.0] * width for _ in range(height)]
    for y in range(height):
        gy = y / cell
        y0 = int(gy)
        ty = _smooth(gy - y0)
        for x in range(width):
            gx = x / cell
            x0 = int(gx)
            tx = _smooth(gx - x0)
            v00 = lattice[y0][x0]
            v10 = lattice[y0][x0 + 1]
            v01 = lattice[y0 + 1][x0]
            v11 = lattice[y0 + 1][x0 + 1]
            a = v00 + (v10 - v00) * tx
            b = v01 + (v11 - v01) * tx
            out[y][x] = a + (b - a) * ty
    return out


def _fbm(seed, width, height, base_cell, octaves=3):
    out = [[0.0] * width for _ in range(height)]
    total = 0.0
    amp = 0.58
    cell = base_cell
    for _ in range(octaves):
        rng = random.Random(seed)
        layer = _value_noise(rng, width, height, max(3, cell))
        for y in range(height):
            row, lrow = out[y], layer[y]
            for x in range(width):
                row[x] += lrow[x] * amp
        total += amp
        amp *= 0.52
        cell = max(3, cell // 2)
        seed = seed * 1103515245 + 12345
    for y in range(height):
        row = out[y]
        for x in range(width):
            row[x] /= total
    return out


# ==============================================================================
# UTILITAS GRID
# ==============================================================================
def _inside(w, h, x, y):
    return 0 <= x < w and 0 <= y < h


def _stamp_rect(terrain, solid, x0, y0, x1, y1, kind, is_solid=False):
    h, w = len(terrain), len(terrain[0])
    for y in range(max(0, y0), min(h, y1 + 1)):
        for x in range(max(0, x0), min(w, x1 + 1)):
            terrain[y][x] = kind
            solid[y][x] = is_solid


def _stamp_circle(terrain, solid, cx, cy, radius, kind, is_solid=False):
    h, w = len(terrain), len(terrain[0])
    for y in range(max(0, cy - radius), min(h, cy + radius + 1)):
        for x in range(max(0, cx - radius), min(w, cx + radius + 1)):
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius + radius * 0.6:
                terrain[y][x] = kind
                solid[y][x] = is_solid


def _line_points(a, b):
    """Bresenham + langkah kecil -> daftar titik antara dua koordinat tile."""
    x0, y0 = a
    x1, y1 = b
    dx, dy = x1 - x0, y1 - y0
    steps = max(abs(dx), abs(dy), 1)
    pts = []
    for i in range(steps + 1):
        t = i / steps
        pts.append((round(x0 + dx * t), round(y0 + dy * t)))
    return pts


def _rect_contains(rect, x, y):
    rx, ry, rw, rh = rect
    return rx <= x < rx + rw and ry <= y < ry + rh


# ==============================================================================
# GENERATOR UTAMA
# ==============================================================================
def generate_world(seed=config.LEVEL_SEED_DEFAULT) -> WorldData:
    """Bangun data dunia yang disinkronkan dengan peta pulau GameMap."""
    from world.game_map import GameMap

    gm = GameMap()
    tile_size = config.TILE_SIZE
    W = gm.width // tile_size
    H = gm.height // tile_size

    # Evaluasi solid grid dari GameMap
    solid = [[False for _ in range(W)] for _ in range(H)]
    terrain = [[T_GRASS for _ in range(W)] for _ in range(H)]
    water = set()
    road = set()
    bridge = set()

    # Identifikasi jembatan
    s = gm.scale
    for br in gm.bridge_rects:
        gx0, gy0 = br.left // tile_size, br.top // tile_size
        gx1, gy1 = (br.right - 1) // tile_size, (br.bottom - 1) // tile_size
        for gy in range(max(0, gy0), min(H, gy1 + 1)):
            for gx in range(max(0, gx0), min(W, gx1 + 1)):
                bridge.add((gx, gy))

    for gy in range(H):
        for gx in range(W):
            rect = pygame.Rect(gx * tile_size + 8, gy * tile_size + 8, 16, 16)
            is_sol = gm.is_solid(rect)
            solid[gy][gx] = is_sol
            if (gx, gy) in bridge:
                terrain[gy][gx] = T_BRIDGE
                solid[gy][gx] = False
            elif is_sol:
                terrain[gy][gx] = T_WATER
                water.add((gx, gy))
            else:
                terrain[gy][gx] = T_GRASS

    # Spawn di jalan tanah tengah pulau
    spawn = (int(gm.spawn_x // tile_size), int(gm.spawn_y // tile_size))
    if 0 <= spawn[1] < H and 0 <= spawn[0] < W:
        solid[spawn[1]][spawn[0]] = False
        terrain[spawn[1]][spawn[0]] = T_PATH
        road.add(spawn)

    # Core di area terbuka dekat pemukiman
    core = (min(W - 2, spawn[0] + 6), max(1, spawn[1] - 4))
    if 0 <= core[1] < H and 0 <= core[0] < W:
        solid[core[1]][core[0]] = False
        terrain[core[1]][core[0]] = T_STONE

    # Spawns monster di sel lantai terbuka
    floor_cells = [(x, y) for y in range(H) for x in range(W) if not solid[y][x] and (x, y) != spawn]
    rng = random.Random((seed * 2654435761) & 0x7FFFFFFF)
    monster_spawns = rng.sample(floor_cells, min(4, len(floor_cells))) if floor_cells else []

    props = []
    houses = []
    zones = [
        Zone(name="PULAU SUNNYSIDE", subtitle="Area Terbuka",
             x=spawn[0], y=spawn[1], radius=15, color=config.CYAN)
    ]

    animals_list = []
    map_json_p = os.path.join(config.ASSETS_DIR, "maps", "sunnyside_isle.json")
    if os.path.isfile(map_json_p):
        try:
            with open(map_json_p, "r", encoding="utf-8") as f:
                d = json.load(f)
                animals_list = d.get("animals", [])
        except Exception:
            pass

    return WorldData(
        width=W, height=H, terrain=terrain, solid=solid,
        spawn=spawn, core=core, monster_spawns=monster_spawns,
        props=props, houses=houses, animals=animals_list, road=road,
        water=water, bridge=bridge, zones=zones,
        village_rect=(spawn[0] - 8, spawn[1] - 8, 16, 16),
        ruin_rect=(core[0] - 4, core[1] - 4, 8, 8),
        world_name="SUNNYSIDE ISLE",
    )

    elev = _fbm(seed ^ 0xA53C9E1, W, H, base_cell=20, octaves=4)
    moist = _fbm(seed ^ 0x17B4D2, W, H, base_cell=14, octaves=3)
    forest = _fbm(seed ^ 0x51F0AA, W, H, base_cell=10, octaves=3)

    terrain = [[T_GRASS for _ in range(W)] for _ in range(H)]
    solid = [[False for _ in range(W)] for _ in range(H)]

    # ---------- 1. BIOMA DASAR -------------------------------------------
    for y in range(H):
        for x in range(W):
            e = elev[y][x]
            m = moist[y][x]
            # tepi dunia = tebing batu (dinding alami)
            if x < 2 or y < 2 or x >= W - 2 or y >= H - 2:
                terrain[y][x] = T_CLIFF
                solid[y][x] = True
            elif e < 0.255:
                terrain[y][x] = T_DEEP
                solid[y][x] = True
            elif e < 0.322:
                terrain[y][x] = T_WATER
                solid[y][x] = True
            elif e < 0.365:
                terrain[y][x] = T_SAND
            elif e > 0.775:
                terrain[y][x] = T_STONE
            elif m > 0.615 and e < 0.66:
                terrain[y][x] = T_FOREST
            elif m > 0.50:
                terrain[y][x] = T_GRASS
            else:
                terrain[y][x] = T_MEADOW

    # ---------- 2. SUNGAI + DANAU ----------------------------------------
    river_x = W * 0.53
    for y in range(3, H - 3):
        cx = int(river_x + math.sin(y * 0.145) * 6.0 + math.sin(y * 0.047 + 1.3) * 3.5)
        half = 1 + (1 if 20 < y < 42 else 0)
        for dx in range(-half - 1, half + 2):
            x = cx + dx
            if not _inside(W, H, x, y):
                continue
            if abs(dx) <= half:
                terrain[y][x] = T_DEEP if abs(dx) == 0 else T_WATER
                solid[y][x] = True
            elif terrain[y][x] not in (T_CLIFF, T_WALL):
                terrain[y][x] = T_SAND
                solid[y][x] = False

    # danau kristal di tenggara
    lake = (70, 57, 8)
    for y in range(lake[1] - lake[2], lake[1] + lake[2] + 1):
        for x in range(lake[0] - lake[2] - 2, lake[0] + lake[2] + 3):
            if not _inside(W, H, x, y):
                continue
            d = math.hypot((x - lake[0]) * 0.85, y - lake[1])
            if d <= lake[2]:
                terrain[y][x] = T_DEEP if d < lake[2] - 2 else T_WATER
                solid[y][x] = True
            elif d <= lake[2] + 1.6:
                terrain[y][x] = T_SAND
                solid[y][x] = False

    # danau kecil di barat laut
    for y in range(10, 22):
        for x in range(22, 33):
            d = math.hypot((x - 27) * 0.9, y - 16)
            if d <= 4.2:
                terrain[y][x] = T_WATER if d > 2.1 else T_DEEP
                solid[y][x] = True
            elif d <= 5.4:
                terrain[y][x] = T_SAND
                solid[y][x] = False

    # ---------- 3. LOKASI PENTING ----------------------------------------
    spawn = (14, 51)
    core = (82, 14)
    village_rect = (4, 40, 42, 22)          # x,y,w,h (diperluas ke barat & timur)
    ruin_rect = (71, 4, 22, 23)

    # ---------- 4. JALAN DARI DESA KE CORE -------------------------------
    waypoints = [
        spawn,
        (20, 52),
        (27, 47),
        (32, 41),
        (38, 39),
        (45, 38),
        (51, 35),
        (58, 31),
        (65, 27),
        (71, 24),
        (78, 23),
        (82, 25),
    ]
    road = set()
    for a, b in zip(waypoints, waypoints[1:]):
        for (x, y) in _line_points(a, b):
            # jalan selebar 2 tile (bukan 3) supaya terasa seperti jalur
            # setapak yang menyatu dengan alam, bukan blok raksasa.
            for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                nx, ny = x + dx, y + dy
                if not _inside(W, H, nx, ny):
                    continue
                if terrain[ny][nx] in (T_CLIFF, T_WALL):
                    continue
                if terrain[ny][nx] in WATER_KINDS:
                    terrain[ny][nx] = T_BRIDGE
                    solid[ny][nx] = False
                else:
                    terrain[ny][nx] = T_PATH
                    solid[ny][nx] = False
                road.add((nx, ny))

    # jalan batu di dalam reruntuhan
    for (x, y) in _line_points((82, 25), (82, 15)) + _line_points((82, 15), (72, 15)):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if _inside(W, H, nx, ny) and _rect_contains(ruin_rect, nx, ny):
                    terrain[ny][nx] = T_DUNGEON if (nx + ny) % 7 else T_STONE
                    solid[ny][nx] = False

    # ---------- 5. DESA MEADOWBROOK --------------------------------------
    vx, vy, vw, vh = village_rect
    _stamp_rect(terrain, solid, vx, vy, vx + vw - 1, vy + vh - 1, T_MEADOW)
    # area spawn selalu lapang
    _stamp_circle(terrain, solid, spawn[0], spawn[1], 4, T_MEADOW)
    # Jalan utama desa: horisontal (barat-timur) dan vertikal (utara-selatan)
    for a, b in [((5, 50), (44, 50)), ((14, 42), (14, 61)), ((28, 44), (28, 61)),
                 ((5, 56), (44, 56)), ((14, 44), (44, 44))]:
        for (x, y) in _line_points(a, b):
            for dx, dy in ((0, 0), (1, 0), (0, 1)):
                nx, ny = x + dx, y + dy
                if _inside(W, H, nx, ny) and terrain[ny][nx] not in (T_CLIFF, T_WALL) + tuple(WATER_KINDS):
                    # Jangan menimpa badan rumah utama yang solid
                    if solid[ny][nx] and any(hp.gx <= nx < hp.gx + hp.w and hp.gy <= ny < hp.gy + hp.h for hp in houses):
                        continue
                    terrain[ny][nx] = T_PATH
                    solid[ny][nx] = False
                    road.add((nx, ny))

    # ---------- 6. RERUNTUHAN OBSIDIAN KEEP ------------------------------
    rx, ry, rw, rh = ruin_rect
    _stamp_rect(terrain, solid, rx, ry, rx + rw - 1, ry + rh - 1, T_DUNGEON)
    # tembok luar dengan gerbang selatan dan barat
    for x in range(rx, rx + rw):
        if _inside(W, H, x, ry):
            terrain[ry][x] = T_WALL
            solid[ry][x] = True
        if _inside(W, H, x, ry + rh - 1):
            terrain[ry + rh - 1][x] = T_WALL
            solid[ry + rh - 1][x] = True
    for y in range(ry, ry + rh):
        if _inside(W, H, rx, y):
            terrain[y][rx] = T_WALL
            solid[y][rx] = True
        if _inside(W, H, rx + rw - 1, y):
            terrain[y][rx + rw - 1] = T_WALL
            solid[y][rx + rw - 1] = True
    # gerbang selatan (3 tile) dan gerbang barat (2 tile)
    for x in range(core[0] - 1, core[0] + 2):
        if _inside(W, H, x, ry + rh - 1):
            terrain[ry + rh - 1][x] = T_DUNGEON
            solid[ry + rh - 1][x] = False
    for y in range(core[1] + 1, core[1] + 3):
        if _inside(W, H, rx, y):
            terrain[y][rx] = T_DUNGEON
            solid[y][rx] = False
    # koridor & pelataran dalam
    _stamp_rect(terrain, solid, rx + 2, ry + 2, rx + rw - 3, ry + rh - 3, T_DUNGEON)
    for (x, y) in _line_points((core[0], ry + rh - 1), (core[0], core[1])):
        for dx in (-1, 0, 1):
            if _inside(W, H, x + dx, y):
                terrain[y][x + dx] = T_DUNGEON if (x + y) % 6 else T_STONE
                solid[y][x + dx] = False
    for (x, y) in _line_points((rx, core[1] + 1), (core[0] - 2, core[1] + 1)):
        if _inside(W, H, x, y):
            terrain[y][x] = T_DUNGEON if (x + y) % 6 else T_STONE
            solid[y][x] = False
    # pelataran Core
    _stamp_circle(terrain, solid, core[0], core[1], 3, T_STONE)
    if _inside(W, H, core[0], core[1]):
        terrain[core[1]][core[0]] = T_DUNGEON
        solid[core[1]][core[0]] = False
    # pecahan tembok dalam (atmosfer reruntuhan)
    for (x, y) in [(76, 8), (77, 8), (88, 8), (89, 8),
                   (76, 20), (77, 20), (88, 20), (89, 20),
                   (76, 12), (90, 16), (78, 22), (88, 22)]:
        if _inside(W, H, x, y) and _rect_contains(ruin_rect, x, y) and (x, y) != core:
            terrain[y][x] = T_WALL
            solid[y][x] = True

    houses = []
    props = []

    # ---------- 7. RUMAH SUNNYSIDE, KINCIR, DAN DEKORASI DESA ------------
    # Penempatan rumah di baris-baris yang berbeda agar jalan desa tetap terbaca.
    # solid_tiles: daftar (dx, dy) relatif dari (hx, hy) yang diblokir player.
    # Kolom BARAT (baris atas - jalan utara y=44)
    # Kolom TIMUR (baris atas + baru y=44)
    houses_def = [
        # kind,         hx, hy,  w,  h,  solid_cols_range, solid_rows_range
        ("house_blue",   5, 41,   6,  6,  (0, 5),  (3, 5)),   # Pondok biru, kiri atas desa
        ("house_red",   15, 41,   6,  5,  (0, 5),  (2, 4)),   # Rumah merah, tengah atas
        ("house_cabin", 25, 41,   5,  5,  (0, 4),  (2, 4)),   # Kabin, kanan atas
        ("house_forge", 33, 41,   6,  5,  (0, 5),  (2, 4)),   # Pandai besi, timur atas
        ("house_barn",   5, 52,   7,  4,  (0, 6),  (1, 3)),   # Lumbung, barat bawah
        ("house_manor", 17, 52,   7,  5,  (0, 6),  (2, 4)),   # Manor bertingkat, tengah bawah
    ]

    def _place_house(kind, hx, hy, hw, hh, solid_x_range, solid_y_range):
        """Pasang rumah dengan solid footprint tepat (tidak termasuk teras)."""
        base_y = (hy + solid_y_range[1]) * config.TILE_SIZE
        hp = PropData(kind, hx, hy, 0, w=hw, h=hh, solid=True, base_y=base_y)
        # Mark solid tiles untuk badan utama rumah saja (bukan seluruh bbox)
        sx0, sx1 = hx + solid_x_range[0], hx + solid_x_range[1]
        sy0, sy1 = hy + solid_y_range[0], hy + solid_y_range[1]
        _stamp_rect(terrain, solid, sx0, sy0, sx1 - 1, sy1 - 1, T_DIRT, is_solid=True)
        # Area teras/halaman di sekitar rumah (tidak solid, tapi jadi dirt)
        _stamp_rect(terrain, solid, hx, hy, hx + hw - 1, hy + hh - 1, T_DIRT, is_solid=False)
        # Tandai badan rumah solid kembali
        _stamp_rect(terrain, solid, sx0, sy0, sx1 - 1, sy1 - 1, T_DIRT, is_solid=True)
        houses.append(hp)
        props.append(hp)

    for kind, hx, hy, hw, hh, sx_range, sy_range in houses_def:
        _place_house(kind, hx, hy, hw, hh, sx_range, sy_range)

    # Kincir angin Sunnyside besar (ikonik desa, ditempatkan di area terbuka tanpa memotong jalan)
    windmill_p = PropData("windmill", 39, 45, 0, w=5, h=4, solid=True,
                          base_y=49 * config.TILE_SIZE)
    _stamp_rect(terrain, solid, 40, 46, 42, 48, T_DIRT, is_solid=True)
    _stamp_rect(terrain, solid, 39, 45, 43, 48, T_DIRT, is_solid=False)
    props.append(windmill_p)

    # Patung kesatria batu di alun-alun desa
    props.append(PropData("statue", 13, 47, 0, w=2, h=2, solid=True,
                          base_y=49 * config.TILE_SIZE))
    solid[48][13] = True; solid[48][14] = True
    solid[47][13] = True; solid[47][14] = True

    # Sumur, api unggun, anvil pandai besi, tong, peti
    props.append(PropData("well", 24, 47, 0, solid=True))
    solid[47][24] = True; solid[48][24] = True
    props.append(PropData("campfire", 15, 54, 0, solid=False))
    props.append(PropData("anvil", 36, 48, 0, solid=True))
    solid[48][36] = True
    props.append(PropData("log", 16, 54, 0, solid=False))
    props.append(PropData("tree_stump", 17, 54, 0, solid=False))

    # Dekorasi desa (lentera, papan, peti, tong, papan nama)
    for kind, gx, gy, variant in [
        ("sign",   14, 49, 0),
        ("sign",   28, 49, 0),
        ("crate",  37, 47, 0),
        ("barrel", 38, 47, 0),
        ("lantern", 12, 49, 0), ("lantern", 16, 49, 0),
        ("lantern", 26, 49, 0), ("lantern", 30, 49, 0),
        ("lantern", 12, 55, 0), ("lantern", 26, 55, 0),
        # Pagar di sepanjang jalan utama dan kandang
        ("fence",  5, 49, 0), ("fence", 5, 50, 0), ("fence", 5, 51, 0),
        ("fence", 15, 49, 1), ("fence", 15, 50, 1),
        ("fence", 29, 49, 0), ("fence", 29, 50, 0),
        ("mushroom", 34, 53, 1), ("mushroom", 6, 48, 0),
    ]:
        solid_cell = kind in ("sign", "crate", "barrel")
        if _inside(W, H, gx, gy) and not (solid_cell and solid[gy][gx]):
            p = PropData(kind, gx, gy, variant, solid=solid_cell)
            props.append(p)
            if solid_cell:
                solid[gy][gx] = True

    # Pohon apel di kebun buah desa (baris pohon)
    for ax, ay, av in [(10, 48, 0), (11, 48, 1), (36, 53, 2),
                       (37, 53, 0), (38, 53, 1)]:
        if _inside(W, H, ax, ay) and not solid[ay][ax]:
            props.append(PropData("tree_apple", ax, ay, av, solid=True))
            solid[ay][ax] = True

    # ---------- 7b. LADANG DESA BESAR (kebun sayur + bunga) --------------
    farm_rect = (29, 52, 10, 7)
    fx, fy, fw, fh = farm_rect
    _stamp_rect(terrain, solid, fx, fy, fx + fw - 1, fy + fh - 1, T_DIRT)
    for x in range(fx - 1, fx + fw + 1):
        props.append(PropData("fence", x, fy - 1, x % 2))
        props.append(PropData("fence", x, fy + fh, (x + 1) % 2))
    for y in range(fy, fy + fh):
        props.append(PropData("fence", fx + fw, y, 0))
        props.append(PropData("fence", fx - 1, y, 1))
    crop_rows = (
        (fy + 1, ["wheat", "wheat", "cabbage"]),
        (fy + 2, ["carrot", "pumpkin", "carrot"]),
        (fy + 3, ["sunflower", "sunflower", "wheat"]),
        (fy + 4, ["cabbage", "carrot", "pumpkin"]),
        (fy + 5, ["wheat", "cabbage", "wheat"]),
    )
    for (crow, kinds) in crop_rows:
        for x in range(fx, fx + fw):
            name = kinds[(x - fx) % len(kinds)]
            if not solid[crow][x]:
                props.append(PropData(f"crop_{name}", x, crow, (x + crow) % 4))
    props.append(PropData("crate", fx + fw - 1, fy, 0))
    if not solid[fy][fx + fw - 1]:
        solid[fy][fx + fw - 1] = True

    # Ladang kedua (barat daya, lebih kecil)
    farm2_rect = (5, 59, 9, 5)
    f2x, f2y, f2w, f2h = farm2_rect
    _stamp_rect(terrain, solid, f2x, f2y, f2x + f2w - 1, f2y + f2h - 1, T_DIRT)
    for x in range(f2x - 1, f2x + f2w + 1):
        props.append(PropData("fence", x, f2y - 1, x % 2))
        props.append(PropData("fence", x, f2y + f2h, (x + 1) % 2))
    for y in range(f2y, f2y + f2h):
        props.append(PropData("fence", f2x + f2w, y, 0))
        props.append(PropData("fence", f2x - 1, y, 1))
    for crow in (f2y + 1, f2y + 3):
        for x in range(f2x, f2x + f2w):
            name = ["pumpkin", "sunflower", "wheat"][(x - f2x) % 3]
            if not solid[crow][x]:
                props.append(PropData(f"crop_{name}", x, crow, (x + crow) % 4))

    # ---------- 7c. KANDANG & HEWAN DINAMIS (AI Jelajah Bebas) ----------
    pen_rect = (20, 58, 8, 5)
    px_, py_, pw_, ph_ = pen_rect
    _stamp_rect(terrain, solid, px_, py_, px_ + pw_ - 1, py_ + ph_ - 1, T_MEADOW)
    for x in range(px_, px_ + pw_):
        if x not in (px_ + 3, px_ + 4):          # celah gerbang
            props.append(PropData("fence", x, py_ - 1, x % 2))
        props.append(PropData("fence", x, py_ + ph_, (x + 1) % 2))
    for y in range(py_, py_ + ph_):
        props.append(PropData("fence", px_ - 1, y, 0))
        props.append(PropData("fence", px_ + pw_, y, 1))

    # Palung air di dalam kandang
    props.append(PropData("trough", px_ + 1, py_ + 3, 0, solid=False))

    animals = [
        # Hewan di kandang peternakan (radius jelajah 2-3 petak)
        ("cow",     px_ + 1, py_ + 1, 2),
        ("cow",     px_ + 5, py_ + 1, 2),
        ("sheep",   px_ + 3, py_ + 1, 2),
        ("pig",     px_ + 2, py_ + 2, 3),
        ("chicken", px_ + 5, py_ + 2, 2),
        ("chicken", px_ + 1, py_ + 2, 2),
        ("chicken", px_ + 3, py_ + 3, 2),
        # Hewan bebas di padang rumput desa (radius jelajah 4-6 petak)
        ("cow",     12, 56, 5),
        ("sheep",   10, 53, 4),
        ("sheep",   16, 57, 4),
        ("pig",     40, 44, 4),
        ("chicken", 38, 53, 5),
        ("chicken", 42, 47, 4),
        ("chicken", 8,  60, 5),
        ("chicken", 11, 60, 4),
        # Bebek berenang di air danau & sungai (bebek bisa berenang!)
        ("duck", 68, 56, 5),
        ("duck", 71, 58, 4),
        ("duck", 73, 54, 4),
        ("duck", 26, 17, 4),
        ("duck", 28, 15, 3),
    ]

    # Dermaga kayu & beberapa perahu di danau kristal & danau barat laut
    for px, py in [(65, 54), (66, 54), (67, 54), (68, 54)]:
        terrain[py][px] = T_BRIDGE
        solid[py][px] = False
    for px, py in [(65, 57), (65, 58), (66, 58)]:
        terrain[py][px] = T_BRIDGE
        solid[py][px] = False
    props.append(PropData("boat", 69, 55, 0, w=2, h=2, solid=False))
    props.append(PropData("boat", 71, 61, 0, w=2, h=2, solid=False))
    props.append(PropData("boat", 25, 18, 0, w=2, h=2, solid=False))

    # Jembatan kayu kecil + gardu jaga di tepi desa
    for px, py in [(4, 56), (5, 56)]:
        if _inside(W, H, px, py):
            terrain[py][px] = T_PATH
            road.add((px, py))

    # Pos penjaga utara desa
    props.append(PropData("sign", 14, 41, 1, solid=True))
    if not solid[41][14]:
        solid[41][14] = True

    # Pohon apel tambahan di timur desa
    for ax, ay, av in [(43, 45, 2), (44, 46, 0), (43, 47, 3)]:
        if _inside(W, H, ax, ay) and not solid[ay][ax]:
            props.append(PropData("tree_apple", ax, ay, av, solid=True))
            solid[ay][ax] = True


    # ---------- 8. DEKORASI RERUNTUHAN -----------------------------------
    for (gx, gy) in [(74, 7), (89, 7), (74, 18), (89, 18),
                     (76, 10), (88, 10), (76, 18), (88, 18)]:
        if _rect_contains(ruin_rect, gx, gy):
            props.append(PropData("pillar", gx, gy, rng.randrange(3), solid=True))
            solid[gy][gx] = True
    for (gx, gy) in [(79, 22), (85, 22), (80, 9), (84, 9)]:
        if _rect_contains(ruin_rect, gx, gy):
            if solid[gy][gx]:
                continue
            props.append(PropData("brazier", gx, gy, rng.randrange(2), solid=True))
            solid[gy][gx] = True
    # batu puing
    for _ in range(16):
        gx = rng.randint(rx + 2, rx + rw - 3)
        gy = rng.randint(ry + 2, ry + rh - 3)
        if solid[gy][gx] or (gx, gy) == core:
            continue
        props.append(PropData("rubble", gx, gy, rng.randrange(3)))
    # gapura batu di gerbang selatan
    for gx in (core[0] - 2, core[0] + 2):
        if solid[ry + rh - 1][gx]:
            continue
        props.append(PropData("gate", gx, ry + rh - 1, 0, solid=False))

    # ---------- 9. POHON, BATU, SEMAK ------------------------------------
    # 460 pohon: cukup rimbun untuk hutan, tetapi jalan tetap terbaca.
    tree_target = 460
    attempts = 0
    while len([p for p in props if p.kind in ("tree", "pine", "birch")]) < tree_target \
            and attempts < 9000:
        attempts += 1
        x = rng.randrange(3, W - 3)
        y = rng.randrange(3, H - 3)
        if solid[y][x]:
            continue
        kind = terrain[y][x]
        if kind not in (T_GRASS, T_MEADOW, T_FOREST, T_STONE):
            continue
        if (x, y) in road:
            continue
        if (_rect_contains(village_rect, x, y) or _rect_contains(ruin_rect, x, y)
                or _rect_contains(farm_rect, x, y) or _rect_contains(pen_rect, x, y)):
            continue
        if math.hypot(x - spawn[0], y - spawn[1]) < 10:
            continue
        if math.hypot(x - core[0], y - core[1]) < 15:
            continue
        # jarak ke jalan
        if any((x + dx, y + dy) in road for dx in (-2, -1, 0, 1, 2)
               for dy in (-2, -1, 0, 1, 2)):
            continue
        f = forest[y][x]
        if kind == T_MEADOW:
            f -= 0.10
        if kind == T_STONE:
            f -= 0.16
        if rng.random() > max(0.0, (f - 0.34) * 1.9):
            continue
        species = "tree"
        if kind == T_FOREST and moist[y][x] > 0.66:
            species = "pine"
        elif moist[y][x] < 0.47:
            species = "birch"
        variant = rng.randrange(4)
        props.append(PropData(species, x, y, variant, solid=True))
        solid[y][x] = True

    # kluster hutan tambahan agar wilayah HUTAN WHISPERWOOD terasa rimbun
    for (fcx, fcy, frad) in [(28, 20, 8), (46, 54, 8), (64, 45, 7)]:
        for y in range(fcy - frad, fcy + frad + 1):
            for x in range(fcx - frad, fcx + frad + 1):
                if not _inside(W, H, x, y) or solid[y][x]:
                    continue
                if (x - fcx) ** 2 + (y - fcy) ** 2 > frad * frad:
                    continue
                if terrain[y][x] not in (T_GRASS, T_MEADOW, T_FOREST):
                    continue
                if (x, y) in road:
                    continue
                if (_rect_contains(village_rect, x, y) or _rect_contains(ruin_rect, x, y)
                        or _rect_contains(farm_rect, x, y) or _rect_contains(pen_rect, x, y)):
                    continue
                if math.hypot(x - spawn[0], y - spawn[1]) < 11:
                    continue
                if math.hypot(x - core[0], y - core[1]) < 16:
                    continue
                if rng.random() > 0.46:
                    continue
                species = "pine" if rng.random() < 0.6 else "tree"
                props.append(PropData(species, x, y, rng.randrange(4), solid=True))
                solid[y][x] = True

    # batu & semak di ruang terbuka
    for _ in range(420):
        x = rng.randrange(3, W - 3)
        y = rng.randrange(3, H - 3)
        if solid[y][x] or (x, y) in road:
            continue
        if (_rect_contains(village_rect, x, y) or _rect_contains(ruin_rect, x, y)
                or _rect_contains(farm_rect, x, y) or _rect_contains(pen_rect, x, y)):
            continue
        if math.hypot(x - spawn[0], y - spawn[1]) < 7:
            continue
        kind = terrain[y][x]
        if kind in (T_GRASS, T_MEADOW, T_STONE, T_SAND):
            if rng.random() < 0.42:
                props.append(PropData("rock", x, y, rng.randrange(4), solid=True))
                solid[y][x] = True
            else:
                props.append(PropData("bush", x, y, rng.randrange(4)))
        elif kind == T_FOREST:
            props.append(PropData("bush", x, y, rng.randrange(4)))

    # ---------- 9b. KELOMPOK JAMUR ---------------------------------------
    # Jamur merah/biru khas Sunnyside tumbuh di bawah kanopi hutan.
    for _ in range(90):
        x = rng.randrange(3, W - 3)
        y = rng.randrange(3, H - 3)
        if solid[y][x] or (x, y) in road:
            continue
        if terrain[y][x] not in (T_FOREST, T_GRASS):
            continue
        if (_rect_contains(village_rect, x, y) or _rect_contains(ruin_rect, x, y)
                or _rect_contains(farm_rect, x, y) or _rect_contains(pen_rect, x, y)):
            continue
        if math.hypot(x - spawn[0], y - spawn[1]) < 8:
            continue
        props.append(PropData("mushroom", x, y, rng.randrange(4)))

    # ---------- 10. TITIK SPAWN MONSTER ----------------------------------
    # Hanya pilih sel yang benar-benar terhubung ke Spawn, supaya tidak ada
    # monster yang "terkurung" di balik danau/tebing.
    reachable = set()
    q = [spawn]
    reachable.add(spawn)
    while q:
        x, y = q.pop()
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nx, ny = x + dx, y + dy
            if _inside(W, H, nx, ny) and not solid[ny][nx] \
                    and (nx, ny) not in reachable:
                reachable.add((nx, ny))
                q.append((nx, ny))

    land = []
    for y in range(3, H - 3):
        for x in range(3, W - 3):
            if solid[y][x] or (x, y) not in reachable:
                continue
            if terrain[y][x] in (T_PATH, T_BRIDGE, T_GRASS, T_MEADOW, T_FOREST):
                if math.hypot(x - spawn[0], y - spawn[1]) < 16:
                    continue
                if math.hypot(x - core[0], y - core[1]) < 8:
                    continue
                land.append((x, y))
    rng.shuffle(land)
    monster_spawns = []
    wanted = 11
    for cell in land:
        if len(monster_spawns) >= wanted:
            break
        if all(math.hypot(cell[0] - c[0], cell[1] - c[1]) >= 7
               for c in monster_spawns):
            monster_spawns.append(cell)

    # ---------- 11. ZONA ------------------------------------------------
    zones = [
        Zone("DESA MEADOWBROOK", "Aman - titik awal perjalanan",
             spawn[0], spawn[1], 12, (120, 220, 140)),
        Zone("HUTAN WHISPERWOOD", "Pepohonan rapat & monster berkeliaran",
             27, 23, 18, (105, 190, 120)),
        Zone("SUNGAI EMBERFLOW", "Jembatan kayu satu-satunya penyeberangan",
             int(river_x), 37, 15, (95, 190, 230)),
        Zone("DANAU KRISTAL", "Air jernih di bawah sinar senja",
             70, 57, 13, (105, 195, 235)),
        Zone("RERUNTUHAN OBSIDIAN KEEP", "Core berada di pelataran dalam",
             core[0], core[1], 16, (235, 120, 185)),
        Zone("PADANG LIAR ELDORIA", "Hamparan rumput tanpa batas",
             48, 55, 99, (215, 205, 130)),
    ]

    # ---------- 12. WATER / BRIDGE SETS UNTUK RENDER -----------------------
    water = set()
    bridge = set()
    for y in range(H):
        for x in range(W):
            if terrain[y][x] in WATER_KINDS:
                water.add((x, y))
            elif terrain[y][x] == T_BRIDGE:
                bridge.add((x, y))
                water.add((x, y))

    return WorldData(
        width=W, height=H, terrain=terrain, solid=solid,
        spawn=spawn, core=core, monster_spawns=monster_spawns,
        props=props, houses=houses, animals=animals, road=road, water=water, bridge=bridge,
        zones=zones, village_rect=village_rect, ruin_rect=ruin_rect,
        world_name="ELDORIA",
    )
