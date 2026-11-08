#!/usr/bin/env python3
"""
build_sunnyside_map.py - Builder peta HD Sunnyside World Isle (86x48).

Mengekstrak data lengkap dari assets/sunnyside_world/Sunnyside_World_Gamemaker/rooms/Room1/Room1.yy:
1. Merender seluruh lapisan tile (sea, land, paths, shadows, walls, building, decoration)
   langsung dari tileset asli sunnyside_world.png (1280x1280) ke resolusi tinggi:
   - assets/maps/island_map.png (2752 x 1536 px - HD pixel art 32px)
   - assets/maps/island_map_1x.png (1376 x 768 px - Native 16px)
2. Menghasilkan assets/maps/collision.json secara presisi untuk bangunan, jembatan, dan pohon.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SUNNYSIDE = ASSETS / "sunnyside_world"
GM = SUNNYSIDE / "Sunnyside_World_Gamemaker"
ROOM1_FILE = GM / "rooms" / "Room1" / "Room1.yy"
MAPS = ASSETS / "maps"
MAPS.mkdir(parents=True, exist_ok=True)

W_TILES = 86
H_TILES = 48
TILE_1X = 16
TILE_2X = 32


def decompress(data_list):
    """Dekompresi GameMaker RLE TileCompressedData."""
    out = []
    i = 0
    while i < len(data_list):
        count = data_list[i]
        i += 1
        if count < 0:
            val = data_list[i]
            i += 1
            out.extend([val] * (-count))
        else:
            out.extend(data_list[i:i + count])
            i += count
    return out


def build():
    print("[1/4] Membaca data Room1.yy & tileset...")
    if not ROOM1_FILE.exists():
        raise FileNotFoundError(f"File Room1 tidak ditemukan di: {ROOM1_FILE}")

    content = ROOM1_FILE.read_text(encoding="utf-8")
    tileset_path = SUNNYSIDE / "Tileset" / "sunnyside_world.png"
    if not tileset_path.exists():
        tileset_path = SUNNYSIDE / "Tileset" / "spr_tileset_sunnysideworld_16px.png"
    tileset = pygame.image.load(str(tileset_path))

    pattern = r'\"resourceType\":\"GMRTileLayer\"[^\}]*?\"name\":\"([^\"]+)\".*?\"SerialiseWidth\":(\d+),\"SerialiseHeight\":(\d+),\"TileCompressedData\":\[(.*?)\]'
    matches = re.findall(pattern, content, re.DOTALL)
    layer_dict = {m[0]: m for m in matches}

    sea_pattern = r'\"resourceType\":\"GMRTileLayer\"[^\}]*?\"name\":\"sea\".*?\"TileSerialiseData\":\[(.*?)\]'
    sea_m = re.search(sea_pattern, content, re.DOTALL)
    sea_nums = [int(x.strip()) for x in sea_m.group(1).split(",") if x.strip()]

    def get_layer(name):
        if name not in layer_dict:
            return [0] * (W_TILES * H_TILES)
        m = layer_dict[name]
        nums = [int(x.strip()) for x in m[3].split(",") if x.strip()]
        return decompress(nums)

    land = get_layer("land")
    paths = get_layer("paths")
    shadows = get_layer("shadows")
    walls = get_layer("walls")
    building = get_layer("building")
    deco1 = get_layer("decoration_01")
    deco2 = get_layer("decoration_02")
    deco3 = get_layer("decoration_03")

    print("[2/4] Merender peta HD dari tileset asli...")
    # Siapkan kanvas 1x (1376 x 768)
    surf_1x = pygame.Surface((W_TILES * 16, H_TILES * 16))
    surf_1x.fill((43, 153, 219))  # Warna laut biru Sunnyside

    # Tile laut default (1291)
    default_sea_rect = pygame.Rect((1291 % 64) * 20 + 2, (1291 // 64) * 20 + 2, 16, 16)
    default_sea_surf = tileset.subsurface(default_sea_rect)

    # 1. Render sea base
    for idx, raw in enumerate(sea_nums):
        tid = (raw & 0x0FFFFFFF) if raw != 0 else 1291
        col, row = tid % 64, tid // 64
        rect = pygame.Rect(col * 20 + 2, row * 20 + 2, 16, 16)
        if tileset.get_rect().contains(rect):
            t_surf = tileset.subsurface(rect)
            surf_1x.blit(t_surf, ((idx % W_TILES) * 16, (idx // W_TILES) * 16))
        else:
            surf_1x.blit(default_sea_surf, ((idx % W_TILES) * 16, (idx // W_TILES) * 16))

    # 2. Render tile layers tanah, jalan, tembok, bangunan, dekorasi
    layers_order = ["land", "paths", "shadows", "walls", "building", "decoration_01", "decoration_02", "decoration_03"]
    for lname in layers_order:
        tiles = get_layer(lname)
        for idx, raw in enumerate(tiles):
            if raw == -2147483648 or raw == 0:
                continue
            gx = idx % W_TILES
            gy = idx // W_TILES

            # Filter rumah panggung debug di air
            if lname in ("building", "walls", "decoration_01", "decoration_02", "decoration_03"):
                if (gx >= 70 and gy >= 38) or (gx <= 6 and 20 <= gy <= 36):
                    continue

            flip_x = bool(raw & 0x10000000)
            flip_y = bool(raw & 0x20000000)
            tid = raw & 0x0FFFFFFF
            col, row = tid % 64, tid // 64
            rect = pygame.Rect(col * 20 + 2, row * 20 + 2, 16, 16)
            if tileset.get_rect().contains(rect):
                t_surf = tileset.subsurface(rect)
                if flip_x or flip_y:
                    t_surf = pygame.transform.flip(t_surf, flip_x, flip_y)
                surf_1x.blit(t_surf, (gx * 16, gy * 16))

    # Simpan hasil 1x dan 2x HD
    out_1x = MAPS / "island_map_1x.png"
    out_2x = MAPS / "island_map.png"
    pygame.image.save(surf_1x, str(out_1x))

    surf_2x = pygame.transform.scale(surf_1x, (W_TILES * 32, H_TILES * 32))
    pygame.image.save(surf_2x, str(out_2x))
    print(f"  -> Disimpan ke {out_2x} (2752x1536 HD) & {out_1x} (1376x768 1x)")

    print("[3/4] Membangun collision data (bangunan, jembatan, pohon)...")
    bridge_cells = set()
    for y in range(H_TILES):
        for x in range(W_TILES):
            if 29 <= y <= 33 and 35 <= x <= 41: bridge_cells.add((x, y))
            if 14 <= y <= 17 and 48 <= x <= 53: bridge_cells.add((x, y))
            if 13 <= y <= 24 and 6 <= x <= 9:   bridge_cells.add((x, y))
            if 22 <= y <= 25 and 9 <= x <= 17:  bridge_cells.add((x, y))
            if 24 <= y <= 27 and 80 <= x <= 85: bridge_cells.add((x, y))
            if 46 <= y <= 48 and 23 <= x <= 31: bridge_cells.add((x, y))
            if 30 <= y <= 35 and 89 <= x <= 95: bridge_cells.add((x, y))

    colliders = []
    # Jembatan
    bridges = [
        {"name": "central_village_bridge", "x": 35 * 16, "y": 29 * 16, "w": 6 * 16, "h": 4 * 16, "type": "bridge"},
        {"name": "north_river_bridge",    "x": 48 * 16, "y": 14 * 16, "w": 5 * 16, "h": 3 * 16, "type": "bridge"},
        {"name": "nw_bridge",             "x": 6 * 16,  "y": 13 * 16, "w": 3 * 16, "h": 11 * 16, "type": "bridge"},
        {"name": "west_bridge",           "x": 9 * 16,  "y": 22 * 16, "w": 8 * 16, "h": 3 * 16, "type": "bridge"},
        {"name": "east_island_bridge",    "x": 80 * 16, "y": 24 * 16, "w": 5 * 16, "h": 3 * 16, "type": "bridge"},
        {"name": "south_dock",            "x": 23 * 16, "y": 46 * 16, "w": 8 * 16, "h": 2 * 16, "type": "bridge"},
        {"name": "east_dock",             "x": 89 * 16, "y": 30 * 16, "w": 7 * 16, "h": 5 * 16, "type": "bridge"},
    ]
    colliders.extend(bridges)

    # Deteksi klaster bangunan daratan
    visited_b = set()
    for y in range(H_TILES):
        for x in range(W_TILES):
            if (x >= 70 and y >= 38) or (x <= 6 and 20 <= y <= 36):
                continue
            idx = y * W_TILES + x
            raw_b = building[idx] & 0x0FFFFFFF
            raw_w = walls[idx] & 0x0FFFFFFF
            if (raw_b > 0 or raw_w > 0) and (x, y) not in visited_b and (x, y) not in bridge_cells:
                comp = []
                q = [(x, y)]
                visited_b.add((x, y))
                while q:
                    cx, cy = q.pop(0)
                    comp.append((cx, cy))
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < W_TILES and 0 <= ny < H_TILES:
                            n_idx = ny * W_TILES + nx
                            nb = building[n_idx] & 0x0FFFFFFF
                            nw = walls[n_idx] & 0x0FFFFFFF
                            if (nb > 0 or nw > 0) and (nx, ny) not in visited_b and (nx, ny) not in bridge_cells:
                                visited_b.add((nx, ny))
                                q.append((nx, ny))
                bx = min(p[0] for p in comp)
                by = min(p[1] for p in comp)
                bw = max(p[0] for p in comp) - bx + 1
                bh = max(p[1] for p in comp) - by + 1
                colliders.append({
                    "name": f"building_{bx}_{by}",
                    "x": bx * 16,
                    "y": by * 16,
                    "w": bw * 16,
                    "h": bh * 16,
                    "type": "house"
                })

    # Pohon terseleksi agar rapi dan tidak menghalangi jalan
    sprite_pattern = r'\{\"resourceType\":\"GMRSpriteGraphic\".*?\"spriteId\":\{\"name\":\"([^\"]+)\".*?\"x\":([0-9\.-]+),\"y\":([0-9\.-]+)'
    sprite_matches = re.findall(sprite_pattern, content)
    placed_trees = []
    for name, sx, sy in sprite_matches:
        if "tree_01" in name or "tree_02" in name:
            gx = int(round(float(sx) / 16.0))
            gy = int(round(float(sy) / 16.0))
            if 27 <= gy <= 34 and 35 <= gx <= 50:
                continue
            if any(abs(gx - tx) <= 2 and abs(gy - ty) <= 2 for tx, ty in placed_trees):
                continue
            if 0 <= gx < W_TILES and 0 <= gy < H_TILES and (gx, gy) not in visited_b and (gx, gy) not in bridge_cells:
                colliders.append({
                    "name": f"tree_{gx}_{gy}",
                    "x": gx * 16,
                    "y": gy * 16 + 8,
                    "w": 16,
                    "h": 16,
                    "type": "tree"
                })
                placed_trees.append((gx, gy))

    col_file = MAPS / "collision.json"
    with open(col_file, "w", encoding="utf-8") as f:
        json.dump(colliders, f, indent=2)
    print(f"  -> {len(colliders)} colliders disimpan ke {col_file}")

    print("[4/4] Selesai! Peta HD Sunnyside siap digunakan di game.")


if __name__ == "__main__":
    build()
