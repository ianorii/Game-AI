"""
test_plan_validator.py - Pengujian Validator Rencana Independen STRIPS dan Kebijakan MEU
Sesuai arahan audit kritis Claude.
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from planning.pddl_parser import parse_domain, parse_problem
from planning.grounding import ground_problem
from planning.planner import search_weighted_astar_hff, validate_plan
from decision.combat_policy import CombatRiskModel, CombatDecision


class TestPlanValidatorAndMEU(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open("data/planning/ojek.domain", "r", encoding="utf-8") as f:
            dom = parse_domain(f.read())
        with open("data/planning/ojek.problem", "r", encoding="utf-8") as f:
            prob = parse_problem(f.read())
        cls.prob_ojek = ground_problem(dom, prob, enable_pruning=True)

    def test_01_validate_ojek_plan(self):
        """Memvalidasi rencana domain ojek delivery menggunakan validator independen."""
        res = search_weighted_astar_hff(self.prob_ojek, weight=1.5)
        self.assertTrue(res.success)
        
        # Eksekusi validator independen
        valid, msg, cost = validate_plan(self.prob_ojek, res.plan)
        self.assertTrue(valid, msg)
        self.assertEqual(len(res.plan), 4)

    def test_02_validate_invalid_plan(self):
        """Validator harus menolak rencana yang melanggar prasyarat aksi."""
        res = search_weighted_astar_hff(self.prob_ojek, weight=1.5)
        self.assertTrue(res.success)

        # Ubah urutan: aksi terakhir diletakkan di awal
        corrupted_plan = [res.plan[-1]] + res.plan[:-1]
        valid, msg, cost = validate_plan(self.prob_ojek, corrupted_plan)
        self.assertFalse(valid, "Rencana dengan prasyarat invalid harus ditolak")
        self.assertIn("gagal", msg)

    def test_03_combat_meu_threshold_derivation(self):
        """
        Memverifikasi bahwa ambang batas 35% HP adalah hasil derivasi analitis MEU:
        EU(Engage) = EU(Evade) => P*(win) = 72.55% => HP ~ 35.0%.
        """
        model = CombatRiskModel(u_loot=5.5, u_death=-20.0, u_evade_cost=-1.5)
        self.assertAlmostEqual(model.p_star, 18.5 / 25.5, places=3)

        # Di bawah 35% HP (misal 30%): Evade harus memiliki EU lebih tinggi dari Engage
        action_30, met_30 = model.decide(0.30, goblin_count=1)
        self.assertEqual(action_30, CombatDecision.EVADE)
        self.assertLess(met_30["eu_engage"], met_30["eu_evade"])

        # Di atas 35% HP (misal 50%): Engage harus optimal
        action_50, met_50 = model.decide(0.50, goblin_count=1)
        self.assertEqual(action_50, CombatDecision.ENGAGE)
        self.assertGreaterEqual(met_50["eu_engage"], met_50["eu_evade"])

    def test_04_combat_meu_hysteresis(self):
        """
        Memverifikasi histeresis: saat hero sudah engage pada HP 36%,
        jika HP turun ke 30%, hero tetap mempertahankan komitmen bertarung
        hingga di bawah batas histeresis (25%).
        """
        model = CombatRiskModel(u_loot=5.5, u_death=-20.0, u_evade_cost=-1.5, hysteresis_margin=0.10)
        
        # Sedang bertarung, HP 30% (antara 25% dan 35%): tetap ENGAGE karena histeresis
        action, _ = model.decide(0.30, goblin_count=1, currently_engaged=True)
        self.assertEqual(action, CombatDecision.ENGAGE)

        # HP drop drastis ke 20% (< 25%): harus EVADE segera
        action_critical, _ = model.decide(0.20, goblin_count=1, currently_engaged=True)
        self.assertEqual(action_critical, CombatDecision.EVADE)


if __name__ == "__main__":
    unittest.main()
