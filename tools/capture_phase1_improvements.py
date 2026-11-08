"""
tools/capture_phase1_improvements.py - Generator Screenshot Pembuktian Fase 1A & 1B

Menghasilkan bukti tangkapan layar bersih tanpa overlay yang menghalangi:
  1. inventory_ui_newgame.png: Inventori Game Baru (Pedang Biasa, Kain, 20 Koin, 0 Bahan)
  2. shop_ui_buy_scrolled.png: Toko tab BELI ter-scroll ke Halaman 2 (Zirah, Senjata, Jimat)
  3. shop_ui_sell.png: Toko tab JUAL
  4. farm_clean_growth.png: Ladang Barat Laut rapi (progress bar ramping, 1 label aktif, tanpa banner)
  5. gate_route_full.png: Rute koridor chokepoint ke Boss (~600 px, 20 langkah A*, gerbang terkunci vs terbuka)
  6. interact_chicken_coop.png, interact_cow_pasture.png, interact_river_fishing.png,
     interact_forest_wood.png, interact_quarry_rock.png (+ gabungan phase1b_interaction_points.png)
"""

import os
import sys

# Atur environment headless SDL dan pythonpath
os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.abspath("src"))

import pygame
pygame.init()
pygame.display.set_mode((1024, 768))

import config
from asset_catalog import get_asset_catalog
from inventory import Inventory, InventoryUI
from economy import Shop, ShopUI
from farm import FarmManager
from world_state import WorldState, LockedGate
from world.game_map import GameMap
from hero_sprite import get_hero_sprite_manager
from ai.pathfinding import astar
import world_actions

OUT_DIR = os.path.abspath("data/screenshots")
os.makedirs(OUT_DIR, exist_ok=True)


def capture_newgame_inventory():
    print("[1/6] Capturing inventory_ui_newgame.png...")
    ws = WorldState(starting_coins=config.STARTING_COINS)
    ui = InventoryUI()
    ui.is_open = True

    surf = pygame.Surface((1024, 768))
    surf.fill((20, 20, 32))
    ui.draw(surf, ws.inventory, ws.coins)

    path = os.path.join(OUT_DIR, "inventory_ui_newgame.png")
    pygame.image.save(surf, path)
    print(f"  -> Saved {path}")


def capture_shop_ui():
    print("[2/6] Capturing shop_ui_buy_scrolled.png and shop_ui_sell.png...")
    shop = Shop()
    ui = ShopUI()

    # Tas contoh untuk tampilan jual
    inv = Inventory(max_slots=12)
    inv.add_item("radish", 5)
    inv.add_item("wheat", 8)
    inv.add_item("egg", 3)
    inv.add_item("milk", 2)
    inv.add_item("fish", 4)
    inv.add_item("wood", 10)
    inv.add_item("rock", 6)

    # 1. Tab BUY Scrolled ke Halaman 2 (New Game: 20 Koin)
    ui.open()
    ui.active_tab = "BUY"
    ui.page = 1  # Halaman 2
    items_buy = list(shop.catalog.keys())
    ui.selected_item = items_buy[6] if len(items_buy) > 6 else None

    surf_buy = pygame.Surface((1024, 768))
    surf_buy.fill((22, 22, 35))
    ui.draw(surf_buy, shop, inv, 20)
    path_buy = os.path.join(OUT_DIR, "shop_ui_buy_scrolled.png")
    pygame.image.save(surf_buy, path_buy)
    print(f"  -> Saved {path_buy}")

    # 2. Tab SELL (New Game: 20 Koin)
    ui.open()
    ui.active_tab = "SELL"
    ui.page = 0
    sellable = [it for it in shop.sell_prices.keys() if inv.has_item(it)]
    ui.selected_item = sellable[0] if sellable else None

    surf_sell = pygame.Surface((1024, 768))
    surf_sell.fill((22, 22, 35))
    ui.draw(surf_sell, shop, inv, 20)
    path_sell = os.path.join(OUT_DIR, "shop_ui_sell.png")
    pygame.image.save(surf_sell, path_sell)
    print(f"  -> Saved {path_sell}")


def capture_clean_farm():
    print("[3/6] Capturing farm_clean_growth.png...")
    game_map = GameMap(scale=2)
    farm = FarmManager()
    inv = Inventory(max_slots=12)

    # Siapkan 6 petak sejajar grid dengan variasi tahap tumbuh 0..5
    stages = [5, 1, 2, 3, 4, 0]
    crops = ["radish", "wheat", "radish", "wheat", "radish", "wheat"]
    for i, p in enumerate(farm.plots):
        p.crop_type = crops[i]
        p.stage = stages[i]
        if i in (1, 3, 4):
            p.is_watered = True

    surf = pygame.Surface((1024, 768))
    # Kamera berpusat di ladang barat laut (512, 400)
    cam = (512 - 512, 400 - 384)
    game_map.draw(surf, cam)

    # Hero berdiri di samping petak #0 (480, 384) untuk memicu prompt aktif tunggal PANEN [E]
    hero_pos = (454, 388)
    farm.draw(surf, cam, hero_pos, debug_mode=False)

    # Gambar Hero di dekat ladang
    mgr = get_hero_sprite_manager()
    idle_frames = mgr.get_world_frames("idle")
    if idle_frames:
        hx = int(hero_pos[0] - cam[0])
        hy = int(hero_pos[1] - cam[1])
        surf.blit(idle_frames[0], (hx - 24, hy - 24))

    path = os.path.join(OUT_DIR, "farm_clean_growth.png")
    pygame.image.save(surf, path)
    print(f"  -> Saved {path}")


def capture_gate_and_route():
    print("[4/6] Capturing gate_route_full.png...")
    game_map = GameMap(scale=2)
    w, h = 86, 48
    spawn_cell = (1440 // 32, 1056 // 32)
    gate_stand_cell = (2384 // 32, 880 // 32)
    boss_cell = (2464 // 32, 448 // 32)
    gate = LockedGate(x=2336, y=816, w=288, h=48)

    # 1. A* route dari gate ke boss saat gerbang terbuka
    def is_blocked(cx, cy):
        return not game_map.is_walkable_at(cx * 32 + 16, cy * 32 + 16)

    res_route = astar(w, h, gate_stand_cell, boss_cell, is_blocked)

    # Render tampilan berpusat pada koridor chokepoint gerbang
    cam_gate = (2384 - 512, 840 - 384)

    # Surface gabungan 2 panel (Kiri: Gerbang Terkunci | Kanan: Gerbang Terbuka + Rute A* ke Boss)
    combined = pygame.Surface((1024, 768))

    # Panel Kiri: Gerbang Terkunci (Hero berdiri dekat gerbang memicu prompt "Butuh Kunci Gerbang")
    sub_left = pygame.Surface((508, 768))
    game_map.draw(sub_left, cam_gate)
    gate.is_open = False
    hero_gate_pos = (2384, 880)
    gate.draw(sub_left, cam_gate, hero_pos=hero_gate_pos)

    # Gambar Hero berdiri di depan gerbang terkunci
    mgr = get_hero_sprite_manager()
    idle_frames = mgr.get_world_frames("idle")
    if idle_frames:
        ghx = int(hero_gate_pos[0] - cam_gate[0])
        ghy = int(hero_gate_pos[1] - cam_gate[1])
        sub_left.blit(idle_frames[0], (ghx - 24, ghy - 24))

    # Panel Kanan: Gerbang Terbuka + Jalur A*
    sub_right = pygame.Surface((508, 768))
    game_map.draw(sub_right, cam_gate)
    gate.is_open = True
    gate.open_progress = 1.0
    gate.draw(sub_right, cam_gate)

    # Gambar garis lintasan A* menuju Boss
    if res_route.found:
        points = []
        for cx, cy in [gate_stand_cell] + res_route.path:
            sx = int(cx * 32 + 16 - cam_gate[0])
            sy = int(cy * 32 + 16 - cam_gate[1])
            points.append((sx, sy))
        if len(points) >= 2:
            pygame.draw.lines(sub_right, (60, 220, 255), False, points, 4)
            for p in points:
                pygame.draw.circle(sub_right, (255, 230, 80), p, 4)

    # Judul / Tag pada masing-masing panel ditaruh di pojok atas agar tidak menutupi gerbang
    font = pygame.font.Font(None, 22)
    t_left = font.render(f"GERBANG TERKUNCI (Chokepoint 288 px)", True, (255, 140, 140))
    t_right = font.render(f"GERBANG TERBUKA (Rute A*: {len(res_route.path)} Langkah)", True, (120, 255, 120))

    sub_left.blit(t_left, (20, 20))
    sub_right.blit(t_right, (20, 20))

    combined.fill((15, 15, 25))
    combined.blit(sub_left, (0, 0))
    combined.blit(sub_right, (516, 0))
    pygame.draw.line(combined, config.GOLD, (512, 0), (512, 768), 2)

    path = os.path.join(OUT_DIR, "gate_route_full.png")
    pygame.image.save(combined, path)
    print(f"  -> Saved {path}")


def capture_interaction_points_and_animations():
    print("[5/6] Capturing 5 Phase 1B interaction points with hero animations and real animals...")
    from core.map import TileMap
    from asset_loader import AssetManager
    assets = AssetManager()
    tile_map = TileMap(seed=42, assets=assets)
    mgr = get_hero_sprite_manager()
    cat = get_asset_catalog()

    interactions = [
        ("chicken_coop", config.INTERACT_CHICKEN_POS, "doing", "egg", "crop_item", "Kandang Ayam (Ambil Telur)"),
        ("cow_pasture", config.INTERACT_COW_POS, "doing", "milk", "crop_item", "Padang Rumput Sapi (Perah Susu)"),
        ("river_fishing", config.INTERACT_FISHING_POS, "reeling", "fish", "crop_item", "Dermaga Sungai (Mancing Ikan)"),
        ("forest_wood", config.INTERACT_TREE_POS, "axe", "wood", "crop_item", "Tepi Hutan Desa (Tebang Kayu)"),
        ("quarry_rock", config.INTERACT_ROCK_POS, "mining", "rock", "crop_item", "Tebing Reruntuhan (Tambang Batu)"),
    ]

    disc_base = cat.get_ui_icon("itemdisc_01", scale=2)
    font = pygame.font.Font(None, 20)
    font_xs = pygame.font.Font(None, 16)

    composite_w = 320 * 5
    composite = pygame.Surface((composite_w, 360))

    for idx, (name, (px, py), anim, icon_name, icon_src, label) in enumerate(interactions):
        surf = pygame.Surface((320, 360))
        cam = (px - 160, py - 180)
        tile_map.draw(surf, assets, 0.0, cam)

        # Gambar hewan ternak riil di sekitar titik jika ada
        for animal in getattr(tile_map, "animals", []):
            ax = animal.px - cam[0]
            ay = animal.py - cam[1]
            if -32 <= ax <= 352 and -32 <= ay <= 392:
                animal.draw(surf, cam)

        # 1. Gambar Marker Item Disc di lokasi interaksi
        sx = int(px - cam[0])
        sy = int(py - cam[1])
        disc_x = sx - disc_base.get_width() // 2
        disc_y = sy - disc_base.get_height() // 2 + 10
        surf.blit(disc_base, (disc_x, disc_y))

        # Ikon melayang di atas marker disc
        if icon_src == "crop_item":
            icon_surf = cat.get_crop_item(icon_name, scale=1)
        else:
            icon_surf = cat.get_ui_icon(icon_name, scale=1)
        surf.blit(icon_surf, (sx - icon_surf.get_width() // 2, sy - icon_surf.get_height() // 2 - 2))

        # 2. Gambar Hero berdiri di SAMPING marker disc (offset 28 px) sehingga KEDUANYA terlihat utuh
        frames = mgr.get_world_frames(anim)
        if frames:
            frame_idx = min(3, len(frames) - 1)
            hero_frame = frames[frame_idx]
            hx = sx - 32
            hy = sy - 14
            surf.blit(hero_frame, (hx, hy))

        # 3. Label judul & info
        pygame.draw.rect(surf, (20, 20, 32, 220), (10, 10, 300, 48), border_radius=4)
        pygame.draw.rect(surf, config.GOLD, (10, 10, 300, 48), 1, border_radius=4)
        surf.blit(font.render(label, True, config.GOLD), (18, 16))
        surf.blit(font_xs.render(f"Posisi: ({px}, {py}) | Animasi: '{anim}'", True, (180, 230, 255)), (18, 36))

        # Simpan screenshot individual
        single_path = os.path.join(OUT_DIR, f"interact_{name}.png")
        pygame.image.save(surf, single_path)
        print(f"  -> Saved {single_path}")

        # Tempel ke composite
        composite.blit(surf, (idx * 320, 0))
        if idx > 0:
            pygame.draw.line(composite, config.GOLD, (idx * 320, 0), (idx * 320, 360), 2)

    comp_path = os.path.join(OUT_DIR, "phase1b_interaction_points.png")
    pygame.image.save(composite, comp_path)
    print(f"  -> Saved composite {comp_path}")
    pygame.image.save(composite, comp_path)
    print(f"  -> Saved composite {comp_path}")


if __name__ == "__main__":
    print("=== Generating Phase 1A & 1B Verification Screenshots ===")
    capture_newgame_inventory()
    capture_shop_ui()
    capture_clean_farm()
    capture_gate_and_route()
    capture_interaction_points_and_animations()
    print("=== All Verification Screenshots Generated Successfully! ===")
