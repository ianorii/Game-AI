"""
world_art.py - Seni dunia open-world bercampur aset Sunnyside.

Tanah, jalan, air, dan batu diambil langsung dari atlas Sunnyside
(`assets/tilesets/sunnyside_world.png`) lalu diberi variasi prosedural tipis
(flower, retak, busa) agar tidak terlihat berulang. Pohon, jamur, batu, dan
hewan memakai sprite asli dari `assets/props/`.

Rumah, sumur, pilar, dan gerbang masih digambar prosedural karena pack tidak
menyediakan versi jadi; warnanya diselaraskan dengan palet Sunnyside.

Kelas utama: `WorldArt` (cache tile + sprite) dan `WorldProp` (objek tinggi
yang digambar oleh core/map.py dan ikut di-y-sort bersama Hero).
"""

from __future__ import annotations

import math
import random

import pygame

import config

TILE = config.TILE_SIZE
S = 2                     # logical 16 px -> layar 32 px (pixel art)
BIG = (TILE, TILE)


# ==============================================================================
# PALET (diselaraskan dengan atlas Sunnyside World)
# ==============================================================================
PAL = {
    "grass": (100, 199, 77),
    "grass_dark": (72, 152, 66),
    "grass_light": (146, 220, 96),
    "meadow": (128, 205, 90),
    "forest": (72, 156, 94),
    "dirt": (170, 98, 72),
    "path": (223, 162, 112),
    "path_dark": (184, 124, 86),
    "sand": (228, 213, 114),
    "stone": (132, 136, 148),
    "stone_dark": (92, 96, 110),
    "dungeon": (104, 108, 124),
    "water": (78, 193, 235),
    "deep": (57, 127, 163),
    "foam": (223, 247, 250),
    "wood": (176, 118, 72),
    "wood_dark": (108, 70, 44),
    "leaf": (74, 156, 88),
    "leaf_light": (124, 200, 104),
    "leaf_dark": (46, 104, 62),
    "pine": (52, 112, 72),
    "pine_light": (86, 156, 92),
    "trunk": (122, 82, 50),
    "trunk_dark": (78, 52, 34),
    "rock": (134, 137, 146),
    "rock_dark": (92, 95, 106),
    "rock_light": (176, 178, 186),
}

FLOWER_COLORS = {
    "yellow": (252, 224, 106),
    "white": (250, 246, 230),
    "red": (238, 104, 104),
    "purple": (196, 128, 220),
    "blue": (122, 176, 238),
}


def _scale(surf, size=None):
    size = size or (surf.get_width() * S, surf.get_height() * S)
    return pygame.transform.scale(surf, size)


def _jitter(color, rng, amount=8):
    return tuple(max(0, min(255, c + rng.randint(-amount, amount))) for c in color)


def _new(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def _speckle(surf, rng, colors, count, area=None):
    w, h = surf.get_size()
    x0, y0, x1, y1 = area or (0, 0, w, h)
    for _ in range(count):
        x = rng.randrange(x0, max(x0 + 1, x1))
        y = rng.randrange(y0, max(y0 + 1, y1))
        surf.set_at((x, y), rng.choice(colors))


def _tree_shadow(w, h):
    surf = _new(w, h)
    pygame.draw.ellipse(surf, (0, 0, 0, 96), surf.get_rect())
    return surf


# ==============================================================================
# WORLD ART
# ==============================================================================
class WorldArt:
    def __init__(self, assets):
        self.assets = assets
        self._ground = {}
        self._deco = {}
        self._props = {}
        self._glow = {}
        self._vignette = None
        self.sparkle = self._make_sparkle()
        self.particle = {
            "pollen": self._make_particle((255, 232, 130), 3, glow=True),
            "leaf": self._make_particle((136, 190, 104), 3, glow=False),
            "firefly": self._make_particle((190, 255, 160), 4, glow=True),
            "dust": self._make_particle((230, 220, 190), 2, glow=False),
        }
        self._fire_frames = self._make_fire_frames()

    # ================================================================ GROUND
    def ground(self, kind, variant=0, mask=0):
        """Tile tanah 32x32. `mask` = bit tetangga untuk autotile."""
        key = (kind, variant % 4, mask)
        surf = self._ground.get(key)
        if surf is None:
            surf = self._build_ground(kind, variant % 4, mask)
            if pygame.display.get_surface() is not None:
                surf = surf.convert()
            self._ground[key] = surf
        return surf

    def _tile(self, kind, variant):
        """Ambil satu tile atlas 32x32 untuk jenis permukaan tertentu."""
        tiles = self.assets.tiles.get(kind)
        if not tiles:
            tiles = self.assets.tiles.get("grass")
        return tiles[variant % len(tiles)] if tiles else None

    def _build_ground(self, kind, variant, mask):
        rng = random.Random(hash((kind, variant, mask)) & 0x7FFFFFFF)
        if kind == "wall":
            return self.assets.tile_wall_block_face.copy()
        if kind == "dungeon":
            return self._build_dungeon_ground(variant, rng)
        if kind == "path":
            return self._build_path(variant, mask, rng)
        if kind in ("water", "deep_water"):
            return self._build_water(kind, variant, mask, rng)
        if kind == "bridge":
            return self._build_bridge(variant, rng)
        if kind == "cliff":
            return self._build_cliff(variant, rng)

        tile = self._tile(kind, variant)
        surf = tile.copy()
        if kind == "meadow":
            # padang desa: rumput + rona hangat + bunga kecil
            warm = _new(TILE, TILE)
            warm.fill((255, 240, 150, 26))
            surf.blit(warm, (0, 0))
            for _ in range(2):
                fx, fy = rng.randrange(6, TILE - 6), rng.randrange(6, TILE - 6)
                col = rng.choice(list(FLOWER_COLORS.values()))
                pygame.draw.rect(surf, col, (fx, fy, 2, 2))
                surf.set_at((fx, fy + 2), PAL["grass_dark"])
        elif kind == "forest_floor":
            # serasah daun di bawah kanopi
            for _ in range(4):
                fx, fy = rng.randrange(3, TILE - 3), rng.randrange(3, TILE - 3)
                surf.set_at((fx, fy), rng.choice([(190, 128, 70),
                                                  (140, 96, 56),
                                                  PAL["leaf_light"]]))
        elif kind == "stone":
            for _ in range(2):
                x0 = rng.randrange(6, TILE - 6)
                y0 = rng.randrange(6, TILE - 6)
                pygame.draw.line(surf, PAL["stone_dark"], (x0, y0),
                                 (x0 + rng.randint(3, 7), y0 + rng.randint(2, 5)), 1)
        elif kind == "sand":
            _speckle(surf, rng, [(206, 190, 96), (240, 226, 140),
                                 (188, 170, 86)], 8)
        return surf

    def _build_path(self, variant, mask, rng):
        """
        Jalan setapak: tile pasir atlas dipotong membulat sesuai tetangga
        (autotile 4 arah) lalu ditempel di atas rumput.
        """
        base = self._tile("grass", (variant + 1) % 4).copy()
        grass_small = pygame.transform.scale(base, (16, 16))
        path_small = pygame.transform.scale(self._tile("path", variant), (16, 16))

        left = 0 if mask & 8 else 3
        right = 16 if mask & 2 else 13
        top = 0 if mask & 1 else 3
        bottom = 16 if mask & 4 else 13

        shape = _new(16, 16)
        shape.blit(path_small, (0, 0))
        clip = _new(16, 16)
        pygame.draw.rect(clip, (255, 255, 255, 255),
                         (left, top, max(2, right - left), max(2, bottom - top)),
                         border_radius=0 if mask == 15 else 2)
        shape.blit(clip, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        grass_small.blit(shape, (0, 0))

        # garis tepi hanya pada sisi yang benar-benar terbuka
        edge = PAL["path_dark"]
        if not mask & 1:
            pygame.draw.line(grass_small, edge, (left + 2, top),
                             (right - 3, top), 1)
        if not mask & 4:
            pygame.draw.line(grass_small, edge, (left + 2, bottom - 1),
                             (right - 3, bottom - 1), 1)
        if not mask & 8:
            pygame.draw.line(grass_small, edge, (left, top + 2),
                             (left, bottom - 3), 1)
        if not mask & 2:
            pygame.draw.line(grass_small, edge, (right - 1, top + 2),
                             (right - 1, bottom - 3), 1)
        return _scale(grass_small)

    def _build_water(self, kind, variant, mask, rng):
        """
        Air atlas + busa di tepi darat.

        Atlas Sunnyside hanya menyediakan satu jenis tile air. Air dalam
        dibuat dengan menggelapkan tile yang sama (BLEND_MULT) supaya sungai
        punya kedalaman tanpa memakai tile "air terjun" yang salah.
        """
        if kind == "water":
            small = pygame.transform.scale(self._tile("water", variant), (16, 16))
        else:
            small = pygame.transform.scale(self._tile("deep_water", variant), (16, 16))
            small = small.copy()
            small.fill((140, 172, 198), special_flags=pygame.BLEND_RGB_MULT)

        # variasi orientasi agar pola ombak bawaan atlas tidak berulang
        if variant & 1:
            small = pygame.transform.flip(small, True, False)
        if variant & 2:
            small = pygame.transform.flip(small, False, True)

        if kind == "deep_water":
            # transisi ke air dangkal (tanpa busa)
            shelf = PAL["water"]
            if mask & 16:
                pygame.draw.rect(small, shelf, (0, 0, 16, 2))
            if mask & 64:
                pygame.draw.rect(small, shelf, (0, 14, 16, 2))
            if mask & 128:
                pygame.draw.rect(small, shelf, (0, 0, 2, 16))
            if mask & 32:
                pygame.draw.rect(small, shelf, (14, 0, 2, 16))

        if kind == "water":
            foam = PAL["foam"]
            if mask & 1:
                pygame.draw.line(small, foam, (0, 0), (15, 0), 1)
                pygame.draw.line(small, (150, 219, 238), (1, 1), (14, 1), 1)
            if mask & 4:
                pygame.draw.line(small, foam, (0, 15), (15, 15), 1)
                pygame.draw.line(small, (150, 219, 238), (1, 14), (14, 14), 1)
            if mask & 8:
                pygame.draw.line(small, foam, (0, 0), (0, 15), 1)
            if mask & 2:
                pygame.draw.line(small, foam, (15, 0), (15, 15), 1)

        # kilau kecil
        for _ in range(2):
            y = rng.randrange(3, 13)
            x = rng.randrange(1, 10)
            pygame.draw.line(small, (176, 235, 246), (x, y),
                             (x + rng.randint(2, 4), y), 1)
        return _scale(small)

    def _build_bridge(self, variant, rng):
        surf = _new(16, 16)
        surf.fill(PAL["wood_dark"])
        for y in range(1, 16, 4):
            pygame.draw.rect(surf, PAL["wood"], (1, y, 14, 3))
            pygame.draw.line(surf, (174, 126, 76), (2, y), (13, y), 1)
            pygame.draw.line(surf, (98, 67, 42), (2, y + 3), (13, y + 3), 1)
        # paku
        for x in (3, 12):
            for y in (3, 11):
                surf.set_at((x, y), (63, 49, 38))
        # pagar atas/bawah
        pygame.draw.rect(surf, (77, 53, 35), (0, 0, 16, 2))
        pygame.draw.rect(surf, (77, 53, 35), (0, 14, 16, 2))
        return _scale(surf)

    def _build_dungeon_ground(self, variant, rng):
        """Lantai reruntuhan: lempeng batu atlas yang digelapkan + retak/runes."""
        base = self._tile("dungeon", variant).copy()
        shade = _new(TILE, TILE)
        shade.fill((0, 0, 0, 12 + variant * 6))
        base.blit(shade, (0, 0))
        if variant == 3:
            glow = (90, 210, 240)
            pygame.draw.line(base, glow, (7, 24), (14, 17), 1)
            pygame.draw.line(base, glow, (14, 17), (21, 20), 1)
            pygame.draw.line(base, glow, (24, 11), (24, 22), 1)
        elif variant == 2:
            pygame.draw.line(base, PAL["stone_dark"], (6, 21), (13, 15), 1)
            pygame.draw.line(base, PAL["stone_dark"], (13, 15), (11, 9), 1)
        return base

    def _build_cliff(self, variant, rng):
        """Tebing batu di tepi dunia: batu gelap dengan guratan vertikal."""
        base = self._tile("cliff", variant).copy()
        base.fill((118, 118, 140, 0), special_flags=pygame.BLEND_MULT)
        for _ in range(5):
            x = rng.randrange(2, TILE - 2)
            y0 = rng.randrange(0, 10)
            pygame.draw.line(base, (52, 54, 68), (x, y0),
                             (x, TILE - 1), 1)
        pygame.draw.line(base, (154, 156, 172), (0, 0), (TILE - 1, 0), 1)
        return base

    # ================================================================== DECO
    def deco(self, kind, variant=0):
        key = (kind, variant)
        surf = self._deco.get(key)
        if surf is None:
            surf = self._build_deco(kind, variant)
            if pygame.display.get_surface() is not None:
                surf = surf.convert_alpha()
            self._deco[key] = surf
        return surf

    def _build_deco(self, kind, variant):
        rng = random.Random(hash(("deco", kind, variant)) & 0x7FFFFFFF)
        surf = _new(16, 16)
        if kind == "tuft":
            for i in range(3):
                x = 4 + i * 4 + rng.randint(-1, 1)
                h = rng.randint(3, 6)
                pygame.draw.line(surf, PAL["grass_dark"], (x, 13), (x - 1, 13 - h), 1)
                pygame.draw.line(surf, PAL["grass_light"], (x + 1, 13), (x + 2, 14 - h), 1)
        elif kind.startswith("flower"):
            color = FLOWER_COLORS.get(kind.split("_")[-1], FLOWER_COLORS["yellow"])
            pygame.draw.line(surf, PAL["grass_dark"], (8, 14), (8, 8), 1)
            pygame.draw.circle(surf, color, (8, 7), 2)
            surf.set_at((8, 7), (255, 250, 208))
            if variant % 2:
                pygame.draw.line(surf, PAL["grass_dark"], (11, 14), (11, 9), 1)
                pygame.draw.circle(surf, color, (11, 8), 1)
        elif kind == "pebble":
            pygame.draw.ellipse(surf, PAL["rock_dark"], (4, 10, 8, 4))
            pygame.draw.ellipse(surf, PAL["rock"], (5, 10, 6, 3))
        elif kind == "mushroom":
            pygame.draw.rect(surf, (225, 215, 190), (7, 9, 2, 4))
            pygame.draw.ellipse(surf, (188, 74, 72), (3, 5, 10, 6))
            surf.set_at((6, 7), (246, 226, 210))
            surf.set_at((9, 8), (246, 226, 210))
        elif kind == "lily":
            pygame.draw.ellipse(surf, (61, 129, 79), (3, 7, 10, 6))
            pygame.draw.line(surf, (32, 83, 55), (8, 8), (10, 10), 1)
            if variant % 3 == 0:
                pygame.draw.circle(surf, (244, 175, 204), (8, 7), 2)
        elif kind == "reed":
            for i in range(3):
                x = 5 + i * 3
                pygame.draw.line(surf, (74, 122, 64), (x, 15), (x + i - 1, 3 + i), 1)
                if i == 1:
                    pygame.draw.rect(surf, (150, 115, 64), (x - 1, 3, 2, 4))
        elif kind == "leaf":
            pygame.draw.ellipse(surf, (132, 92, 52), (4, 10, 8, 4))
            pygame.draw.line(surf, (94, 65, 39), (5, 12), (11, 12), 1)
        elif kind == "moss":
            pygame.draw.ellipse(surf, (64, 116, 62), (3, 8, 10, 5))
            pygame.draw.ellipse(surf, (82, 140, 74), (5, 9, 6, 3))
            surf.set_at((7, 7), (105, 160, 84))
            surf.set_at((10, 11), (61, 111, 59))
        elif kind == "crack":
            pygame.draw.line(surf, (62, 63, 73), (3, 5), (8, 9), 1)
            pygame.draw.line(surf, (62, 63, 73), (8, 9), (6, 13), 1)
            pygame.draw.line(surf, (62, 63, 73), (8, 9), (12, 11), 1)
        elif kind == "bones":
            pygame.draw.line(surf, (218, 212, 190), (4, 11), (11, 8), 2)
            pygame.draw.circle(surf, (228, 222, 202), (4, 11), 2)
            pygame.draw.circle(surf, (228, 222, 202), (11, 8), 2)
            surf.set_at((7, 9), (123, 110, 94))
        return _scale(surf)

    # ================================================================= PROPS
    def prop(self, kind, variant=0):
        key = (kind, variant % 4)
        surf = self._props.get(key)
        if surf is None:
            surf = self._build_prop(kind, variant % 4)
            if pygame.display.get_surface() is not None:
                surf = surf.convert_alpha()
            self._props[key] = surf
        return surf

    def _asset_prop(self, name, variant):
        """Ambil frame prop dari assets/props (sudah diskalakan oleh loader)."""
        frames = self.assets.props.get(name)
        if not frames:
            return None
        return frames[variant % len(frames)].copy()

    def _build_prop(self, kind, variant):
        # 1. Rumah Sunnyside asli
        if kind == "house" or kind.startswith("house_"):
            house_names = ["house_blue", "house_red", "house_manor", "house_barn", "house_cabin", "house_forge"]
            hname = kind if kind in house_names else house_names[variant % len(house_names)]
            img = self._asset_prop(hname, 0)
            if img is not None:
                return img
            return self._build_house(variant)

        # 2. Pohon apel Sunnyside
        if kind == "tree_apple":
            img = self._asset_prop("tree_apple", variant)
            if img is not None:
                return img
            return self._build_tree("tree", variant)

        # 3. Kincir angin, sumur, patung, perahu, tunggul, api unggun
        if kind in ("windmill", "well", "statue", "boat", "tree_stump", "log", "anvil", "trough", "campfire"):
            img = self._asset_prop(kind, variant)
            if img is not None:
                return img

        if kind in ("tree", "pine", "birch"):
            img = self._asset_prop(
                {"tree": "tree_oak", "pine": "tree_oak",
                 "birch": "tree_birch"}[kind], variant)
            if img is not None:
                if kind == "pine":
                    img.fill((170, 205, 190, 0), special_flags=pygame.BLEND_MULT)
                return img
            return self._build_tree(kind, variant)
        if kind == "mushroom":
            img = self._asset_prop("mushroom_red" if variant % 2 == 0
                                   else "mushroom_blue", variant)
            if img is not None:
                return img
        if kind in ("cow", "sheep", "pig", "chicken", "duck"):
            img = self._asset_prop(kind, variant)
            if img is not None:
                return img
        if kind.startswith("crop_"):
            img = self._asset_prop(kind, variant)
            if img is not None:
                return img
        if kind == "rock":
            img = self._asset_prop("rock", variant)
            if img is not None:
                return img
        if kind == "crate":
            img = self._asset_prop("crate", variant)
            if img is not None:
                return img
        if kind == "bush":
            return self._build_bush(variant)
        if kind == "rubble":
            return self._build_rubble(variant)
        if kind == "sign":
            return self._build_sign()
        if kind == "barrel":
            return self._build_container(kind)
        if kind == "lantern":
            return self._build_lantern()
        if kind == "fence":
            return self._build_fence(variant)
        if kind == "pillar":
            return self._build_pillar(variant)
        if kind == "brazier":
            return self._build_brazier()
        if kind == "gate":
            return self._build_gate()
        return _new(16, 16)

    def _build_tree(self, species, variant):
        rng = random.Random(hash((species, variant)) & 0x7FFFFFFF)
        w, h = 34, 46
        surf = _new(w, h)
        cx = w // 2
        base = h - 3
        trunk = PAL["trunk"] if species != "birch" else (212, 205, 186)
        trunk_dark = PAL["trunk_dark"] if species != "birch" else (126, 118, 104)
        # batang
        pygame.draw.rect(surf, trunk_dark, (cx - 3, base - 16, 6, 16))
        pygame.draw.rect(surf, trunk, (cx - 2, base - 16, 4, 16))
        if species == "birch":
            for y in range(base - 14, base - 1, 4):
                surf.set_at((cx - 1, y), (73, 65, 56))
                surf.set_at((cx + 1, y + 1), (73, 65, 56))
        if species == "pine":
            colors = [(41, 86, 54), (48, 100, 59), (57, 117, 69)]
            for i, (half, top) in enumerate([(15, 7), (12, 15), (8, 23)]):
                pts = [(cx, top), (cx - half, top + 17), (cx + half, top + 17)]
                pygame.draw.polygon(surf, colors[i], pts)
                pygame.draw.polygon(surf, (30, 66, 45), pts, 1)
            for _ in range(10):
                surf.set_at((cx + rng.randint(-12, 12), base - rng.randint(8, 28)),
                            PAL["pine_light"])
        else:
            leaf = PAL["leaf"] if species == "tree" else (92, 145, 74)
            light = PAL["leaf_light"] if species == "tree" else (130, 181, 100)
            dark = PAL["leaf_dark"] if species == "tree" else (62, 108, 59)
            blobs = [
                (cx - 8, base - 25, 10), (cx + 8, base - 26, 10),
                (cx, base - 33, 11), (cx - 12, base - 18, 7),
                (cx + 12, base - 18, 7), (cx, base - 21, 12),
            ]
            for (bx, by, r) in blobs:
                pygame.draw.circle(surf, dark, (bx, by), r + 1)
            for (bx, by, r) in blobs:
                pygame.draw.circle(surf, leaf, (bx, by), r)
                pygame.draw.circle(surf, light, (bx - 2, by - 3), max(2, r - 5))
            for _ in range(14):
                bx = cx + rng.randint(-13, 13)
                by = base - rng.randint(14, 36)
                if 2 < bx < w - 2:
                    surf.set_at((bx, by), light)
        return _scale(surf)

    def _build_bush(self, variant):
        rng = random.Random(hash(("bush", variant)) & 0x7FFFFFFF)
        surf = _new(24, 18)
        blobs = [(7, 11, 6), (12, 9, 7), (17, 11, 6), (11, 13, 6)]
        for bx, by, r in blobs:
            pygame.draw.circle(surf, PAL["leaf_dark"], (bx, by), r + 1)
        for bx, by, r in blobs:
            pygame.draw.circle(surf, PAL["leaf"], (bx, by), r)
            pygame.draw.circle(surf, PAL["leaf_light"], (bx - 1, by - 2), max(2, r - 4))
        for _ in range(5):
            surf.set_at((rng.randrange(4, 21), rng.randrange(5, 15)),
                        rng.choice([(226, 96, 92), (247, 218, 90)]))
        return _scale(surf)

    def _build_rock(self, variant):
        rng = random.Random(hash(("rock", variant)) & 0x7FFFFFFF)
        surf = _new(22, 16)
        pts = [(3, 14), (5, 8), (10, 4), (17, 6), (20, 12), (17, 15), (5, 15)]
        pygame.draw.polygon(surf, PAL["rock_dark"], pts)
        inner = [(5, 13), (7, 8), (11, 5), (16, 7), (18, 12), (15, 13)]
        pygame.draw.polygon(surf, PAL["rock"], inner)
        pygame.draw.line(surf, PAL["rock_light"], (8, 7), (10, 5), 2)
        if variant % 3 == 0:
            pygame.draw.line(surf, (74, 126, 70), (5, 12), (9, 13), 1)
        for _ in range(4):
            surf.set_at((rng.randrange(7, 18), rng.randrange(8, 13)),
                        PAL["rock_dark"])
        return _scale(surf)

    def _build_rubble(self, variant):
        rng = random.Random(hash(("rubble", variant)) & 0x7FFFFFFF)
        surf = _new(18, 12)
        for _ in range(6):
            x, y = rng.randrange(2, 14), rng.randrange(4, 10)
            w, h = rng.randint(2, 5), rng.randint(2, 3)
            pygame.draw.rect(surf, PAL["stone_dark"], (x, y, w, h))
            pygame.draw.rect(surf, PAL["stone"], (x, y, max(1, w - 1), max(1, h - 1)))
        return _scale(surf)

    def _build_house(self, variant):
        rng = random.Random(hash(("house", variant)) & 0x7FFFFFFF)
        w, h = 48, 42
        surf = _new(w, h)
        wall_colors = [(248, 228, 186), (236, 210, 170), (214, 226, 218),
                       (246, 214, 166)]
        roof_colors = [(226, 98, 84), (78, 148, 190), (98, 176, 112),
                       (226, 166, 74)]
        wall = wall_colors[variant]
        roof = roof_colors[variant]
        # bayangan dalam sprite
        pygame.draw.ellipse(surf, (0, 0, 0, 60), (2, 34, 44, 8))
        # pondasi batu
        pygame.draw.rect(surf, PAL["stone_dark"], (5, 32, 38, 8))
        pygame.draw.rect(surf, PAL["stone"], (5, 32, 38, 2))
        # badan rumah
        pygame.draw.rect(surf, (91, 70, 50), (4, 16, 40, 18))
        pygame.draw.rect(surf, wall, (5, 17, 38, 16))
        # papan kayu
        for y in range(18, 32, 5):
            pygame.draw.line(surf, _jitter(wall, rng, 12), (6, y), (42, y), 1)
        # pintu
        pygame.draw.rect(surf, (84, 57, 38), (22, 22, 8, 11))
        pygame.draw.rect(surf, (120, 82, 52), (23, 23, 6, 10))
        surf.set_at((27, 28), (232, 199, 100))
        # jendela
        for x in (11, 34):
            pygame.draw.rect(surf, (71, 58, 45), (x, 21, 6, 6))
            pygame.draw.rect(surf, (244, 208, 109), (x + 1, 22, 4, 4))
            pygame.draw.line(surf, (96, 70, 46), (x + 3, 22), (x + 3, 25), 1)
        # atap
        roof_dark = tuple(max(0, c - 35) for c in roof)
        roof_light = tuple(min(255, c + 28) for c in roof)
        pts = [(2, 18), (24, 3), (46, 18)]
        pygame.draw.polygon(surf, roof_dark, pts)
        pygame.draw.polygon(surf, roof, [(4, 17), (24, 5), (44, 17)])
        for x in range(7, 43, 5):
            yy = 17 - int((24 - abs(x - 24)) * 0.45)
            pygame.draw.line(surf, roof_light, (x, yy), (x + 3, yy + 2), 1)
        pygame.draw.line(surf, (63, 53, 47), (24, 4), (24, 16), 1)
        # cerobong
        pygame.draw.rect(surf, (100, 86, 76), (36, 5, 5, 9))
        pygame.draw.rect(surf, (145, 128, 112), (36, 5, 5, 2))
        # pintu depan kecil
        pygame.draw.rect(surf, (70, 50, 35), (22, 27, 8, 12))
        return _scale(surf)

    def _build_well(self):
        surf = _new(20, 28)
        pygame.draw.ellipse(surf, (0, 0, 0, 70), (1, 22, 18, 6))
        pygame.draw.ellipse(surf, (92, 92, 101), (2, 17, 16, 10))
        pygame.draw.ellipse(surf, (143, 144, 151), (3, 16, 14, 8))
        pygame.draw.ellipse(surf, (31, 52, 70), (5, 17, 10, 5))
        pygame.draw.ellipse(surf, (72, 151, 190), (6, 18, 8, 3))
        pygame.draw.rect(surf, (104, 80, 59), (3, 4, 2, 14))
        pygame.draw.rect(surf, (104, 80, 59), (15, 4, 2, 14))
        pygame.draw.polygon(surf, (120, 61, 52), [(1, 5), (10, 0), (19, 5)])
        pygame.draw.line(surf, (167, 96, 77), (3, 4), (17, 4), 1)
        return _scale(surf)

    def _build_sign(self):
        surf = _new(18, 24)
        pygame.draw.rect(surf, PAL["wood_dark"], (8, 10, 3, 13))
        pygame.draw.rect(surf, PAL["wood"], (2, 2, 15, 10))
        pygame.draw.rect(surf, PAL["wood_dark"], (2, 2, 15, 10), 1)
        pygame.draw.line(surf, (173, 130, 86), (4, 5), (14, 5), 1)
        pygame.draw.line(surf, (173, 130, 86), (4, 8), (11, 8), 1)
        return _scale(surf)

    def _build_container(self, kind):
        surf = _new(16, 16)
        if kind == "crate":
            pygame.draw.rect(surf, (118, 81, 48), (2, 4, 12, 11))
            pygame.draw.rect(surf, (165, 119, 72), (3, 5, 10, 9))
            pygame.draw.line(surf, (115, 78, 47), (3, 5), (12, 13), 1)
            pygame.draw.line(surf, (115, 78, 47), (12, 5), (3, 13), 1)
        else:
            pygame.draw.ellipse(surf, (90, 64, 43), (2, 3, 12, 12))
            pygame.draw.ellipse(surf, (141, 97, 56), (3, 4, 10, 10))
            for y in (6, 9, 12):
                pygame.draw.line(surf, (77, 55, 39), (3, y), (12, y), 1)
            pygame.draw.ellipse(surf, (190, 151, 94), (5, 5, 6, 2))
        return _scale(surf)

    def _build_lantern(self):
        surf = _new(12, 28)
        pygame.draw.rect(surf, (76, 64, 53), (5, 10, 2, 17))
        pygame.draw.rect(surf, (96, 82, 68), (3, 25, 6, 2))
        pygame.draw.rect(surf, (63, 55, 48), (2, 5, 8, 8))
        pygame.draw.rect(surf, (255, 208, 96), (3, 6, 6, 6))
        pygame.draw.rect(surf, (255, 245, 190), (4, 7, 3, 3))
        pygame.draw.polygon(surf, (63, 55, 48), [(2, 5), (6, 1), (10, 5)])
        return _scale(surf)

    def _build_fence(self, variant):
        surf = _new(16, 14)
        vertical = variant % 2 == 0
        if vertical:
            pygame.draw.rect(surf, PAL["wood_dark"], (6, 2, 3, 12))
            for x in (2, 11):
                pygame.draw.rect(surf, PAL["wood"], (x, 2, 2, 12))
            pygame.draw.line(surf, PAL["wood"], (1, 5), (15, 5), 2)
            pygame.draw.line(surf, PAL["wood"], (1, 10), (15, 10), 2)
        else:
            pygame.draw.rect(surf, PAL["wood_dark"], (2, 3, 12, 3))
            for x in (2, 11):
                pygame.draw.rect(surf, PAL["wood"], (x, 2, 2, 12))
            pygame.draw.line(surf, PAL["wood"], (1, 5), (15, 5), 2)
            pygame.draw.line(surf, PAL["wood"], (1, 10), (15, 10), 2)
        return _scale(surf)

    def _build_pillar(self, variant):
        surf = _new(18, 34)
        pygame.draw.ellipse(surf, (0, 0, 0, 65), (1, 28, 16, 6))
        pygame.draw.rect(surf, PAL["stone_dark"], (4, 6, 10, 25))
        pygame.draw.rect(surf, PAL["stone"], (5, 6, 8, 25))
        pygame.draw.rect(surf, PAL["rock_light"], (6, 6, 2, 25))
        pygame.draw.rect(surf, PAL["stone_dark"], (2, 3, 14, 4))
        pygame.draw.rect(surf, PAL["stone"], (3, 3, 12, 3))
        pygame.draw.rect(surf, PAL["stone_dark"], (3, 29, 12, 4))
        if variant % 2 == 0:
            pygame.draw.polygon(surf, (67, 68, 78),
                                [(4, 7), (8, 3), (9, 12), (5, 13)])
        return _scale(surf)

    def _build_brazier(self):
        surf = _new(16, 28)
        pygame.draw.ellipse(surf, (0, 0, 0, 60), (2, 22, 12, 5))
        pygame.draw.rect(surf, (82, 80, 88), (7, 12, 2, 12))
        pygame.draw.rect(surf, (105, 102, 110), (4, 21, 8, 3))
        pygame.draw.polygon(surf, (78, 76, 84),
                            [(2, 8), (14, 8), (11, 14), (5, 14)])
        pygame.draw.polygon(surf, (160, 155, 158),
                            [(3, 8), (13, 8), (10, 10), (6, 10)])
        return _scale(surf)

    def _build_gate(self):
        surf = _new(16, 34)
        pygame.draw.rect(surf, (96, 94, 102), (1, 8, 14, 25))
        pygame.draw.rect(surf, (135, 134, 142), (2, 8, 12, 23))
        pygame.draw.rect(surf, (70, 69, 79), (1, 7, 14, 4))
        pygame.draw.line(surf, (173, 170, 176), (3, 10), (3, 30), 1)
        pygame.draw.line(surf, (173, 170, 176), (12, 10), (12, 30), 1)
        return _scale(surf)

    # ================================================================ FIRE
    def _make_fire_frames(self):
        frames = []
        for i in range(4):
            surf = _new(16, 18)
            flick = (0, 1, 0, -1)[i]
            pygame.draw.ellipse(surf, (255, 118, 40), (4, 5 + flick, 8, 12))
            pygame.draw.ellipse(surf, (255, 186, 62), (5, 7 + flick, 6, 9))
            pygame.draw.ellipse(surf, (255, 238, 158), (7, 10 + flick, 3, 5))
            frames.append(_scale(surf))
        return frames

    def fire_frame(self, t):
        return self._fire_frames[int(t * 10) % len(self._fire_frames)]

    def glow(self, color, radius):
        key = (color, radius)
        surf = self._glow.get(key)
        if surf is None:
            surf = _new(radius * 2, radius * 2)
            for r in range(radius, 0, -2):
                alpha = int(22 * (1 - r / radius) ** 1.4) + 4
                pygame.draw.circle(surf, tuple(color) + (alpha,), (radius, radius), r)
            self._glow[key] = surf
        return surf

    def sparkle_sprite(self):
        return self.sparkle

    def _make_sparkle(self):
        surf = _new(16, 6)
        pygame.draw.line(surf, (225, 249, 250), (2, 3), (13, 3), 1)
        pygame.draw.line(surf, (172, 225, 236), (5, 5), (11, 5), 1)
        return _scale(surf)

    def _make_particle(self, color, size, glow=False):
        pad = 8 if glow else 2
        surf = _new(size + pad * 2, size + pad * 2)
        if glow:
            for r in range(pad + size, 0, -2):
                pygame.draw.circle(surf, color + (12,), (surf.get_width() // 2,
                                                          surf.get_height() // 2), r)
        pygame.draw.circle(surf, color + (230,), (surf.get_width() // 2,
                                                   surf.get_height() // 2), size)
        return surf

    # ============================================================= VIGNETTE
    def vignette_strips(self, size):
        """
        Vignette ringan berupa 4 pita tepi (atas/bawah/kiri/kanan).

        Versi full-screen alpha-blit memakan ~3 ms/frame; pita tepi hanya
        menyentuh area pinggir sehingga efek visual sama dengan biaya jauh
        lebih kecil.
        """
        if self._vignette is not None:
            return self._vignette
        w, h = size
        # Cukup dalam untuk membingkai pandangan, tetapi strip tetap tipis agar
        # blit alpha hanya memakan ~1 ms per frame.
        ex = min(58, max(42, w // 18))
        ey = min(48, max(34, h // 13))
        tint = (8, 12, 20)

        def horizontal(length, depth, flip=False):
            small = _new(64, 16)
            for y in range(16):
                a = int(68 * (1 - y / 15) ** 1.6)
                if flip:
                    a = int(68 * (y / 15) ** 1.6)
                for x in range(64):
                    small.set_at((x, y), tint + (a,))
            return pygame.transform.smoothscale(small, (length, depth))

        def vertical(length, depth, flip=False):
            small = _new(16, 64)
            for x in range(16):
                a = int(58 * (1 - x / 15) ** 1.6)
                if flip:
                    a = int(58 * (x / 15) ** 1.6)
                for y in range(64):
                    small.set_at((x, y), tint + (a,))
            return pygame.transform.smoothscale(small, (depth, length))

        strips = [
            (horizontal(w, ey, flip=False), (0, 0)),
            (horizontal(w, ey, flip=True), (0, h - ey)),
            (vertical(h, ex, flip=False), (0, 0)),
            (vertical(h, ex, flip=True), (w - ex, 0)),
        ]
        if pygame.display.get_surface() is not None:
            strips = [(surf.convert_alpha(), pos) for surf, pos in strips]
        self._vignette = strips
        return strips

    # ========================================================= CLOUD SHADOWS
    def draw_cloud_shadows(self, surface, camera, t):
        """Bayangan awan meluncur halus di atas permukaan tanah (estetika Sunnyside World)."""
        if not hasattr(self, "_cloud_surfs"):
            clouds = []
            for (cw, ch) in ((240, 130), (310, 160), (200, 100)):
                cs = _new(cw, ch)
                pygame.draw.ellipse(cs, (0, 14, 28, 32), (18, 22, cw - 36, ch - 40))
                pygame.draw.circle(cs, (0, 14, 28, 36), (int(cw * 0.42), int(ch * 0.46)), int(ch * 0.36))
                pygame.draw.circle(cs, (0, 14, 28, 38), (int(cw * 0.65), int(ch * 0.48)), int(ch * 0.32))
                if pygame.display.get_surface() is not None:
                    cs = cs.convert_alpha()
                clouds.append(cs)
            self._cloud_surfs = clouds

        camx, camy = camera
        total_w = config.WORLD_PIXEL_W
        total_h = config.WORLD_PIXEL_H
        speed = 18.0
        drift_x = (t * speed) % (total_w + 600)
        drift_y = (t * speed * 0.32) % (total_h + 600)

        cloud_positions = [
            (250, 350), (950, 800), (1650, 420),
            (600, 1350), (1450, 1600), (2200, 1200)
        ]
        for i, (base_x, base_y) in enumerate(cloud_positions):
            cs = self._cloud_surfs[i % len(self._cloud_surfs)]
            wx = (base_x + drift_x) % (total_w + 500) - 250
            wy = (base_y + drift_y) % (total_h + 500) - 200
            sx = int(wx - camx)
            sy = int(wy - camy)
            if -320 < sx < config.MAP_PIXEL_W + 50 and -200 < sy < config.MAP_PIXEL_H + 50:
                surface.blit(cs, (sx, sy))


# ==============================================================================
# PROP RUNTIME (y-sort + bayangan tanah kokoh + animasi)
# ==============================================================================
class WorldProp:
    """
    Objek tinggi (pohon/rumah/pilar) dengan bayangan tanah menapak kokoh
    dan sway dedaunan lembut (bayangan tidak ikut goyang).
    """

    def __init__(self, data, art: WorldArt):
        self.data = data
        self.kind = data.kind
        self.gx, self.gy = data.gx, data.gy
        self.variant = data.variant
        self.image = art.prop(data.kind, data.variant)
        self.art = art
        self.base_y = data.base_y if data.base_y is not None \
            else (data.gy + data.h) * TILE
        self.sway = data.kind in ("tree", "pine", "birch", "bush", "tree_apple")
        self.phase = ((data.gx * 31 + data.gy * 17) % 100) / 16.0
        self.is_house = data.kind == "house" or data.kind.startswith("house_")
        self.is_tree = data.kind in ("tree", "pine", "birch", "tree_apple")
        self.is_windmill = data.kind == "windmill"
        self.is_boat = data.kind == "boat"

        iw, ih = self.image.get_size()
        # Posisi x: objek 1-tile dipusatkan; rumah diletakkan dari tepi kiri
        if self.is_house:
            self.x = data.gx * TILE
        else:
            self.x = data.gx * TILE + (data.w * TILE) // 2 - iw // 2
        self.y = self.base_y - ih

        # Bayangan tanah: DITETAPKAN DI DASAR BATANG POHON/PONDASI
        if self.is_tree:
            # Bayangan pohon: tepat di bawah tapak batang pohon
            sw = 36
            sh = 11
            self.shadow = _tree_shadow(sw, sh)
            self.shadow_x = self.x + iw // 2 - sw // 2
            # Batang pohon menapak 6 piksel di atas batas bawah sprite karena padding transparan
            self.shadow_y = self.base_y - sh // 2 - 2
        elif self.is_house:
            sw = max(32, int(iw * 0.90))
            sh = 14
            self.shadow = _tree_shadow(sw, sh)
            self.shadow_x = self.x + iw // 2 - sw // 2
            self.shadow_y = self.base_y - sh // 2 - 2
        elif self.kind in ("well", "statue", "pillar", "brazier", "windmill", "anvil", "trough"):
            sw = max(16, int(iw * 0.75))
            sh = max(6, int(sw * 0.32))
            self.shadow = _tree_shadow(sw, sh)
            self.shadow_x = self.x + iw // 2 - sw // 2
            self.shadow_y = self.base_y - sh // 2 - 1
        elif self.is_boat:
            # Riak air di bawah perahu
            self.shadow = None
        else:
            sw = max(12, int(iw * 0.65))
            sh = max(5, int(sw * 0.30))
            self.shadow = _tree_shadow(sw, sh)
            self.shadow_x = self.x + iw // 2 - sw // 2
            self.shadow_y = self.base_y - sh // 2

    @property
    def sort_y(self):
        return self.base_y

    def draw(self, surface, camera, t):
        ox, oy = camera
        sx = self.x - ox
        sy = self.y - oy
        iw, ih = self.image.get_size()

        # Culling viewport
        if sx < -iw - 32 or sx > config.MAP_PIXEL_W + 32:
            return
        if sy < -ih - 32 or sy > config.MAP_PIXEL_H + 64:
            return

        # 1. Gambar bayangan tanah TERLEBIH DAHULU (statis di tanah, tidak ikut bergoyang!)
        if self.shadow is not None:
            surface.blit(self.shadow, (self.shadow_x - ox, self.shadow_y - oy))

        # 2. Gerakan sway dedaunan (hanya bagian atas pohon yang melambai ditiup angin)
        sway = 0.0
        if self.sway:
            sway = math.sin(t * 1.35 + self.phase) * 1.5

        # 3. Ayunan perahu di air
        bob = 0.0
        if self.is_boat:
            bob = math.sin(t * 2.1 + self.phase) * 2.0

        # 4. Gambar sprite utama
        if self.is_windmill:
            frames = self.art.assets.props.get("windmill")
            frame = frames[int(t * 8.0) % len(frames)] if frames else self.image
            surface.blit(frame, (sx, sy))
        elif self.is_boat:
            frames = self.art.assets.props.get("boat")
            frame = frames[int(t * 2.0) % len(frames)] if frames else self.image
            surface.blit(frame, (sx, int(sy + bob)))
        else:
            surface.blit(self.image, (int(sx + sway), int(sy + bob)))

        # 5. Asap cerobong rumah
        if self.is_house:
            smoke_frames = self.art.assets.props.get("smoke")
            if smoke_frames:
                s_idx = int((t * 3.5 + self.phase * 3) % len(smoke_frames))
                s_frame = smoke_frames[s_idx]
                smk_x = sx + iw - 44
                smk_y = sy - 14 + int(math.sin(t * 2.2 + self.phase) * 3)
                surface.blit(s_frame, (smk_x, smk_y))

        # 6. Api brazier / lentera
        if self.kind == "brazier":
            frame = self.art.fire_frame(t + self.phase)
            fx = sx + self.image.get_width() // 2 - frame.get_width() // 2
            fy = sy + 2
            glow = self.art.glow((255, 148, 54), 26)
            surface.blit(glow, (fx + frame.get_width() // 2 - glow.get_width() // 2,
                                fy + 8 - glow.get_height() // 2),
                         special_flags=pygame.BLEND_ADD)
            surface.blit(frame, (fx, fy))
        elif self.kind == "lantern":
            glow = self.art.glow((255, 196, 92), 20)
            surface.blit(glow,
                         (sx + self.image.get_width() // 2 - glow.get_width() // 2,
                          sy + 10 - glow.get_height() // 2),
                         special_flags=pygame.BLEND_ADD)
