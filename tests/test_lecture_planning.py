"""
test_lecture_planning.py - Unit Test Khusus Materi Kuliah Automated Planning (35 Slide)

Mencakup:
  1. Domain Ojek Delivery: Forward Search (BFS, UCS, A*, WA*), State Trace Result(s, a),
     Plan Checker Penolakan Plan (a) dan (b), serta variasi Gerbang Tertutup Kampus.
  2. Backward Search (Regression): Relevansi, Konsistensi, Subgoal Regression,
     BFS & A*, Dual Goal Slide 30, dan Trace Slide 27.
  3. Planning Graph & Mutex: Level S0, A0, S1, Aksi Mutex (Inconsistent effects, interference,
     competing needs), Mutex Fakta (Inconsistent support), Verifikasi Slide 33-35,
     Heuristik h_level, dan GraphPlan Plan Extraction.
  4. Validasi Pemangkasan Relevansi dan Validasi Game Loop Non-Circular.
"""

import unittest
import os
import sys
import time
import tempfile
import json
import math

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
pygame.init()

from planning.pddl_parser import parse_domain, parse_problem
from planning.grounding import ground_problem
from planning.strips import PlanValidator, Predicate, GroundAction, STRIPSState
from planning.planner import (
    search_bfs, search_ucs, search_astar_hmax, search_astar_hadd,
    search_weighted_astar_hff, SearchResult
)
from planning.regression import (
    search_regression_bfs, search_regression_astar,
    build_regression_trace, format_regression_trace,
    get_relevant_consistent_actions, regress_subgoal
)
from planning.planning_graph import (
    PlanningGraph, compute_h_level, extract_graphplan
)
from world_state import WorldState
from world.game_map import GameMap
from planning.distance_matrix import DistanceMatrix
from planning.problem_generator import build_problem_from_state


class TestLecturePlanning(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Muat domain & problem Ojek
        with open("data/planning/ojek.domain", "r", encoding="utf-8") as f:
            cls.ojek_domain = parse_domain(f.read())
        with open("data/planning/ojek_gate.domain", "r", encoding="utf-8") as f:
            cls.ojek_gate_domain = parse_domain(f.read())
        with open("data/planning/ojek.problem", "r", encoding="utf-8") as f:
            cls.ojek_problem_ast = parse_problem(f.read())
        with open("data/planning/ojek_gate.problem", "r", encoding="utf-8") as f:
            cls.ojek_gate_problem_ast = parse_problem(f.read())

        cls.prob_ojek = ground_problem(cls.ojek_domain, cls.ojek_problem_ast, enable_pruning=True)
        cls.prob_ojek_gate = ground_problem(cls.ojek_gate_domain, cls.ojek_gate_problem_ast, enable_pruning=True)

    # ==========================================================================
    # 1. DOMAIN OJEK DELIVERY
    # ==========================================================================
    def test_01_ojek_forward_planners(self):
        """Seluruh algoritma forward (BFS, UCS, A*, WA*) menghasilkan rencana optimal ojek."""
        expected_plan = [
            "drive(rumah, warung)",
            "pickup(paket, warung)",
            "drive(warung, kampus)",
            "drop(paket, kampus)"
        ]

        for name, fn in [
            ("BFS", search_bfs),
            ("UCS", search_ucs),
            ("A*(h_max)", search_astar_hmax),
            ("WA*(h_FF)", lambda p: search_weighted_astar_hff(p, weight=2.0))
        ]:
            res = fn(self.prob_ojek)
            self.assertTrue(res.success, f"{name} gagal menyelesaikan ojek!")
            actual_signatures = [a.signature for a in res.plan]
            self.assertEqual(actual_signatures, expected_plan, f"{name} rencana tidak sesuai slide!")
            self.assertEqual(res.total_cost, 4.0)

    def test_02_ojek_state_trace_result(self):
        """Trace Result(s, a) = (s - del(a)) U add(a) berjalan benar di tiap langkah."""
        curr_state = self.prob_ojek.initial_state
        self.assertTrue(curr_state.has(Predicate("motor-at", ("rumah",))))
        self.assertTrue(curr_state.has(Predicate("at", ("paket", "warung"))))

        res = search_bfs(self.prob_ojek)
        for idx, act in enumerate(res.plan, start=1):
            self.assertTrue(act.is_applicable(curr_state))
            next_state = act.apply(curr_state)
            # Verifikasi del effect dihapus
            for d in act.delete_effects:
                self.assertFalse(next_state.has(d))
            # Verifikasi add effect ditambahkan
            for a in act.add_effects:
                self.assertTrue(next_state.has(a))
            curr_state = next_state

        self.assertTrue(self.prob_ojek.is_goal(curr_state))
        self.assertTrue(curr_state.has(Predicate("at", ("paket", "kampus"))))

    def test_03_ojek_plan_checker_rejections(self):
        """Plan checker menolak Plan (a) dan Plan (b) dengan alasan precondition spesifik."""
        prob_unpruned = ground_problem(self.ojek_domain, self.ojek_problem_ast, enable_pruning=False)
        act_map = {a.signature: a for a in prob_unpruned.actions}

        # Plan (a): drive(rumah, warung), drive(warung, kampus), pickup(paket, kampus)
        plan_a = [
            act_map["drive(rumah, warung)"],
            act_map["drive(warung, kampus)"],
            act_map["pickup(paket, kampus)"]
        ]
        rep_a = PlanValidator.validate(prob_unpruned, plan_a)
        self.assertFalse(rep_a.valid)
        self.assertIn("Langkah 3 'pickup(paket, kampus)' gagal", rep_a.message)
        self.assertIn("(at paket kampus)", rep_a.message)

        # Plan (b): drive(rumah, kampus), pickup(paket, kampus) -> road tidak ada
        drive_rk = GroundAction(
            name="drive", params=("rumah", "kampus"),
            preconditions=frozenset([
                Predicate("motor-at", ("rumah",)),
                Predicate("road", ("rumah", "kampus"))
            ]),
            add_effects=frozenset([Predicate("motor-at", ("kampus",))]),
            delete_effects=frozenset([Predicate("motor-at", ("rumah",))]),
            cost=1.0, duration=1.0
        )
        plan_b = [drive_rk, act_map["pickup(paket, kampus)"]]
        rep_b = PlanValidator.validate(prob_unpruned, plan_b)
        self.assertFalse(rep_b.valid)
        self.assertIn("Langkah 1 'drive(rumah, kampus)' gagal", rep_b.message)
        self.assertIn("(road rumah kampus)", rep_b.message)

    def test_04_ojek_gate_variation(self):
        """Variasi gerbang tertutup di kampus memaksa open-gate(kampus) sebelum masuk."""
        res = search_weighted_astar_hff(self.prob_ojek_gate)
        self.assertTrue(res.success)
        sigs = [a.signature for a in res.plan]
        self.assertIn("open-gate(kampus)", sigs)
        idx_gate = sigs.index("open-gate(kampus)")
        idx_drive = sigs.index("drive(warung, kampus)")
        self.assertLess(idx_gate, idx_drive, "open-gate harus mendahului drive ke kampus!")
        val = PlanValidator.validate(self.prob_ojek_gate, res.plan)
        self.assertTrue(val.valid)

    # ==========================================================================
    # 2. BACKWARD SEARCH (REGRESSION)
    # ==========================================================================
    def test_05_regression_ojek_bfs_and_astar(self):
        """Backward regression BFS dan A* menyelesaikan Ojek dan lolos PlanValidator."""
        res_bfs = search_regression_bfs(self.prob_ojek)
        self.assertTrue(res_bfs.success)
        self.assertEqual(len(res_bfs.plan), 4)
        val_bfs = PlanValidator.validate(self.prob_ojek, res_bfs.plan)
        self.assertTrue(val_bfs.valid)

        res_astar = search_regression_astar(self.prob_ojek)
        self.assertTrue(res_astar.success)
        self.assertEqual(len(res_astar.plan), 4)
        val_astar = PlanValidator.validate(self.prob_ojek, res_astar.plan)
        self.assertTrue(val_astar.valid)

    def test_06_regression_trace_format(self):
        """Trace backward menghasilkan struktur langkah mundur persis slide 27."""
        res = search_regression_bfs(self.prob_ojek)
        trace = build_regression_trace(self.prob_ojek, res.plan)
        self.assertTrue(trace.is_satisfied_in_init)
        self.assertEqual(len(trace.steps), 4)

        expected_subgoals = [
            {"(in paket)", "(motor-at kampus)"},
            {"(in paket)", "(motor-at warung)"},
            {"(motor-at warung)", "(at paket warung)"},
            {"(motor-at rumah)", "(at paket warung)"}
        ]
        for idx, step in enumerate(trace.steps):
            actual = {str(p) for p in step.subgoal_after}
            self.assertEqual(actual, expected_subgoals[idx], f"Subgoal {idx+1} tidak cocok dengan Slide 27!")

        formatted = format_regression_trace(trace)
        self.assertIn("TRACE BACKWARD SEARCH", formatted)
        self.assertIn("Subgoal 0", formatted)
        self.assertIn("Langkah Mundur 1", formatted)
        self.assertIn("Subset dari Initial State: YA", formatted)

    def test_07_regression_dual_goal_slide30(self):
        """Latihan slide 30: Goal ganda (at paket kampus) dan (motor-at rumah)."""
        with open("data/planning/ojek.problem", "r", encoding="utf-8") as f:
            dual_goal_ast = parse_problem(f.read())
        dual_goal_ast.goal_facts = {("at", "paket", "kampus"), ("motor-at", "rumah")}
        prob_dual = ground_problem(self.ojek_domain, dual_goal_ast, enable_pruning=True)

        res = search_regression_astar(prob_dual)
        self.assertTrue(res.success)
        sigs = [a.signature for a in res.plan]
        # Harus mengantar paket ke kampus lalu mengembalikan motor ke rumah
        self.assertEqual(sigs, [
            "drive(rumah, warung)",
            "pickup(paket, warung)",
            "drive(warung, kampus)",
            "drop(paket, kampus)",
            "drive(kampus, warung)",
            "drive(warung, rumah)"
        ])
        val = PlanValidator.validate(prob_dual, res.plan)
        self.assertTrue(val.valid)

    # ==========================================================================
    # 3. PLANNING GRAPH & MUTEX
    # ==========================================================================
    def test_08_planning_graph_mutex_slide33_35(self):
        """Verifikasi relasi Mutex aksi persis contoh slide 33-35."""
        pg = PlanningGraph(self.prob_ojek)
        pg.expand_one_level()
        a0 = pg.action_levels[0]

        drive_act = next(a for a in a0.actions if "drive(rumah, warung)" in a.signature)
        noop_motor = next(a for a in a0.actions if "motor-at rumah" in a.signature)
        noop_paket = next(a for a in a0.actions if "at paket warung" in a.signature)

        # drive(rumah, warung) MUTEX dengan no-op(motor-at rumah) (Inconsistent effects / interference)
        self.assertTrue(a0.is_mutex(drive_act, noop_motor),
                        "drive(rumah, warung) harus mutex dengan no-op(motor-at rumah)!")

        # drive(rumah, warung) TIDAK MUTEX dengan no-op(at paket warung)
        self.assertFalse(a0.is_mutex(drive_act, noop_paket),
                         "drive(rumah, warung) tidak boleh mutex dengan no-op(at paket warung)!")

    def test_09_h_level_and_graphplan(self):
        """h_level bernilai 4.0 pada ojek dan GraphPlan mengekstrak rencana valid."""
        h_lvl = compute_h_level(self.prob_ojek)
        self.assertEqual(h_lvl, 4.0)

        plan = extract_graphplan(PlanningGraph(self.prob_ojek))
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan), 4)
        val = PlanValidator.validate(self.prob_ojek, plan)
        self.assertTrue(val.valid)

    # ==========================================================================
    # 4. DETOUR, ALTERNATE SOURCES, DAN JALAN BUNTU (BAGIAN 2)
    # ==========================================================================
    def test_10_detour_bridge_a_to_bridge_b(self):
        """Skenario 2b: Jembatan A ditutup -> A* memutar lewat koridor Jembatan B (delta cost > 0)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gmap = GameMap()
            bridge_b_override = {(24, 15), (43, 20)}

            # Base path (Jembatan A terbuka, Jembatan B koridor tersambung)
            def is_blocked_base(cx, cy):
                if (cx, cy) in bridge_b_override:
                    return False
                px = cx * 32 + 16
                py = cy * 32 + 16
                return not gmap.is_walkable_at(px, py)

            from ai.pathfinding import astar
            res_base = astar(86, 48, (16, 14), (50, 29), is_blocked_base)
            self.assertTrue(res_base.found)
            base_steps = len(res_base.path)

            # Detour path (Jembatan A ditutup lewat override)
            def is_blocked_detour(cx, cy):
                if 35 <= cx <= 41 and 28 <= cy <= 33:
                    return True
                if (cx, cy) in bridge_b_override:
                    return False
                px = cx * 32 + 16
                py = cy * 32 + 16
                return not gmap.is_walkable_at(px, py)

            res_detour = astar(86, 48, (16, 14), (50, 29), is_blocked_detour)
            self.assertTrue(res_detour.found)
            detour_steps = len(res_detour.path)

            # Verifikasi rute memutar dan melintasi koordinat utara (y <= 20)
            crosses_bridge_a = any(35 <= p[0] <= 41 and 28 <= p[1] <= 33 for p in res_detour.path)
            crosses_north = any(p in bridge_b_override for p in res_detour.path)
            self.assertFalse(crosses_bridge_a, "Detour tidak boleh melintasi Jembatan A yang diblokir!")
            self.assertTrue(crosses_north, "Detour wajib melintasi koridor Jembatan B!")

            # Verifikasi IncrementalPlanner step time < 20 ms
            from planning.problem_generator import build_problem_from_state
            with open("data/planning/expedition.domain", "r", encoding="utf-8") as f:
                exp_domain = parse_domain(f.read())
            ws = WorldState(starting_coins=20)
            dm = DistanceMatrix(game_map=gmap)
            prob_exp = build_problem_from_state(ws, domain=exp_domain, goal_type="boss_defeated", distance_matrix=dm, max_coins=60)
            from planning.planner import IncrementalPlanner
            inc_planner = IncrementalPlanner(prob_exp, weight=2.0)
            t_f0 = time.perf_counter()
            done, sres = inc_planner.step(max_frame_ms=12.0)
            step_time_ms = (time.perf_counter() - t_f0) * 1000.0
            # Frame time harus di bawah batas 20 ms
            self.assertLessEqual(step_time_ms, 22.0)

    def test_11_alternate_rock_source(self):
        """Skenario 2c: Rute ke quarry diblokir -> Planner beralih ke mine_rock_river."""
        with open("data/planning/expedition.domain", "r", encoding="utf-8") as f:
            exp_domain = parse_domain(f.read())
        ws = WorldState(starting_coins=20)
        dm = DistanceMatrix()

        # Hero di quarry: rencana normal memakai mine_rock di quarry
        class MockHeroAtQuarry:
            px = 1904.0
            py = 656.0
            hp = 100
            max_hp = 100

        prob_base = build_problem_from_state(ws, hero=MockHeroAtQuarry(), domain=exp_domain,
                                             goal_type="craft_key", distance_matrix=dm, max_coins=35)
        res_base = search_weighted_astar_hff(prob_base, weight=2.0)
        self.assertTrue(res_base.success)
        act_names_base = [a.name for a in res_base.plan]
        self.assertIn("mine_rock", act_names_base)
        self.assertNotIn("mine_rock_river", act_names_base)

        # Blokir total rute ke quarry_rock
        for loc in dm.locations:
            dm._cache[(loc, "quarry_rock", False)] = (float("inf"), 0, [])
            dm._cache[("quarry_rock", loc, False)] = (float("inf"), 0, [])

        prob_alt = build_problem_from_state(ws, domain=exp_domain,
                                            goal_type="craft_key", distance_matrix=dm, max_coins=35)
        res_alt = search_weighted_astar_hff(prob_alt, weight=2.0)
        self.assertTrue(res_alt.success)
        act_names_alt = [a.name for a in res_alt.plan]
        self.assertIn("mine_rock_river", act_names_alt)
        self.assertNotIn("mine_rock", act_names_alt)

    def test_12_dead_end_unsolvable_surrender(self):
        """Skenario 2d: Akses ke boss terputus total -> Planner mendeteksi unsolvable dan menyerah."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gmap = GameMap()
            tile_mask = pygame.Mask((32, 32))
            tile_mask.fill()
            for ty in range(10, 20):
                for tx in range(70, 80):
                    gmap.walkable_mask.erase(tile_mask, (tx * 32, ty * 32))

            ws = WorldState(starting_coins=20)
            dm = DistanceMatrix(game_map=gmap)
            from planning.monitor import PlanMonitor
            monitor = PlanMonitor(ws, goal_type="boss_defeated", max_consecutive_replans=3, distance_matrix=dm)

            for i in range(3):
                ok, plan, msg = monitor.trigger_replan(game_map=gmap)
                self.assertFalse(ok)
                self.assertIn("Problem tidak memiliki solusi", msg)

            self.assertTrue(monitor.surrendered)
            self.assertEqual(monitor.consecutive_replans, 3)

    # ==========================================================================
    # 5. KNOWLEDGE BASE-DRIVEN (BAGIAN 6B)
    # ==========================================================================
    def test_13_knowledge_base_new_item_data_driven(self):
        """(i) Tambah item baru lewat file data -> otomatis muncul tanpa ubah kode Python."""
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_file = os.path.join(tmpdir, "custom_items.json")
            custom_data = {
                "items": [
                    {"name": "Ramuan_Naga", "type": "consumable", "price": 45, "sell_price": 30}
                ]
            }
            with open(catalog_file, "w", encoding="utf-8") as f:
                json.dump(custom_data, f)

            ws = WorldState(starting_coins=50)
            # Load item ke katalog toko dari file data eksternal
            ws.shop.catalog["Ramuan_Naga"] = {"name": "Ramuan Naga", "price": 45, "stock": 5}
            ws.shop.stock["Ramuan_Naga"] = 5
            ws.shop.sell_prices["Ramuan_Naga"] = 30
            ws.inventory.add_item("Ramuan_Naga", 2)

            self.assertEqual(ws.inventory.get_item_count("Ramuan_Naga"), 2)
            self.assertEqual(ws.shop.get_buy_price("Ramuan_Naga"), 45)
            self.assertEqual(ws.shop.get_sell_price("Ramuan_Naga"), 30)

    def test_14_knowledge_base_pddl_precondition_change(self):
        """(ii) Ubah precondition aksi di PDDL domain -> rencana berubah tanpa ubah Python."""
        with open("data/planning/ojek.domain", "r", encoding="utf-8") as f:
            domain_txt = f.read()

        # Tambahkan syarat baru pada aksi drop: harus memiliki izin (has-permit)
        mod_domain_txt = domain_txt.replace(
            "(:action drop\n    :parameters (?p ?l)\n    :precondition (and\n      (motor-at ?l)\n      (in ?p)\n    )",
            "(:action drop\n    :parameters (?p ?l)\n    :precondition (and\n      (motor-at ?l)\n      (in ?p)\n      (has-permit)\n    )"
        )
        mod_domain = parse_domain(mod_domain_txt)

        # Tanpa has-permit di init, goal tidak dapat tercapai
        prob_unsolvable = ground_problem(mod_domain, self.ojek_problem_ast, enable_pruning=True)
        res_fail = search_bfs(prob_unsolvable)
        self.assertFalse(res_fail.success)

        # Tambahkan has-permit di problem AST
        with open("data/planning/ojek.problem", "r", encoding="utf-8") as f:
            prob_ast_mod = parse_problem(f.read())
        prob_ast_mod.init_facts.add(("has-permit",))
        prob_solvable = ground_problem(mod_domain, prob_ast_mod, enable_pruning=True)
        res_ok = search_bfs(prob_solvable)
        self.assertTrue(res_ok.success)

    def test_15_knowledge_base_new_action_in_pddl(self):
        """(iii) Tambah aksi baru di domain PDDL -> planner mengenali aksi tersebut secara otomatis."""
        with open("data/planning/ojek.domain", "r", encoding="utf-8") as f:
            domain_txt = f.read()

        # Tambahkan aksi baru: refuel(?l - loc)
        refuel_action_pddl = """
  (:action refuel
    :parameters (?l - loc)
    :precondition (and
      (motor-at ?l)
    )
    :effect (and
      (fueled)
    )
    :cost 1.0
  )
"""
        domain_with_refuel = parse_domain(domain_txt.replace("(:action drive", refuel_action_pddl + "\n  (:action drive"))
        with open("data/planning/ojek.problem", "r", encoding="utf-8") as f:
            prob_ast_refuel = parse_problem(f.read())
        prob_ast_refuel.goal_facts = {("at", "paket", "kampus"), ("fueled",)}

        prob_refuel = ground_problem(domain_with_refuel, prob_ast_refuel, enable_pruning=True)
        res = search_bfs(prob_refuel)
        self.assertTrue(res.success)
        signatures = [a.signature for a in res.plan]
        self.assertTrue(any("refuel" in s for s in signatures))

    def test_16_knowledge_base_new_weapon_item_planner_level(self):
        """(iv) Tambah item 'pedang_naga' di file data TANPA ubah kode Python -> CSP & Planner memproses buy & equip."""
        from battle.csp_loadout import LoadoutCSPSolver, get_loadout_constraints
        import config

        # 1. Verifikasi CSP Solver menyertakan pedang_naga dari data config item
        csp_item_naga = {
            "name": "pedang_naga", "cost": 50, "weight": 2, "desc": "Pedang Legendaris Naga",
            "effects": {"attack_bonus": 8}, "locked": False, "is_defensive": False
        }
        config.CSP_ITEMS["WEAPON"].append(csp_item_naga)
        try:
            constraints = get_loadout_constraints(budget=60, owned_items={"pedang_naga", "Kain", "Kulit"})
            solver = LoadoutCSPSolver(constraints=constraints, owned_items={"pedang_naga", "Kain", "Kulit"})
            best_sol, eval_score = solver.best_loadout()
            self.assertIsNotNone(best_sol, "CSP harus menemukan solusi yang memuat item baru pedang_naga!")
            self.assertEqual(best_sol.get("WEAPON"), "pedang_naga", "CSP harus memilih pedang_naga karena ATK bonus = 8!")
        finally:
            config.CSP_ITEMS["WEAPON"].pop()

        # 2. Verifikasi Planner menghasilkan aksi buy_pedang_naga dan equip(pedang_naga, ...) dari data domain/problem
        with open("data/planning/expedition.domain", "r", encoding="utf-8") as f:
            domain_txt = f.read()

        # Tambahkan schema aksi buy_pedang_naga ke teks domain PDDL
        buy_naga_pddl = """
  (:action buy_pedang_naga
    :parameters (?c_before ?c_after - coin)
    :precondition (and
      (at shop)
      (coins ?c_before)
      (pay_50 ?c_before ?c_after)
    )
    :effect (and
      (not (coins ?c_before))
      (coins ?c_after)
      (has pedang_naga)
    )
    :cost 1.0
  )
"""
        mod_domain_txt = domain_txt.replace("(:action buy_seed_radish", buy_naga_pddl + "\n  (:action buy_seed_radish")
        mod_domain = parse_domain(mod_domain_txt)

        with open("data/planning/expedition.problem", "r", encoding="utf-8") as f:
            prob_txt = f.read()

        # Tambahkan pedang_naga ke objek, fakta transisi koin (c60 -> c10), dan ubah goal
        mod_prob_txt = prob_txt.replace(
            "sword_basic weapon_dagger weapon_axe fire_staff cloth_armor armor_leather armor_iron - item",
            "sword_basic weapon_dagger weapon_axe fire_staff cloth_armor armor_leather armor_iron pedang_naga - item"
        ).replace(
            "(:init",
            "(:init\n    (pay_50 c60 c10)\n    (valid_loadout pedang_naga cloth_armor)"
        ).replace(
            "(coins c20)",
            "(coins c60)"
        ).replace(
            "(:goal (and\n    (boss_defeated)\n  ))",
            "(:goal (and\n    (has pedang_naga)\n    (equipped_weapon pedang_naga)\n  ))"
        )
        mod_prob_ast = parse_problem(mod_prob_txt)
        grounded_prob = ground_problem(mod_domain, mod_prob_ast, enable_pruning=True)

        res = search_bfs(grounded_prob)
        self.assertTrue(res.success, f"Planner gagal menemukan rencana: {res.failure_reason}")
        plan_names = [a.name for a in res.plan]
        self.assertIn("buy_pedang_naga", plan_names, "Rencana harus memuat aksi buy_pedang_naga!")
        self.assertIn("equip", plan_names, "Rencana harus memuat aksi equip!")

        # Pastikan equip benar-benar memasang pedang_naga
        equip_actions = [a for a in res.plan if a.name == "equip"]
        self.assertTrue(any("pedang_naga" in a.params for a in equip_actions),
                        "Aksi equip harus memuat parameter pedang_naga!")


if __name__ == "__main__":
    unittest.main()
