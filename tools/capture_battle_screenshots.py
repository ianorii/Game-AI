"""
tools/capture_battle_screenshots.py - Generator Screenshot State Battle Mode

Menghasilkan screenshot autentik dari berbagai kondisi Battle Mode:
  1. battle_start.png       : Awal pertempuran, giliran player, HP penuh, 3 potion
  2. battle_boss_turn.png   : Giliran boss [BOSS BERPIKIR (MINIMAX)...]
  3. battle_defend_active.png : DEFEND aktif dengan ikon/badge perisai pada bar HP
  4. battle_potion_zero.png : Potion habis (0), tombol [2] disabled (abu-abu, HABIS)
  5. battle_f3_ai_panel.png : Panel AI Thinking (F3) terbuka dengan metrik & kandidat aksi
  6. battle_victory.png     : Kondisi kemenangan (Boss dikalahkan)
  7. battle_defeat.png      : Kondisi kekalahan (Hero gugur, layar game over respawn)
"""

import os
import sys
from collections import deque

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
pygame.init()
screen = pygame.display.set_mode((1024, 768))

import config
from asset_loader import AssetManager
from ai import adversarial as adv
from core.battle_ui import BattleUI


class MockGame:
    """Mock Game untuk rendering battle UI dengan aset nyata."""
    def __init__(self, assets):
        self.screen = screen
        self.assets = assets
        self.time = 1.0
        self.battle = None
        self.battle_ai = adv.MinimaxBattleAI(depth=3)
        self.battle_ui = BattleUI()
        self.game_over = None


def main():
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "screenshots"))
    os.makedirs(out_dir, exist_ok=True)

    assets = AssetManager()
    game = MockGame(assets)

    # -------------------------------------------------------------------------
    # 1. BATTLE START
    # -------------------------------------------------------------------------
    s_start = adv.BattleState(player_hp=100, boss_hp=120, potion_count=3, turn_number=1)
    game.battle = {
        "state": s_start,
        "phase": "HERO",
        "timer": config.BATTLE_HERO_TURN_TIME,
        "log": deque([
            f"Pertarungan dimulai! Hadapi {config.BOSS_NAME}!",
            "Giliran Hero: Pilih aksi [1] Serang, [2] Potion, [3] Bertahan"
        ], maxlen=14),
        "chosen": "-"
    }
    game.time = 0.4
    game.battle_ui.anim_state = "IDLE"
    game.battle_ui.hero_offset_x = 0.0
    game.battle_ui.boss_offset_x = 0.0
    game.battle_ui.slash_vfx_timer = 0.0
    game.battle_ui.telegraph_timer = 0.0
    game.battle_ui.selected_action_index = 0
    game.battle_ui.show_ai_panel = False
    game.battle_ui.floating_texts.clear()
    game.battle_ui.particles.clear()

    screen.fill(config.BLACK)
    game.battle_ui.draw(screen, game)
    p1 = os.path.join(out_dir, "battle_start.png")
    pygame.image.save(screen, p1)
    print(f"[OK] Saved {p1}")

    # -------------------------------------------------------------------------
    # 2. HERO ATTACK (FRAME SLASH & TOOLS_ATTACK_STRIP10 VFX)
    # -------------------------------------------------------------------------
    s_atk = adv.BattleState(player_hp=100, boss_hp=99, potion_count=3, turn_number=1)
    game.battle = {
        "state": s_atk,
        "phase": "HERO",
        "timer": 0.5,
        "log": deque([
            f"Pertarungan dimulai! Hadapi {config.BOSS_NAME}!",
            "Hero melancarkan serangan pedang!",
            "Hero ATTACK -> Boss -21 HP!"
        ], maxlen=14),
        "chosen": "ATTACK"
    }
    game.time = 0.5  # Frame 5 dari attack strip (puncak tebasan pedang)
    game.battle_ui.anim_state = "HERO_SLASH"
    game.battle_ui.hero_offset_x = 75.0
    game.battle_ui.boss_offset_x = 0.0
    game.battle_ui.slash_vfx_timer = 0.12
    game.battle_ui.boss_flash = 0.20
    game.battle_ui.selected_action_index = 0
    game.battle_ui.show_ai_panel = False
    game.battle_ui.floating_texts.clear()
    game.battle_ui.particles.clear()
    game.battle_ui.spawn_floating_text("-21 HP", config.BATTLE_BOSS_POS[0], config.BATTLE_BOSS_POS[1] - 180, config.RED)
    game.battle_ui.spawn_particles(config.BATTLE_BOSS_POS[0], config.BATTLE_BOSS_POS[1] - 90, (255, 90, 90), count=16)

    screen.fill(config.BLACK)
    game.battle_ui.draw(screen, game)
    p_atk = os.path.join(out_dir, "battle_hero_attack.png")
    pygame.image.save(screen, p_atk)
    print(f"[OK] Saved {p_atk}")

    # -------------------------------------------------------------------------
    # 3. BOSS TURN (TELEGRAPH HEAVY ATTACK)
    # -------------------------------------------------------------------------
    s_boss = adv.BattleState(player_hp=95, boss_hp=99, potion_count=3, turn_number=2)
    game.battle = {
        "state": s_boss,
        "phase": "BOSS",
        "timer": config.BATTLE_BOSS_DELAY,
        "log": deque([
            f"Pertarungan dimulai! Hadapi {config.BOSS_NAME}!",
            "Hero PHYSICAL ATTACK -> Boss -21 HP",
            "PERINGATAN: Boss mengumpulkan energi untuk HEAVY ATTACK!"
        ], maxlen=14),
        "chosen": "HEAVY_ATTACK"
    }
    game.time = 0.2
    game.battle_ui.anim_state = "BOSS_TELEGRAPH"
    game.battle_ui.hero_offset_x = 0.0
    game.battle_ui.boss_offset_x = 0.0
    game.battle_ui.slash_vfx_timer = 0.0
    game.battle_ui.telegraph_timer = 0.28
    game.battle_ui.boss_flash = 0.0
    game.battle_ui.selected_action_index = 0
    game.battle_ui.show_ai_panel = False
    game.battle_ui.floating_texts.clear()
    game.battle_ui.particles.clear()
    game.battle_ui.spawn_floating_text("! HEAVY TELEGRAPH !", config.BATTLE_BOSS_POS[0], config.BATTLE_BOSS_POS[1] - 180, config.RED)
    game.battle_ai.choose_move(s_boss)

    screen.fill(config.BLACK)
    game.battle_ui.draw(screen, game)
    p2 = os.path.join(out_dir, "battle_boss_turn.png")
    pygame.image.save(screen, p2)
    print(f"[OK] Saved {p2}")

    # -------------------------------------------------------------------------
    # 4. DEFEND ACTIVE (SHIELD ICON & BADGE)
    # -------------------------------------------------------------------------
    s_def = adv.BattleState(player_hp=75, boss_hp=90, potion_count=2, player_defending=True, turn_number=3)
    game.battle = {
        "state": s_def,
        "phase": "HERO",
        "timer": config.BATTLE_HERO_TURN_TIME,
        "log": deque([
            "Hero PHYSICAL ATTACK -> Boss -21 HP",
            "Boss ATTACK -> Hero -15 HP",
            "Hero DEFEND -> Menahan 60% damage serangan lawan berikutnya!"
        ], maxlen=14),
        "chosen": "-"
    }
    game.time = 0.0
    game.battle_ui.anim_state = "IDLE"
    game.battle_ui.hero_offset_x = 0.0
    game.battle_ui.boss_offset_x = 0.0
    game.battle_ui.slash_vfx_timer = 0.0
    game.battle_ui.telegraph_timer = 0.0
    game.battle_ui.selected_action_index = 2
    game.battle_ui.show_ai_panel = False
    game.battle_ui.floating_texts.clear()
    game.battle_ui.particles.clear()
    game.battle_ui.spawn_floating_text("DEFEND (-60%)", config.BATTLE_HERO_POS[0], config.BATTLE_HERO_POS[1] - 80, config.CYAN)

    screen.fill(config.BLACK)
    game.battle_ui.draw(screen, game)
    p3 = os.path.join(out_dir, "battle_defend_active.png")
    pygame.image.save(screen, p3)
    print(f"[OK] Saved {p3}")

    # -------------------------------------------------------------------------
    # 4. POTION ZERO (DISABLED STATE)
    # -------------------------------------------------------------------------
    s_no_pot = adv.BattleState(player_hp=45, boss_hp=65, potion_count=0, turn_number=6)
    game.battle = {
        "state": s_no_pot,
        "phase": "HERO",
        "timer": config.BATTLE_HERO_TURN_TIME,
        "log": deque([
            "Hero minum POTION -> Pulih +30 HP (Sisa: 0)",
            "Boss HEAVY ATTACK! -> Hero -40 HP hantaman telak!",
            "Semua botol POTION milik Hero telah habis!",
            "Hero harus berjuang tanpa pemulihan HP!"
        ], maxlen=14),
        "chosen": "-"
    }
    game.battle_ui.selected_action_index = 1
    game.battle_ui.show_ai_panel = False
    game.battle_ui.floating_texts.clear()

    screen.fill(config.BLACK)
    game.battle_ui.draw(screen, game)
    p4 = os.path.join(out_dir, "battle_potion_zero.png")
    pygame.image.save(screen, p4)
    print(f"[OK] Saved {p4}")

    # -------------------------------------------------------------------------
    # 5. F3 AI PANEL OPEN
    # -------------------------------------------------------------------------
    s_ai = adv.BattleState(player_hp=60, boss_hp=55, potion_count=1, boss_heal_count=1, boss_heavy_cd=0, turn_number=8)
    game.battle = {
        "state": s_ai,
        "phase": "BOSS",
        "timer": config.BATTLE_BOSS_DELAY,
        "log": deque([
            "Hero ATTACK -> Boss -21 HP",
            "Boss HEAL -> Memulihkan +20 HP",
            "Hero ATTACK -> Boss -21 HP",
            "Boss mengevaluasi pohon keputusan Minimax [F3]..."
        ], maxlen=14),
        "chosen": "HEAVY_ATTACK"
    }
    game.battle_ui.show_ai_panel = True
    game.battle_ai.choose_move(s_ai)

    screen.fill(config.BLACK)
    game.battle_ui.draw(screen, game)
    p5 = os.path.join(out_dir, "battle_f3_ai_panel.png")
    pygame.image.save(screen, p5)
    print(f"[OK] Saved {p5}")

    # -------------------------------------------------------------------------
    # 6. VICTORY
    # -------------------------------------------------------------------------
    s_win = adv.BattleState(player_hp=70, boss_hp=0, potion_count=1, turn_number=10)
    game.battle = {
        "state": s_win,
        "phase": "HERO",
        "timer": 0.0,
        "log": deque([
            "Hero ATTACK -> Boss -24 HP!",
            f"BOSS {config.BOSS_NAME} TERKALAHKAN!",
            "Core dungeon berhasil diamankan oleh sang Hero!"
        ], maxlen=14),
        "chosen": "-"
    }
    game.battle_ui.show_ai_panel = False
    game.game_over = "HERO"

    screen.fill(config.BLACK)
    game.battle_ui.draw(screen, game)
    game.battle_ui.draw_game_over(screen, game)
    p6 = os.path.join(out_dir, "battle_victory.png")
    pygame.image.save(screen, p6)
    print(f"[OK] Saved {p6}")

    # -------------------------------------------------------------------------
    # 7. DEFEAT (GAME OVER)
    # -------------------------------------------------------------------------
    s_lose = adv.BattleState(player_hp=0, boss_hp=45, potion_count=0, turn_number=9)
    game.battle = {
        "state": s_lose,
        "phase": "HERO",
        "timer": 0.0,
        "log": deque([
            "Boss HEAVY ATTACK! -> Hero -40 HP!",
            "Hero tidak berdaya dan gugur di arena pertempuran!",
            "Pertarungan berakhir - Tekan [R] untuk respawn."
        ], maxlen=14),
        "chosen": "-"
    }
    game.battle_ui.show_ai_panel = False
    game.game_over = "OVERSEER"

    screen.fill(config.BLACK)
    game.battle_ui.draw(screen, game)
    game.battle_ui.draw_game_over(screen, game)
    p7 = os.path.join(out_dir, "battle_defeat.png")
    pygame.image.save(screen, p7)
    print(f"[OK] Saved {p7}")


if __name__ == "__main__":
    main()

