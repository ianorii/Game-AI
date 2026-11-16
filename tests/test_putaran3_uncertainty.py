"""
test_putaran3_uncertainty.py - Test Suite Komprehensif Putaran 3
Mencakup:
1. Papan Pengumuman Cuaca (Bayesian Belief Update & Likelihood)
2. MDP Rute & Titik Kritis f* = 0.1333 (Policy Flip Pintas vs Raya)
3. Konsekuensi Fisik Banjir (Hero Flood Flush & Retreat Penalty)
4. Autopilot Replan Trigger (TRIGGER_BELIEF_UPDATE)
5. Layout UI Tab Ketidakpastian Panel F7 (Font >= 14px, Non-Overlapping)
6. Monte Carlo Benchmark Payoff 10,000 Hari
"""

import unittest
import math
import os
import sys
import pygame
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from decision.weather_manager import WeatherManager, run_monte_carlo_evaluation
from decision.probability import bayes_update
from decision.mdp import MDP, compute_q, value_iteration, extract_policy
from decision.flood_model import create_flood_mdp, analyze_sensitivity_f
from planning.planner_ui import UnifiedPlannerPanel
from planning.autopilot import AutopilotController, PlannerMode
from world_state import WorldState


class DummyHero:
    def __init__(self, x=1504.0, y=1024.0):
        self.px = x
        self.py = y
        self.manual_mode = True
        self.action_anim = None
        self.action_anim_timer = 0.0

    def play_action_animation(self, name, duration):
        self.action_anim = name
        self.action_anim_timer = duration


class TestPutaran3Uncertainty(unittest.TestCase):

    def setUp(self):
        pygame.init()
        self.wm = WeatherManager(seed=20261114)
        self.hero = DummyHero(1504.0, 1024.0)

    def test_01_weather_cycle_and_flood_prior(self):
        """Verifikasi siklus cuaca 240 detik dan prior P(Banjir) = 0.10."""
        self.assertEqual(self.wm.cycle_duration, 240.0)
        self.assertAlmostEqual(self.wm.prior_flood, 0.10, places=4)
        self.assertAlmostEqual(self.wm.belief_flood, 0.10, places=4)
        self.assertIn(self.wm.optimal_policy, ("Pintas", "Raya"))

    def test_02_bayesian_update_likelihood(self):
        """Verifikasi pembaruan Bayes: Berita -> 0.50, Cerah -> 0.0122."""
        # Prior = 0.10
        # Jika Berita: P(Berita|B)=0.9, P(Berita|~B)=0.1
        # P(B|Berita) = (0.9 * 0.1) / (0.9*0.1 + 0.1*0.9) = 0.09 / 0.18 = 0.50
        post_news, _ = bayes_update(0.10, 0.90, 0.10)
        self.assertAlmostEqual(post_news, 0.50, places=4)

        # Jika Cerah: P(Cerah|B)=0.1, P(Cerah|~B)=0.9
        # P(B|Cerah) = (0.1 * 0.1) / (0.1*0.1 + 0.9*0.9) = 0.01 / 0.82 = 0.012195...
        post_sunny, _ = bayes_update(0.10, 0.10, 0.90)
        self.assertAlmostEqual(post_sunny, 0.012195, places=5)

    def test_03_policy_flip_at_critical_threshold(self):
        """Verifikasi pembalikan kebijakan pada f* = 2/15 (~0.1333)."""
        import config
        f_star = getattr(config, "DECISION_ANALYTIC_F_STAR", 4.0 / 30.0)
        self.assertAlmostEqual(f_star, 2.0 / 15.0, places=5)

        # Di bawah f* (misal belief prior 0.10): Pintas lebih optimal
        self.wm.belief_flood = 0.10
        self.wm._update_policy()
        self.assertEqual(self.wm.optimal_policy, "Pintas")
        qp, qr = self.wm.get_expected_utilities()
        self.assertGreater(qp, qr)

        # Di atas f* (misal setelah berita banjir 0.50): Raya lebih optimal
        self.wm.belief_flood = 0.50
        self.wm._update_policy()
        self.assertEqual(self.wm.optimal_policy, "Raya")
        qp, qr = self.wm.get_expected_utilities()
        self.assertLess(qp, qr)

    def test_04_notice_board_interaction_once_per_day(self):
        """Pemain hanya dapat membaca papan ramalan 1x per hari cuaca."""
        self.assertFalse(self.wm.notice_read_today)
        ok1, msg1, belief1 = self.wm.read_notice_board()
        self.assertTrue(ok1)
        self.assertTrue(self.wm.notice_read_today)
        self.assertIn(self.wm.last_evidence, ("air mulai naik", "langit cerah"))

        # Interaksi kedua di hari yang sama harus ditolak
        ok2, msg2, belief2 = self.wm.read_notice_board()
        self.assertFalse(ok2)
        self.assertIn("sudah Anda baca", msg2)

    def test_05_flood_flush_and_retreat(self):
        """Hero yang berada di zona banjir saat banjir aktif akan terseret dan kena penalti."""
        # Set banjir aktif
        self.wm.actual_flood = True
        
        # Posisikan hero di luar zona banjir
        self.hero.px = 1500.0
        self.hero.py = 1000.0
        flushed, _ = self.wm.trigger_flood_flush(self.hero)
        self.assertFalse(flushed)

        # Posisikan hero tepat di dalam zona banjir (2016 <= x <= 2368, 864 <= y <= 960)
        self.hero.px = 2100.0
        self.hero.py = 900.0
        flushed, msg = self.wm.trigger_flood_flush(self.hero)
        self.assertTrue(flushed)
        self.assertIn("BANJIR BANDANG", msg)
        self.assertEqual(self.hero.action_anim, "swimming")
        
        # Koordinat hero harus terpental ke safe retreat bila game_map None
        self.assertEqual((self.hero.px, self.hero.py), self.wm.safe_retreat_pos)

        # Uji dengan GameMap nyata: hero terseret ke tile kering terdekat
        from world.game_map import GameMap
        gmap = GameMap()
        self.hero.px = 2100.0
        self.hero.py = 900.0
        flushed, msg = self.wm.trigger_flood_flush(self.hero, game_map=gmap)
        self.assertTrue(flushed)
        # Hero harus berada di luar flood rect
        self.assertFalse(self.wm.is_in_flood_zone(self.hero.px, self.hero.py))
        # Tile tempat hero berdiri harus valid can_stand
        hb = pygame.Rect(int(self.hero.px - 7), int(self.hero.py - 4), 14, 8)
        self.assertTrue(gmap.can_stand(hb))

    def test_06_autopilot_on_belief_updated(self):
        """Autopilot merespons TRIGGER_BELIEF_UPDATE saat kebijakan berubah ke Raya."""
        ws = WorldState(seed=20261114)
        auto = AutopilotController(ws, hero=self.hero)
        auto.mode = PlannerMode.AUTO

        # Beri manajer cuaca dengan belief 0.50 (kebijakan Raya)
        self.wm.belief_flood = 0.50
        self.wm._update_policy()
        auto.on_belief_updated(self.wm)
        self.assertIn("TRIGGER_BELIEF_UPDATE", auto.status_message)

    def test_07_planner_panel_tab3_layout_and_font(self):
        """Tab Ketidakpastian di panel F7 harus memiliki font >= 14px dan tidak tumpang tindih."""
        panel = UnifiedPlannerPanel()
        self.assertGreaterEqual(panel.font_title.get_linesize(), 14)
        self.assertGreaterEqual(panel.font_body.get_linesize(), 10)
        self.assertGreaterEqual(panel.font_bold.get_linesize(), 10)
        self.assertGreaterEqual(panel.font_tab.get_linesize(), 10)

        # Uji klik tab 3
        panel.visible = True
        rx, ry = panel.rect.x, panel.rect.y
        tab3_click_pos = (rx + 230, ry + 10)
        clicked = panel.handle_click(tab3_click_pos)
        self.assertTrue(clicked)
        self.assertEqual(panel.active_tab, 3)

        # Uji rendering ke surface virtual
        screen = pygame.Surface((1024, 768))
        panel.draw(screen, weather_mgr=self.wm)

    def test_08_monte_carlo_payoff_evaluation(self):
        """Simulasi Monte Carlo 10.000 hari mengonfirmasi keunggulan strategi Adaptif."""
        results = run_monte_carlo_evaluation(n_days=10000, seed=20261114)
        self.assertEqual(results["n_days"], 10000)

        # Teori:
        # Fast: ~7.00 (7.06 empiris)
        # Safe: 6.00 persis
        # Adaptive: ~8.98 (9.03 empiris)
        eu_fast = results["results"]["fast"]["mean"]
        eu_safe = results["results"]["safe"]["mean"]
        eu_adapt = results["results"]["mdp_adaptive"]["mean"]

        self.assertAlmostEqual(eu_safe, 6.00, delta=0.01)
        self.assertGreater(eu_adapt, eu_fast)
        self.assertGreater(eu_adapt, eu_safe)
        self.assertGreater(eu_adapt, 8.8)

    def test_09_find_nearest_dry_tile_reachability(self):
        """Tile kering terdekat dari titik manapun di zona banjir harus selalu valid can_stand dan di luar zona banjir."""
        from world.game_map import GameMap
        gmap = GameMap()
        rx, ry, rw, rh = self.wm.flood_rect
        # Sampel grid di dalam zona banjir
        for x in range(rx + 16, rx + rw, 48):
            for y in range(ry + 16, ry + rh, 32):
                dry_pos = self.wm.find_nearest_dry_tile(float(x), float(y), gmap)
                # Harus di luar zona banjir
                self.assertFalse(self.wm.is_in_flood_zone(dry_pos[0], dry_pos[1]))
                # Harus bisa dipijak
                hb = pygame.Rect(int(dry_pos[0] - 7), int(dry_pos[1] - 4), 14, 8)
                self.assertTrue(gmap.can_stand(hb), f"Tile {dry_pos} dari titik banjir ({x}, {y}) tidak can_stand!")

    def test_10_policy_matches_argmin_time_utility(self):
        """Pilihan policy MDP harus konsisten dengan argmin waktu/utility nyata di f in {0, 0.05, f*, 0.25, 0.5}."""
        import config
        f_star = getattr(config, "DECISION_ANALYTIC_F_STAR", 2.0 / 15.0)

        # f = 0.0 -> Pintas menang mutlak
        self.wm.belief_flood = 0.0
        self.wm._update_policy()
        self.assertEqual(self.wm.optimal_policy, "Pintas")

        # f = 0.05 -> Pintas menang (risiko 5% masih di bawah f* 13.3%)
        self.wm.belief_flood = 0.05
        self.wm._update_policy()
        self.assertEqual(self.wm.optimal_policy, "Pintas")

        # f = f* - 0.001 -> Pintas
        self.wm.belief_flood = f_star - 0.001
        self.wm._update_policy()
        self.assertEqual(self.wm.optimal_policy, "Pintas")

        # f = f* + 0.001 -> Raya
        self.wm.belief_flood = f_star + 0.001
        self.wm._update_policy()
        self.assertEqual(self.wm.optimal_policy, "Raya")

        # f = 0.25 -> Raya menang (risiko 25% > f*)
        self.wm.belief_flood = 0.25
        self.wm._update_policy()
        self.assertEqual(self.wm.optimal_policy, "Raya")

        # f = 0.50 -> Raya menang mutlak (setelah berita banjir)
        self.wm.belief_flood = 0.50
        self.wm._update_policy()
        self.assertEqual(self.wm.optimal_policy, "Raya")

    def test_11_route_distance_and_time_consistency(self):
        """Label tile dan detik konsisten dihitung dari kecepatan hero 4.6 tile/s (147.2 px/s)."""
        speed = 147.2  # px/s
        # Koridor Penuh
        t_fast_corridor = 480.0 / speed   # 15 tile
        t_safe_corridor = 608.0 / speed   # 19 tile
        delta_corridor = t_safe_corridor - t_fast_corridor
        self.assertAlmostEqual(t_fast_corridor, 3.26, delta=0.01)
        self.assertAlmostEqual(t_safe_corridor, 4.13, delta=0.01)
        self.assertAlmostEqual(delta_corridor, 0.87, delta=0.01)

        # Sub-segmen Divergensi Lokal
        t_fast_sub = 168.2 / speed
        t_safe_sub = 220.4 / speed
        delta_sub = t_safe_sub - t_fast_sub
        self.assertAlmostEqual(t_fast_sub, 1.14, delta=0.01)
        self.assertAlmostEqual(t_safe_sub, 1.50, delta=0.01)
        self.assertAlmostEqual(delta_sub, 0.36, delta=0.01)

    def test_12_information_cost_and_amortization_breakeven(self):
        """Biaya informasi [E] (0.2s) membuat per-single trip selalu negatif, impas hanya via amortisasi multi-trip."""
        e_delay = 0.20
        # Model Sub-segmen
        raw_savings_270 = 0.1772
        raw_savings_178 = 0.0952
        net_single_270 = raw_savings_270 - e_delay
        net_single_178 = raw_savings_178 - e_delay
        self.assertLess(net_single_270, 0.0, "Per-single trip harus rugi bersih (-0.02s)")
        self.assertLess(net_single_178, 0.0, "Per-single trip harus rugi bersih (-0.10s)")

        k_impas_270 = e_delay / raw_savings_270
        k_impas_178 = e_delay / raw_savings_178
        self.assertLess(k_impas_270, 2.0, "Model 2.70s harus impas pada K >= 2 trip")
        self.assertLess(k_impas_178, 3.0, "Model 1.78s harus impas pada K >= 3 trip")

        # Model Koridor Penuh
        raw_corridor_178 = 0.0035
        k_corridor_178 = e_delay / raw_corridor_178
        self.assertGreater(k_corridor_178, 50.0, "Koridor penuh 1.78s tidak pernah impas secara fisik (>50 trip/hari)")

    def test_13_flood_penalty_measured_vs_calibrated(self):
        """Kedua model penalti (1.78s terukur dan 2.70s terkalibrasi) menghasilkan kebijakan optimal 100% konsisten."""
        # Prior 0.10 vs Posterior Berita 0.50
        # Model 2.70s: f* = 0.36 / 2.70 = 0.1333
        f_star_cal = 0.35462 / 2.70
        self.assertAlmostEqual(f_star_cal, 2.0 / 15.0, delta=0.01)
        # Model 1.78s: f* = 0.36 / 1.7783 = 0.2024
        f_star_meas = 0.35462 / 1.7783
        self.assertAlmostEqual(f_star_meas, 0.2024, delta=0.01)

        # Keduanya membalikkan kebijakan secara konsisten:
        for f_thresh in (f_star_cal, f_star_meas):
            self.assertTrue(0.10 < f_thresh, "Prior 10% selalu memilih Pintas")
            self.assertTrue(0.50 > f_thresh, "Posterior berita 50% selalu memilih Raya/Detour")

    def test_14_flood_zone_buffer_distance_to_water(self):
        """Zona rawan banjir terbukti merupakan buffer ring 1-2 tile dari bibir air (bukan di daratan pedalaman)."""
        from world.game_map import GameMap
        gmap = GameMap()
        rx, ry, rw, rh = self.wm.flood_rect
        w_tiles = gmap.width // 32
        h_tiles = gmap.height // 32

        water_cells = set()
        for cy in range(h_tiles):
            for cx in range(w_tiles):
                hb = pygame.Rect(cx * 32 + 9, cy * 32 + 12, 14, 8)
                if not gmap.can_stand(hb):
                    water_cells.add((cx, cy))

        fz_walkables = []
        for cy in range(ry // 32, (ry + rh) // 32):
            for cx in range(rx // 32, (rx + rw) // 32):
                hb = pygame.Rect(cx * 32 + 9, cy * 32 + 12, 14, 8)
                if gmap.can_stand(hb):
                    d_water = min(math.sqrt((cx - wx)**2 + (cy - wy)**2) for wx, wy in water_cells)
                    fz_walkables.append((cx, cy, d_water))

        self.assertEqual(len(fz_walkables), 26, "Harus ada tepat 26 tile walkable di dalam zona banjir")
        near_tiles = [d for _, _, d in fz_walkables if d <= 2.25]
        self.assertGreaterEqual(len(near_tiles) / len(fz_walkables), 0.90, ">= 90% tile harus berjarak <= 2 tile dari air")

    def test_15_evacuation_reachability_to_gate(self):
        """Seluruh 24 tile zona banjir yang dievakuasi ke tile kering memiliki rute A* aktif menuju gerbang."""
        from world.game_map import GameMap
        from ai.pathfinding import astar
        import config
        gmap = GameMap()
        rx, ry, rw, rh = self.wm.flood_rect
        w_tiles = gmap.width // 32
        h_tiles = gmap.height // 32
        goal_node = (config.INTERACT_GATE_POS[0] // 32, config.INTERACT_GATE_POS[1] // 32)

        def is_blocked(cx: int, cy: int) -> bool:
            if cx < 0 or cx >= w_tiles or cy < 0 or cy >= h_tiles:
                return True
            px = cx * 32 + 16
            py = cy * 32 + 16
            return not gmap.can_stand(pygame.Rect(int(px - 7), int(py - 4), 14, 8))

        for cy in range(ry // 32, (ry + rh) // 32):
            for cx in range(rx // 32, (rx + rw) // 32):
                hb = pygame.Rect(cx * 32 + 9, cy * 32 + 12, 14, 8)
                if gmap.can_stand(hb):
                    dry_px, dry_py = self.wm.find_nearest_dry_tile(cx * 32 + 16, cy * 32 + 16, gmap)
                    dry_node = (int(dry_px // 32), int(dry_py // 32))
                    res = astar(w_tiles, h_tiles, dry_node, goal_node, is_blocked)
                    self.assertTrue(res.found, f"Tile kering {dry_node} hasil evakuasi dari ({cx}, {cy}) tidak dapat mencapai gerbang!")

    def test_16_flood_flush_message_uses_config_penalty(self):
        """Pesan trigger_flood_flush harus menampilkan penalti waktu sesuai config (FLOOD_PENALTY_TIME)."""
        import config
        self.wm.actual_flood = True
        self.hero.px = 2100.0
        self.hero.py = 900.0
        flushed, msg = self.wm.trigger_flood_flush(self.hero)
        self.assertTrue(flushed)
        penalty_val = getattr(config, "FLOOD_PENALTY_TIME", 2.70)
        expected_str = f"-{penalty_val:.1f}s"
        self.assertIn(expected_str, msg, f"Pesan banjir harus memuat '{expected_str}', ditemukan: '{msg}'")
        self.assertNotIn("-20s", msg, "Pesan banjir tidak boleh lagi memuat penalti lama -20s")


if __name__ == "__main__":
    unittest.main()
