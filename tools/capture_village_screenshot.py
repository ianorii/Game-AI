#!/usr/bin/env python3
"""
tools/capture_village_screenshot.py - Tangkap Screenshot Dekorasi Desa Sunnyside
"""

import os
import sys

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

    screen = pygame.display.get_surface()
    assets = AssetManager()
    game = Game(screen, assets, seed=42)

    # Letakkan kamera agar kincir angin (1860, 960) dan rumah desa timur (1760, 992) terlihat jelas
    # Viewport ukuran 1024 x 640
    # Kincir di (1860, 960) -> kamera di (1860 - 512, 960 - 320) = (1348, 640)
    target_cam_x = 1360
    target_cam_y = 660
    game.cam_x = float(target_cam_x)
    game.cam_y = float(target_cam_y)
    game.hero.px = 1680.0
    game.hero.py = 920.0

    # Simulasikan beberapa detik agar animasi kincir angin dan asap cerobong berjalan
    for _ in range(30):
        game.update(1.0 / 30.0)

    game.render()

    out_path = os.path.join(out_dir, "village_windmill_smoke.png")
    pygame.image.save(game.screen, out_path)
    print(f"[SCREENSHOT] Berhasil disimpan ke: {out_path}")


if __name__ == "__main__":
    main()
