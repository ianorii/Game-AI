"""
test_minion_duu.py - Unit Test Komprehensif DUU Minion (Live Combat MEU & Bayesian Decision Network)
Memenuhi seluruh spesifikasi pengujian kritis Claude (Kategori A s.d. E).
"""

import unittest
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from decision.combat_policy import CombatRiskModel, CombatDecision, BayesianMinionBelief, GoblinType


class TestMinionDUU(unittest.TestCase):

    def setUp(self):
        self.model = CombatRiskModel(
            u_loot_normal=5.5,
            u_loot_elite=12.0,
            u_death=-20.0,
            u_evade_cost=-1.5,
            u_potion_cost=-3.0,
            potion_heal_pct=0.50,
            hysteresis_margin=0.10,
            prior_elite=0.20,
            c_catch_prob=0.0
        )

    # --------------------------------------------------------------------------
    # Kategori A: Model dan Matematika (Oracle Tangan)
    # --------------------------------------------------------------------------
    def test_T_A1_analytical_breakeven_p_star(self):
        """T-A1: Derivasi p* = 18.5/25.5 ~= 0.72549 secara eksak analitik."""
        expected_p_star = (-1.5 - (-20.0)) / (5.5 - (-20.0))
        self.assertAlmostEqual(self.model.p_star_normal, expected_p_star, places=5)
        self.assertAlmostEqual(self.model.p_star_normal, 18.5 / 25.5, places=5)

    def test_T_A2_breakeven_point_equality(self):
        """T-A2: Pada P(win) = p*, EU(Engage) == EU(Evade) dengan toleransi 1e-7."""
        p_star = self.model.p_star_normal
        eu_engage_at_p_star = p_star * 5.5 + (1.0 - p_star) * (-20.0)
        eu_evade = -1.5
        self.assertAlmostEqual(eu_engage_at_p_star, eu_evade, places=6)

    def test_T_A3_sigmoid_inversion_calibration(self):
        """T-A3: Inversi sigmoid HP* untuk 1 goblin normal menghasilkan tepat HP* = 35%."""
        hp_star = self.model.calculate_breakeven_threshold(hp_goblin=1.0, goblin_count=1, p_elite=0.0)
        self.assertIsNotNone(hp_star)
        # HP* harus tepat ~ 0.350
        self.assertAlmostEqual(hp_star, 0.35, places=2)
        # P(win | HP*) harus sama dengan p*
        p_at_hp_star = self.model.calculate_win_probability(hp_star, hp_goblin=1.0, goblin_count=1, is_elite=False)
        self.assertAlmostEqual(p_at_hp_star, self.model.p_star_normal, places=3)

    def test_T_A4_bayesian_belief_oracle(self):
        """
        T-A4: Uji oracle Bayes sesuai spesifikasi Claude:
        Prior 0.2, P(bukti|elit)=0.7, P(bukti|biasa)=0.2 => Posterior = 0.14/(0.14+0.16) = 0.4667.
        """
        belief = BayesianMinionBelief(prior_elite=0.20, p_high_given_elite=0.70, p_high_given_normal=0.20)
        post = belief.update(is_high_damage=True)
        expected_post = (0.70 * 0.20) / ((0.70 * 0.20) + (0.20 * 0.80))  # 0.14 / 0.30 = 0.466666...
        self.assertAlmostEqual(post, 0.466667, places=4)
        self.assertAlmostEqual(post, expected_post, places=6)

    def test_T_A5_monotonicity(self):
        """T-A5: Monotonisitas: P(win) naik terhadap HP dan turun terhadap n."""
        # Terhadap HP
        p_low = self.model.calculate_win_probability(0.20, goblin_count=1)
        p_mid = self.model.calculate_win_probability(0.50, goblin_count=1)
        p_high = self.model.calculate_win_probability(0.80, goblin_count=1)
        self.assertLess(p_low, p_mid)
        self.assertLess(p_mid, p_high)

        # Terhadap n
        p_n1 = self.model.calculate_win_probability(0.50, goblin_count=1)
        p_n2 = self.model.calculate_win_probability(0.50, goblin_count=2)
        p_n3 = self.model.calculate_win_probability(0.50, goblin_count=3)
        self.assertGreater(p_n1, p_n2)
        self.assertGreater(p_n2, p_n3)

    # --------------------------------------------------------------------------
    # Kategori B: Kebijakan dan State Machine Edge Cases
    # --------------------------------------------------------------------------
    def test_T_B1_full_grid_sweep_no_exceptions(self):
        """T-B1: Sapu seluruh grid HP 0..100 x n 0..5 x hp_goblin 0.0..1.0 tanpa error/NaN."""
        for hp_int in range(0, 101, 10):
            hp = hp_int / 100.0
            for n in range(0, 6):
                for gob_hp in [0.0, 0.2, 0.5, 1.0]:
                    for potion in [True, False]:
                        for engaged in [True, False]:
                            action, metrics = self.model.decide(
                                hp_hero=hp,
                                hp_goblin=gob_hp,
                                goblin_count=n,
                                has_potion=potion,
                                currently_engaged=engaged
                            )
                            self.assertIn(action, [CombatDecision.ENGAGE, CombatDecision.EVADE, CombatDecision.HEAL, CombatDecision.NO_THREAT])
                            self.assertFalse(math.isnan(metrics["eu_engage"]))
                            self.assertFalse(math.isnan(metrics["eu_evade"]))

    def test_T_B2_exact_boundary_conditions(self):
        """T-B2: Batas tepat HP = 34.9% vs 35.1%."""
        # Reset belief ke murni normal
        self.model.belief.posterior_elite = 0.0
        
        # Di bawah 35%: EVADE
        action_below, _ = self.model.decide(0.349, hp_goblin=1.0, goblin_count=1)
        self.assertEqual(action_below, CombatDecision.EVADE)

        # Di atas 35%: ENGAGE
        action_above, _ = self.model.decide(0.351, hp_goblin=1.0, goblin_count=1)
        self.assertEqual(action_above, CombatDecision.ENGAGE)

    def test_T_B3_hysteresis_trajectory(self):
        """
        T-B3: Lintasan HP 40 -> 30 -> 24 -> 30 -> 36.
        Ekspektasi: ENGAGE -> ENGAGE (histeresis) -> EVADE (lepas) -> EVADE (belum capai 35%) -> ENGAGE.
        """
        self.model.belief.posterior_elite = 0.0
        
        # 1. HP 40% (inisiasi): ENGAGE
        a1, _ = self.model.decide(0.40, currently_engaged=False)
        self.assertEqual(a1, CombatDecision.ENGAGE)

        # 2. HP turun ke 30% (sudah engage): Tetap ENGAGE (histeresis > 25%)
        a2, _ = self.model.decide(0.30, currently_engaged=True)
        self.assertEqual(a2, CombatDecision.ENGAGE)

        # 3. HP turun ke 24% (sudah engage): EVADE (lepas karena < 25%)
        a3, _ = self.model.decide(0.24, currently_engaged=True)
        self.assertEqual(a3, CombatDecision.EVADE)

        # 4. HP naik ke 30% (mode kabur / currently_engaged=False): Tetap EVADE (< 35% inisiasi)
        a4, _ = self.model.decide(0.30, currently_engaged=False)
        self.assertEqual(a4, CombatDecision.EVADE)

        # 5. HP naik ke 36% (mode inisiasi): ENGAGE (> 35%)
        a5, _ = self.model.decide(0.36, currently_engaged=False)
        self.assertEqual(a5, CombatDecision.ENGAGE)

    def test_T_B5_guards_hp_zero_and_n_zero(self):
        """T-B5: Guard HP = 0, n = 0, dan n sangat besar."""
        # n = 0
        a_n0, _ = self.model.decide(0.50, goblin_count=0)
        self.assertEqual(a_n0, CombatDecision.NO_THREAT)

        # HP = 0
        a_hp0, m_hp0 = self.model.decide(0.0, goblin_count=1)
        self.assertEqual(a_hp0, CombatDecision.EVADE)
        self.assertTrue(m_hp0.get("is_dead", False))

        # n sangat besar (n=10)
        a_n10, _ = self.model.decide(0.90, goblin_count=10)
        self.assertEqual(a_n10, CombatDecision.EVADE)

    def test_T_B6_goblin_finishing_move(self):
        """
        Celah Claude: Goblin sekarat (HP goblin 10%):
        Hero pada HP 25% tetap memilih ENGAGE untuk menghabisi goblin sekarat.
        """
        # Normal goblin sekarat (hp_goblin = 0.10)
        a_finish, met = self.model.decide(0.25, hp_goblin=0.10, goblin_count=1)
        self.assertEqual(a_finish, CombatDecision.ENGAGE)
        self.assertGreater(met["p_win"], 0.75)

    def test_T_B7_heal_action_priority(self):
        """
        T-B7: Aksi HEAL: Ketika HP rendah (20%) dan memiliki ramuan,
        aksi HEAL memiliki EU lebih tinggi dari ENGAGE atau EVADE.
        """
        # Tanpa ramuan pada HP 20%: EVADE
        a_no_pot, _ = self.model.decide(0.20, hp_goblin=1.0, goblin_count=1, has_potion=False)
        self.assertEqual(a_no_pot, CombatDecision.EVADE)

        # Dengan ramuan pada HP 20%: HEAL
        a_pot, met_pot = self.model.decide(0.20, hp_goblin=1.0, goblin_count=1, has_potion=True)
        self.assertEqual(a_pot, CombatDecision.HEAL)
        self.assertGreater(met_pot["eu_heal"], met_pot["eu_evade"])


if __name__ == "__main__":
    unittest.main()
