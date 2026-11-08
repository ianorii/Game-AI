"""
test_battle_mode.py - Unit tests untuk Turn-Based Boss Battle & Adversarial Search

Memverifikasi:
  1. Geometri UI: tidak ada tumpang tindih (0 overlap) antar Rect elemen battle.
  2. Aksi player: strictly 3 (ATTACK, POTION, DEFEND), POTION disabled saat 0.
  3. Defend: mengurangi damage 60% dan hanya berlaku 1 giliran lawan.
  4. Boss actions: ATTACK, HEAVY_ATTACK (cd 3), DEFEND, HEAL (maks 2x).
  5. Minimax AI: candidate scores dihitung untuk semua opsi aksi boss.
  6. Determinisme search vs variasi eksekusi nyata.
  7. Batas maksimal 50 ronde.
"""

import os
import random
import sys
import unittest

# Pastikan path modul terdeteksi
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
pygame.init()
pygame.display.set_mode((100, 100), pygame.HIDDEN)

import config
from ai import adversarial as adv
from core.battle_ui import get_battle_layout_rects, BattleUI


class TestBattleRulesAndActions(unittest.TestCase):
    """Pengujian logika battle state, aksi player & boss, serta determinisme."""

    def setUp(self):
        self.state = adv.BattleState(
            player_hp=100,
            player_max_hp=100,
            boss_hp=120,
            boss_max_hp=120,
            potion_count=3,
            boss_heal_count=2,
            boss_heavy_cd=0,
            turn_number=1
        )

    def test_player_actions_strictly_three(self):
        """Player HANYA memiliki 3 aksi sah: ATTACK, POTION, DEFEND."""
        acts = adv.hero_actions(self.state)
        self.assertEqual(len(acts), 3)
        self.assertEqual(set(acts), {"ATTACK", "POTION", "DEFEND"})

        # Pastikan aksi legacy tidak ada
        for legacy in ("HEAVY", "HEAVY_STRIKE", "BUFF", "CAST_MAGIC", "GUARD"):
            self.assertNotIn(legacy, acts)

    def test_potion_disabled_at_zero(self):
        """Saat potion = 0, POTION tidak boleh ada di hero_actions."""
        s = self.state.clone()
        s.potion_count = 0
        acts = adv.hero_actions(s)
        self.assertNotIn("POTION", acts)
        self.assertEqual(acts, ["ATTACK", "DEFEND"])

        # Mencoba minum saat 0 tidak menambah HP
        s.player_hp = 50
        s_after, _ = adv.apply_action(s, "player", "POTION", rng=None)
        self.assertEqual(s_after.player_hp, 50)
        self.assertEqual(s_after.potion_count, 0)

    def test_potion_heals_correctly(self):
        """Potion memulihkan 30 HP dan mengurangi jumlah potion."""
        s = self.state.clone()
        s.player_hp = 50
        s_after, _ = adv.apply_action(s, "player", "POTION", rng=None)
        self.assertEqual(s_after.player_hp, 80)
        self.assertEqual(s_after.potion_count, 2)

        # Capped pada player_max_hp
        s_after.player_hp = 95
        s_capped, _ = adv.apply_action(s_after, "player", "POTION", rng=None)
        self.assertEqual(s_capped.player_hp, 100)

    def test_player_defend_lasts_one_turn(self):
        """DEFEND mengurangi damage 60% dan hilang setelah giliran lawan selesai."""
        s = self.state.clone()
        # Player memilih DEFEND
        s_def, _ = adv.apply_action(s, "player", "DEFEND", rng=None)
        self.assertTrue(s_def.player_defending)

        # Boss menyerang dengan normal ATTACK
        # Damage terpotong 60%: expected * (1 - 0.60)
        s_hit, _ = adv.apply_action(s_def, "boss", "ATTACK", rng=None)
        expected_dmg = int(config.BOSS_ATTACK_EXPECTED * (1.0 - config.HERO_DEFEND_REDUCE))
        self.assertEqual(s_hit.player_hp, 100 - expected_dmg)

        # Setelah giliran boss selesai, player_defending harus kembali False
        self.assertFalse(s_hit.player_defending)

        # Serangan boss berikutnya menghasilkan damage penuh
        s_full, _ = adv.apply_action(s_hit, "boss", "ATTACK", rng=None)
        self.assertEqual(s_full.player_hp, 100 - expected_dmg - config.BOSS_ATTACK_EXPECTED)

    def test_boss_heavy_attack_defend_reduction(self):
        """HEAVY ATTACK hanya dipotong 30% oleh DEFEND (bukan 60%)."""
        s = self.state.clone()
        s_def, _ = adv.apply_action(s, "player", "DEFEND", rng=None)

        # Boss HEAVY_ATTACK
        # Dengan defend: HEAVY_DMG * (1 - 0.30)
        s_hit, _ = adv.apply_action(s_def, "boss", "HEAVY_ATTACK", rng=None)
        expected_heavy = int(config.BOSS_HEAVY_DMG * (1.0 - config.BOSS_HEAVY_GUARD_REDUCE))
        self.assertEqual(s_hit.player_hp, 100 - expected_heavy)
        self.assertEqual(s_hit.boss_heavy_cd, 3)

    def test_boss_heavy_attack_cooldown(self):
        """HEAVY ATTACK memiliki cooldown 3 giliran."""
        s = self.state.clone()
        s_used, _ = adv.apply_action(s, "boss", "HEAVY_ATTACK", rng=None)
        self.assertEqual(s_used.boss_heavy_cd, 3)
        self.assertNotIn("HEAVY_ATTACK", adv.boss_actions(s_used))

        # Turun 1 per giliran boss
        s_t1, _ = adv.apply_action(s_used, "boss", "ATTACK", rng=None)
        self.assertEqual(s_t1.boss_heavy_cd, 2)
        s_t2, _ = adv.apply_action(s_t1, "boss", "ATTACK", rng=None)
        self.assertEqual(s_t2.boss_heavy_cd, 1)
        s_t3, _ = adv.apply_action(s_t2, "boss", "ATTACK", rng=None)
        self.assertEqual(s_t3.boss_heavy_cd, 0)
        self.assertIn("HEAVY_ATTACK", adv.boss_actions(s_t3))

    def test_boss_heal_limits(self):
        """Boss HEAL hanya tersedia jika HP belum penuh dan sisa heal > 0 (maks 2x)."""
        s = self.state.clone()
        # HP masih penuh -> HEAL tidak tersedia
        self.assertNotIn("HEAL", adv.boss_actions(s))

        # Terkena damage
        s.boss_hp = 80
        self.assertIn("HEAL", adv.boss_actions(s))

        # Pakai 1x
        s1, _ = adv.apply_action(s, "boss", "HEAL", rng=None)
        self.assertEqual(s1.boss_hp, 80 + config.BOSS_HEAL_AMOUNT)
        self.assertEqual(s1.boss_heal_count, 1)

        # Pakai 2x
        s1.boss_hp = 80
        s2, _ = adv.apply_action(s1, "boss", "HEAL", rng=None)
        self.assertEqual(s2.boss_hp, 80 + config.BOSS_HEAL_AMOUNT)
        self.assertEqual(s2.boss_heal_count, 0)

        # Heal habis -> tidak ada lagi di actions
        s2.boss_hp = 80
        self.assertNotIn("HEAL", adv.boss_actions(s2))

    def test_deterministic_search_vs_random_execution(self):
        """Search deterministik (rng=None) menggunakan nilai rata-rata, sedangkan rng menghasilkan variasi."""
        s = self.state.clone()
        # Player ATTACK deterministik = 21
        s_det, _ = adv.apply_action(s, "player", "ATTACK", rng=None)
        self.assertEqual(s_det.boss_hp, self.state.boss_hp - 21)

        # Boss ATTACK deterministik
        s_boss_det, _ = adv.apply_action(s, "boss", "ATTACK", rng=None)
        self.assertEqual(s_boss_det.player_hp, 100 - config.BOSS_ATTACK_EXPECTED)

        # Eksekusi dengan RNG bervariasi antara 18-24
        dmgs = []
        for seed in range(20):
            rng = random.Random(seed)
            res, _ = adv.apply_action(s, "player", "ATTACK", rng=rng)
            dmgs.append(self.state.boss_hp - res.boss_hp)
        self.assertTrue(all(18 <= d <= 24 for d in dmgs))
        self.assertTrue(len(set(dmgs)) > 1)

    def test_max_turns_terminal(self):
        """Batas 50 ronde membuat pertarungan terminal dan pemenang dihitung dari % HP."""
        s = self.state.clone()
        s.turn_number = 51
        self.assertTrue(adv.is_terminal(s))

        # Boss HP 80% (96/120), Player HP 50% (50/100) -> Boss menang
        s.boss_hp = 96
        s.player_hp = 50
        score = adv.evaluate(s)
        self.assertEqual(score, config.EVAL_WIN_SCORE)

        # Player HP 90%, Boss HP 50% -> Player menang
        s.boss_hp = 60
        s.player_hp = 90
        score_p = adv.evaluate(s)
        self.assertEqual(score_p, -config.EVAL_WIN_SCORE)


class TestAdversarialSearch(unittest.TestCase):
    """Pengujian algoritma Minimax + Alpha-Beta Pruning dan Candidate Scores."""

    def setUp(self):
        self.ai = adv.MinimaxBattleAI(depth=3)
        self.state = adv.BattleState(
            player_hp=70,
            boss_hp=80,
            potion_count=1,
            boss_heal_count=1,
            boss_heavy_cd=0
        )

    def test_choose_move_candidate_scores(self):
        """Minimax menghasilkan skor untuk semua aksi kandidat boss."""
        move, root, stats = self.ai.choose_move(self.state)
        self.assertIn(move, ["ATTACK", "HEAVY_ATTACK", "DEFEND", "HEAL"])
        self.assertGreater(stats.nodes, 0)
        self.assertGreaterEqual(stats.pruned, 0)
        self.assertGreaterEqual(stats.elapsed_ms, 0.0)

        # Candidate actions must cover all legal boss actions
        legal = adv.boss_actions(self.state)
        candidate_acts = [c["action"] for c in stats.candidates]
        for act in legal:
            self.assertIn(act, candidate_acts)

        # Chosen action must be flagged
        chosen_candidates = [c for c in stats.candidates if c["chosen"]]
        self.assertEqual(len(chosen_candidates), 1)
        self.assertEqual(chosen_candidates[0]["action"], move)


class TestBattleUILayout(unittest.TestCase):
    """Pengujian geometri layout UI Battle Mode (verifikasi 0 tumpang tindih Rect)."""

    def test_no_ui_rect_overlaps(self):
        """Uji bahwa tidak ada komponen Rect UI yang tumpang tindih secara tidak sengaja."""
        rects = get_battle_layout_rects()

        # 1. Zona Atas vs Bawah
        arena = rects["arena"]
        menu = rects["menu_panel"]
        log = rects["log_panel"]

        # Arena di atas (y <= 430), Menu dan Log di bawah (y >= 440)
        self.assertLessEqual(arena.bottom, menu.top)
        self.assertLessEqual(arena.bottom, log.top)

        # Menu di kiri (right=540), Log di kanan (left=560)
        self.assertLessEqual(menu.right, log.left)
        self.assertFalse(menu.colliderect(log))

        # 2. Elemen di dalam Menu Panel tidak saling tumpang tindih
        menu_items = [
            ("btn_attack", rects["btn_attack"]),
            ("btn_potion", rects["btn_potion"]),
            ("btn_defend", rects["btn_defend"]),
            ("action_desc", rects["action_desc"]),
        ]
        for name, r in menu_items:
            # Harus berada sepenuhnya di dalam menu_panel
            self.assertTrue(menu.contains(r), f"{name} keluar dari menu_panel: {r} vs {menu}")

        # Pasangan di dalam menu tidak boleh colliderect
        for i in range(len(menu_items)):
            for j in range(i + 1, len(menu_items)):
                n1, r1 = menu_items[i]
                n2, r2 = menu_items[j]
                self.assertFalse(r1.colliderect(r2), f"Overlap antara {n1} dan {n2}")

        # 3. Elemen HUD Arena tidak saling tumpang tindih
        arena_hud = [
            ("hero_hp", rects["hero_hp"]),
            ("boss_hp", rects["boss_hp"]),
            ("turn_pill", rects["turn_pill"]),
            ("boss_title", rects["boss_title"]),
            ("ai_panel", rects["ai_panel"]),
        ]
        for name, r in arena_hud:
            self.assertTrue(arena.contains(r), f"{name} keluar dari arena: {r} vs {arena}")

        for i in range(len(arena_hud)):
            for j in range(i + 1, len(arena_hud)):
                n1, r1 = arena_hud[i]
                n2, r2 = arena_hud[j]
                self.assertFalse(r1.colliderect(r2), f"Overlap dalam arena antara {n1} dan {n2}")


if __name__ == "__main__":
    unittest.main()

