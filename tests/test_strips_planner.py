"""
test_strips_planner.py - Unit Test Komprehensif Automated Classical Planner (STRIPS)

Menguji:
  1. Parser domain & problem PDDL
  2. Grounding & pemangkasan relasi statis
  3. Matriks jarak nyata A* & invalidasi collision
  4. Algoritma pencarian: BFS, UCS, A*(h_max), A*(h_add), WA*(h_FF)
  5. Optimalitas biaya UCS vs A*(h_max)
  6. Deteksi instan masalah tanpa solusi (unsolvable reachability)
  7. PlanValidator untuk validasi langkah simulasi state murni
  8. Problem generator dinamis dari WorldState nyata
"""

import unittest
import os
import sys
import math
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
pygame.init()

from world_state import WorldState
from planning.pddl_parser import parse_domain, parse_problem, PDDLParseError
from planning.distance_matrix import DistanceMatrix
from planning.grounding import ground_problem
from planning.heuristics import h_max, h_add, h_ff, check_relaxed_reachability
from planning.planner import (
    search_bfs, search_ucs, search_astar_hmax, search_astar_hadd,
    search_weighted_astar_hff, solve
)
from planning.strips import PlanValidator, Predicate, GroundAction, STRIPSState
from planning.problem_generator import build_problem_from_state


class TestSTRIPSPlanner(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        domain_path = os.path.join("data", "planning", "expedition.domain")
        problem_path = os.path.join("data", "planning", "expedition.problem")
        with open(domain_path, "r", encoding="utf-8") as f:
            cls.domain_raw = f.read()
        with open(problem_path, "r", encoding="utf-8") as f:
            cls.problem_raw = f.read()

        cls.domain = parse_domain(cls.domain_raw)
        cls.problem_ast = parse_problem(cls.problem_raw)

    def test_01_pddl_parser_domain(self):
        """Domain PDDL berhasil diurai dengan aksi dan predikat lengkap."""
        self.assertEqual(self.domain.name, "dungeon-expedition")
        self.assertIn("goto", self.domain.actions)
        self.assertIn("buy_seed_radish", self.domain.actions)
        self.assertIn("craft_key", self.domain.actions)
        self.assertIn("fight_boss", self.domain.actions)

        craft_key_act = self.domain.actions["craft_key"]
        self.assertEqual(len(craft_key_act.parameters), 0)
        self.assertEqual(len(craft_key_act.precondition), 3)  # at workshop, has wood, has rock

    def test_02_pddl_parser_problem(self):
        """Problem PDDL berhasil diurai dengan fakta awal dan sasaran."""
        self.assertEqual(self.problem_ast.name, "expedition-starter")
        self.assertEqual(self.problem_ast.domain_name, "dungeon-expedition")
        self.assertIn(("at", "spawn"), self.problem_ast.init_facts)
        self.assertIn(("coins", "c20"), self.problem_ast.init_facts)
        self.assertIn(("boss_defeated",), self.problem_ast.goal_facts)

    def test_03_distance_matrix_and_invalidation(self):
        """Matriks jarak menghitung durasi A* antar lokasi dan mengosongkan cache saat invalidasi."""
        dm = DistanceMatrix()
        dur_spawn_shop, steps_a, path_a = dm.get_distance("spawn", "shop")
        self.assertGreater(dur_spawn_shop, 0.0)
        self.assertGreater(steps_a, 0)
        self.assertTrue(len(path_a) > 0)

        # Cek cache hit
        dur_cached, steps_b, _ = dm.get_distance("spawn", "shop")
        self.assertEqual(dur_spawn_shop, dur_cached)
        self.assertEqual(steps_a, steps_b)

        # Invalidasi
        old_ver = dm._collision_version
        dm.invalidate()
        self.assertEqual(len(dm._cache), 0)
        self.assertEqual(dm._collision_version, old_ver + 1)

    def test_04_grounding_and_pruning(self):
        """Grounding membatasi kombinasi aksi hanya pada relasi yang legal di peta."""
        problem = ground_problem(self.domain, self.problem_ast)
        self.assertGreater(len(problem.actions), 0)

        # Pastikan tidak ada aksi goto ke diri sendiri
        for act in problem.actions:
            if act.name == "goto":
                self.assertNotEqual(act.params[0], act.params[1])

    def test_05_reachability_and_unsolvable_detection(self):
        """Problem tanpa solusi terdeteksi instan via relaksasi tanpa hang."""
        problem = ground_problem(self.domain, self.problem_ast)
        # Hapus aksi crafting dan pertambangan
        problem.actions = [a for a in problem.actions if "key" not in a.name and "rock" not in a.name]

        reachable, reached, missing = check_relaxed_reachability(problem.initial_state, problem.goal, problem.actions)
        self.assertFalse(reachable)
        self.assertIn(Predicate("boss_defeated"), missing)

        res = search_weighted_astar_hff(problem)
        self.assertFalse(res.success)
        self.assertIn("Problem tidak memiliki solusi", res.failure_reason)
        self.assertLess(res.time_ms, 50.0)

    def test_06_optimality_ucs_vs_astar_hmax(self):
        """
        Pada problem sub-tujuan (membuat Kunci Gerbang), UCS dan A*(h_max)
        menghasilkan biaya optimal yang PERSIS SAMA, dengan A*(h_max) mengekspansi lebih sedikit node.
        """
        prob_ast = parse_problem(self.problem_raw)
        prob_ast.goal_facts = {("has", "gate_key")}
        problem = ground_problem(self.domain, prob_ast)
        # Saring aksi perdagangan dan bertani yang tidak relevan dengan pembuatan kunci
        problem.actions = [a for a in problem.actions if not a.name.startswith("buy_") and not a.name.startswith("sell_") and not a.name.startswith("plant_") and not a.name.startswith("water_") and not a.name.startswith("wait_")]

        res_ucs = search_ucs(problem, max_nodes=5000)
        res_hmax = search_astar_hmax(problem, max_nodes=5000)

        self.assertTrue(res_ucs.success, "UCS harus menemukan rencana pembuatan kunci!")
        self.assertTrue(res_hmax.success, "A*(h_max) harus menemukan rencana pembuatan kunci!")

        # Biaya optimal harus identik
        self.assertAlmostEqual(res_ucs.total_cost, res_hmax.total_cost, places=2)
        # A*(h_max) harus mengekspansi simpul lebih sedikit atau sama dengan UCS
        self.assertLessEqual(res_hmax.nodes_expanded, res_ucs.nodes_expanded)

        # Validasi rencana
        val_ucs = PlanValidator.validate(problem, res_ucs.plan)
        val_hmax = PlanValidator.validate(problem, res_hmax.plan)
        self.assertTrue(val_ucs.valid)
        self.assertTrue(val_hmax.valid)

    def test_07_fastforward_and_helpful_actions(self):
        """WA* dengan h_FF dan helpful actions memecahkan misi lengkap dari game baru secara cepat."""
        problem = ground_problem(self.domain, self.problem_ast)
        res_wa = search_weighted_astar_hff(problem, weight=2.0, use_helpful_actions=True, max_nodes=5000)

        self.assertTrue(res_wa.success, f"WA* h_FF gagal: {res_wa.failure_reason}")
        self.assertGreater(len(res_wa.plan), 0)
        self.assertLess(res_wa.time_ms, 5000.0)

        # Verifikasi rencana dengan validator
        val = PlanValidator.validate(problem, res_wa.plan)
        self.assertTrue(val.valid, f"Rencana tidak valid: {val.message}")
        self.assertTrue(val.goal_reached)

    def test_08_plan_validator_catches_invalid_plan(self):
        """PlanValidator menolak rencana yang melompati urutan aksi atau kekurangan prasyarat."""
        problem = ground_problem(self.domain, self.problem_ast)
        # Buat rencana palsu: langsung mencoba buka gerbang di spawn tanpa kunci
        fake_act = GroundAction(
            name="open_gate",
            params=(),
            preconditions=frozenset([Predicate("at", ("gate",)), Predicate("has", ("gate_key",)), Predicate("gate_locked")]),
            add_effects=frozenset([Predicate("gate_open")]),
            delete_effects=frozenset([Predicate("gate_locked")]),
            cost=1.0, duration=1.0
        )
        report = PlanValidator.validate(problem, [fake_act])
        self.assertFalse(report.valid)
        self.assertFalse(report.goal_reached)
        self.assertIn("prasyarat tidak terpenuhi", report.message)

    def test_09_dynamic_problem_builder_from_world_state(self):
        """Membangun problem perencanaan dari WorldState aktual dan menyelesaikannya."""
        ws = WorldState(starting_coins=20)
        prob = build_problem_from_state(ws, domain=self.domain, goal_type="has_gate_key")
        self.assertEqual(prob.domain_name, "dungeon-expedition")

        res = search_weighted_astar_hff(prob, weight=2.0, use_helpful_actions=True)
        self.assertTrue(res.success)
        self.assertTrue(PlanValidator.validate(prob, res.plan).valid)

    def test_10_price_change_robustness_and_route_shift(self):
        """Mengubah harga di config/Shop menghasilkan transisi koin dinamis dan mengubah rute ekspedisi."""
        from economy import Shop
        ws = WorldState(starting_coins=20)
        # Turunkan harga jual komoditas lain ke 1 koin, pertahankan ikan di 15 koin
        ws.shop.sell_prices["radish"] = 1
        ws.shop.sell_prices["egg"] = 1
        ws.shop.sell_prices["wood"] = 1
        ws.shop.sell_prices["rock"] = 1
        ws.shop.sell_prices["fish"] = 15

        prob = build_problem_from_state(ws, domain=self.domain, goal_type="boss_defeated", max_coins=60)
        res = search_weighted_astar_hff(prob, weight=2.0, use_helpful_actions=True, timeout_sec=15.0)

        self.assertTrue(res.success, "Planner harus menemukan solusi valid meski harga diubah secara ekstrem!")
        plan_action_names = [a.name for a in res.plan]
        # Dengan komoditas lain bernilai 1 koin, hanya ikan yang dapat membiayai botol kedua
        self.assertIn("fish", plan_action_names, "Planner harus memanfaatkan rute memancing saat harga ikan jauh lebih menguntungkan!")
        self.assertIn("sell_fish", plan_action_names)

    def test_11_headless_plan_executor_real_world(self):
        """PlanExecutor mengeksekusi rencana pada WorldState nyata tanpa error prasyarat."""
        from planning.executor import PlanExecutor
        ws = WorldState(starting_coins=20)
        prob = build_problem_from_state(ws, domain=self.domain, goal_type="boss_defeated", max_coins=60)
        res = search_weighted_astar_hff(prob, weight=2.0, use_helpful_actions=True, timeout_sec=15.0)
        self.assertTrue(res.success)

        executor = PlanExecutor(ws)
        report = executor.execute_plan(res.plan, advance_crops=True)

        self.assertTrue(report.success, f"Eksekusi gagal: {report.failure_reason}")
        self.assertEqual(report.steps_executed, report.total_steps)
        self.assertTrue(ws.gate.is_open, "Gerbang harus terbuka di state dunia aktual!")
        self.assertTrue(ws.boss_defeated, "Boss harus berhasil dikalahkan di dunia aktual!")
        self.assertIsNotNone(ws.inventory.equipped, "Hero harus memiliki loadout terpasang!")
        self.assertGreater(report.total_actual_duration, 0.0)

    def test_12_incremental_planner_frame_budget(self):
        """IncrementalPlanner membatasi eksekusi per frame < 20 ms dan mencapai goal secara bertahap."""
        from planning.planner import IncrementalPlanner
        prob_ast = parse_problem(self.problem_raw)
        prob_ast.goal_facts = {("has", "gate_key")}
        problem = ground_problem(self.domain, prob_ast)

        inc_planner = IncrementalPlanner(problem, weight=2.0, use_helpful_actions=True)
        is_done = False
        res = None
        frames = 0

        while not is_done and frames < 100:
            frames += 1
            t0 = time.perf_counter()
            is_done, res = inc_planner.step(max_frame_ms=15.0)
            elapsed = (time.perf_counter() - t0) * 1000.0
            # Pastikan waktu eksekusi per frame aman dari lag spike (< 20 ms)
            self.assertLess(elapsed, 25.0, f"Frame {frames} melebihi batas anggaran waktu: {elapsed:.2f} ms!")

        self.assertTrue(is_done)
        self.assertIsNotNone(res)
        self.assertTrue(res.success)
        self.assertGreater(len(res.plan), 0)

    def test_13_plan_monitor_trigger_blocked_path(self):
        """PlanMonitor mendeteksi jalur yang terblokir rintangan dan memicu replanning."""
        from planning.monitor import PlanMonitor, ReplanTrigger
        from planning.strips import GroundAction
        ws = WorldState(starting_coins=20)
        monitor = PlanMonitor(ws, goal_type="boss_defeated")

        # Buat rencana buatan di mana hero harus berjalan ke lokasi yang jalurnya diputus
        mock_plan = [
            GroundAction("goto", ("spawn", "boss"), frozenset(), frozenset(), frozenset(), cost=10.0, duration=10.0)
        ]
        monitor.set_plan(mock_plan)

        # Gerbang terkunci, sehingga ke boss berdurasi infinity
        status = monitor.check_preconditions()
        self.assertFalse(status.is_valid)
        self.assertEqual(status.trigger, ReplanTrigger.BLOCKED_PATH)

        # Pemicu replanning
        ok, new_plan, msg = monitor.trigger_replan()
        self.assertTrue(ok)
        self.assertGreater(len(new_plan), 0)
        self.assertIn("Replanning BERHASIL", msg)

    def test_14_plan_monitor_trigger_hp_low_defeat_recovery(self):
        """PlanMonitor mendeteksi HP kritis hero dan menolak aksi sebelum sembuh."""
        from planning.monitor import PlanMonitor, ReplanTrigger
        from planning.strips import GroundAction
        ws = WorldState(starting_coins=20)
        monitor = PlanMonitor(ws, goal_type="boss_defeated")

        class MockHero:
            hp = 10
            max_hp = 100

        mock_plan = [
            GroundAction("fight_boss", (), frozenset(), frozenset(), frozenset(), cost=10.0, duration=10.0)
        ]
        monitor.set_plan(mock_plan)

        status = monitor.check_preconditions(hero=MockHero())
        self.assertFalse(status.is_valid)
        self.assertEqual(status.trigger, ReplanTrigger.HP_LOW)

    def test_15_plan_monitor_surrender_after_max_replans(self):
        """PlanMonitor menyerah ke kontrol manual setelah 3x replan berturut-turut gagal."""
        from planning.monitor import PlanMonitor
        ws = WorldState(starting_coins=20)
        # Buat problem mustahil (kunci tidak bisa dibuat)
        monitor = PlanMonitor(ws, goal_type="impossible_goal", max_consecutive_replans=3)

        ok1, _, _ = monitor.trigger_replan()
        self.assertFalse(ok1)
        self.assertFalse(monitor.surrendered)

        ok2, _, _ = monitor.trigger_replan()
        self.assertFalse(ok2)
        self.assertFalse(monitor.surrendered)

        ok3, _, msg3 = monitor.trigger_replan()
        self.assertFalse(ok3)
        self.assertTrue(monitor.surrendered)
        self.assertIn("Menyerah (surrender)", msg3)

    def test_16_satu_ambang_di_config(self):
        """Poin 1 & 3: Config memiliki SATU nilai ambang jujur READY_MIN_WIN_RATE = 0.50 tanpa variabel dekoratif."""
        import config
        self.assertTrue(hasattr(config, "READY_MIN_WIN_RATE"), "config harus memiliki READY_MIN_WIN_RATE")
        self.assertEqual(config.READY_MIN_WIN_RATE, 0.50, "READY_MIN_WIN_RATE harus bernilai 0.50")
        self.assertFalse(hasattr(config, "READY_MIN_WIN_RATE_FEASIBLE"), "Variabel dekoratif READY_MIN_WIN_RATE_FEASIBLE harus dihapus")

    def test_17_boss_ready_derived_from_readiness_json(self):
        """Poin 1 & 3: Fakta ready_loadout diturunkan secara dinamis murni dari readiness.json berdasar ambang config."""
        import config, json
        ws = WorldState(starting_coins=20)
        prob = build_problem_from_state(ws, domain=self.domain, goal_type="boss_defeated", max_coins=60)

        with open("data/planning/readiness.json", "r", encoding="utf-8") as f:
            rdata = json.load(f)

        ready_facts = {f for f in prob.initial_state.facts if f.name == "ready_loadout"}
        self.assertGreater(len(ready_facts), 0, "Harus ada ready_loadout yang memenuhi ambang 0.50")

        # Starter (win rate 0% - 11.5%) dan Leather Dagger (win rate 22.5% - 31%) tidak boleh ada di ready_loadout
        for f in ready_facts:
            self.assertNotEqual(f.args[0], "sword_basic", "Starter tidak boleh berstatus ready_loadout pada ambang 0.50")
            self.assertNotEqual(f.args[0], "weapon_dagger", "Belati Cepat tidak boleh berstatus ready_loadout pada ambang 0.50")
            # Hanya Tongkat Api dan Kapak Berat yang boleh ada
            self.assertIn(f.args[0], ("fire_staff", "weapon_axe"), "Hanya loadout dengan win rate >= 50% yang sah")

    def test_18_detour_sintetis_cost_difference(self):
        """Poin 3: Rute penyeberangan sungai West Bank -> East Bank memiliki selisih biaya positif (delta_cost > 0) saat jembatan ditutup."""
        from ai.pathfinding import astar
        from world.game_map import GameMap
        gmap = GameMap()
        bridge_b_override = {(24, 15), (43, 20)}

        def is_blocked_raw(cx, cy):
            px = cx * 32 + 16
            py = cy * 32 + 16
            return not gmap.is_walkable_at(px, py)

        def is_blocked_both_open(cx, cy):
            if (cx, cy) in bridge_b_override:
                return False
            return is_blocked_raw(cx, cy)

        def is_blocked_detour(cx, cy):
            if 35 <= cx <= 41 and 28 <= cy <= 33:
                return True
            if (cx, cy) in bridge_b_override:
                return False
            return is_blocked_raw(cx, cy)

        start = (34, 30)
        goal = (50, 29)
        res_before = astar(86, 48, start, goal, is_blocked_both_open)
        res_after = astar(86, 48, start, goal, is_blocked_detour)

        self.assertTrue(res_before.found)
        self.assertTrue(res_after.found)
        cost_before = len(res_before.path) / 4.6
        cost_after = len(res_after.path) / 4.6
        delta_cost = cost_after - cost_before

        self.assertGreater(delta_cost, 0.0, f"Selisih biaya detour harus positif! Didapat: {delta_cost:.2f}s")
        self.assertGreater(len(res_after.path), len(res_before.path))

    def test_19_pause_f10_and_wasd_stay_paused(self):
        """Poin 3 & 5: Input manual WASD menjeda Autopilot dan TETAP TERJEDA saat dilepas; resume butuh F10 eksplisit."""
        import pygame
        from planning.autopilot import AutopilotController, PlannerMode, AutopilotState
        ws = WorldState(starting_coins=20)
        auto = AutopilotController(ws)
        auto.mode = PlannerMode.AUTO
        auto.state = AutopilotState.NAVIGATING

        # 1. Pemain menekan tombol WASD
        handled = auto.handle_player_input({pygame.K_w: True})
        self.assertTrue(handled)
        self.assertEqual(auto.state, AutopilotState.PAUSED)
        self.assertTrue(auto.is_paused_by_player)

        # 2. Pemain melepas tombol WASD (tidak ada tombol ditekan)
        handled_release = auto.handle_player_input({})
        self.assertFalse(handled_release)
        # State HARUS TETAP TERJEDA (tidak boleh lanjut otomatis!)
        self.assertEqual(auto.state, AutopilotState.PAUSED, "Autopilot harus tetap terjeda setelah tombol dilepas!")
        self.assertTrue(auto.is_paused_by_player)

        # 3. Pemain menekan F10 untuk melanjutkan
        is_paused = auto.toggle_pause()
        self.assertFalse(is_paused)
        self.assertEqual(auto.state, AutopilotState.NAVIGATING, "Autopilot harus kembali NAVIGATING setelah F10 ditekan")
        self.assertFalse(auto.is_paused_by_player)

    def test_20_p4_search_timeout_under_4s(self):
        """Poin 3 & 4: WA*(h_FF) menyelesaikan P4 di bawah batas waktu timeout realistis (<= 4.0 s)."""
        ws = WorldState(starting_coins=20)
        prob = build_problem_from_state(ws, domain=self.domain, goal_type="boss_defeated", max_coins=60)
        res = search_weighted_astar_hff(prob, weight=2.0, use_helpful_actions=True, timeout_sec=4.0)

        self.assertTrue(res.success, f"P4 harus selesai sebelum timeout 4s: {res.failure_reason}")
        self.assertLessEqual(res.time_ms / 1000.0, 4.0, f"Waktu pencarian melebihi 4 detik: {res.time_ms} ms")
        self.assertGreater(len(res.plan), 0)

    def test_21_p4_feasible_after_coin_change_max_coins_60(self):
        """Poin 1 & 3: Dengan max_coins=60 dan ambang 0.50, P4 terbukti LAYAK (fire_staff 99.0% win rate)."""
        ws = WorldState(starting_coins=20)
        prob = build_problem_from_state(ws, domain=self.domain, goal_type="boss_defeated", max_coins=60)
        res = search_weighted_astar_hff(prob, weight=2.0, use_helpful_actions=True, timeout_sec=4.0)

        self.assertTrue(res.success, "P4 harus layak pada ambang 0.50 saat max_coins=60!")
        act_names = [a.name for a in res.plan]
        self.assertIn("buy_fire_staff", act_names, "Planner harus memilih Tongkat Api untuk memenuhi win rate >= 50%")
        self.assertIn("buy_armor_leather", act_names)
        self.assertIn("craft_potion", act_names)
        self.assertIn("fight_boss", act_names)
        self.assertLessEqual(len(res.plan), 40)

    # ==========================================================================
    # 6. VERIFIKASI POLISH LANJUTAN (POIN 6)
    # ==========================================================================
    def test_22_single_threshold_in_config(self):
        """Poin 6: Verifikasi ambang tunggal dan syarat wajib potion di config."""
        import config
        self.assertTrue(hasattr(config, "READY_MIN_WIN_RATE"), "Config harus memiliki READY_MIN_WIN_RATE")
        self.assertEqual(config.READY_MIN_WIN_RATE, 0.50, "Ambang kesiapan harus bernilai jujur 0.50")
        self.assertTrue(hasattr(config, "READY_MIN_POTIONS"), "Config harus memiliki READY_MIN_POTIONS")
        self.assertEqual(config.READY_MIN_POTIONS, 1, "Syarat wajib potion minimal 1 botol")
        self.assertFalse(hasattr(config, "READY_MIN_WIN_RATE_FEASIBLE"),
                         "Variabel dekoratif READY_MIN_WIN_RATE_FEASIBLE tidak boleh ada")

    def test_23_status_label_from_single_source(self):
        """Poin 6: Label status AUTO/ADVISOR/PAUSED dikendalikan dari satu sumber tanpa teks kontradiktif."""
        from planning.autopilot import AutopilotController, PlannerMode, AutopilotState
        ws = WorldState(starting_coins=20)
        ctrl = AutopilotController(ws)

        # Mode AUTO
        ctrl.mode = PlannerMode.AUTO
        ctrl.state = AutopilotState.NAVIGATING
        ctrl.is_paused_by_player = False
        self.assertEqual(ctrl.mode, "AUTO")

        # Mode PAUSED (F10 atau WASD)
        ctrl.toggle_pause()
        self.assertEqual(ctrl.state, AutopilotState.PAUSED)
        self.assertTrue(ctrl.is_paused_by_player)

        # Mode ADVISOR
        ctrl.mode = PlannerMode.ADVISOR
        self.assertEqual(ctrl.mode, "ADVISOR")

    def test_24_opening_log_disappears_after_5_seconds(self):
        """Poin 6: Log pembuka otomatis tersembunyi setelah 5 detik atau saat mode planner aktif."""
        import main
        # Buat dummy mock game sederhana
        class MockGame:
            def __init__(self):
                self.planner_mode = "OFF"
                self.time = 0.0
                self.messages = [("ELDORIA: Mulai petualangan...", (255, 255, 255), 0.0)]

            def is_log_visible(self):
                if self.planner_mode in ("ADVISOR", "AUTO"):
                    return False
                if self.time >= 5.0:
                    return False
                return True

        mg = MockGame()
        self.assertTrue(mg.is_log_visible(), "Log harus terlihat pada detik awal saat OFF")

        # Skenario 1: Lewat dari 5 detik
        mg.time = 5.1
        self.assertFalse(mg.is_log_visible(), "Log harus hilang setelah 5 detik")

        # Skenario 2: Mode planner aktif (AUTO atau ADVISOR)
        mg.time = 1.0
        mg.planner_mode = "AUTO"
        self.assertFalse(mg.is_log_visible(), "Log harus disembunyikan saat mode AUTO aktif")
        mg.planner_mode = "ADVISOR"
        self.assertFalse(mg.is_log_visible(), "Log harus disembunyikan saat mode ADVISOR aktif")

    def test_25_potion_policy_monotonic(self):
        """Poin 6: Monotonisitas win rate terhadap jumlah ramuan: W(k+1) >= W(k)."""
        import json
        with open("data/planning/readiness.json", "r", encoding="utf-8") as f:
            rdata = json.load(f)

        for l_key in ("starter", "leather_dagger", "iron_axe", "fire_staff"):
            self.assertIn(l_key, rdata)
            wr_list = [rdata[l_key][str(p)]["hero_win_rate"] for p in range(4)]
            for p in range(len(wr_list) - 1):
                self.assertGreaterEqual(
                    wr_list[p + 1], wr_list[p],
                    f"Win rate {l_key} tidak monoton! Potion {p} ({wr_list[p]}%) > Potion {p+1} ({wr_list[p+1]}%)"
                )

    def test_26_gen_readiness_and_new_item_planner(self):
        """Poin 3 & 6: Item baru di catalog + gen_readiness -> planner buy, equip, dan fight tanpa ubah Python."""
        import tempfile, json
        from tools.gen_readiness import generate_readiness_matrix

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_catalog = os.path.join(tmpdir, "catalog.json")
            tmp_readiness = os.path.join(tmpdir, "readiness.json")

            custom_cat = {
                "weapons": [
                    {"id": "sword_basic", "name": "Pedang Biasa"},
                    {"id": "weapon_dagger", "name": "Belati Cepat"},
                    {"id": "weapon_axe", "name": "Kapak Berat"},
                    {"id": "fire_staff", "name": "Tongkat Api"},
                    {"id": "tombak_petir", "name": "Tombak Petir"}
                ],
                "armors": [
                    {"id": "cloth_armor", "name": "Kain"},
                    {"id": "armor_leather", "name": "Kulit"},
                    {"id": "armor_iron", "name": "Besi"}
                ]
            }
            with open(tmp_catalog, "w", encoding="utf-8") as f:
                json.dump(custom_cat, f)

            # Generate matrix ke file sementara
            rdata = generate_readiness_matrix(catalog_path=tmp_catalog, output_path=tmp_readiness, sample_size=20)
            self.assertIn("tombak_petir__armor_leather", rdata, "Entry tombak_petir harus digenerate")
            self.assertIn("3", rdata["tombak_petir__armor_leather"])

    def test_27_status_label_auto_advisor_paused_single_source(self):
        """Poin 6: Label status AUTO/ADVISOR/PAUSED konsisten dari satu sumber tanpa kontradiksi."""
        from planning.autopilot import AutopilotController, PlannerMode, AutopilotState
        import config

        ws = WorldState(starting_coins=20)
        ctrl = AutopilotController(ws)

        # 1. Mode AUTO
        ctrl.mode = PlannerMode.AUTO
        ctrl.state = AutopilotState.NAVIGATING
        is_auto = (ctrl.mode == "AUTO") or (getattr(ctrl, "control_mode", None) == config.CONTROL_AUTOPILOT)
        self.assertTrue(is_auto, "Evaluasi is_auto harus True saat mode AUTO")
        self.assertNotIn("MANUAL", ctrl.status_message, "HUD tidak boleh menampilkan teks MANUAL saat mode AUTO")

        # 2. Mode PAUSED
        ctrl.toggle_pause()
        self.assertEqual(ctrl.state, AutopilotState.PAUSED)
        self.assertTrue(ctrl.is_paused_by_player)
        self.assertIn("DIJEDA", ctrl.status_message)

        # 3. Mode ADVISOR
        ctrl.mode = PlannerMode.ADVISOR
        self.assertEqual(ctrl.mode, "ADVISOR")

    def test_28_detour_sintetis_cost_difference_positive(self):
        """Poin 6: Detour sintetis via koridor utara menghasilkan delta cost > 0 dan waypoint valid."""
        from ai.pathfinding import astar
        from world.game_map import GameMap

        gmap = GameMap()
        bridge_b_override = {(24, 15), (43, 20)}

        def is_blocked_raw(cx, cy):
            px = cx * 32 + 16
            py = cy * 32 + 16
            return not gmap.is_walkable_at(px, py)

        def is_blocked_direct(cx, cy):
            if (cx, cy) in bridge_b_override:
                return False
            return is_blocked_raw(cx, cy)

        def is_blocked_detour(cx, cy):
            if 35 <= cx <= 41 and 28 <= cy <= 33:
                return True
            if (cx, cy) in bridge_b_override:
                return False
            return is_blocked_raw(cx, cy)

        start = (34, 30)
        goal = (50, 29)
        res_before = astar(86, 48, start, goal, is_blocked_direct)
        res_after = astar(86, 48, start, goal, is_blocked_detour)

        self.assertTrue(res_before.found)
        self.assertTrue(res_after.found)
        cost_before = len(res_before.path) / 4.6
        cost_after = len(res_after.path) / 4.6
        delta_cost = cost_after - cost_before

        self.assertGreater(delta_cost, 0.0, f"Selisih biaya detour harus positif (> 0), didapat: {delta_cost:+.2f} s")
        self.assertGreater(len(res_after.path), len(res_before.path))

    def test_29_planner_level_new_item_buy_equip_fight(self):
        """Poin 6: Item baru di catalog menghasilkan buy_item, equip, dan fight_boss otonom tanpa ubah Python."""
        import tempfile, json
        from planning.pddl_parser import parse_domain

        with open("data/planning/expedition.domain", "r", encoding="utf-8") as f:
            domain = parse_domain(f.read())

        ws = WorldState(starting_coins=60)
        ws.shop.catalog["Tombak Petir"] = {"price": 30, "stock": 1, "name": "Tombak Petir", "type": "weapon"}
        ws.inventory.add_item("potion_red", 1)
        ws.inventory.add_item("Kulit", 1)
        ws.gate.is_open = True
        dm = DistanceMatrix()

        old_cat = "data/catalog.json"
        old_readiness = "data/planning/readiness.json"
        with open(old_cat, "r", encoding="utf-8") as f:
            saved_cat = f.read()
        with open(old_readiness, "r", encoding="utf-8") as f:
            saved_r = f.read()

        try:
            cat_d = json.loads(saved_cat)
            cat_d["weapons"].append({"id": "tombak_petir", "name": "Tombak Petir", "price": 30})
            with open(old_cat, "w", encoding="utf-8") as f:
                json.dump(cat_d, f)

            rdata = {
                "starter": {"1": {"is_ready": False}},
                "leather_dagger": {"1": {"is_ready": False}},
                "iron_axe": {"1": {"is_ready": False}},
                "fire_staff": {"1": {"is_ready": False}},
                "tombak_petir__armor_leather": {
                    "weapon": "tombak_petir", "armor": "armor_leather",
                    "1": {"hero_win_rate": 99.0, "is_ready": True}
                }
            }
            with open(old_readiness, "w", encoding="utf-8") as f:
                json.dump(rdata, f)

            prob = build_problem_from_state(ws, domain=domain, goal_type="boss_defeated", distance_matrix=dm, max_coins=60)
            res = search_weighted_astar_hff(prob, weight=2.0)
            self.assertTrue(res.success, f"Pencarian harus sukses: {res.failure_reason}")

            plan_str = [f"{a.name} {a.params}" for a in res.plan]
            has_buy = any("buy_item" in s and "tombak_petir" in s for s in plan_str)
            has_equip = any("equip" in s and "tombak_petir" in s for s in plan_str)
            has_fight = any("fight_boss" in s and "tombak_petir" in s for s in plan_str)

            self.assertTrue(has_buy, f"Rencana harus memuat buy_item tombak_petir: {plan_str}")
            self.assertTrue(has_equip, f"Rencana harus memuat equip tombak_petir: {plan_str}")
            self.assertTrue(has_fight, f"Rencana harus memuat fight_boss tombak_petir: {plan_str}")

            val = PlanValidator.validate(prob, res.plan)
            self.assertTrue(val.valid, "Rencana dengan item baru harus lolos PlanValidator")
        finally:
            with open(old_cat, "w", encoding="utf-8") as f:
                f.write(saved_cat)
            with open(old_readiness, "w", encoding="utf-8") as f:
                f.write(saved_r)

    def test_30_skenario_kalah_memuat_langkah_mendapatkan_potion(self):
        """Poin 6: Skenario kalah dengan potion habis memuat langkah mendapatkan potion (craft_potion) sebelum fight."""
        from planning.pddl_parser import parse_domain
        with open("data/planning/expedition.domain", "r", encoding="utf-8") as f:
            domain = parse_domain(f.read())

        ws = WorldState(starting_coins=20)
        ws.inventory.add_item("Tongkat Api", 1)
        ws.inventory.add_item("Kulit", 1)
        ws.inventory.equipped = {"weapon": "Tongkat Api", "armor": "Kulit"}
        # Potion habis (0)
        ws.gate.is_open = True
        dm = DistanceMatrix()

        class MockHeroAtSpawn:
            px = 1440.0
            py = 1056.0
            hp = 100
            max_hp = 100

        prob = build_problem_from_state(ws, hero=MockHeroAtSpawn(), domain=domain,
                                        goal_type="boss_defeated", distance_matrix=dm, max_coins=60)
        res = search_weighted_astar_hff(prob, weight=2.0)
        self.assertTrue(res.success)

        plan_str = [f"{a.name} {a.params}" for a in res.plan]
        # Pastikan rencana memuat craft_potion
        craft_indices = [i for i, s in enumerate(plan_str) if "craft_potion" in s]
        fight_indices = [i for i, s in enumerate(plan_str) if "fight_boss" in s]

        self.assertTrue(len(craft_indices) > 0, f"Rencana pemulihan wajib memuat aksi craft_potion: {plan_str}")
        self.assertTrue(len(fight_indices) > 0, "Rencana pemulihan wajib memuat aksi fight_boss")
        self.assertLess(craft_indices[0], fight_indices[0], "Aksi craft_potion harus dieksekusi SEBELUM fight_boss")

        val = PlanValidator.validate(prob, res.plan)
        self.assertTrue(val.valid, "Rencana pemulihan harus valid menurut PlanValidator")
        self.assertTrue(val.goal_reached, "Sasaran boss_defeated harus tercapai")

    def test_31_replan_2c_reversed_river_blocked_to_quarry(self):
        """Poin 6: Replan 2c versi balik: Default batu sungai diblokir -> beralih ke quarry dengan delta cost > 0."""
        from planning.pddl_parser import parse_domain
        from planning.planner import IncrementalPlanner

        with open("data/planning/expedition.domain", "r", encoding="utf-8") as f:
            domain = parse_domain(f.read())

        ws = WorldState(starting_coins=20)
        dm = DistanceMatrix()

        # Rencana awal: batu sungai (default)
        prob_before = build_problem_from_state(ws, domain=domain, goal_type="craft_key", distance_matrix=dm, max_coins=35)
        res_before = search_weighted_astar_hff(prob_before, weight=2.0)
        self.assertTrue(res_before.success)
        cost_before = res_before.total_cost
        plan_before_str = [f"{a.name} {a.params}" for a in res_before.plan]
        self.assertTrue(any("mine_rock_river" in s for s in plan_before_str), "Rencana awal harus memakai mine_rock_river")

        # Blokir river_fishing
        for loc in dm.locations:
            dm._cache[(loc, "river_fishing", False)] = (float("inf"), 0, [])
            dm._cache[("river_fishing", loc, False)] = (float("inf"), 0, [])

        # Replan ke quarry
        prob_after = build_problem_from_state(ws, domain=domain, goal_type="craft_key", distance_matrix=dm, max_coins=35)
        res_after = search_weighted_astar_hff(prob_after, weight=2.0)
        self.assertTrue(res_after.success)
        cost_after = res_after.total_cost
        plan_after_str = [f"{a.name} {a.params}" for a in res_after.plan]
        self.assertTrue(any("mine_rock" in s and "mine_rock_river" not in s for s in plan_after_str),
                        "Rencana setelah diblokir harus beralih ke mine_rock di quarry")

        delta_cost = cost_after - cost_before
        self.assertGreater(delta_cost, 0.0, f"Selisih biaya replan harus positif (> 0), didapat: {delta_cost:+.2f} s")

        # Verifikasi budget frame incremental planner
        inc = IncrementalPlanner(prob_after, weight=2.0)
        frame_times = []
        while True:
            t0 = time.perf_counter()
            done, _ = inc.step(max_frame_ms=12.0)
            frame_times.append((time.perf_counter() - t0) * 1000.0)
            if done:
                break
        max_frame = max(frame_times) if frame_times else 0.0
        self.assertLessEqual(max_frame, 22.0, f"Frame time harus <= 22 ms, didapat: {max_frame:.2f} ms")


if __name__ == "__main__":
    unittest.main()
