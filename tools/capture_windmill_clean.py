#!/usr/bin/env python3
"""
tools/capture_windmill_clean.py - Tangkap Screenshot Kincir Angin Bersih (Tanpa HUD/Toast)
"""

import os
import sys
import shutil

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pygame
pygame.init()
pygame.display.set_mode((1024, 768))

import config
from asset_loader import AssetManager
from main import Game


def main():
    out_dir = os.path.join(ROOT_DIR, "data", "screenshots")
    os.makedirs(out_dir, exist_ok=True)
    art_dir = "/home/rarch/.gemini/antigravity/brain/58dcfd1e-5586-448b-9e4c-9fd4826ad39f"

    screen = pygame.display.get_surface()
    assets = AssetManager()
    game = Game(screen, assets, seed=42)

    # Pastikan HUD, banner, toast, dan overlay dinonaktifkan
    game.debug_map_collision = False

    # Crop close-up: menara (1280, 448, 96, 192), hub (1328, 526)
    # Area kincir utuh: x in [1216, 1440], y in [414, 638]
    # Crop box 400 x 340 mencakup seluruh bilah atas, samping, bawah, menara, dan sungai
    crop_w, crop_h = 420, 340
    crop_x = 1328 - crop_w // 2 # 1118
    crop_y = 526 - crop_h // 2 + 10 # 366 (mencakup y dari 366 sampai 706)

    game.cam_x = float(crop_x)
    game.cam_y = float(crop_y)
    # Jauhkan hero sementara dari menara untuk screenshot kincir bersih
    game.hero.px = 800.0
    game.hero.py = 800.0

    frames_to_capture = [
        (0, "windmill_turn_frame0.png", "Frame 0 (Bilah Tegak Lurus / Plus '+')"),
        (3, "windmill_turn_frame3.png", "Frame 3 (Bilah Miring 120 Derajat)"),
        (6, "windmill_turn_frame6.png", "Frame 6 (Bilah Miring 240 Derajat)"),
    ]

    for f_idx, filename, label in frames_to_capture:
        game.village_deco.windmill.frame_idx = float(f_idx)
        # Render world & entities tanpa overlay/HUD
        render_cam = (int(game.cam_x), int(game.cam_y))
        game.game_map.draw(screen, render_cam)
        for obj in sorted(game.village_deco.get_y_sort_entities(), key=lambda o: getattr(o, "sort_y", o.y)):
            obj.draw(screen, render_cam)
        game.village_deco.draw_overhead(screen, render_cam)

        # Ambil subsurface crop
        sub = screen.subsurface(pygame.Rect(0, 0, crop_w, crop_h)).copy()
        target_path = os.path.join(out_dir, filename)
        pygame.image.save(sub, target_path)
        shutil.copy(target_path, os.path.join(art_dir, filename))
        print(f"[OK] Disimpan {filename} ({label})")

    # Screenshot ke-4: Hero berjalan di samping menara (x=1250, y=520) - buktikan tidak tertutup bilah
    game.hero.px = 1245.0
    game.hero.py = 515.0
    game.village_deco.windmill.frame_idx = 0.0 # Bilah horizontal membentang ke kiri (x=1232..1423)
    render_cam = (int(game.cam_x), int(game.cam_y))
    game.game_map.draw(screen, render_cam)

    entities = [game.hero] + game.village_deco.get_y_sort_entities()
    for obj in sorted(entities, key=lambda o: getattr(o, "sort_y", o.py if hasattr(o, "py") else o.y)):
        obj.draw(screen, render_cam)
    game.village_deco.draw_overhead(screen, render_cam)

    hero_beside_sub = screen.subsurface(pygame.Rect(0, 0, crop_w, crop_h)).copy()
    hb_path = os.path.join(out_dir, "windmill_hero_beside_tower.png")
    pygame.image.save(hero_beside_sub, hb_path)
    shutil.copy(hb_path, os.path.join(art_dir, "windmill_hero_beside_tower.png"))
    print("[OK] Disimpan windmill_hero_beside_tower.png (Hero di samping menara tidak tertutup bilah)")


if __name__ == "__main__":
    main()
