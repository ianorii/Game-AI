"""
capture_debug_overlay_screenshots.py

Menangkap 3 screenshot bukti visual implementasi Debug Overlay Dual-Layer:
1. screen_overlay_planning.png: Tab [F7] Planning Inspector (STRIPS PDDL live)
2. screen_overlay_uncertainty.png: Tab [F8] Decisions Under Uncertainty (Bayesian MEU live)
3. screen_overlay_spatial.png: Layer 2 In-World Spatial Visualizer [G] (Jalur A*, Zona Banjir, Percabangan)
"""

import os
import sys
import shutil

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
pygame.init()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import config
from asset_catalog import get_asset_catalog
from main import Game, create_display, AssetManager

ARTIFACT_DIR = "/home/rarch/.gemini/antigravity/brain/53718f08-2a7c-4520-a4aa-4f1689c4f2d4"
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def main():
    screen = create_display()
    assets = AssetManager()

    # =========================================================================
    # 1. SCREENSHOT TAB 0: PLANNING INSPECTOR [F7]
    # =========================================================================
    print("[CAPTURE] Menyiapkan visualisasi Tab 0 (Planning Inspector)...")
    game1 = Game(screen, assets, seed=42)
    # Jalankan autopilot 1 langkah agar goal dan schema terisi live
    game1.planner_mode = "AUTO"
    game1.autopilot_controller.mode = "AUTO"
    game1.autopilot_controller._request_new_plan()
    game1.unified_panel.visible = True
    game1.unified_panel.active_tab = 0
    game1.render()
    pygame.display.flip()

    p0_path = os.path.join(SCREENSHOT_DIR, "screen_overlay_planning.png")
    pygame.image.save(screen, p0_path)
    shutil.copy(p0_path, os.path.join(ARTIFACT_DIR, "screen_overlay_planning.png"))
    print(f"  -> Tersimpan: {p0_path}")

    # =========================================================================
    # 2. SCREENSHOT TAB 3: DECISIONS UNDER UNCERTAINTY [F8]
    # =========================================================================
    print("[CAPTURE] Menyiapkan visualisasi Tab 3 (Uncertainty Inspector)...")
    game2 = Game(screen, assets, seed=42)
    game2.weather_manager.forced_evidence = "air mulai naik"
    game2.weather_manager.read_notice_board()  # Bayesian update -> P=50%
    game2.unified_panel.visible = True
    game2.unified_panel.active_tab = 3
    game2.render()
    pygame.display.flip()

    p3_path = os.path.join(SCREENSHOT_DIR, "screen_overlay_uncertainty.png")
    pygame.image.save(screen, p3_path)
    shutil.copy(p3_path, os.path.join(ARTIFACT_DIR, "screen_overlay_uncertainty.png"))
    print(f"  -> Tersimpan: {p3_path}")

    # =========================================================================
    # 3. SCREENSHOT LAYER 2: SPATIAL DEBUG OVERLAY [G]
    # =========================================================================
    print("[CAPTURE] Menyiapkan visualisasi Layer 2 (Spatial Debug Overlay)...")
    game3 = Game(screen, assets, seed=42)
    game3.weather_manager.forced_evidence = "air mulai naik"
    game3.weather_manager.read_notice_board()
    game3.show_spatial_debug = True
    game3.unified_panel.visible = False
    # Posisikan hero di sekitar koridor pantai (2100, 880) agar kamera terpusat pada percabangan dan zona banjir
    game3.hero.px = 2100.0
    game3.hero.py = 880.0
    game3._snap_camera()
    # Beri rute aktif ke hero agar polyline tergambar jelas
    if game3.autopilot_controller:
        game3.autopilot_controller.current_path = [
            (53, 29), (54, 29), (55, 29), (56, 28), (57, 28), (58, 28), (59, 28),
            (60, 27), (61, 27), (62, 27), (63, 27), (64, 27), (65, 27), (66, 26),
            (67, 26), (68, 26), (69, 25), (70, 25), (71, 24), (72, 23), (73, 22),
            (74, 21), (75, 20), (76, 19), (77, 18), (78, 17), (78, 16)
        ]
    game3.render()
    pygame.display.flip()

    ps_path = os.path.join(SCREENSHOT_DIR, "screen_overlay_spatial.png")
    pygame.image.save(screen, ps_path)
    shutil.copy(ps_path, os.path.join(ARTIFACT_DIR, "screen_overlay_spatial.png"))
    print(f"  -> Tersimpan: {ps_path}")

    print("[SUCCESS] Seluruh 3 screenshot berhasil ditangkap dan disimpan!")

if __name__ == "__main__":
    main()
