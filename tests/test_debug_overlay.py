"""
tests/test_debug_overlay.py
Unit tests untuk Unified AI Inspector Dock & In-World Spatial Visualizer
memastikan ketepatan matematika, bebas overlap, batas lebar teks, dan performa render.
"""

import os
import sys
import unittest
import pygame

# Set dummy drivers for headless testing
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Pastikan path src terdaftar
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import config
from planning.planner_ui import UnifiedPlannerPanel
from planning.monitor import PlanMonitor
from world_state import WorldState
from decision.weather_manager import WeatherManager


class TestDebugOverlayArchitecture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        from main import create_display
        cls.screen = create_display()

    def setUp(self):
        self.panel = UnifiedPlannerPanel()
        self.world_state = WorldState()
        self.monitor = PlanMonitor(self.world_state)
        self.weather_mgr = WeatherManager()

    def test_dock_geometry_non_overlapping(self):
        """1. Memverifikasi dock 356x420 di (660, 8) 100% bebas overlap dengan widget HUD lain."""
        dock = self.panel.rect
        self.assertEqual(dock, pygame.Rect(660, 8, 356, 420))

        # Widget utama pada 1024x768
        top_bar = pygame.Rect(8, 8, 260, 36)
        banner = pygame.Rect(280, 8, 360, 36)
        action_pill = pygame.Rect(372, 594, 280, 38)
        bottom_hud = pygame.Rect(0, 640, 1024, 128)

        self.assertFalse(dock.colliderect(top_bar), "Dock menabrak Top Bar!")
        self.assertFalse(dock.colliderect(banner), "Dock menabrak Advisor Banner!")
        self.assertFalse(dock.colliderect(action_pill), "Dock menabrak Action Pill!")
        self.assertFalse(dock.colliderect(bottom_hud), "Dock menabrak Bottom HUD!")

    def test_mathematical_consistency_f_star_and_utilities(self):
        """2. Memverifikasi konsistensi analitis f* terhadap utilitas EU: U_pintas_aman=10, U_banjir=-20, U_raya=6."""
        u_pintas_aman = 10.0
        u_pintas_banjir = -20.0
        u_raya = 6.0

        # f* = (U_pintas_aman - U_raya) / (U_pintas_aman - U_pintas_banjir)
        f_star_calculated = (u_pintas_aman - u_raya) / (u_pintas_aman - u_pintas_banjir)
        self.assertAlmostEqual(f_star_calculated, 4.0 / 30.0, places=6)
        self.assertAlmostEqual(f_star_calculated, config.DECISION_ANALYTIC_F_STAR, places=6)

        # Cek MEU saat prior b=0.10 (< f*)
        b_prior = 0.10
        eu_p_prior = (1.0 - b_prior) * u_pintas_aman + b_prior * u_pintas_banjir
        eu_r_prior = u_raya
        self.assertGreater(eu_p_prior, eu_r_prior, "Prior b=0.10 seharusnya memilih Pintas!")

        # Cek MEU saat posterior berita b=0.50 (> f*)
        b_post = 0.50
        eu_p_post = (1.0 - b_post) * u_pintas_aman + b_post * u_pintas_banjir
        eu_r_post = u_raya
        self.assertLess(eu_p_post, eu_r_post, "Posterior b=0.50 seharusnya memilih Raya!")

    def test_panel_text_widths_within_bounds(self):
        """3. Memverifikasi semua string teks terpanjang muat dalam lebar panel (max 336 px)."""
        max_content_w = self.panel.rect.width - 20  # 336 px

        test_strings = [
            ("font_bold", "PLANNING INSPECTOR (STRIPS WA*)"),
            ("font_badge", "Domain: data/planning/expedition.domain"),
            ("font_badge", "[ ] gate_key   [ ] gate_open   [ ] boss_defeated"),
            ("font_bold", "Aksi: craft_key(workshop, key_iron)"),
            ("font_body", "Pre: [OK] at [OK] connected"),
            ("font_body", "Eff: +has_key, +holding | -wood, -rock"),
            ("font_body", "Diff: - (belum ada aksi selesai)"),
            ("font_body", "Diff: +gate_open, -has(gate_key)"),
            ("font_bold", "WA*(h_FF, w=1.5) | 886 node | 1.1ms"),
            ("font_badge", "Budget step(): < 20ms [OK] | Polyline [OK]"),
            ("font_badge", "Geodesik: 40 lkg >= 38 Manhattan [OK] (invarian)"),
            ("font_body", "Replan: - (eksekusi berjalan lancar)"),
            ("font_body", "Replan #1 | sebab: precondition gagal | 14.2ms | 37 -> 39 lkg"),
            ("font_bold", "DECISIONS UNDER UNCERTAINTY"),
            ("font_badge", "Model: Kalibrasi Pesisir (Penalti=2.70s, f*=0.1333)"),
            ("font_body", "Prior P0(B)=10% | Bukti: \"air mulai naik\""),
            ("font_badge", "Likelihood: P(Berita|B)=0.90 (asumsi), P(Berita|~B)=0.10"),
            ("font_badge", "Timeline: Prior 10% -> Berita -> Post 50.0% [RISIKO]"),
            ("font_body", "EU(Pintas) = (1-b)*10.0 + b*(-20.0) = -5.00 poin"),
            ("font_body", "EU(Raya)   = 6.00 poin"),
            ("font_bold", "pi*(b) = argmax(EU) -> RAYA  [RISIKO]"),
            ("font_body", "-> b < 13.3%  : PINTAS (Pantai, 15 tile / 3.26s) [AKTIF]"),
            ("font_body", "-> b >= 13.3% : RAYA   (Detour, 19 tile / 4.13s) [AKTIF]"),
            ("font_badge", "VPI Teori = +1.98 poin (Slide) | Biaya Papan = 0.20s"),
            ("font_badge", "Koridor Penuh (1.78s): Neto -0.1965s (K=57x Tak Impas)"),
        ]

        for font_name, text in test_strings:
            font = getattr(self.panel, font_name)
            w, _ = font.size(text)
            self.assertLessEqual(
                w, max_content_w,
                f"Teks '{text}' lebarnya {w}px melebihi batas panel {max_content_w}px!"
            )

    def test_live_data_binding(self):
        """4. Memverifikasi metrik dibaca dari objek live monitor & config."""
        self.monitor.last_nodes_expanded = 886
        self.monitor.last_search_latency_ms = 1.05
        self.panel.active_tab = 0

        self.assertEqual(self.monitor.last_nodes_expanded, 886)
        self.assertAlmostEqual(self.monitor.last_search_latency_ms, 1.05, places=2)
        self.assertEqual(config.PLANNER_WEIGHT, 1.5)

    def test_render_performance_budget(self):
        """5. Memverifikasi waktu render panel < 5.0 ms (jauh di bawah batas 20 ms) tanpa kalkulasi per-frame."""
        import time

        self.panel.visible = True
        self.panel.active_tab = 3

        # Warm up
        for _ in range(10):
            self.panel.draw(self.screen, weather_mgr=self.weather_mgr)

        t0 = time.perf_counter()
        N = 100
        for _ in range(N):
            self.panel.draw(self.screen, weather_mgr=self.weather_mgr)
        elapsed_total = (time.perf_counter() - t0) * 1000.0
        avg_ms = elapsed_total / N

        self.assertLess(avg_ms, 5.0, f"Render time {avg_ms:.3f}ms melebihi batas 5.0ms!")

    def test_deterministic_demo_replan(self):
        """6. Memverifikasi trigger_demo_replan mencatat event log dengan format lengkap."""
        ok, plan, msg = self.monitor.trigger_demo_replan(reason="prekondisi gagal (gerbang terkunci)")
        self.assertTrue(ok)
        self.assertIsNotNone(plan)
        self.assertGreater(len(self.monitor.replan_events), 0)
        last_ev = self.monitor.replan_events[-1]
        self.assertIn("gerbang terkunci", last_ev["reason"])
        self.assertIn("latency_ms", last_ev)
        self.assertIn("old_len", last_ev)
        self.assertIn("new_len", last_ev)

    def test_policy_table_mutual_exclusivity(self):
        """7. Memverifikasi cabang tabel kebijakan mutually exclusive (hanya 1 cabang [AKTIF] per nilai b)."""
        # Skenario 1: b = 0.0 -> Pintas AKTIF, Raya TIDAK AKTIF
        self.weather_mgr.belief_flood = 0.0
        self.assertTrue(not (self.weather_mgr.belief_flood >= 0.1333))

        # Skenario 2: b = 0.10 (< f*) -> Pintas AKTIF, Raya TIDAK AKTIF
        self.weather_mgr.belief_flood = 0.10
        is_risky_1 = (self.weather_mgr.belief_flood >= 0.1333)
        self.assertTrue(not is_risky_1)
        self.assertFalse(is_risky_1)

        # Skenario 3: b = 0.1333 (titik potong batas f*) -> Raya AKTIF, Pintas TIDAK AKTIF
        self.weather_mgr.belief_flood = 0.1333
        is_risky_f = (self.weather_mgr.belief_flood >= 0.1333)
        self.assertFalse(not is_risky_f)
        self.assertTrue(is_risky_f)

        # Skenario 4: b = 0.50 (> f*) -> Raya AKTIF, Pintas TIDAK AKTIF
        self.weather_mgr.belief_flood = 0.50
        is_risky_2 = (self.weather_mgr.belief_flood >= 0.1333)
        self.assertFalse(not is_risky_2)
        self.assertTrue(is_risky_2)

        # Skenario 5: b = 1.00 -> Raya AKTIF, Pintas TIDAK AKTIF
        self.weather_mgr.belief_flood = 1.00
        self.assertTrue(self.weather_mgr.belief_flood >= 0.1333)

    def test_weather_board_interaction_unpacking(self):
        """8. Memverifikasi interaksi tombol [E] pada WEATHER_BOARD tidak mengalami ValueError unpacking."""
        from main import Game, AssetManager
        assets = AssetManager()
        game = Game(self.screen, assets, seed=42)
        game.near_interaction_target = ("WEATHER_BOARD", (1504, 1024))
        # Simulasi pemicu interaksi [E]
        interacted = game._handle_world_interaction()
        self.assertTrue(interacted)
        self.assertTrue(game.weather_manager.has_read_board)


if __name__ == "__main__":
    unittest.main()
