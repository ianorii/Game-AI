"""
test_csp_local_search.py - Unit test suite untuk CSP Loadout, Local Search Tuning,
dan Integrasi dengan Minimax Alpha-Beta pada Boss Battle.
"""

import os
import sys
import unittest
import copy
import random
import pygame

# Pastikan path modul terdeteksi
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import config
config.VERBOSE_SPRITE_LOGS = False
from ai.adversarial import (
    BattleState,
    MinimaxBattleAI,
    evaluate,
    hero_actions,
    boss_actions,
    apply_action,
    pure_minimax_root
)
from battle.csp_loadout import (
    LoadoutCSPSolver,
    check_constraints,
    apply_loadout,
    calculate_cost,
    calculate_weight,
    get_item_dict,
    get_default_constraints,
    UnlockedConstraint,
    BudgetConstraint,
    WeightConstraint,
    HeavyAxeNoCritCharmConstraint,
    FireStaffLightArmorConstraint,
    DefensiveItemConstraint
)
from battle.local_search import (
    OpponentModel,
    evaluate_fitness,
    clamp_weights,
    HillClimbingTuner,
    SimulatedAnnealingTuner,
    BossRotationPlanner,
    describe_adaptation
)


class TestCSPConstraints(unittest.TestCase):
    """Pengujian unit batasan eksplisit CSP Loadout Hero."""

    def test_unlocked_constraint(self):
        c = UnlockedConstraint()
        valid_assign = {"WEAPON": "Pedang Biasa", "ARMOR": "Kulit"}
        sat, _ = c.is_satisfied(valid_assign)
        self.assertTrue(sat)

        # Cek item terkunci palsu
        config.CSP_ITEMS["WEAPON"].append({
            "name": "Senjata Terkunci", "cost": 1, "weight": 1, "desc": "Locked",
            "effects": {}, "locked": True, "is_defensive": False
        })
        try:
            invalid_assign = {"WEAPON": "Senjata Terkunci"}
            sat, reason = c.is_satisfied(invalid_assign)
            self.assertFalse(sat)
            self.assertIn("terkunci", reason.lower())
        finally:
            config.CSP_ITEMS["WEAPON"].pop()

    def test_budget_constraint(self):
        c = BudgetConstraint()
        # Biaya total <= 10
        assign_ok = {"WEAPON": "Pedang Biasa", "ARMOR": "Kulit", "CHARM": "Jimat Vitalitas", "CONSUMABLE": "Kosong"}
        # Pedang (2) + Kulit (3) + Jimat (3) + Kosong (0) = 8 <= 10
        sat, _ = c.is_satisfied(assign_ok)
        self.assertTrue(sat)

        # Biaya total melebihi 10
        # Tongkat Api (5) + Besi (5) + Jimat Kritikal (4) = 14 > 10
        assign_over = {"WEAPON": "Tongkat Api", "ARMOR": "Besi", "CHARM": "Jimat Kritikal"}
        sat, reason = c.is_satisfied(assign_over)
        self.assertFalse(sat)
        self.assertIn("anggaran", reason.lower())

    def test_weight_constraint(self):
        c = WeightConstraint()
        # Beban <= 10
        assign_ok = {"WEAPON": "Belati Cepat", "ARMOR": "Kain", "CHARM": "Kosong", "CONSUMABLE": "Kosong"}
        # Belati (1) + Kain (1) = 2 <= 10
        sat, _ = c.is_satisfied(assign_ok)
        self.assertTrue(sat)

        # Beban melebihi 10: Kapak Berat (6) + Besi (6) = 12 > 10
        assign_heavy = {"WEAPON": "Kapak Berat", "ARMOR": "Besi"}
        sat, reason = c.is_satisfied(assign_heavy)
        self.assertFalse(sat)
        self.assertIn("beban", reason.lower())

    def test_heavy_axe_no_crit_charm_conflict(self):
        c = HeavyAxeNoCritCharmConstraint()
        # Konflik Kapak Berat + Jimat Kritikal
        conflict_assign = {"WEAPON": "Kapak Berat", "CHARM": "Jimat Kritikal"}
        sat, reason = c.is_satisfied(conflict_assign)
        self.assertFalse(sat)
        self.assertIn("bentrok", reason.lower())

        # Kompatibel: Kapak Berat + Jimat Vitalitas
        ok_assign = {"WEAPON": "Kapak Berat", "CHARM": "Jimat Vitalitas"}
        sat, _ = c.is_satisfied(ok_assign)
        self.assertTrue(sat)

    def test_fire_staff_requires_light_armor(self):
        c = FireStaffLightArmorConstraint()
        # Tongkat Api + Besi -> Tidak diizinkan
        invalid_assign = {"WEAPON": "Tongkat Api", "ARMOR": "Besi"}
        sat, reason = c.is_satisfied(invalid_assign)
        self.assertFalse(sat)
        self.assertIn("jubah", reason.lower())

        # Tongkat Api + Kain -> Diizinkan
        ok_kain = {"WEAPON": "Tongkat Api", "ARMOR": "Kain"}
        sat, _ = c.is_satisfied(ok_kain)
        self.assertTrue(sat)

        # Tongkat Api + Kulit -> Diizinkan
        ok_kulit = {"WEAPON": "Tongkat Api", "ARMOR": "Kulit"}
        sat, _ = c.is_satisfied(ok_kulit)
        self.assertTrue(sat)

    def test_defensive_item_constraint(self):
        c = DefensiveItemConstraint()
        # Tidak ada item defensif sama sekali
        no_def = {
            "WEAPON": "Belati Cepat",
            "ARMOR": "Kosong" if "Kosong" in [x["name"] for x in config.CSP_ITEMS["ARMOR"]] else "Kain",
            "CHARM": "Jimat Kritikal",
            "CONSUMABLE": "Bom Asap"
        }
        # Kain adalah defensif, ganti dengan dict tanpa item defensif jika armor diisi non-defensif
        fake_assign = {"WEAPON": "Belati Cepat", "ARMOR": "Baju Tipis", "CHARM": "Jimat Kritikal", "CONSUMABLE": "Bom Asap"}
        sat, reason = c.is_satisfied(fake_assign, partial=False)
        self.assertFalse(sat)
        self.assertIn("defensif", reason.lower())

        # Membawa Jimat Vitalitas (defensif)
        has_def = {"WEAPON": "Belati Cepat", "ARMOR": "Baju Tipis", "CHARM": "Jimat Vitalitas", "CONSUMABLE": "Bom Asap"}
        sat, _ = c.is_satisfied(has_def, partial=False)
        self.assertTrue(sat)


class TestCSPSolver(unittest.TestCase):
    """Pengujian performa dan kebenaran CSP Solver (MRV, Forward Checking, LCV)."""

    def setUp(self):
        self.solver = LoadoutCSPSolver(seed=42)

    def test_solver_produces_valid_solution(self):
        sol, stats = self.solver.solve()
        self.assertIsNotNone(sol)
        self.assertEqual(len(sol), 4)
        is_valid, reason = check_constraints(sol, partial=False)
        self.assertTrue(is_valid, f"Solusi melanggar batasan: {reason}")
        self.assertLessEqual(calculate_cost(sol), config.CSP_BUDGET)
        self.assertLessEqual(calculate_weight(sol), config.CSP_WEIGHT_LIMIT)

    def test_solver_all_solutions_valid(self):
        all_sols, stats = self.solver.solve_all(use_mrv=True, use_fc=True)
        self.assertGreater(len(all_sols), 0)
        self.assertEqual(len(all_sols), 56)  # Domain menghasilkan tepat 56 kombinasi valid

        for s in all_sols:
            is_valid, msg = check_constraints(s, partial=False)
            self.assertTrue(is_valid, f"Kombinasi tidak valid ditemukan: {s} - {msg}")

    def test_four_csp_variants_identical_solutions(self):
        """Verifikasi bahwa 4 varian CSP solver menghasilkan himpunan solusi identik 100%."""
        naive_sols, naive_st = self.solver.solve_all_naive()
        inc_sols, inc_st = self.solver.solve_all_bt_incremental()
        heur_sols, heur_st = self.solver.solve_all_heuristics()
        fc_sols, fc_st = self.solver.solve_all_fc()

        def sol_to_tuple(s):
            return tuple(sorted(s.items()))

        set_naive = set(sol_to_tuple(s) for s in naive_sols)
        set_inc = set(sol_to_tuple(s) for s in inc_sols)
        set_heur = set(sol_to_tuple(s) for s in heur_sols)
        set_fc = set(sol_to_tuple(s) for s in fc_sols)

        self.assertEqual(len(naive_sols), 56)
        self.assertEqual(set_naive, set_inc)
        self.assertEqual(set_naive, set_heur)
        self.assertEqual(set_naive, set_fc)

    def test_tight_scenario_heuristics_vs_naive(self):
        """Pada skenario ketat (Budget=6, Weight=6), heuristik + FC harus memangkas node & backtrack jauh lebih efisien dari naive."""
        tight_constraints = get_default_constraints(
            budget=config.CSP_TIGHT_BUDGET,
            weight_limit=config.CSP_TIGHT_WEIGHT
        )
        tight_solver = LoadoutCSPSolver(constraints=tight_constraints, seed=42)

        naive_sols, naive_st = tight_solver.solve_all_naive()
        fc_sols, fc_st = tight_solver.solve_all_fc()

        def sol_to_tuple(s):
            return tuple(sorted(s.items()))
        self.assertEqual(set(sol_to_tuple(s) for s in naive_sols), set(sol_to_tuple(s) for s in fc_sols))
        self.assertEqual(len(fc_sols), 5)

        # Heuristik MRV+FC harus mengeksplorasi node & backtrack lebih sedikit daripada naive
        self.assertLess(fc_st.nodes_visited, naive_st.nodes_visited)
        self.assertLess(fc_st.backtracks_count, naive_st.backtracks_count)

    def test_best_loadout_selection(self):
        best, stats = self.solver.best_loadout()
        self.assertIsNotNone(best)
        is_valid, _ = check_constraints(best, partial=False)
        self.assertTrue(is_valid)

    def test_apply_loadout_purity_and_effects(self):
        initial = BattleState(player_hp=100, boss_hp=120)
        loadout = {
            "WEAPON": "Tongkat Api",      # atk_bonus: 8
            "ARMOR": "Kulit",             # def_bonus: 0.15, max_hp: 10
            "CHARM": "Jimat Vitalitas",    # max_hp: 25
            "CONSUMABLE": "Bom Asap"      # boss_hp_penalty: 15
        }

        updated = apply_loadout(initial, loadout)

        # Pastikan initial state TIDAK termutasi (Pure Function)
        self.assertEqual(initial.player_hp, 100)
        self.assertEqual(initial.player_max_hp, 100)
        self.assertEqual(initial.boss_hp, 120)
        self.assertEqual(initial.hero_attack_bonus, 0)

        # Periksa atribut state baru
        self.assertEqual(updated.player_max_hp, 135)
        self.assertEqual(updated.player_hp, 135)
        self.assertEqual(updated.hero_attack_bonus, 7)
        self.assertAlmostEqual(updated.hero_defend_bonus, 0.05)
        self.assertEqual(updated.boss_hp, 105)

        # Player actions tetap HANYA 3
        acts = hero_actions(updated)
        self.assertEqual(set(acts), {"ATTACK", "POTION", "DEFEND"})


class TestLocalSearch(unittest.TestCase):
    """Pengujian Opponent Model, Fitness, dan Algoritma Local Search (HC & SA)."""

    def setUp(self):
        self.state = BattleState()

    def test_opponent_model_laplace_smoothing(self):
        opp = OpponentModel({"WEAPON": "Kapak Berat"})
        dist = opp.get_distribution()

        # Total probabilitas harus 1.0
        self.assertAlmostEqual(sum(dist.values()), 1.0)

        # Prior dari Kapak Berat meningkatkan probabilitas ATTACK
        self.assertGreater(dist["ATTACK"], dist["POTION"])

        # Catat aksi berulang
        for _ in range(5):
            opp.record_action("POTION")

        new_dist = opp.get_distribution()
        self.assertAlmostEqual(sum(new_dist.values()), 1.0)
        self.assertGreater(new_dist["POTION"], dist["POTION"])

    def test_clamp_weights(self):
        raw_w = [-10.0, 99.0, 3.0, 0.0]
        clamped = clamp_weights(raw_w)
        # Bounds: (0.5, 10.0), (2.0, 30.0), (4.0, 40.0), (1.0, 25.0)
        self.assertEqual(clamped[0], config.BOSS_WEIGHT_BOUNDS[0][0])
        self.assertEqual(clamped[1], config.BOSS_WEIGHT_BOUNDS[1][1])
        self.assertEqual(clamped[2], config.BOSS_WEIGHT_BOUNDS[2][0])
        self.assertEqual(clamped[3], config.BOSS_WEIGHT_BOUNDS[3][0])

    def test_fitness_evaluation_determinism(self):
        opp = OpponentModel()
        w = (2.0, 8.0, 12.0, 6.0)
        f1 = evaluate_fitness(w, self.state, opp, sim_count=10, seed=123)
        f2 = evaluate_fitness(w, self.state, opp, sim_count=10, seed=123)
        self.assertEqual(f1, f2)

    def test_simulated_annealing_tuning(self):
        opp = OpponentModel({"WEAPON": "Kapak Berat"})
        opp.record_action("ATTACK")
        opp.record_action("ATTACK")

        sa = SimulatedAnnealingTuner(max_time_ms=200, seed=42)
        best_w, fit, stats = sa.tune(config.BOSS_DEFAULT_WEIGHTS, self.state, opp)

        # Waktu harus terkendali
        self.assertLess(stats["time_ms"], 350.0)
        self.assertGreaterEqual(stats["iterations"], 2)
        self.assertGreaterEqual(len(stats["history"]), 2)

        # Bobot baru harus berada dalam batasan
        for val, (low, high) in zip(best_w, config.BOSS_WEIGHT_BOUNDS):
            self.assertGreaterEqual(val, low)
            self.assertLessEqual(val, high)

    def test_hill_climbing_tuning(self):
        opp = OpponentModel({"ARMOR": "Besi"})
        hc = HillClimbingTuner(restarts=2, max_time_ms=200, seed=42)
        best_w, fit, stats = hc.tune(config.BOSS_DEFAULT_WEIGHTS, self.state, opp)

        self.assertLess(stats["time_ms"], 350.0)
        for val, (low, high) in zip(best_w, config.BOSS_WEIGHT_BOUNDS):
            self.assertGreaterEqual(val, low)
            self.assertLessEqual(val, high)

    def test_boss_rotation_planner(self):
        planner = BossRotationPlanner()
        plan = planner.generate_plan(self.state)

        self.assertEqual(len(plan), 4)

        # Cooldown Heavy Attack: Heavy Attack muncul maks 1x dalam 4 ronde
        heavy_count = plan.count("HEAVY_ATTACK")
        self.assertLessEqual(heavy_count, 1)

        # Heal limit: Heal muncul maks 1x dalam 4 ronde
        heal_count = plan.count("HEAL")
        self.assertLessEqual(heal_count, 1)

        # Tidak ada aksi yang muncul 3x berturut-turut
        for i in range(len(plan) - 2):
            self.assertFalse(plan[i] == plan[i+1] == plan[i+2])

    def test_adaptation_description(self):
        old_w = (2.0, 8.0, 12.0, 6.0)
        new_w = (2.0, 12.0, 12.0, 6.0)
        desc = describe_adaptation(old_w, new_w)
        self.assertIn("pertahanan", desc.lower())


class TestIntegration(unittest.TestCase):
    """Pengujian integrasi Minimax dengan bobot hasil Local Search dan Rotation Planner."""

    def test_minimax_with_tuned_weights(self):
        ai = MinimaxBattleAI(depth=2, weights=(3.0, 10.0, 15.0, 8.0))
        st = BattleState()
        act, tree, stats = ai.choose_move(st)
        self.assertIn(act, boss_actions(st))
        self.assertGreater(stats.nodes, 0)

    def test_minimax_move_ordering_with_rotation_planner(self):
        planner = BossRotationPlanner()
        st = BattleState()
        planner.cached_plan = ["DEFEND", "ATTACK", "HEAVY_ATTACK", "ATTACK"]
        planner.plan_start_turn = st.turn_number

        ai = MinimaxBattleAI(depth=2, move_prior_provider=planner)
        act, tree, stats = ai.choose_move(st)

        # Kandidat pertama yang diperiksa harus DEFEND (prior dari planner)
        self.assertEqual(stats.candidates[0]["action"], "DEFEND")

    def test_alpha_beta_identical_to_pure_minimax(self):
        """Memverifikasi Minimax murni vs Alpha-Beta menghasilkan move & skor identik 100% pada berbagai state."""
        test_states = [
            BattleState(player_hp=100, boss_hp=120, potion_count=3, boss_heavy_cd=0),
            BattleState(player_hp=30, boss_hp=90, potion_count=1, boss_heavy_cd=1),
            BattleState(player_hp=70, boss_hp=28, potion_count=2, boss_heal_count=1),
            BattleState(player_hp=15, boss_hp=20, potion_count=0, boss_heavy_cd=0),
        ]
        ai_ab = MinimaxBattleAI(depth=3, use_ordering=True)

        for st in test_states:
            pure_act, pure_val, pure_nodes = pure_minimax_root(st, depth=3)
            ab_act, _, ab_stats = ai_ab.choose_move(st)

            self.assertEqual(pure_act, ab_act, f"Move berbeda pada state: {st}")
            self.assertEqual(pure_val, ab_stats.best_value, f"Score berbeda pada state: {st}")
            self.assertLess(ab_stats.nodes, pure_nodes, "Alpha-Beta harus mengevaluasi node lebih sedikit")

    def test_boss_tactical_behavior_heal_at_critical(self):
        """Boss harus memprioritaskan HEAL saat HP-nya berada pada batas lethal damage lawan (< 21) dan memiliki heal."""
        ai = MinimaxBattleAI(depth=3)
        st = BattleState(player_hp=80, boss_hp=18, potion_count=2, boss_heal_count=1, boss_heavy_cd=2)
        act, _, _ = ai.choose_move(st)
        self.assertEqual(act, "HEAL")

    def test_boss_tactical_behavior_defend_at_critical_when_no_heals(self):
        """Boss harus memilih DEFEND saat HP kritis lethal dan slot heal habis untuk mencegah kekalahan instan."""
        ai = MinimaxBattleAI(depth=3)
        st = BattleState(player_hp=80, boss_hp=18, potion_count=2, boss_heal_count=0, boss_heavy_cd=2)
        act, _, _ = ai.choose_move(st)
        self.assertEqual(act, "DEFEND")

    def test_boss_tactical_behavior_heavy_when_vulnerable(self):
        """Boss harus menggunakan HEAVY_ATTACK ketika cooldown 0 dan hero tidak dalam posisi guard."""
        ai = MinimaxBattleAI(depth=3)
        st = BattleState(player_hp=35, boss_hp=90, potion_count=1, boss_heavy_cd=0, player_defending=False)
        act, _, _ = ai.choose_move(st)
        self.assertEqual(act, "HEAVY_ATTACK")

    def test_boss_never_chooses_illegal_moves(self):
        """Boss tidak boleh memilih aksi ilegal (misal HEAL saat heal_count=0 atau HEAVY saat cooldown)."""
        ai = MinimaxBattleAI(depth=3)
        st = BattleState(player_hp=80, boss_hp=20, potion_count=1, boss_heal_count=0, boss_heavy_cd=2)
        act, _, _ = ai.choose_move(st)
        self.assertIn(act, ["ATTACK", "DEFEND"])
        self.assertNotEqual(act, "HEAL")
        self.assertNotEqual(act, "HEAVY_ATTACK")

    def test_difficulty_depth_configuration(self):
        """Memastikan konfigurasi depth tingkat kesulitan sesuai spesifikasi."""
        self.assertEqual(config.MINIMAX_DEPTH_EASY, 1)
        self.assertEqual(config.MINIMAX_DEPTH_NORMAL, 3)
        self.assertEqual(config.MINIMAX_DEPTH_HARD, 5)

    def test_difficulty_monotonicity(self):
        """Memastikan tingkat kemenangan Boss monotonik: Easy < Normal < Hard."""
        from battle.csp_loadout import LoadoutCSPSolver, apply_loadout
        from ai.adversarial import is_terminal, apply_action
        solver = LoadoutCSPSolver(seed=123)
        best, _ = solver.best_loadout()
        hero_st = apply_loadout(BattleState(), best)

        def sim(depth_val, weights_val, count=100):
            boss_wins = 0
            for i in range(count):
                r = random.Random(7777 + i)
                st = hero_st.clone()
                ai = MinimaxBattleAI(depth=depth_val, weights=weights_val)
                while not is_terminal(st) and st.turn_number <= 25:
                    if st.turn == "player":
                        if st.player_hp <= 40 and st.potion_count > 0:
                            act = "POTION"
                        elif st.boss_heavy_cd == 0 and r.random() < 0.6:
                            act = "DEFEND"
                        else:
                            act = "ATTACK"
                        st, _ = apply_action(st, "player", act, rng=r)
                    else:
                        b_act, _, _ = ai.choose_move(st)
                        st, _ = apply_action(st, "boss", b_act, rng=r)
                if st.player_hp <= 0 or (st.boss_hp > st.player_hp and st.turn_number > 25):
                    boss_wins += 1
            return boss_wins

        easy_wins = sim(config.MINIMAX_DEPTH_EASY, config.BOSS_WEIGHTS_EASY, 100)
        normal_wins = sim(config.MINIMAX_DEPTH_NORMAL, config.BOSS_WEIGHTS_NORMAL, 100)
        hard_wins = sim(config.MINIMAX_DEPTH_HARD, config.BOSS_WEIGHTS_HARD, 100)

        self.assertLess(easy_wins, normal_wins, f"Easy ({easy_wins}%) harus < Normal ({normal_wins}%)")
        self.assertLess(normal_wins, hard_wins, f"Normal ({normal_wins}%) harus < Hard ({hard_wins}%)")

    def test_vfx_assets_disentangled(self):
        """Memastikan aset hit spark dan glint VFX otentik terpisah dan dapat dimuat."""
        spark_path = os.path.join(config.SUNNYSIDE_DIR, "Elements", "VFX", "Glint", "spr_deco_glint_02_strip4.png")
        glint_path = os.path.join(config.SUNNYSIDE_DIR, "Elements", "VFX", "Glint", "spr_deco_glint_01_strip6.png")
        self.assertTrue(os.path.exists(spark_path), f"Hit spark file harus ada: {spark_path}")
        self.assertTrue(os.path.exists(glint_path), f"Glint file harus ada: {glint_path}")

        from core.battle_ui import BattleSpriteLoader
        loader = BattleSpriteLoader()
        self.assertEqual(len(loader.spark_frames), 4, "Hit spark harus memuat 4 frame")
        self.assertEqual(len(loader.glint_frames), 6, "Glint harus memuat 6 frame")


from battle.prep_ui import PrepUI, get_prep_layout_rects
import itertools


class TestPrepUIRedesign(unittest.TestCase):
    """Pengujian unit untuk Desain Ulang UI Layar Persiapan & Sentralisasi Validasi."""

    def setUp(self):
        if not pygame.get_init():
            pygame.init()
        self.prep_ui = PrepUI()

    def test_get_prep_layout_rects_no_overlap(self):
        """Memastikan fungsi get_prep_layout_rects menghasilkan panel struktural yang tidak saling tumpang tindih."""
        rects = get_prep_layout_rects()

        # 1. Panel utama struktural tidak boleh overlap satu sama lain
        main_panels = ["header", "col_left", "col_center", "col_right", "footer"]
        for i in range(len(main_panels)):
            for j in range(i + 1, len(main_panels)):
                p1, p2 = main_panels[i], main_panels[j]
                r1, r2 = rects[p1], rects[p2]
                self.assertFalse(
                    r1.colliderect(r2),
                    f"Panel '{p1}' {r1} bertabrakan dengan panel '{p2}' {r2}"
                )

        # 2. Seluruh panel berada di dalam batas resolusi layar 1024x768
        screen_rect = rects["screen"]
        for p in main_panels:
            self.assertTrue(
                screen_rect.contains(rects[p]),
                f"Panel '{p}' berada di luar batas layar 1024x768: {rects[p]}"
            )

        # 3. Empat tombol aksi seragam dan berada di dalam panel footer
        buttons = ["btn_csp", "btn_reset", "btn_start", "btn_cancel"]
        footer_rect = rects["footer"]
        for btn in buttons:
            r = rects[btn]
            self.assertTrue(
                footer_rect.contains(r),
                f"Tombol '{btn}' berada di luar panel footer: {r} not in {footer_rect}"
            )
            self.assertEqual(r.width, 226, f"Lebar tombol '{btn}' harus seragam (226)")
            self.assertEqual(r.height, 42, f"Tinggi tombol '{btn}' harus seragam (42)")

        # 4. Tombol dan hint bar tidak saling overlap
        btn_elements = buttons + ["hint_bar"]
        for i in range(len(btn_elements)):
            for j in range(i + 1, len(btn_elements)):
                b1, b2 = btn_elements[i], btn_elements[j]
                self.assertFalse(
                    rects[b1].colliderect(rects[b2]),
                    f"Elemen footer '{b1}' bertabrakan dengan '{b2}'"
                )

    def test_centralized_validation_across_192_combinations(self):
        """
        Validasi sentral: menguji seluruh 192 kombinasi domain loadout (4 x 3 x 4 x 4).
        Memastikan self.is_valid, status pill, dan tombol [Enter] tidak pernah bertolak belakang.
        """
        weapons = [it["name"] for it in config.CSP_ITEMS["WEAPON"]]        # 4
        armors = [it["name"] for it in config.CSP_ITEMS["ARMOR"]]          # 3
        charms = [it["name"] for it in config.CSP_ITEMS["CHARM"]]          # 4
        consumables = [it["name"] for it in config.CSP_ITEMS["CONSUMABLE"]]# 4

        total_tested = 0
        valid_count = 0
        invalid_count = 0

        for w, a, c, cs in itertools.product(weapons, armors, charms, consumables):
            loadout = {
                "WEAPON": w,
                "ARMOR": a,
                "CHARM": c,
                "CONSUMABLE": cs,
            }
            expected_sat, expected_reason = check_constraints(loadout, partial=False)

            self.prep_ui.set_loadout(loadout)
            total_tested += 1

            # 1. Status is_valid UI harus identik dengan check_constraints
            self.assertEqual(
                self.prep_ui.is_valid,
                expected_sat,
                f"is_valid UI ({self.prep_ui.is_valid}) tidak sinkron dengan CSP solver ({expected_sat}) untuk {loadout}"
            )

            # 2. Tombol [Enter] hanya menghasilkan 'START_BATTLE' jika dan hanya jika valid
            enter_evt = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
            res = self.prep_ui.handle_event(enter_evt)
            if expected_sat:
                self.assertEqual(res, "START_BATTLE", f"Loadout valid harus dapat memulai battle: {loadout}")
                valid_count += 1
            else:
                self.assertIsNone(res, f"Loadout invalid tidak boleh dapat memulai battle: {loadout}")
                self.assertNotEqual(self.prep_ui.invalid_reason, "", "Harus menyediakan invalid_reason")
                invalid_count += 1

        self.assertEqual(total_tested, 192, f"Total kombinasi yang diuji harus 192, didapat: {total_tested}")
        self.assertGreater(valid_count, 0, "Harus ada minimal satu solusi loadout yang valid")
        self.assertGreater(invalid_count, 0, "Harus ada kombinasi loadout yang melanggar batasan")


if __name__ == "__main__":
    unittest.main()
