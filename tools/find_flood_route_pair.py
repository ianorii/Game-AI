#!/usr/bin/env python3
"""
tools/find_flood_route_pair.py
Menganalisis peta untuk menemukan pasangan lokasi di config.LOCATIONS yang memiliki:
1. Rute cepat (melewati zona rawan banjir di tepi air/pantai)
2. Rute aman (menghindari zona rawan banjir, >= 20% lebih lama)
"""
import os
import sys
import math
import pygame

sys.path.insert(0, os.path.abspath("src"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import config
from asset_loader import AssetManager
from main import Game
from ai.pathfinding import astar

def analyze_routes():
    pygame.init()
    config.VERBOSE_SPRITE_LOGS = False
    screen = pygame.display.set_mode(config.WINDOW_SIZE)
    game = Game(screen, AssetManager())
    game_map = game.game_map

    w_tiles = game_map.width // config.TILE_SIZE
    h_tiles = game_map.height // config.TILE_SIZE
    tile_size = config.TILE_SIZE

    # Identifikasi zona rawan banjir: tile walkable yang berjarak 1-2 tile dari air (non-walkable water)
    flood_risk_cells = set()
    water_cells = set()

    for cy in range(h_tiles):
        for cx in range(w_tiles):
            foot = pygame.Rect(cx * tile_size + 9, cy * tile_size + 23, 14, 8)
            if not game_map.can_stand(foot):
                water_cells.add((cx, cy))

    for cy in range(h_tiles):
        for cx in range(w_tiles):
            foot = pygame.Rect(cx * tile_size + 9, cy * tile_size + 23, 14, 8)
            if game_map.can_stand(foot):
                # Cek jarak ke air (cincin 1-2 tile)
                is_near_water = False
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        if dx == 0 and dy == 0:
                            continue
                        dist_sq = dx*dx + dy*dy
                        if dist_sq <= 5:  # radius <= 2.23 tile
                            nb = (cx + dx, cy + dy)
                            if nb in water_cells:
                                is_near_water = True
                                break
                    if is_near_water:
                        break
                if is_near_water:
                    flood_risk_cells.add((cx, cy))

    print(f"[Analisis Peta] Ukuran: {w_tiles}x{h_tiles} tiles. Total walkable cells dekat air (zona rawan): {len(flood_risk_cells)}")

    # Fungsi is_blocked biasa
    def is_blocked_normal(cx: int, cy: int) -> bool:
        if cx < 0 or cx >= w_tiles or cy < 0 or cy >= h_tiles:
            return True
        foot = pygame.Rect(cx * tile_size + 9, cy * tile_size + 23, 14, 8)
        return not game_map.can_stand(foot)

    # Fungsi is_blocked aman (memblokir zona rawan banjir)
    def is_blocked_safe(cx: int, cy: int) -> bool:
        if is_blocked_normal(cx, cy):
            return True
        return (cx, cy) in flood_risk_cells

    locs = config.LOCATIONS
    results = []

    loc_keys = list(locs.keys())
    for i in range(len(loc_keys)):
        for j in range(i + 1, len(loc_keys)):
            loc_a = loc_keys[i]
            loc_b = loc_keys[j]
            pos_a = locs[loc_a]
            pos_b = locs[loc_b]

            cell_a = (int(pos_a[0] // tile_size), int(pos_a[1] // tile_size))
            cell_b = (int(pos_b[0] // tile_size), int(pos_b[1] // tile_size))

            # Snap cell jika pos awal/akhir kena is_blocked
            if is_blocked_normal(*cell_a) or is_blocked_normal(*cell_b):
                continue

            # Rute Cepat (Normal)
            res_fast = astar(w_tiles, h_tiles, cell_a, cell_b, is_blocked_normal)
            if not res_fast.found or not res_fast.path:
                continue

            # Hitung seberapa banyak cell rute cepat melewati zona rawan
            risk_cells_in_path = [c for c in res_fast.path if c in flood_risk_cells]
            if len(risk_cells_in_path) < 3:
                # Kurang signifikan melewati zona rawan
                continue

            # Rute Aman (Menghindari zona rawan)
            # Jika cell_a atau cell_b ada di zona rawan, izinkan start dan goal tetap
            def is_blocked_safe_pair(cx: int, cy: int) -> bool:
                if (cx, cy) in (cell_a, cell_b):
                    return False
                return is_blocked_safe(cx, cy)

            res_safe = astar(w_tiles, h_tiles, cell_a, cell_b, is_blocked_safe_pair)
            if not res_safe.found or not res_safe.path:
                continue

            len_fast = len(res_fast.path)
            len_safe = len(res_safe.path)
            ratio = len_safe / len_fast

            if ratio >= 1.20:
                speed_px_per_sec = 80.0
                time_fast = (len_fast * tile_size) / speed_px_per_sec
                time_safe = (len_safe * tile_size) / speed_px_per_sec
                results.append({
                    "pair": (loc_a, loc_b),
                    "cell_a": cell_a,
                    "cell_b": cell_b,
                    "len_fast_tiles": len_fast,
                    "len_safe_tiles": len_safe,
                    "time_fast_sec": round(time_fast, 2),
                    "time_safe_sec": round(time_safe, 2),
                    "ratio": round(ratio, 2),
                    "risk_tile_count": len(risk_cells_in_path)
                })

    # Urutkan berdasarkan rasio dan relevansi
    results.sort(key=lambda r: (r["risk_tile_count"], r["ratio"]), reverse=True)
    print(f"\n[HASIL] Ditemukan {len(results)} pasangan lokasi yang memenuhi syarat (ratio >= 1.20x):\n")
    for r in results[:10]:
        print(f"Pasangan: {r['pair'][0]} <-> {r['pair'][1]}")
        print(f"  - Rute Cepat (Pintas): {r['len_fast_tiles']} tiles ({r['time_fast_sec']}s), {r['risk_tile_count']} tile rawan banjir")
        print(f"  - Rute Aman  (Raya)  : {r['len_safe_tiles']} tiles ({r['time_safe_sec']}s)")
        print(f"  - Rasio Jarak/Waktu  : {r['ratio']}x (+{round((r['ratio']-1)*100)}% lebih lama)")
        print("-" * 50)

if __name__ == "__main__":
    analyze_routes()

