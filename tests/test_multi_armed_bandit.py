"""
test_multi_armed_bandit.py - Unit Test Komprehensif Multi-Armed Bandit
Sunnyside Isle - Pengambilan Keputusan dalam Ketidakpastian (Decisions Under Uncertainty)

Mencakup Pengujian:
  1. SpotBandit Environment & Common Random Numbers (CRN) determinism
  2. 5 Algoritma Aktor: Random, Greedy, Epsilon-Greedy, UCB1, Thompson Sampling
  3. RegretTracker & Batas Teoretis Lai-Robbins
  4. BanditDirector Orkestrasi Lockstep Ghost Agents
  5. Integrasi Gameplay (WorldState, Inventory, Economy)
"""

import math
import random
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from decision.bandit import (
    SpotBandit,
    ActorView,
    BanditAgent,
    RandomAgent,
    GreedyAgent,
    EpsilonGreedyAgent,
    UCB1Agent,
    ThompsonSamplingAgent,
    RegretTracker,
    BanditDirector,
    BANDIT_PRESETS,
)
from world_state import WorldState
from economy import Shop, DEFAULT_SELL_PRICES


class TestMultiArmedBandit(unittest.TestCase):
    """Pengujian Unit Komprehensif Multi-Armed Bandit."""

    def setUp(self):
        self.thetas = [0.10, 0.20, 0.40, 0.60, 0.80]
        self.K = len(self.thetas)
        self.horizon = 50
        self.seed = 12345
        self.env = SpotBandit(self.thetas, horizon=self.horizon, seed=self.seed)

    def test_01_crn_determinism_across_views(self):
        """Memverifikasi Common Random Numbers (CRN): Dua aktor independen menerima undian identik."""
        view_a = self.env.create_actor_view()
        view_b = self.env.create_actor_view()

        pulls_a = [view_a.pull(3) for _ in range(20)]
        pulls_b = [view_b.pull(3) for _ in range(20)]

        self.assertEqual(pulls_a, pulls_b, "CRN harus menjamin lemparan ke-n menghasilkan reward identik!")
        self.assertEqual(self.env.best_arm, 4)
        self.assertAlmostEqual(self.env.theta_star, 0.80)

    def test_02_random_agent(self):
        """RandomAgent selalu memilih indeks arm yang valid."""
        agent = RandomAgent(self.K, rng=random.Random(42))
        for _ in range(30):
            arm = agent.select()
            self.assertTrue(0 <= arm < self.K)
            agent.update(arm, 1)
        self.assertEqual(agent.t, 30)

    def test_03_greedy_agent_untried_first_and_exploit(self):
        """GreedyAgent harus mencoba seluruh arm sebelum mengeksploitasi mu_hat tertinggi."""
        agent = GreedyAgent(self.K, rng=random.Random(42))
        # 5 tarikan pertama harus mencakup seluruh arm 0..4
        first_five = []
        for _ in range(self.K):
            arm = agent.select()
            first_five.append(arm)
            r = 1 if arm == 2 else 0
            agent.update(arm, r)

        self.assertEqual(set(first_five), set(range(self.K)), "Greedy harus mencoba seluruh arm dulu.")
        # Tarikan ke-6 wajib memilih arm 2 (mu_hat=1.0)
        next_pick = agent.select()
        self.assertEqual(next_pick, 2, "Greedy harus mengeksploitasi arm dengan mu_hat tertinggi!")

    def test_04_epsilon_greedy_agent_modes(self):
        """EpsilonGreedy dengan eps=0 bersikap pure greedy, eps=1 bersikap random."""
        # eps = 0.0 -> pure greedy setelah untried
        agent_greedy = EpsilonGreedyAgent(self.K, rng=random.Random(42), eps=0.0)
        for i in range(self.K):
            agent_greedy.update(i, 1 if i == 1 else 0)
        self.assertEqual(agent_greedy.select(), 1)

        # eps = 1.0 -> eksplorasi seragam
        agent_random = EpsilonGreedyAgent(self.K, rng=random.Random(42), eps=1.0)
        for i in range(self.K):
            agent_random.update(i, 1 if i == 1 else 0)
        picks = {agent_random.select() for _ in range(50)}
        self.assertGreater(len(picks), 1, "Eps=1.0 harus mengeksplorasi banyak arm.")

    def test_05_ucb1_agent_upper_confidence_bonus(self):
        """UCB1Agent menghitung bonus ketidakpastian dan memilih arm dengan score tertinggi."""
        agent = UCB1Agent(self.K, rng=random.Random(42), c=1.414)
        # Coba setiap arm 1x
        for i in range(self.K):
            agent.update(i, 0)
        self.assertEqual(agent.t, 5)

        # Arm yang belum pernah ditarik memiliki bonus tak terhingga
        new_agent = UCB1Agent(self.K, rng=random.Random(42))
        self.assertEqual(new_agent.bonus(0), float("inf"))

        # Hitung skor terbobot setelah tarikan
        scores = [agent.score(i) for i in range(self.K)]
        self.assertEqual(len(scores), self.K)
        pick = agent.select()
        self.assertTrue(0 <= pick < self.K)

    def test_06_thompson_sampling_credible_interval(self):
        """ThompsonSamplingAgent menghasilkan sampel acak valid dan credible interval 95%."""
        agent = ThompsonSamplingAgent(self.K, rng=random.Random(42))
        # Simulasi 10 sukses pada arm 4, 10 gagal pada arm 0
        for _ in range(10):
            agent.update(4, 1)
            agent.update(0, 0)

        ci_4 = agent.credible_interval(4, samples=100)
        ci_0 = agent.credible_interval(0, samples=100)
        # Interval arm 4 harus berada jauh di atas arm 0
        self.assertGreater(ci_4[0], ci_0[1], "Posterior interval arm 4 harus lebih tinggi dari arm 0!")

    def test_07_regret_tracker_monotonicity(self):
        """RegretTracker menghasilkan akumulasi regret monoton naik (R_t >= R_{t-1})."""
        tracker = RegretTracker(self.env)
        # Tarik arm optimal -> delta regret = 0
        tracker.record(self.env.best_arm, 1)
        self.assertAlmostEqual(tracker.total_regret, 0.0)

        # Tarik arm sub-optimal (arm 0, theta=0.10, theta*=0.80) -> delta regret = 0.70
        tracker.record(0, 0)
        self.assertAlmostEqual(tracker.total_regret, 0.70)
        self.assertEqual(len(tracker.cum_regret), 3)

    def test_08_bandit_director_lockstep_ghosts(self):
        """BanditDirector mengeksekusi 5 ghost agent secara paralel lockstep setiap cast."""
        director = BanditDirector(preset_key="REALISTIC", seed=42, primary_kind="player")
        self.assertEqual(director.t, 0)
        self.assertFalse(director.is_finished)

        # Selesaikan 5 lemparan pada spot 2
        for _ in range(5):
            is_rare, coins = director.resolve_cast(2)
            self.assertIn(coins, (15, 60))

        self.assertEqual(director.t, 5)
        # Verifikasi bahwa semua 5 ghost agent juga telah melangkah tepat 5 kali!
        for name, g in director.ghosts.items():
            agent = g["agent"]
            self.assertEqual(agent.t, 5, f"Ghost agent {name} harus sinkron pada t=5!")

    def test_09_lai_robbins_bound(self):
        """Batas teoritis Lai-Robbins c*ln(t) bernilai non-negatif dan tumbuh logaritmik."""
        director = BanditDirector(preset_key="REALISTIC", seed=42)
        for _ in range(10):
            director.resolve_cast(0)
        bound = director.get_lai_robbins_bound()
        self.assertEqual(len(bound), 11)
        self.assertAlmostEqual(bound[0], 0.0)
        self.assertGreater(bound[-1], bound[1], "Batas logaritmik harus membesar seiring t.")

    def test_10_world_state_and_economy_integration(self):
        """WorldState terintegrasi dengan BanditDirector dan ekonomi rare_fish."""
        ws = WorldState(starting_coins=20, seed=42)
        self.assertTrue(hasattr(ws, "bandit_director"), "WorldState wajib memiliki bandit_director!")
        self.assertIn("rare_fish", DEFAULT_SELL_PRICES)
        self.assertEqual(DEFAULT_SELL_PRICES["rare_fish"], 60)

        # Lakukan pancingan di spot 3
        ok, msg = ws.fish(spot_id=3)
        self.assertTrue(ok)
        self.assertTrue(ws.inventory.has_item("fish", 1))
        self.assertEqual(ws.bandit_director.t, 1)

    def test_11_bandit_hud_headless_rendering(self):
        """BanditHUD dapat dirender pada seluruh 3 mode display tanpa error visual."""
        import pygame
        from decision.bandit_ui import BanditHUD
        pygame.init()
        surf = pygame.Surface((1024, 576))
        director = BanditDirector(preset_key="REALISTIC", seed=42)
        for i in range(10):
            director.resolve_cast(i % 5)
        hud = BanditHUD(director, 1024, 576)
        hud.visible = True

        for mode in (BanditHUD.MODE_PLAYER, BanditHUD.MODE_ANALYST, BanditHUD.MODE_REVEAL):
            hud.mode = mode
            hud.render(surf)

        hud.cycle_mode()
        self.assertTrue(hud.mode in (BanditHUD.MODE_PLAYER, BanditHUD.MODE_ANALYST, BanditHUD.MODE_REVEAL))


if __name__ == "__main__":
    unittest.main()
