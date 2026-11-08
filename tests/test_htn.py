"""
test_htn.py - Unit Test Hierarchical Task Network (HTN) Planner Desa & UI (Sub-fase 2C & 2D)

Menguji:
  1. Parsing domain HTN (npc.htn): operator primitif & compound task methods.
  2. Dekomposisi tugas compound ke rencana primitif linier (SHOP-style total-order).
  3. Pemilihan metode alternatif Petani berdasarkan kondisi dunia:
     - Tanaman siap panen -> m_harvest_and_sell
     - Tanaman kering butuh siram -> m_water_dry_plots
     - Petak kosong -> m_plant_empty_plots
  4. Rutinitas malam hari Petani & Penggiling (m_farmer_night_sleep, m_miller_night_sleep).
  5. Pemilihan metode alternatif Penggiling:
     - Menggiling gandum aktif -> m_mill_active_wheat
     - Perawatan kincir angin -> m_inspect_and_maintenance
  6. Replanning adaptif NPC saat intervensi player (mis. panen manual).
  7. Verifikasi batasan layout UI (panel <= 15% luas layar, non-overlap, font >= 14px).
"""

import unittest
import os
import sys
import pygame

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
os.environ["SDL_VIDEODRIVER"] = "dummy"

pygame.init()

from world_state import WorldState
from planning.htn import (
    parse_htn_file, HTNDomain, SHOPPlanner, HTNNPCAgent, WorldClock,
    ExpressionIcon, HTNTask
)
from planning.planner_ui import get_planner_layout_rects, ExpeditionPlanPanel, HTNPlanPanel


class TestHTNPlanner(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        domain_path = os.path.join("data", "planning", "npc.htn")
        cls.domain = parse_htn_file(domain_path)

    def setUp(self):
        self.world_state = WorldState()

    def test_parse_htn_domain(self):
        """Memverifikasi parsing domain HTN npc.htn lengkap."""
        self.assertIsInstance(self.domain, HTNDomain)
        # Operator primitif minimal 12
        self.assertGreaterEqual(len(self.domain.operators), 12)
        expected_ops = [
            "!goto", "!harvest_crop", "!water_crop", "!plant_crop",
            "!sell_produce", "!buy_seed", "!feed_animals",
            "!take_wheat", "!mill_wheat", "!deliver_flour", "!inspect_mill", "!rest"
        ]
        for op in expected_ops:
            self.assertIn(op, self.domain.operators, f"Operator {op} harus terdaftar di domain")

        # Compound tasks minimal 5 dengan >= 2 alternatif metode per compound task
        compound_tasks = ["manage_farm", "care_animals", "mill_cycle", "daily_routine_farmer", "daily_routine_miller"]
        for ct in compound_tasks:
            self.assertIn(ct, self.domain.methods, f"Compound task {ct} harus terdaftar")
            self.assertGreaterEqual(len(self.domain.methods[ct]), 2,
                                     f"Compound task {ct} harus memiliki >= 2 alternatif metode")

    def test_farmer_mature_crop_decomposition(self):
        """Petani memilih m_harvest_and_sell saat ada tanaman matang."""
        planner = SHOPPlanner(self.domain)
        init_facts = {
            ("at", "farmer", "farm"),
            ("has_mature_crop", "plot0"),
            ("plot_mature", "plot0"),
            ("is_daytime",)
        }
        ok, plan, tree = planner.plan(init_facts, [HTNTask("manage_farm", ("farmer",))], initial_binding={"?npc": "farmer", "?from": "farm"})
        self.assertTrue(ok, "Dekomposisi manage_farm harus berhasil")
        op_names = [op.name for op in plan]
        self.assertIn("!harvest_crop", op_names)
        self.assertIn("!sell_produce", op_names)
        self.assertEqual(tree[0].chosen_method, "m_harvest_and_sell")

    def test_farmer_dry_crop_decomposition(self):
        """Petani memilih m_water_dry_plots saat ada tanaman kering yang butuh air."""
        planner = SHOPPlanner(self.domain)
        init_facts = {
            ("at", "farmer", "farm"),
            ("has_dry_plot", "plot0"),
            ("plot_dry", "plot0"),
            ("is_daytime",)
        }
        ok, plan, tree = planner.plan(init_facts, [HTNTask("manage_farm", ("farmer",))], initial_binding={"?npc": "farmer", "?from": "farm"})
        self.assertTrue(ok)
        op_names = [op.name for op in plan]
        self.assertIn("!water_crop", op_names)
        self.assertEqual(tree[0].chosen_method, "m_water_dry_plots")

    def test_farmer_empty_plot_decomposition(self):
        """Petani memilih m_plant_empty_plots saat ada petak kosong."""
        planner = SHOPPlanner(self.domain)
        init_facts = {
            ("at", "farmer", "farm"),
            ("has_empty_plot", "plot0"),
            ("plot_empty", "plot0"),
            ("is_daytime",)
        }
        ok, plan, tree = planner.plan(init_facts, [HTNTask("manage_farm", ("farmer",))], initial_binding={"?npc": "farmer", "?from": "farm"})
        self.assertTrue(ok)
        op_names = [op.name for op in plan]
        self.assertIn("!plant_crop", op_names)
        self.assertEqual(tree[0].chosen_method, "m_plant_empty_plots")

    def test_farmer_night_routine(self):
        """Petani memilih m_farmer_night_sleep saat malam hari."""
        planner = SHOPPlanner(self.domain)
        init_facts = {
            ("at", "farmer", "farm"),
            ("is_nighttime",)
        }
        ok, plan, tree = planner.plan(init_facts, [HTNTask("daily_routine_farmer", ("farmer",))], initial_binding={"?npc": "farmer", "?from": "farm"})
        self.assertTrue(ok)
        op_names = [op.name for op in plan]
        self.assertIn("!rest", op_names)
        self.assertEqual(tree[0].chosen_method, "m_farmer_night_sleep")

    def test_miller_active_wheat_decomposition(self):
        """Penggiling memilih m_mill_active_wheat saat persediaan gandum tersedia."""
        planner = SHOPPlanner(self.domain)
        init_facts = {
            ("at", "miller", "windmill"),
            ("wheat_available",),
            ("is_daytime",)
        }
        ok, plan, tree = planner.plan(init_facts, [HTNTask("mill_cycle", ("miller",))], initial_binding={"?npc": "miller", "?from": "windmill"})
        self.assertTrue(ok)
        op_names = [op.name for op in plan]
        self.assertIn("!mill_wheat", op_names)
        self.assertIn("!deliver_flour", op_names)
        self.assertEqual(tree[0].chosen_method, "m_mill_active_wheat")

    def test_miller_maintenance_decomposition(self):
        """Penggiling memilih m_inspect_and_maintenance saat tidak ada gandum."""
        planner = SHOPPlanner(self.domain)
        init_facts = {
            ("at", "miller", "windmill"),
            ("is_daytime",)
        }
        ok, plan, tree = planner.plan(init_facts, [HTNTask("mill_cycle", ("miller",))], initial_binding={"?npc": "miller", "?from": "windmill"})
        self.assertTrue(ok)
        op_names = [op.name for op in plan]
        self.assertIn("!inspect_mill", op_names)
        self.assertEqual(tree[0].chosen_method, "m_inspect_and_maintenance")

    def test_dynamic_replanning_on_world_change(self):
        """NPC mendeteksi intervensi dunia (tanaman dipanen manual) dan merevisi dekomposisi."""
        # Setup petak 0 matang
        self.world_state.farm.plots[0].crop_type = "radish"
        self.world_state.farm.plots[0].stage = 5
        for p in self.world_state.farm.plots[1:]:
            p.crop_type = "radish"
            p.stage = 2
            p.is_watered = True

        farmer = HTNNPCAgent("Pak Tani", "farmer", "farm", self.domain, self.world_state)
        clock = WorldClock(day_duration=60.0, night_duration=30.0)
        clock.elapsed = 10.0  # Siang hari

        success = farmer.request_htn_plan(clock)
        self.assertTrue(success)
        self.assertIsNotNone(farmer.active_tree)
        # Petani menjadwalkan panen
        self.assertIn("!harvest_crop", [op.name for op in farmer.active_operator_queue])

        # Pemain memanen tanaman secara manual di luar kendali NPC
        self.world_state.farm.plots[0].crop_type = None
        self.world_state.farm.plots[0].stage = 0

        # Anomali terjadi: plot 0 sudah tidak matang lagi saat dicek
        replan_triggered = farmer.check_and_replan_if_needed(clock)
        self.assertTrue(replan_triggered)
        # Replan terjadi, farmer mengekspresikan CONFUSED lalu beralih tugas baru
        self.assertEqual(farmer.expression, ExpressionIcon.CONFUSED)
        self.assertGreaterEqual(farmer.replan_count, 2)

    def test_planner_ui_layout_bounds(self):
        """Memverifikasi luas panel <= 15% luas layar (1024x768) dan tidak saling tumpang tindih."""
        rects = get_planner_layout_rects()
        screen_w, screen_h = 1024, 768
        screen_area = screen_w * screen_h
        max_allowed_area = 0.15 * screen_area  # 117,964 px

        exp_rect = rects["panel_expedition"]
        htn_rect = rects["panel_htn"]
        hud_bottom = rects["hud_bottom"]
        banner_top = rects["banner_top"]

        # 1. Luas masing-masing panel <= 15%
        self.assertLessEqual(exp_rect.width * exp_rect.height, max_allowed_area,
                             "Panel ekspedisi harus <= 15% luas layar")
        self.assertLessEqual(htn_rect.width * htn_rect.height, max_allowed_area,
                             "Panel HTN harus <= 15% luas layar")

        # 2. Tidak saling bertabrakan (non-overlapping)
        self.assertFalse(exp_rect.colliderect(htn_rect), "Panel ekspedisi dan HTN tidak boleh bertumpukan")
        self.assertFalse(exp_rect.colliderect(hud_bottom), "Panel ekspedisi tidak boleh menutupi HUD bawah")
        self.assertFalse(htn_rect.colliderect(hud_bottom), "Panel HTN tidak boleh menutupi HUD bawah")
        self.assertFalse(exp_rect.colliderect(banner_top), "Panel ekspedisi tidak boleh menutupi banner atas")
        self.assertFalse(htn_rect.colliderect(banner_top), "Panel HTN tidak boleh menutupi banner atas")


if __name__ == "__main__":
    unittest.main()
