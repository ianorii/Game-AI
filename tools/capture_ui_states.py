#!/usr/bin/env python3
"""
tools/capture_ui_states.py
Menghasilkan 5 tangkapan layar state UI & dunia sesuai arahan Claude:
1. screen_manual.png: State kontrol manual (top bar [MANUAL [TAB]], HUD 4 kolom)
2. screen_auto.png: State autopilot/advisor (top bar [AI AUTO], advisor banner, waypoint route)
3. screen_f7_open.png: Panel F7 terbuka (docked di kanan x=660..1020 tanpa tumpang tindih)
4. screen_prompt_locked.png: Hero di depan gerbang tanpa kunci (pill TERKUNCI merah + hint crafting)
5. screen_prompt_active.png: Hero di depan gerbang membawa kunci (pill hijau [E] Buka Gerbang)
"""
import os
import sys
import pygame
import shutil

sys.path.insert(0, "src")
sys.path.insert(0, ".")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
pygame.init()

from main import create_display, Game
from asset_loader import AssetManager
import config

ARTIFACT_DIR = "/home/rarch/.gemini/antigravity/brain/53718f08-2a7c-4520-a4aa-4f1689c4f2d4"
os.makedirs("docs/screenshots", exist_ok=True)
os.makedirs(ARTIFACT_DIR, exist_ok=True)

screen = create_display()
assets = AssetManager()
game = Game(screen, assets, seed=20261021)
game.time = 6.0
game.messages.clear()

def save_and_copy(filename):
    p_docs = os.path.join("docs", "screenshots", filename)
    p_art = os.path.join(ARTIFACT_DIR, filename)
    pygame.image.save(screen, p_docs)
    shutil.copy2(p_docs, p_art)
    print(f"  -> Disimpan: {p_docs} & {p_art}")

# 1. State Manual
print("[1/5] Mengambil screenshot State Manual...")
game.control_mode = config.CONTROL_MANUAL
game.planner_mode = "OFF"
game.hero.px = 1440.0
game.hero.py = 1056.0
game._snap_camera()
game.render()
save_and_copy("screen_manual.png")

# 2. State Auto (dengan Advisor Banner)
print("[2/5] Mengambil screenshot State Auto...")
game.control_mode = config.CONTROL_AUTOPILOT
game.planner_mode = "AUTO"
game.hero.px = 1440.0
game.hero.py = 1056.0
game._snap_camera()
game.render()
save_and_copy("screen_auto.png")

# 3. State Panel F7 Terbuka
print("[3/5] Mengambil screenshot State Panel F7 Terbuka...")
game.show_planner_panel = True
game.planner_panel_tab = 0
game.render()
save_and_copy("screen_f7_open.png")
game.show_planner_panel = False

# 4. State Prompt Terkunci (di depan gerbang tanpa kunci)
print("[4/5] Mengambil screenshot State Prompt Terkunci...")
game.hero.px = 2544.0
game.hero.py = 560.0
game.hero.direction = "up"
game.control_mode = config.CONTROL_MANUAL
game.planner_mode = "OFF"
game.world_state.inventory.remove_item("gate_key", 99)
game.world_state.gate.is_open = False
game._snap_camera()
game._check_world_interactions()
game.render()
save_and_copy("screen_prompt_locked.png")

# 5. State Prompt Aktif (di depan gerbang membawa kunci)
print("[5/5] Mengambil screenshot State Prompt Aktif...")
game.world_state.inventory.add_item("gate_key", 1)
game.world_state.gate.is_open = False
game._check_world_interactions()
game.render()
save_and_copy("screen_prompt_active.png")

print("SELESAI! Seluruh 5 tangkapan layar UI state berhasil diambil.")

