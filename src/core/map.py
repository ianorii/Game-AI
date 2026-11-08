"""
map.py - Dunia OPEN WORLD: grid, kamera, chunk renderer, minimap, ambient.

Dulu map.py menggambar satu dungeon 32x20 yang memenuhi layar. Sekarang:

    * Dunia 96x72 tile (3072x2304 px) dibangkitkan oleh core/worldgen.py.
    * Hanya area yang terlihat kamera yang digambar.
    * Tanah dirender per CHUNK (config.CHUNK_TILES, default 8x8) lalu di-cache
      (lazy), sehingga peta luas tetap ringan dan start tidak menunggu seluruh
      dunia digambar.
    * Prop tinggi (pohon/rumah/pilar/brazier) diekspos lewat `renderables()`
      agar bisa di-y-sort bersama Hero & monster oleh main.py.
    * Air beranimasi, partikel ambient (pollen/firefly/daun), vignette lembut,
      dan minimap dunia.

Jenis terrain & soliditas tetap disederhanakan untuk AI:
    grid[y][x] == T_WALL  -> tidak bisa dilalui (air juga dianggap "wall")
    floor_cells           -> seluruh sel yang bisa dilalui
Pathfinding, CSP, dan STRIPS tidak perlu tahu soal visual.
"""

from __future__ import annotations

import math
import random

import pygame

import config
from core.worldgen import (
    generate_world,
    T_GRASS, T_MEADOW, T_FOREST, T_DIRT, T_PATH, T_SAND, T_STONE,
    T_DUNGEON, T_WATER, T_DEEP, T_BRIDGE, T_CLIFF, T_WALL, WATER_KINDS,
)
from core.world_art import WorldArt, WorldProp, TILE

# tipe tile legacy (dipakai AI / CSP)
T_FLOOR = 0
T_SPAWN = 2
T_CORE = 3

CELL_SIZE = TILE

#: prop pendek yang dibakar ke chunk tanah (tidak perlu y-sort dengan Hero).
#: Pohon/rumah/pilar/brazier/pagar/papan tetap dinamis agar kedalaman benar.
STATIC_PROP_KINDS = {"bush", "rock", "rubble", "crate", "barrel"}


class TileMap:
    """Grid dunia + renderer chunk + kamera + minimap."""

    def __init__(self, seed=config.LEVEL_SEED_DEFAULT, assets=None, rows=None):
        self.seed = seed
        self.assets = assets
        self.art = assets.world_art if assets is not None else None
        self._chunks = {}
        self._minimap = None
        self._minimap_base = None
        self._minimap_size = None
        self._mini_font = None
        self._ambient = []
        self._ambient_t = 0.0
        self.world_name = "ELDORIA"
        self.zones = []
        self.props = []
        self.static_props = []
        self.dynamic_props = []
        self._static_by_chunk = {}
        self.houses = []
        self.road = set()
        self.water = set()
        self.bridge = set()
        self.terrain = []
        self._wall_tiles = {}
        self.animals = []
        self._pending_animals = []
        # bayangan tepi di-cache: membuat Surface SRCALPHA per tile saat chunk
        # dibangun membuat frame pertama chunk melonjak puluhan ms.
        self._shadow_top = pygame.Surface((TILE, 7), pygame.SRCALPHA)
        self._shadow_top.fill((0, 0, 0, 74))
        self._shadow_side = pygame.Surface((6, TILE), pygame.SRCALPHA)
        self._shadow_side.fill((0, 0, 0, 46))
        if pygame.display.get_surface() is not None:
            self._shadow_top = self._shadow_top.convert_alpha()
            self._shadow_side = self._shadow_side.convert_alpha()
        if rows:
            self.load(rows)
        else:
            self.build_world(seed)

    # ================================================================ MUAT
    def load(self, rows):
        """Fallback kompatibel: bangun dunia dari template ASCII."""
        assert all(len(r) == len(rows[0]) for r in rows), "Lebar baris level tidak seragam"
        self.width = len(rows[0])
        self.height = len(rows)
        self.terrain = [[T_GRASS] * self.width for _ in range(self.height)]
        self.grid = [[T_FLOOR] * self.width for _ in range(self.height)]
        self.spawn = (1, 1)
        self.core = (self.width - 2, self.height - 2)
        self.monster_spawns = []
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == "#":
                    self.grid[y][x] = T_WALL
                    self.terrain[y][x] = T_WALL
                elif ch == "S":
                    self.spawn = (x, y)
                elif ch == "C":
                    self.core = (x, y)
                elif ch == "M":
                    self.monster_spawns.append((x, y))
        self._finalize()

    def build_world(self, seed):
        data = generate_world(seed)
        self.width = data.width
        self.height = data.height
        self.terrain = data.terrain
        self.solid_raw = [row[:] for row in data.solid]
        self.grid = [[T_WALL if data.solid[y][x] else T_FLOOR
                      for x in range(self.width)] for y in range(self.height)]
        self.spawn = data.spawn
        self.core = data.core
        self.monster_spawns = list(data.monster_spawns)
        self.road = data.road
        self.water = data.water
        self.bridge = data.bridge
        self.zones = data.zones
        self.world_name = data.world_name
        self.houses = [p for p in data.props if p.kind == "house"]
        self._pending_props = data.props
        self._pending_animals = getattr(data, "animals", [])
        if self.art is not None:
            self.props = [WorldProp(p, self.art) for p in data.props]
        else:
            self.props = []
        if self.assets is not None and self._pending_animals:
            from core.animal import Animal
            self.animals = [
                Animal(kind, gx, gy, self.assets.props.get(kind, []), wander_radius=rad, assets=self.assets)
                for kind, gx, gy, rad in self._pending_animals
            ]
        else:
            self.animals = []
        self._split_props()
        self._finalize()

    def _split_props(self):
        """Pisahkan prop pendek (dibakar ke chunk) dari prop tinggi (y-sort)."""
        n = config.CHUNK_TILES
        cw = n * TILE
        self.static_props = []
        self.dynamic_props = []
        by_chunk = {}
        for p in self.props:
            if p.kind not in STATIC_PROP_KINDS:
                self.dynamic_props.append(p)
                continue
            # Sprite yang melewati batas atas chunk tetap dinamis agar tidak
            # terpotong (umumnya hanya beberapa piksel semak/rumput).
            chunk_top = (max(0, p.base_y - 1) // cw) * cw
            if p.y < chunk_top:
                self.dynamic_props.append(p)
                continue
            self.static_props.append(p)
            # masukkan berdasarkan titik pijak (base_y), bukan ujung atas sprite
            key = (p.gx // n, max(0, p.base_y - 1) // cw)
            by_chunk.setdefault(key, []).append(p)
        self._static_by_chunk = by_chunk

    def _finalize(self):
        self.floor_cells = [(x, y) for y in range(self.height)
                            for x in range(self.width)
                            if self.grid[y][x] != T_WALL]
        # sel lantai untuk penempatan Overseer (dekat Core / jalan utama)
        cx, cy = self.core
        self.defense_cells = [
            c for c in self.floor_cells
            if abs(c[0] - cx) + abs(c[1] - cy) <= 34
        ]
        self._chunks.clear()
        self._minimap = None
        self._minimap_base = None
        self._minimap_size = None
        self._ambient = self._make_ambient()
        self.hero_start = self.spawn

    # ============================================================ KOORDINAT
    def in_bounds(self, x, y):
        return 0 <= x < self.width and 0 <= y < self.height

    def is_wall(self, x, y):
        if not self.in_bounds(x, y):
            return True
        return self.grid[y][x] == T_WALL

    def is_passable(self, x, y):
        return not self.is_wall(x, y)

    def is_animal_passable(self, gx, gy, is_water=False):
        """Pengecekan batas jalan untuk hewan (darat vs bebek di air)."""
        if not self.in_bounds(gx, gy):
            return False
        terr = self.terrain[gy][gx]
        if is_water:
            # Bebek HANYA boleh berada di air murni (danau/kolam), TIDAK boleh di darat, jembatan, atau rumah
            return terr in ("water", "deep_water") and terr != T_BRIDGE and self.terrain[gy][gx] != T_WALL
        # Hewan darat: tidak boleh menabrak tembok/rumah/kandang, tebing, atau tercebur air
        if self.grid[gy][gx] == T_WALL or terr in WATER_KINDS or terr == T_CLIFF:
            return False
        return True

    @staticmethod
    def to_pixel(x, y):
        return (x * CELL_SIZE, y * CELL_SIZE)

    @staticmethod
    def to_grid(px, py):
        return (px // CELL_SIZE, py // CELL_SIZE)

    def neighbors4(self, x, y):
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nx, ny = x + dx, y + dy
            if self.is_passable(nx, ny):
                yield (nx, ny)

    def terrain_at(self, x, y):
        if not self.in_bounds(x, y):
            return T_CLIFF
        return self.terrain[y][x]

    def zone_at(self, x, y):
        for z in self.zones:
            d = math.hypot(x - z.x, y - z.y)
            if d <= z.radius:
                return z
        best, best_d = None, 10 ** 9
        for z in self.zones:
            d = math.hypot(x - z.x, y - z.y)
            if d < best_d:
                best, best_d = z, d
        return best

    def clamp_camera(self, camx, camy):
        max_x = max(0, self.width * TILE - config.MAP_PIXEL_W)
        max_y = max(0, self.height * TILE - config.MAP_PIXEL_H)
        return (max(0, min(max_x, camx)), max(0, min(max_y, camy)))

    def cell_at_screen(self, pos, camera):
        camx, camy = camera
        x, y = pos
        if 0 <= x < config.MAP_PIXEL_W and 0 <= y < config.MAP_PIXEL_H:
            return (int((x + camx) // TILE), int((y + camy) // TILE))
        return None

    # ============================================================ WILAYAH
    def _compute_regions(self):
        """Legacy: wilayah visual kini mengikuti jenis terrain."""
        return {(x, y): "wall" if self.grid[y][x] == T_WALL
                else self.terrain[y][x]
                for y in range(self.height) for x in range(self.width)}

    def region_of(self, x, y):
        return self.terrain_at(x, y)

    # ============================================================== RENDER
    def draw(self, surface, assets, t, camera=(0, 0)):
        """Gambar lapisan tanah + air beranimasi + bayangan awan. Prop/entity di-sort main.py."""
        self.ensure_art(assets)
        camx, camy = int(camera[0]), int(camera[1])
        self._draw_ground(surface, camx, camy)
        self._draw_water_glints(surface, camx, camy, t)
        if self.art is not None:
            self.art.draw_cloud_shadows(surface, (camx, camy), t)
        self._draw_landmarks(surface, t, camx, camy)
        self._preload_ring(camx, camy)
        self._trim_chunks(camx, camy)

    def ensure_art(self, assets):
        if self.art is None:
            assets.ensure_world_art()
            self.art = assets.world_art
            # bangun ulang prop runtime yang sebelumnya dilewati
            if not self.props and self.terrain:
                data_props = getattr(self, "_pending_props", [])
                self.props = [WorldProp(p, self.art) for p in data_props]
                self._split_props()
        if not self.animals and getattr(self, "_pending_animals", None):
            from core.animal import Animal
            self.animals = [
                Animal(kind, gx, gy, assets.props.get(kind, []), wander_radius=rad, assets=assets)
                for kind, gx, gy, rad in self._pending_animals
            ]

    def update(self, dt, hero=None):
        self._ambient_t += dt
        for p in self._ambient:
            p[0] += p[3] * dt
            p[1] += p[4] * dt
            p[5] += dt
            if p[0] < 0 or p[0] > self.width * TILE or \
                    p[1] < 0 or p[1] > self.height * TILE:
                p[0] = random.uniform(0, self.width * TILE)
                p[1] = random.uniform(0, self.height * TILE)
        for a in self.animals:
            a.update(dt, self.is_animal_passable, hero=hero)

    # ---------------------------------------------------------- ground chunk
    def _draw_ground(self, surface, camx, camy):
        cw = config.CHUNK_TILES * TILE
        x0 = camx // cw
        y0 = camy // cw
        x1 = (camx + config.MAP_PIXEL_W) // cw
        y1 = (camy + config.MAP_PIXEL_H) // cw
        for cy in range(y0, y1 + 1):
            for cx in range(x0, x1 + 1):
                chunk = self._chunk_surface(cx, cy)
                if chunk is not None:
                    surface.blit(chunk, (cx * cw - camx, cy * cw - camy))

    def _preload_ring(self, camx, camy):
        """
        Bangun maksimal SATU chunk di luar viewport per frame.

        Hero berjalan ~2-3 detik per chunk, jadi ring ini hampir selalu selesai
        sebelum chunk berikutnya terlihat. Biaya pembuatan chunk tidak lagi
        menumpuk tepat saat kamera melewati batas chunk.
        """
        cw = config.CHUNK_TILES * TILE
        x0 = camx // cw
        y0 = camy // cw
        x1 = (camx + config.MAP_PIXEL_W) // cw
        y1 = (camy + config.MAP_PIXEL_H) // cw
        for cy in range(y0 - 1, y1 + 2):
            for cx in range(x0 - 1, x1 + 2):
                if x0 <= cx <= x1 and y0 <= cy <= y1:
                    continue
                nt = config.CHUNK_TILES
                if not (0 <= cx < (self.width + nt - 1) // nt and
                        0 <= cy < (self.height + nt - 1) // nt):
                    continue
                if (cx, cy) not in self._chunks:
                    self._chunk_surface(cx, cy)
                    return

    def _chunk_surface(self, cx, cy):
        key = (cx, cy)
        surf = self._chunks.get(key)
        if surf is not None:
            return surf
        n = config.CHUNK_TILES
        px0, py0 = cx * n, cy * n
        if px0 >= self.width or py0 >= self.height or px0 < 0 or py0 < 0:
            return None
        size = n * TILE
        surf = pygame.Surface((size, size))
        if pygame.display.get_surface() is not None:
            surf = surf.convert()

        world_map = getattr(self.assets, "world_map_img", None) if self.assets else None
        if world_map is not None:
            rect = pygame.Rect(px0 * TILE, py0 * TILE, size, size)
            map_rect = world_map.get_rect()
            if map_rect.contains(rect):
                surf.blit(world_map, (0, 0), rect)
            else:
                inter = rect.clip(map_rect)
                surf.fill((14, 16, 20))
                if inter.w > 0 and inter.h > 0:
                    surf.blit(world_map, (inter.x - rect.x, inter.y - rect.y), inter)
        else:
            surf.fill((14, 16, 20))
            for ly in range(n):
                y = py0 + ly
                if y >= self.height:
                    break
                for lx in range(n):
                    x = px0 + lx
                    if x >= self.width:
                        break
                    self._draw_cell(surf, x, y, lx * TILE, ly * TILE)
            self._draw_chunk_shadows(surf, px0, py0, n)

        self._draw_static_props(surf, cx, cy, px0, py0)
        self._chunks[key] = surf
        return surf

    def _trim_chunks(self, camx, camy):
        """Buang chunk jauh satu per satu; jangan pernah clear seluruh cache."""
        limit = 72
        if len(self._chunks) <= limit:
            return
        cw = config.CHUNK_TILES * TILE
        ccx, ccy = camx // cw, camy // cw
        x0 = camx // cw
        y0 = camy // cw
        x1 = (camx + config.MAP_PIXEL_W) // cw
        y1 = (camy + config.MAP_PIXEL_H) // cw
        protected = {(cx, cy) for cy in range(y0 - 1, y1 + 2)
                     for cx in range(x0 - 1, x1 + 2)}
        removable = [k for k in self._chunks if k not in protected]
        removable.sort(key=lambda k: -(abs(k[0] - ccx) + abs(k[1] - ccy)))
        for k in removable[:max(0, len(self._chunks) - limit)]:
            self._chunks.pop(k, None)

    def _draw_static_props(self, surf, cx, cy, px0, py0):
        """Bakar semak/batu/pagar pendek ke surface chunk (hemat draw call)."""
        props = self._static_by_chunk.get((cx, cy))
        if not props:
            return
        camera = (px0 * TILE, py0 * TILE)
        for p in props:
            p.draw(surf, camera, 0.0)

    def _draw_cell(self, surf, x, y, px, py):
        kind = self.terrain[y][x]
        variant = (x * 37 + y * 91 + self.seed) % 4
        if kind == T_WALL:
            face = self.is_passable(x, y + 1)
            if face:
                surf.blit(self.assets.tile_wall_block_face, (px, py))
            else:
                surf.blit(self.assets.tile_wall_block, (px, py))
            # tepi atas batu
            pygame.draw.line(surf, (139, 155, 180), (px, py), (px + TILE - 1, py), 1)
            return
        if kind == T_CLIFF:
            surf.blit(self.art.ground(T_CLIFF, variant), (px, py))
            pygame.draw.line(surf, (55, 56, 66), (px, py + TILE - 1),
                             (px + TILE - 1, py + TILE - 1), 1)
            return
        if kind == T_BRIDGE:
            surf.blit(self.art.ground(T_BRIDGE, variant), (px, py))
            return
        if kind in WATER_KINDS:
            mask = 0
            for bit, (dx, dy) in ((1, (0, -1)), (2, (1, 0)), (4, (0, 1)), (8, (-1, 0))):
                nx, ny = x + dx, y + dy
                if not self.in_bounds(nx, ny) or self.terrain[ny][nx] not in WATER_KINDS:
                    mask |= bit
            if kind == T_DEEP:
                for bit, (dx, dy) in ((16, (0, -1)), (32, (1, 0)),
                                      (64, (0, 1)), (128, (-1, 0))):
                    nx, ny = x + dx, y + dy
                    if self.in_bounds(nx, ny) and self.terrain[ny][nx] == T_WATER:
                        mask |= bit
            for bit, (dx, dy) in ((256, (-1, -1)), (512, (1, -1)),
                                  (1024, (1, 1)), (2048, (-1, 1))):
                nx, ny = x + dx, y + dy
                if self.in_bounds(nx, ny) and self.terrain[ny][nx] not in WATER_KINDS:
                    mask |= bit
            surf.blit(self.art.ground(kind, variant, mask), (px, py))
            self._draw_cell_deco(surf, x, y, px, py, kind)
            return
        if kind == T_PATH:
            mask = 0
            for bit, (dx, dy) in ((1, (0, -1)), (2, (1, 0)), (4, (0, 1)), (8, (-1, 0))):
                nx, ny = x + dx, y + dy
                if self.in_bounds(nx, ny) and self.terrain[ny][nx] in (T_PATH, T_BRIDGE):
                    mask |= bit
            surf.blit(self.art.ground(T_PATH, variant, mask), (px, py))
            self._draw_cell_deco(surf, x, y, px, py, kind)
            return
        surf.blit(self.art.ground(kind, variant), (px, py))
        self._draw_cell_deco(surf, x, y, px, py, kind)

    def _draw_cell_deco(self, surf, x, y, px, py, kind):
        seed = (x * 73856093) ^ (y * 19349663) ^ (self.seed * 83492791)
        h = seed & 0x7FFFFFFF
        roll = h % 1000
        dx = (h // 7) % 12 - 6
        dy = (h // 13) % 10 - 4
        if kind in (T_GRASS, T_MEADOW, T_FOREST):
            if roll < 150:
                spr = self.art.deco("tuft", h % 4)
                surf.blit(spr, (px + dx + 1, py + dy + 2))
            elif roll < 230:
                color = ("yellow", "white", "purple", "blue", "red")[h % 5]
                surf.blit(self.art.deco("flower_" + color, h % 2),
                          (px + dx + 2, py + dy + 1))
            elif kind == T_FOREST and roll < 300:
                surf.blit(self.art.deco("mushroom", h % 3),
                          (px + dx + 3, py + dy + 2))
            elif roll < 325:
                surf.blit(self.art.deco("pebble", h % 2), (px + dx + 4, py + dy + 5))
        elif kind == T_SAND:
            if roll < 120:
                surf.blit(self.art.deco("pebble", h % 2), (px + dx + 3, py + dy + 5))
            elif roll < 190:
                surf.blit(self.art.deco("reed", h % 3), (px + dx + 2, py + dy - 2))
        elif kind in WATER_KINDS:
            if roll < 38:
                surf.blit(self.art.deco("lily", h % 3), (px + dx + 2, py + dy + 7))
        elif kind == T_DUNGEON:
            if roll < 38:
                surf.blit(self.art.deco("pebble", h % 2), (px + dx + 4, py + dy + 6))
            elif roll < 108:
                surf.blit(self.art.deco("moss", h % 3), (px + dx + 3, py + dy + 5))
            elif roll < 164:
                surf.blit(self.art.deco("crack", h % 2), (px + dx + 3, py + dy + 2))
            elif roll < 184:
                surf.blit(self.art.deco("bones", h % 2), (px + dx + 4, py + dy + 5))
        elif kind == T_STONE:
            if roll < 55:
                surf.blit(self.art.deco("pebble", h % 2), (px + dx + 4, py + dy + 5))
            elif roll < 105:
                surf.blit(self.art.deco("moss", h % 3), (px + dx + 3, py + dy + 6))
        elif kind == T_PATH:
            if roll < 60:
                surf.blit(self.art.deco("pebble", h % 2), (px + dx + 3, py + dy + 5))

    def _draw_chunk_shadows(self, surf, px0, py0, n):
        """Ambient occlusion di bawah dinding/tebing + bayangan pohon besar."""
        for ly in range(n):
            y = py0 + ly
            if y >= self.height:
                break
            for lx in range(n):
                x = px0 + lx
                if x >= self.width:
                    break
                if self.grid[y][x] == T_WALL:
                    continue
                px, py = lx * TILE, ly * TILE
                # bayangan dari dinding di atas
                if y > 0 and self.grid[y - 1][x] == T_WALL:
                    surf.blit(self._shadow_top, (px, py))
                if x > 0 and self.grid[y][x - 1] == T_WALL:
                    surf.blit(self._shadow_side, (px, py))
                if x + 1 < self.width and self.grid[y][x + 1] == T_WALL:
                    surf.blit(self._shadow_side, (px + TILE - 6, py))

    # ----------------------------------------------------------- water anim
    def _draw_water_glints(self, surface, camx, camy, t):
        x0 = max(0, camx // TILE - 1)
        y0 = max(0, camy // TILE - 1)
        x1 = min(self.width - 1, (camx + config.MAP_PIXEL_W) // TILE + 1)
        y1 = min(self.height - 1, (camy + config.MAP_PIXEL_H) // TILE + 1)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if self.terrain[y][x] not in WATER_KINDS:
                    continue
                h = (x * 73856093) ^ (y * 19349663)
                if h % 6:
                    continue
                phase = (h % 97) / 16.0
                alpha = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 1.9 + phase))
                if alpha < 0.55:
                    continue
                sx = x * TILE - camx + (h % 9) + 4
                sy = y * TILE - camy + (h // 11) % 18 + 5
                pygame.draw.line(surface, (148, 214, 228), (sx, sy),
                                 (sx + 7, sy), 1)
                if alpha > 0.8:
                    pygame.draw.line(surface, (205, 241, 246), (sx + 2, sy + 2),
                                     (sx + 5, sy + 2), 1)

    # ------------------------------------------------------------ landmark
    def _draw_landmarks(self, surface, t, camx, camy):
        """Core crystal + rune spawn, digambar di bawah entity."""
        cx, cy = self.core
        px, py = cx * TILE - camx, cy * TILE - camy
        if -TILE < px < config.MAP_PIXEL_W + TILE and -TILE < py < config.MAP_PIXEL_H + TILE:
            pulse = 0.5 + 0.5 * math.sin(t * 3.0)
            glow = self.art.glow((70, 160, 255), 34)
            surface.blit(glow, (px + TILE // 2 - glow.get_width() // 2,
                                py + TILE // 2 - glow.get_height() // 2),
                         special_flags=pygame.BLEND_ADD)
            surface.blit(self.assets.frames_core_basin, (px, py))
            frame = self.assets.frames_core[int(t * 6) % len(self.assets.frames_core)]
            surface.blit(frame, (px, py - TILE // 4))
            halo = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            halo.fill((60, 150, 255, int(35 + 55 * pulse)))
            surface.blit(halo, (px, py - TILE // 4))

        sx, sy = self.spawn
        px, py = sx * TILE - camx, sy * TILE - camy
        if -TILE < px < config.MAP_PIXEL_W + TILE and -TILE < py < config.MAP_PIXEL_H + TILE:
            rune = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            r = int(8 + 2 * math.sin(t * 2.2))
            pygame.draw.circle(rune, (37, 149, 106), (TILE // 2, TILE // 2), r, 2)
            pygame.draw.circle(rune, (105, 255, 212), (TILE // 2, TILE // 2), max(3, r - 4), 1)
            surface.blit(rune, (px, py))

    def draw_ambient(self, surface, camera, t):
        camx, camy = camera
        for p in self._ambient:
            wx, wy, kind, _vx, _vy, _age = p
            sx = int(wx - camx)
            sy = int(wy - camy)
            if not (-16 < sx < config.MAP_PIXEL_W + 16 and
                    -16 < sy < config.MAP_PIXEL_H + 16):
                continue
            spr = self.art.particle.get(kind)
            if spr is None:
                continue
            bob = math.sin(t * 2.0 + p[5]) * 3
            if kind in ("firefly", "pollen"):
                surface.blit(spr, (sx, int(sy + bob)), special_flags=pygame.BLEND_ADD)
            else:
                surface.blit(spr, (sx, int(sy + bob)))

    def draw_vignette(self, surface):
        for strip, pos in self.art.vignette_strips(
                (config.MAP_PIXEL_W, config.MAP_PIXEL_H)):
            surface.blit(strip, pos)

    def _make_ambient(self):
        rng = random.Random(self.seed ^ 0x2F7A11)
        parts = []
        for _ in range(64):
            x = rng.uniform(0, self.width * TILE)
            y = rng.uniform(0, self.height * TILE)
            tx, ty = int(x // TILE), int(y // TILE)
            kind = self.terrain_at(tx, ty)
            if kind in WATER_KINDS or kind == T_CLIFF:
                ptype = "dust"
            elif kind in (T_GRASS, T_MEADOW):
                ptype = rng.choice(["pollen", "pollen", "leaf", "dust"])
            elif kind == T_FOREST:
                ptype = rng.choice(["firefly", "leaf", "leaf", "leaf"])
            elif kind in (T_DUNGEON, T_STONE, T_WALL):
                ptype = "dust"
            else:
                ptype = "dust"
            vx = rng.uniform(-9, 12)
            vy = rng.uniform(-5, 3)
            parts.append([x, y, ptype, vx, vy, rng.uniform(0, 6)])
        return parts

    # ------------------------------------------------------------ renderables
    def renderables(self, camera):
        """Prop tinggi yang terlihat, untuk di-y-sort bersama entity."""
        camx, camy = camera
        left = camx - 80
        right = camx + config.MAP_PIXEL_W + 80
        top = camy - 110
        bottom = camy + config.MAP_PIXEL_H + 80
        out = []
        for p in self.dynamic_props:
            if p.x + p.image.get_width() < left or p.x > right:
                continue
            if p.base_y < top or p.y > bottom:
                continue
            out.append(p)
        for a in self.animals:
            if left <= a.px <= right and top <= a.py <= bottom:
                out.append(a)
        return out

    # --------------------------------------------------------------- minimap
    def minimap_surface(self):
        if self._minimap is not None:
            return self._minimap
        scale = 4
        mw = self.width * scale
        mh = self.height * scale
        world_map = getattr(self.assets, "world_map_img", None) if self.assets else None
        if world_map is not None:
            surf = pygame.transform.smoothscale(world_map, (mw, mh))
        else:
            surf = pygame.Surface((mw, mh))
            colors = {
                T_GRASS: (74, 129, 62), T_MEADOW: (105, 155, 74),
                T_FOREST: (48, 92, 54), T_DIRT: (126, 96, 63),
                T_PATH: (187, 154, 100), T_SAND: (208, 188, 137),
                T_STONE: (127, 127, 135), T_DUNGEON: (142, 140, 148),
                T_WATER: (43, 109, 163), T_DEEP: (28, 75, 125),
                T_BRIDGE: (146, 101, 59), T_CLIFF: (72, 72, 82),
                T_WALL: (170, 170, 178),
            }
            for y in range(self.height):
                for x in range(self.width):
                    c = colors.get(self.terrain[y][x], (60, 60, 70))
                    pygame.draw.rect(surf, c, (x * scale, y * scale, scale, scale))
        for p in self.props:
            if p.kind in ("house",):
                cx = (p.data.gx + p.data.w // 2) * scale
                cy = (p.data.gy + p.data.h // 2) * scale
                pygame.draw.rect(surf, (183, 96, 82),
                                 (cx - 4, cy - 4, 8, 8))
        # core & spawn
        pygame.draw.circle(surf, (0, 220, 255),
                           (self.core[0] * scale + 2, self.core[1] * scale + 2), 9)
        pygame.draw.circle(surf, (130, 255, 185),
                           (self.spawn[0] * scale + 2, self.spawn[1] * scale + 2), 6)
        self._minimap = surf
        return surf

    def draw_minimap(self, surface, rect, camera, hero, monsters, boss):
        rect = pygame.Rect(rect)
        if self._mini_font is None:
            self._mini_font = pygame.font.Font(None, 15)
        if self._minimap_base is None or self._minimap_size != (rect.w, rect.h):
            self._minimap_base = self._build_minimap_panel(rect)
            self._minimap_size = (rect.w, rect.h)
        base, geom = self._minimap_base
        surface.blit(base, rect.topleft)
        tx, ty, mw, mh = geom
        ox, oy = rect.x + tx, rect.y + ty
        sx = mw / self.width
        sy = mh / self.height
        # kamera viewport
        cam = pygame.Rect(ox + int(camera[0] / TILE * sx),
                          oy + int(camera[1] / TILE * sy),
                          max(3, int(config.MAP_PIXEL_W / TILE * sx)),
                          max(3, int(config.MAP_PIXEL_H / TILE * sy)))
        pygame.draw.rect(surface, (240, 210, 60), cam, 1)
        for m in monsters:
            pygame.draw.circle(surface, (232, 84, 76),
                               (ox + int(m.gx * sx), oy + int(m.gy * sy)), 2)
        if hero.alive:
            hx, hy = ox + int(hero.gx * sx), oy + int(hero.gy * sy)
            pygame.draw.circle(surface, (250, 250, 250), (hx, hy), 3)
            pygame.draw.circle(surface, (70, 210, 255), (hx, hy), 1)
        if boss.alive:
            pygame.draw.circle(surface, (245, 105, 185),
                               (ox + int(boss.gx * sx), oy + int(boss.gy * sy)), 3)

    def _build_minimap_panel(self, rect):
        """Panel dasar minimap di-cache; hanya marker yang digambar per frame."""
        panel = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        panel.fill((10, 14, 20, 218))
        pygame.draw.rect(panel, (60, 170, 190), panel.get_rect(), 1)
        inner = rect.inflate(-8, -16)
        mini = self.minimap_surface()
        max_w, max_h = inner.w - 2, inner.h - 2
        scale = min(max_w / mini.get_width(), max_h / mini.get_height())
        mw = max(8, int(mini.get_width() * scale))
        mh = max(8, int(mini.get_height() * scale))
        scaled = pygame.transform.smoothscale(mini, (mw, mh))
        tx = 4 + (max_w - mw) // 2
        ty = 14 + (max_h - mh) // 2
        panel.blit(scaled, (tx, ty))
        pygame.draw.rect(panel, (36, 48, 58),
                         (tx - 1, ty - 1, mw + 2, mh + 2), 1)
        panel.blit(self._mini_font.render("PETA DUNIA  (utara ^)", True,
                                          (150, 220, 230)), (4, 2))
        return (panel, (tx, ty, mw, mh))
