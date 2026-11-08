"""
capture_phase1a_deliverables.py - Menangkap Screenshot Bersih untuk Bukti Fase 1A

Menghasilkan 4 gambar bukti tanpa tertutup banner/HUD/toast:
  1. farm_growth_stages.png: 6 petak ladang yang menampilkan berbagai tahap tumbuh (benih hingga matang siap panen)
  2. inventory_ui_modal.png: Modal UI tas inventori 12 slot dengan koin dan rincian item
  3. shop_ui_modal.png: Modal UI toko desa dengan katalog beli dan harga koin
  4. gate_locked_and_open.png: Komparasi gerbang reruntuhan sebelum dibuka (gembok merah) dan sesudah dibuka (terbuka hijau)
"""

import os
import sys
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame

pygame.init()
screen = pygame.display.set_mode((1024, 768))

import config
from asset_loader import AssetManager
from asset_catalog import get_asset_catalog
from inventory import Inventory, InventoryUI
from economy import Shop, ShopUI
from farm import FarmManager
from world_state import WorldState, LockedGate
from main import Game

SCREENSHOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "screenshots"))
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
ARTIFACT_DIR = "/home/rarch/.gemini/antigravity/brain/58dcfd1e-5586-448b-9e4c-9fd4826ad39f"


def save_deliverable(surface, filename):
    out_path = os.path.join(SCREENSHOT_DIR, filename)
    pygame.image.save(surface, out_path)
    if os.path.isdir(ARTIFACT_DIR):
        shutil.copy(out_path, os.path.join(ARTIFACT_DIR, filename))
    print(f"[SCREENSHOT] Berhasil disimpan: {out_path}")


def capture_farm_growth():
    assets = AssetManager()
    game = Game(screen, assets)
    # Atur kamera fokus ke petak ladang (x=992, y=736)
    # Area ladang berada di (960..1056, 720..784)
    cam_x = 992 - 1024 // 2
    cam_y = 736 - 768 // 2

    # Konfigurasi tahap tumbuh pada 6 petak ladang agar menunjukkan variasi 0..5
    # Plot 0: Tahap 0 (Baru ditanam, benih)
    # Plot 1: Tahap 1 (Tunas kecil)
    # Plot 2: Tahap 2 (Daun muda)
    # Plot 3: Tahap 3 (Mulai berumbi)
    # Plot 4: Tahap 4 (Daun lebat)
    # Plot 5: Tahap 5 (Matang berbuah siap panen)
    farm = game.world_state.farm
    crops = ["radish", "wheat", "radish", "wheat", "radish", "wheat"]
    for i in range(6):
        plot = farm.plots[i]
        plot.crop_type = crops[i]
        plot.stage = i
        plot.is_watered = (i % 2 == 1)

    # Render dunia murni tanpa HUD, banner, atau pesan log
    screen.fill((0, 0, 0))
    game.game_map.draw(screen, (cam_x, cam_y))
    farm.draw(screen, (cam_x, cam_y))

    # Hero berdiri di tepi ladang melihat hasil kebun
    game.hero.px = 920
    game.hero.py = 736
    game.hero.draw(screen, (cam_x, cam_y))

    # Buat label header informatif kecil di bagian atas yang tidak menutupi ladang
    font = pygame.font.Font(None, 24)
    lbl = font.render("SISTEM LADANG PERTANIAN DESA (6 TAHAP TUMBUH DARI BENIH HINGGA MATANG)", True, config.GOLD)
    screen.blit(lbl, (1024 // 2 - lbl.get_width() // 2, 24))

    save_deliverable(screen, "farm_growth_stages.png")


def capture_inventory_ui():
    assets = AssetManager()
    game = Game(screen, assets)

    # Beri item beragam pada inventori hero
    inv = game.world_state.inventory
    inv.add_item("radish", 12)
    inv.add_item("wheat", 25)
    inv.add_item("egg", 4)
    inv.add_item("milk", 2)
    inv.add_item("potion_red", 3)
    inv.add_item("wood", 18)
    inv.add_item("rock", 14)
    inv.add_item("key", 1)

    # Hover slot 4 (potion_red) untuk menampilkan deskripsi
    inv_ui = game.inventory_ui
    inv_ui.is_open = True
    inv_ui.hover_slot = 4

    # Background peta desa di belakang
    cam_x = 1600 - 1024 // 2
    cam_y = 940 - 768 // 2
    screen.fill((0, 0, 0))
    game.game_map.draw(screen, (cam_x, cam_y))

    # Gambar modal inventori
    inv_ui.draw(screen, inv, game.world_state.coins)

    save_deliverable(screen, "inventory_ui_modal.png")


def capture_shop_ui():
    assets = AssetManager()
    game = Game(screen, assets)

    shop_ui = game.shop_ui
    shop_ui.is_open = True
    shop_ui.selected_item = "Kapak Berat"
    shop_ui.active_tab = "BUY"

    # Background alun-alun desa di belakang
    cam_x = 1600 - 1024 // 2
    cam_y = 940 - 768 // 2
    screen.fill((0, 0, 0))
    game.game_map.draw(screen, (cam_x, cam_y))

    # Gambar modal toko
    shop_ui.draw(screen, game.world_state.shop, game.world_state.inventory, game.world_state.coins)

    save_deliverable(screen, "shop_ui_modal.png")


def capture_gate_locked_and_open():
    assets = AssetManager()
    game = Game(screen, assets)

    # Gerbang berada di archway reruntuhan (x=1856, y=192)
    cam_x = 1856 - 512 // 2
    cam_y = 192 - 768 // 2

    # Buat permukaan komparasi berdampingan (1024 x 768): Kiri = Terkunci, Kanan = Terbuka
    comp_surf = pygame.Surface((1024, 768))

    # --- Sisi Kiri (Terkunci) ---
    left_sub = pygame.Surface((510, 768))
    game.world_state.gate.is_open = False
    game.game_map.draw(left_sub, (cam_x, cam_y))
    game.world_state.gate.draw(left_sub, (cam_x, cam_y))
    # Hero berdiri di depan gerbang dengan tanda gembok
    game.hero.px = 1856
    game.hero.py = 230
    game.hero.draw(left_sub, (cam_x, cam_y))

    font_title = pygame.font.Font(None, 24)
    font_sub = pygame.font.Font(None, 18)
    t1 = font_title.render("GERBANG TERKUNCI RAPAT", True, config.RED)
    s1 = font_sub.render("Membutuhkan Kunci Gerbang (Key)", True, (220, 220, 220))
    left_sub.blit(t1, (255 - t1.get_width() // 2, 30))
    left_sub.blit(s1, (255 - s1.get_width() // 2, 56))

    # --- Sisi Kanan (Terbuka) ---
    right_sub = pygame.Surface((510, 768))
    game.world_state.gate.is_open = True
    game.game_map.draw(right_sub, (cam_x, cam_y))
    game.world_state.gate.draw(right_sub, (cam_x, cam_y))
    # Hero melangkah melewati gerbang terbuka
    game.hero.px = 1856
    game.hero.py = 180
    game.hero.draw(right_sub, (cam_x, cam_y))

    t2 = font_title.render("GERBANG TERBUKA (UNLOCKED)", True, config.GREEN)
    s2 = font_sub.render("Kunci dimasukkan, akses ke Boss terbuka!", True, (220, 220, 220))
    right_sub.blit(t2, (255 - t2.get_width() // 2, 30))
    right_sub.blit(s2, (255 - s2.get_width() // 2, 56))

    # Satukan
    comp_surf.blit(left_sub, (0, 0))
    comp_surf.blit(right_sub, (514, 0))
    pygame.draw.line(comp_surf, config.GOLD, (512, 0), (512, 768), 3)

    save_deliverable(comp_surf, "gate_locked_and_open.png")


if __name__ == "__main__":
    capture_farm_growth()
    capture_inventory_ui()
    capture_shop_ui()
    capture_gate_locked_and_open()
    print("[ALL SCREENSHOTS CAPTURED OK]")

