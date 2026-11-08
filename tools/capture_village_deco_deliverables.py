#!/usr/bin/env python3
"""
tools/capture_village_deco_deliverables.py - Tangkap Screenshot Deliverables Dekorasi Desa

Menghasilkan 3 tangkapan layar verifikasi:
1. data/screenshots/windmill_tower_frames.png:
   Close-up kincir angin terpasang di menara dari 3 frame animasi berbeda (frame 0, 3, 6).
2. data/screenshots/chimney_anchors_f1.png:
   Kolase 7 rumah berasap dengan mode debug F1 menampilkan tanda silang (+) dan label anchor cerobong.
3. data/screenshots/village_full_overview.png:
   Pemandangan desa Sunnyside penuh memperlihatkan kincir berputar di menara dan asap cerobong membubung.
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


def create_windmill_frames_screenshot(game: Game, out_path: str):
    """Menghasilkan perbandingan 3 frame animasi kincir angin terpasang pada menara."""
    # Tower: Rect(1280, 448, 96, 192), Hub: (1328, 526)
    # Crop box sekitar menara: (1170, 420) ukuran 320 x 260
    crop_w, crop_h = 320, 260
    world_cx, world_cy = 1328, 540
    crop_x = world_cx - crop_w // 2
    crop_y = world_cy - crop_h // 2

    # Render frame 0, 3, 6
    target_frames = [0, 3, 6]
    crops = []

    for f_idx in target_frames:
        # Atur timer kincir agar tepat di frame f_idx
        game.village_deco.windmill.timer = float(f_idx) / game.village_deco.windmill.fps
        # Kamera diset agar menara ada di tengah viewport
        game.cam_x = float(crop_x)
        game.cam_y = float(crop_y)
        game.render()

        # Ambil subsurface viewport game (0, 0, crop_w, crop_h)
        screen = pygame.display.get_surface()
        sub = screen.subsurface(pygame.Rect(0, 0, crop_w, crop_h)).copy()
        crops.append(sub)

    # Gabungkan 3 crop secara horizontal
    panel_gap = 10
    pad = 16
    title_h = 44
    total_w = pad * 2 + crop_w * 3 + panel_gap * 2
    total_h = pad * 2 + title_h + crop_h + 30

    composite = pygame.Surface((total_w, total_h))
    composite.fill((27, 27, 47)) # Dark purple-blue

    # Header
    font_lg = pygame.font.Font(None, 24)
    font_sm = pygame.font.Font(None, 18)
    title_txt = font_lg.render("KINCIR ANGIN SUNNYSIDE: TERPASANG DI PUNCAK MENARA (SKALA 2X HD)", True, config.GOLD)
    sub_txt = font_sm.render(f"Lokasi Menara: (1280, 448, 96, 192) | Hub Poros: {config.WINDMILL_HUB_POS} | Y-Sort Base: 640.0", True, (200, 200, 200))
    composite.blit(title_txt, (pad, pad))
    composite.blit(sub_txt, (pad, pad + 22))

    for i, (f_idx, crop_surf) in enumerate(zip(target_frames, crops)):
        px = pad + i * (crop_w + panel_gap)
        py = pad + title_h
        # Border
        pygame.draw.rect(composite, (70, 70, 110), pygame.Rect(px - 1, py - 1, crop_w + 2, crop_h + 2), 1)
        composite.blit(crop_surf, (px, py))

        # Frame label
        lbl = font_sm.render(f"Frame {f_idx + 1}/9 ({int(f_idx * 40)} deg)", True, config.WHITE)
        lbl_rect = lbl.get_rect(center=(px + crop_w // 2, py + crop_h + 14))
        composite.blit(lbl, lbl_rect)

    pygame.image.save(composite, out_path)
    print(f"[OK] Windmill frames screenshot tersimpan di: {out_path}")


def create_chimney_anchors_screenshot(game: Game, out_path: str):
    """Menghasilkan kolase 7 rumah dengan tanda silang F1 debug pada anchor cerobong."""
    # Aktifkan F1 debug overlay
    game.debug_map_collision = True

    # Biarkan asap beranimasi sebentar
    for _ in range(15):
        game.update(0.1)

    # 7 rumah: ambil crop 260x220 untuk masing-masing rumah
    crop_w, crop_h = 270, 210
    house_names = [
        "1. North Farm (948, 142)",
        "2. NE Manor (1742, 230)",
        "3. Central-West House (1070, 614)",
        "4. River Village House (1388, 812)",
        "5. Central Manor (1774, 838)",
        "6. East Village House (1900, 1036)",
        "7. SW Farm (814, 1070)",
    ]

    crops = []
    screen = pygame.display.get_surface()

    for (cx, cy) in config.CHIMNEY_ANCHORS:
        # Posisikan kamera agar cerobong berada sedikit di atas tengah
        game.cam_x = float(cx - crop_w // 2)
        game.cam_y = float(cy - crop_h // 3)
        game.render()
        sub = screen.subsurface(pygame.Rect(0, 0, crop_w, crop_h)).copy()
        crops.append(sub)

    # Susun grid: 4 kolom di atas, 3 di bawah (atau 4x2)
    cols = 4
    rows = 2
    pad = 16
    gap = 12
    title_h = 50
    lbl_h = 24

    cell_w = crop_w
    cell_h = crop_h + lbl_h
    total_w = pad * 2 + cols * cell_w + (cols - 1) * gap
    total_h = pad * 2 + title_h + rows * cell_h + (rows - 1) * gap

    composite = pygame.Surface((total_w, total_h))
    composite.fill((27, 27, 47))

    font_lg = pygame.font.Font(None, 24)
    font_sm = pygame.font.Font(None, 18)
    title_txt = font_lg.render("7 RUMAH CEROBONG ASAP FISIK DENGAN DEBUG ANCHOR F1 & CONTINUOUS STREAM", True, config.CYAN)
    sub_txt = font_sm.render("Tanda silang cyan (+) menandakan ujung atas cerobong tempat keluarnya asap kontinu 3-instance.", True, (200, 200, 200))
    composite.blit(title_txt, (pad, pad))
    composite.blit(sub_txt, (pad, pad + 24))

    for i, (name, crop_surf) in enumerate(zip(house_names, crops)):
        r = i // cols
        c = i % cols
        px = pad + c * (cell_w + gap)
        py = pad + title_h + r * (cell_h + gap)

        # Border
        pygame.draw.rect(composite, (60, 60, 95), pygame.Rect(px - 1, py - 1, cell_w + 2, crop_h + 2), 1)
        composite.blit(crop_surf, (px, py))

        # House title
        lbl = font_sm.render(name, True, config.GOLD)
        composite.blit(lbl, (px + 4, py + crop_h + 4))

    # Matikan kembali F1 debug
    game.debug_map_collision = False

    pygame.image.save(composite, out_path)
    print(f"[OK] Chimney anchors screenshot tersimpan di: {out_path}")


def create_village_overview_screenshot(game: Game, out_path: str):
    """Menghasilkan pemandangan penuh desa dengan kincir dan cerobong asap aktif."""
    game.debug_map_collision = False

    # Posisikan kamera di pusat desa Sunnyside antara sungai, kincir, dan rumah warga
    # Pusat desa sekitar (1420, 640)
    game.cam_x = 1100.0
    game.cam_y = 480.0
    game.hero.px = 1440.0
    game.hero.py = 780.0

    # Simulasikan gerakan & animasi
    for _ in range(45):
        game.update(1.0 / 30.0)

    game.render()
    screen = pygame.display.get_surface()

    pygame.image.save(screen, out_path)
    print(f"[OK] Village overview screenshot tersimpan di: {out_path}")


def main():
    out_dir = os.path.join(ROOT_DIR, "data", "screenshots")
    os.makedirs(out_dir, exist_ok=True)

    screen = pygame.display.get_surface()
    assets = AssetManager()
    game = Game(screen, assets, seed=42)

    windmill_path = os.path.join(out_dir, "windmill_tower_frames.png")
    chimney_path = os.path.join(out_dir, "chimney_anchors_f1.png")
    village_path = os.path.join(out_dir, "village_full_overview.png")

    create_windmill_frames_screenshot(game, windmill_path)
    create_chimney_anchors_screenshot(game, chimney_path)
    create_village_overview_screenshot(game, village_path)

    print("\n[SUKSES] Semua deliverables screenshot dekorasi desa berhasil dibuat!")


if __name__ == "__main__":
    main()

