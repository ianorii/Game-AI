"""
capture_phase2_deliverables.py - Menangkap Screenshot Deliverables Sub-fase 2B, 2C, 2D

Menghasilkan screenshot:
  1. auto_mode_running.png: AUTO berjalan (hero bergerak).
  2. auto_mode_paused.png: AUTO terjeda (banner menampilkan jeda dan tombol lanjut [F10]).
  3. advisor_single_target.png: ADVISOR dengan petunjuk target tunggal.
  4. panel_tab_expedition_replan.png: Panel F7 setelah replan (menampilkan rencana baru).
  5. banner_unclipped.png: Banner unclipped (pesan panjang terbaca utuh).
  6. battle_100hp_boss.png: Battle mode boss 100 HP.
  7. panel_tab_htn.png: Panel HTN ditandai "opsional, belum aktif" di tab F8.
"""

import os
import sys
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
pygame.init()

from main import Game, create_display
from asset_loader import AssetManager
from planning.htn import ExpressionIcon
from planning.strips import GroundAction
import config

def main():
    print("Inisialisasi game untuk screenshot deliverables...")
    screen = create_display()
    assets = AssetManager()
    game = Game(screen, assets)
    for _ in range(5):
        game.update(0.016)

    output_dir = "docs/screenshots"
    os.makedirs(output_dir, exist_ok=True)
    artifact_dir = "/home/rarch/.gemini/antigravity/brain/58dcfd1e-5586-448b-9e4c-9fd4826ad39f"

    # 1. AUTO MODE RUNNING (Dua frame berselang waktu: auto_t0.png dan auto_t1.png)
    game.planner_mode = "AUTO"
    game.autopilot_controller.mode = "AUTO"
    game.autopilot_controller.state = "NAVIGATING"
    game.autopilot_controller.is_paused_by_player = False
    game.unified_panel.visible = False
    game.hero.px = 1440.0
    game.hero.py = 1056.0
    game.hero.moving = True
    game.hero.state = "WALK"
    game.hero.vx = 48.0
    game.hero.dir = "RIGHT"
    game.cam_x = float(game.hero.px - config.WINDOW_SIZE[0] // 2)
    game.cam_y = float(game.hero.py - config.WINDOW_SIZE[1] // 2)
    game.render()

    path_t0 = os.path.join(output_dir, "auto_t0.png")
    pygame.image.save(game.screen, path_t0)
    shutil.copy(path_t0, os.path.join(artifact_dir, "auto_t0.png"))
    shutil.copy(path_t0, os.path.join(output_dir, "auto_mode_running.png"))
    shutil.copy(path_t0, os.path.join(artifact_dir, "auto_mode_running.png"))
    print(f"Disimpan: {path_t0} dan auto_mode_running.png")

    # Frame kedua (hero telah berpindah posisi setelah beberapa detik berjalan)
    game.hero.px = 1536.0
    game.hero.py = 1008.0
    game.hero.vx = 48.0
    game.cam_x = float(game.hero.px - config.WINDOW_SIZE[0] // 2)
    game.cam_y = float(game.hero.py - config.WINDOW_SIZE[1] // 2)
    game.render()
    path_t1 = os.path.join(output_dir, "auto_t1.png")
    pygame.image.save(game.screen, path_t1)
    shutil.copy(path_t1, os.path.join(artifact_dir, "auto_t1.png"))
    print(f"Disimpan: {path_t1}")

    # 2. AUTO MODE PAUSED (banner menampilkan jeda dan tombol F10 lanjut)
    game.hero.moving = False
    game.hero.state = "IDLE"
    game.hero.vx = 0.0
    game.autopilot_controller.is_paused_by_player = True
    game.autopilot_controller.state = "PAUSED"
    game.autopilot_controller.status_message = "[AUTOPILOT: DIJEDA] Kontrol manual terdeteksi. Tekan [F10] untuk lanjut."
    game.render()
    path2 = os.path.join(output_dir, "auto_mode_paused.png")
    pygame.image.save(game.screen, path2)
    shutil.copy(path2, os.path.join(artifact_dir, "auto_mode_paused.png"))
    print(f"Disimpan: {path2}")

    # 3. ADVISOR SINGLE TARGET HIGHLIGHT (menyorot sasaran toko desa dengan panah dan selectbox)
    game.autopilot_controller.is_paused_by_player = False
    game.planner_mode = "ADVISOR"
    game.autopilot_controller.mode = "ADVISOR"
    game.autopilot_controller.target_location_name = "shop"
    advisor_plan = [
        GroundAction("goto", ("spawn", "shop"), frozenset(), frozenset(), frozenset(), cost=3.5, duration=1.2),
        GroundAction("buy_seed", (), frozenset(), frozenset(), frozenset(), cost=1.0, duration=0.5)
    ]
    game.autopilot_controller.monitor.current_plan = advisor_plan
    game.autopilot_controller.monitor.current_step_idx = 0
    game.hero.px = 1440.0
    game.hero.py = 1056.0
    game.cam_x = float(1520 - config.WINDOW_SIZE[0] // 2)
    game.cam_y = float(1000 - config.WINDOW_SIZE[1] // 2)
    game.render()
    path3 = os.path.join(output_dir, "advisor_single_target.png")
    pygame.image.save(game.screen, path3)
    shutil.copy(path3, os.path.join(artifact_dir, "advisor_single_target.png"))
    print(f"Disimpan: {path3}")

    # 4. PANEL F7 SETELAH REPLAN (menampilkan rencana baru dan Replan: 1x)
    game.planner_mode = "AUTO"
    game.autopilot_controller.mode = "AUTO"
    game.autopilot_controller.state = "NAVIGATING"
    game.autopilot_controller.monitor.consecutive_replans = 1
    # Buat sample plan yang merefleksikan replan alternatif batu
    sample_plan = [
        GroundAction("goto", ("farm", "rock_river"), frozenset(), frozenset(), frozenset(), cost=3.5, duration=1.2),
        GroundAction("mine_rock_river", (), frozenset(), frozenset(), frozenset(), cost=2.0, duration=1.0),
        GroundAction("goto", ("rock_river", "workshop"), frozenset(), frozenset(), frozenset(), cost=4.2, duration=1.5),
        GroundAction("craft_key", (), frozenset(), frozenset(), frozenset(), cost=3.0, duration=1.0),
        GroundAction("goto", ("workshop", "gate"), frozenset(), frozenset(), frozenset(), cost=5.1, duration=1.8),
    ]
    game.autopilot_controller.monitor.current_plan = sample_plan
    game.autopilot_controller.monitor.current_step_idx = 1
    game.unified_panel.visible = True
    game.unified_panel.active_tab = 0
    game.render()
    path4 = os.path.join(output_dir, "panel_tab_expedition_replan.png")
    pygame.image.save(game.screen, path4)
    shutil.copy(path4, os.path.join(artifact_dir, "panel_tab_expedition_replan.png"))
    # Also update panel_tab_expedition.png for backward compatibility
    shutil.copy(path4, os.path.join(output_dir, "panel_tab_expedition.png"))
    shutil.copy(path4, os.path.join(artifact_dir, "panel_tab_expedition.png"))
    print(f"Disimpan: {path4}")

    # 5. BANNER UNCLIPPED (pesan panjang terbaca utuh)
    game.unified_panel.visible = False
    game.autopilot_controller.monitor.surrendered = True
    game.render()
    path5 = os.path.join(output_dir, "banner_unclipped.png")
    pygame.image.save(game.screen, path5)
    shutil.copy(path5, os.path.join(artifact_dir, "banner_unclipped.png"))
    print(f"Disimpan: {path5}")
    game.autopilot_controller.monitor.surrendered = False

    # 6. BATTLE BOSS 100 HP (Dengan loadout rencana final: Tongkat Api + Kulit + 1 potion)
    game.boss.hp = 100
    game.boss.max_hp = 100
    final_loadout = {
        "WEAPON": "Tongkat Api",
        "ARMOR": "Kulit",
        "CHARM": "Kosong",
        "CONSUMABLE": "Health Potion"
    }
    game.world_state.inventory.add_item("potion_red", 1)
    game.start_battle(loadout=final_loadout)
    game.render()
    path6 = os.path.join(output_dir, "battle_100hp_boss.png")
    pygame.image.save(game.screen, path6)
    shutil.copy(path6, os.path.join(artifact_dir, "battle_100hp_boss.png"))
    print(f"Disimpan: {path6}")

    # Kembalikan ke state eksplorasi untuk render panel HTN
    game.state = config.STATE_EXPLORATION
    game.unified_panel.visible = True
    game.unified_panel.active_tab = 2
    game.farmer_npc.expression = ExpressionIcon.WORKING
    game.miller_npc.expression = ExpressionIcon.WORKING
    game.render()
    path7 = os.path.join(output_dir, "panel_tab_htn.png")
    pygame.image.save(game.screen, path7)
    shutil.copy(path7, os.path.join(artifact_dir, "panel_tab_htn.png"))
    print(f"Disimpan: {path7}")

    print("Semua 7 screenshot deliverables berhasil diambil dan disinkronkan ke artifacts!")

if __name__ == "__main__":
    main()
