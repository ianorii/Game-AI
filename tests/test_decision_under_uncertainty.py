"""
test_decision_under_uncertainty.py

Unit test komprehensif untuk memverifikasi modul Decisions Under Uncertainty (Slide 3-23):
1. Probabilitas, Expected Value (EV), Expected Utility (EU), Maximum Expected Utility (MEU).
2. Teorema Bayes (perhitungan P(E)=0.18, P(Banjir|Berita)=0.5, dan bukti Cerah).
3. Struktur kelas MDP, validasi probabilitas = 1.0, penolakan f di luar [0, 1], kasus tanpa aksi.
4. Bellman equation & Synchronous Value Iteration (verifikasi f=0.1 dan f=0.25 sesuai slide).
5. Ekstraksi Policy & perbandingan Plan vs Policy.
6. Analisis sensitivitas batas analitik f* = 4/30 (~0.1333) vs sweep numerik.
7. Varian kesalahan Reward Shaping (+3) menghasilkan loop abadi V=15.0.

CATATAN: Semua operasi file pengujian menggunakan folder sementara (tempfile.TemporaryDirectory).
"""

import os
import sys
import tempfile
import unittest

# Pastikan path src terdaftar
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config
from decision.probability import expected_value, expected_utility, meu, bayes_update
from decision.mdp import MDP, compute_q, value_iteration, extract_policy
from decision.flood_model import (
    create_flood_mdp,
    analyze_sensitivity_f,
    generate_sensitivity_chart
)


class TestDecisionUnderUncertainty(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    # =========================================================================
    # 1. PROBABILITAS, EV, MEU (SLIDE 3-6)
    # =========================================================================
    def test_expected_value_and_meu_slide_example(self):
        """Memverifikasi EV dan MEU pada hari biasa (f=0.1): EV Pintas = 7 vs Jalan Utama = 6."""
        # Pintas: P(Kampus)=0.9 -> +10, P(Banjir)=0.1 -> -20
        outcomes_pintas = [(0.9, 10.0), (0.1, -20.0)]
        ev_pintas = expected_value(outcomes_pintas)
        self.assertAlmostEqual(ev_pintas, 7.0, places=5)

        # Jalan Utama: Pasti bebas banjir (1.0) -> +6
        outcomes_utama = [(1.0, 6.0)]
        ev_utama = expected_value(outcomes_utama)
        self.assertAlmostEqual(ev_utama, 6.0, places=5)

        # MEU: Memilih Pintas (7.0 > 6.0)
        action_outcomes = {
            "pintas": outcomes_pintas,
            "jalan_utama": outcomes_utama
        }
        best_action, max_val = meu(action_outcomes)
        self.assertEqual(best_action, "pintas")
        self.assertAlmostEqual(max_val, 7.0, places=5)

    def test_expected_utility_custom_fn(self):
        """Memverifikasi expected utility dengan fungsi utilitas non-linear (risk-averse)."""
        # U(v) = - (v - 10)^2 untuk penghindaran risiko ekstrim
        outcomes = [(0.9, 10.0), (0.1, -20.0)]
        eu_linear = expected_utility(outcomes)
        self.assertAlmostEqual(eu_linear, 7.0, places=5)

        # Dengan utility kuadratik: U(10) = 0, U(-20) = -900
        eu_risk = expected_utility(outcomes, utility_fn=lambda v: 0.0 if v >= 10 else -900.0)
        self.assertAlmostEqual(eu_risk, -90.0, places=5)

    # =========================================================================
    # 2. TEOREMA BAYES (SLIDE 7-8)
    # =========================================================================
    def test_bayes_update_berita_banjir(self):
        """Memverifikasi pembaruan Bayes bukti Berita: P(Berita)=0.18, P(Banjir|Berita)=0.5."""
        prior = 0.1
        p_berita_banjir = 0.9
        p_berita_nobanjir = 0.1

        post_banjir, p_berita = bayes_update(prior, p_berita_banjir, p_berita_nobanjir)

        # P(Berita) = 0.9*0.1 + 0.1*0.9 = 0.18
        self.assertAlmostEqual(p_berita, 0.18, places=5)
        # P(Banjir | Berita) = 0.09 / 0.18 = 0.5
        self.assertAlmostEqual(post_banjir, 0.5, places=5)

        # Keputusan MEU setelah berita:
        # EU(Pintas | Berita) = 0.5 * 10 + 0.5 * (-20) = -5.0
        outcomes_pintas_post = [(1.0 - post_banjir, 10.0), (post_banjir, -20.0)]
        eu_post = expected_value(outcomes_pintas_post)
        self.assertAlmostEqual(eu_post, -5.0, places=5)

        # Keputusan berubah ke Jalan Utama (6.0 > -5.0)
        best_act, val = meu({"pintas": outcomes_pintas_post, "jalan_utama": [(1.0, 6.0)]})
        self.assertEqual(best_act, "jalan_utama")
        self.assertAlmostEqual(val, 6.0, places=5)

    def test_bayes_update_cuaca_cerah(self):
        """Memverifikasi pembaruan Bayes bukti Cerah: P(Banjir|Cerah) = 0.01 / 0.82 ~ 0.0122."""
        prior = 0.1
        p_cerah_banjir = 0.1
        p_cerah_nobanjir = 0.9

        post_banjir, p_cerah = bayes_update(prior, p_cerah_banjir, p_cerah_nobanjir)

        # P(Cerah) = 0.1*0.1 + 0.9*0.9 = 0.01 + 0.81 = 0.82
        self.assertAlmostEqual(p_cerah, 0.82, places=5)
        # P(Banjir | Cerah) = 0.01 / 0.82 = 0.01219512...
        expected_post = 0.01 / 0.82
        self.assertAlmostEqual(post_banjir, expected_post, places=5)

    # =========================================================================
    # 3. STRUKTUR KELAS MDP & VALIDASI (SLIDE 9-11)
    # =========================================================================
    def test_mdp_probability_validation(self):
        """Memastikan kelas MDP memvalidasi total probabilitas == 1.0 dan menolak probabilitas cacat."""
        # Model normal valid
        mdp = create_flood_mdp(f=0.1)
        self.assertEqual(len(mdp.states), 5)
        self.assertEqual(mdp.terminal_states, {"Kampus", "Banjir"})

        # Aksi di terminal harus kosong
        self.assertEqual(mdp.actions("Kampus"), [])
        self.assertEqual(mdp.actions("Banjir"), [])

        # Penolakan f di luar [0, 1]
        with self.assertRaises(ValueError):
            create_flood_mdp(f=-0.05)
        with self.assertRaises(ValueError):
            create_flood_mdp(f=1.05)

        # Penolakan jika total probabilitas transisi != 1.0
        bad_transitions = {
            ("Rumah", "Jalan"): [("Warung", 0.7)]  # Kurang dari 1.0
        }
        with self.assertRaises(ValueError):
            MDP(
                states=["Rumah", "Warung"],
                actions_dict={"Rumah": ["Jalan"]},
                transitions=bad_transitions,
                rewards={"Rumah": -2.0, "Warung": -2.0}
            )

    # =========================================================================
    # 4. VALUE ITERATION SINKRON & PERSIS SLIDE (SLIDE 13-21)
    # =========================================================================
    def test_iteration_0_format_guarantee(self):
        """Memverifikasi iterasi 0 hanya memuat V0=0.0 dan Q kosong (tanda '-' di tabel, sesuai Slide 17)."""
        mdp = create_flood_mdp(f=0.1)
        _, _, history = value_iteration(mdp)
        it0 = history[0]
        self.assertEqual(it0["iteration"], 0)
        for s in mdp.states:
            self.assertEqual(it0["V"][s], 0.0)
        self.assertEqual(it0["Q"], {})
        self.assertEqual(it0["policy"], {})

    def test_synchronous_update_guarantee(self):
        """Memastikan update murni SINKRON: Q(Warung, Raya) di Iterasi 1 memakai V0(Jalan Raya)=0 -> Q=-2."""
        mdp = create_flood_mdp(f=0.1, gamma=0.8, step_reward=-2.0)
        _, _, history = value_iteration(mdp)

        # Pada iterasi 1:
        # V0(Jalan Raya) = 0.0. Jika sinkron, Q(Warung, Raya) = -2 + 0.8*(0.0) = -2.0.
        # Jika Gauss-Seidel in-place, V1(Jalan Raya)=10 sudah terhitung lebih dulu sehingga Q=6.0.
        it1 = history[1]
        self.assertAlmostEqual(it1["Q"][("Warung", "Raya")], -2.0, places=5)
        self.assertAlmostEqual(it1["V"]["Warung"], 7.0, places=5)
        self.assertAlmostEqual(it1["V"]["Jalan Raya"], 10.0, places=5)

    def test_value_iteration_f_01_exact_slide_numbers(self):
        """Memverifikasi seluruh angka iterasi untuk f = 0.1 persis sesuai slide 15-18."""
        mdp = create_flood_mdp(f=0.1, gamma=0.8, step_reward=-2.0)
        v_final, policy, history = value_iteration(mdp)

        # Iterasi 1
        it1 = history[1]
        self.assertAlmostEqual(it1["V"]["Rumah"], -2.0, places=4)
        self.assertAlmostEqual(it1["Q"][("Warung", "Pintas")], 7.0, places=4)
        self.assertAlmostEqual(it1["Q"][("Warung", "Raya")], -2.0, places=4)
        self.assertAlmostEqual(it1["Q"][("Warung", "Balik")], -2.0, places=4)
        self.assertAlmostEqual(it1["V"]["Warung"], 7.0, places=4)
        self.assertEqual(it1["policy"]["Warung"], "Pintas")
        self.assertAlmostEqual(it1["V"]["Jalan Raya"], 10.0, places=4)

        # Iterasi 2
        it2 = history[2]
        self.assertAlmostEqual(it2["V"]["Rumah"], 3.6, places=4)
        self.assertAlmostEqual(it2["Q"][("Warung", "Pintas")], 7.0, places=4)
        self.assertAlmostEqual(it2["Q"][("Warung", "Raya")], 6.0, places=4)
        self.assertAlmostEqual(it2["Q"][("Warung", "Balik")], -3.6, places=4)
        self.assertAlmostEqual(it2["V"]["Warung"], 7.0, places=4)
        self.assertEqual(it2["policy"]["Warung"], "Pintas")
        self.assertAlmostEqual(it2["V"]["Jalan Raya"], 10.0, places=4)

        # Iterasi 3
        it3 = history[3]
        self.assertAlmostEqual(it3["V"]["Rumah"], 3.6, places=4)
        self.assertAlmostEqual(it3["Q"][("Warung", "Pintas")], 7.0, places=4)
        self.assertAlmostEqual(it3["Q"][("Warung", "Raya")], 6.0, places=4)
        self.assertAlmostEqual(it3["Q"][("Warung", "Balik")], 0.88, places=4)
        self.assertAlmostEqual(it3["V"]["Warung"], 7.0, places=4)
        self.assertEqual(it3["policy"]["Warung"], "Pintas")
        self.assertAlmostEqual(it3["V"]["Jalan Raya"], 10.0, places=4)

        # Kebijakan akhir f = 0.1
        self.assertEqual(policy["Rumah"], "Jalan")
        self.assertEqual(policy["Warung"], "Pintas")
        self.assertEqual(policy["Jalan Raya"], "Jalan")

    def test_value_iteration_f_025_exact_slide_numbers(self):
        """Memverifikasi seluruh angka iterasi untuk f = 0.25 persis sesuai slide 19-21."""
        mdp = create_flood_mdp(f=0.25, gamma=0.8, step_reward=-2.0)
        v_final, policy, history = value_iteration(mdp)

        # Iterasi 1
        it1 = history[1]
        self.assertAlmostEqual(it1["V"]["Rumah"], -2.0, places=4)
        self.assertAlmostEqual(it1["Q"][("Warung", "Pintas")], 2.5, places=4)
        self.assertAlmostEqual(it1["Q"][("Warung", "Raya")], -2.0, places=4)
        self.assertAlmostEqual(it1["Q"][("Warung", "Balik")], -2.0, places=4)
        self.assertAlmostEqual(it1["V"]["Warung"], 2.5, places=4)
        self.assertAlmostEqual(it1["V"]["Jalan Raya"], 10.0, places=4)

        # Iterasi 2
        it2 = history[2]
        self.assertAlmostEqual(it2["V"]["Rumah"], 0.0, places=4)
        self.assertAlmostEqual(it2["Q"][("Warung", "Pintas")], 2.5, places=4)
        self.assertAlmostEqual(it2["Q"][("Warung", "Raya")], 6.0, places=4)
        self.assertAlmostEqual(it2["Q"][("Warung", "Balik")], -3.6, places=4)
        self.assertAlmostEqual(it2["V"]["Warung"], 6.0, places=4)
        self.assertEqual(it2["policy"]["Warung"], "Raya")
        self.assertAlmostEqual(it2["V"]["Jalan Raya"], 10.0, places=4)

        # Hasil Akhir
        self.assertAlmostEqual(v_final["Rumah"], 2.8, places=4)
        self.assertAlmostEqual(v_final["Warung"], 6.0, places=4)
        self.assertAlmostEqual(v_final["Jalan Raya"], 10.0, places=4)
        self.assertEqual(policy["Warung"], "Raya")

    # =========================================================================
    # 5. POLICY EXTRACTION & STOPPING CONDITION
    # =========================================================================
    def test_stopping_condition_tolerance(self):
        """Memastikan value iteration berhenti saat delta < tolerance."""
        mdp = create_flood_mdp(f=0.1)
        tol = 1e-4
        _, _, history = value_iteration(mdp, tolerance=tol)
        last_delta = history[-1]["delta"]
        self.assertLess(last_delta, tol)

    def test_extract_policy_consistency(self):
        """Memastikan extract_policy menghasilkan pemetaan aksi terbaik konsisten dengan Q."""
        mdp = create_flood_mdp(f=0.1)
        V, policy, _ = value_iteration(mdp)
        extracted = extract_policy(mdp, V)
        self.assertEqual(policy, extracted)

    # =========================================================================
    # 6. ANALISIS SENSITIVITAS f* = 4/30 (EKSTENSI ANALITIK DI LUAR SLIDE 22)
    # =========================================================================
    def test_sensitivity_analytic_threshold(self):
        """Memverifikasi batas analitik f* = 4/30 = 0.133333... dan transisi kebijakan."""
        f_star = config.DECISION_ANALYTIC_F_STAR
        self.assertAlmostEqual(f_star, 4.0 / 30.0, places=6)

        # Sedikit di bawah f*: Pintas lebih baik
        mdp_below = create_flood_mdp(f=f_star - 0.01)
        _, pol_below, _ = value_iteration(mdp_below)
        self.assertEqual(pol_below["Warung"], "Pintas")

        # Sedikit di atas f*: Raya lebih baik
        mdp_above = create_flood_mdp(f=f_star + 0.01)
        _, pol_above, _ = value_iteration(mdp_above)
        self.assertEqual(pol_above["Warung"], "Raya")

        # Sweep numerik
        res = analyze_sensitivity_f(f_start=0.0, f_end=0.5, steps=101)
        self.assertAlmostEqual(res["f_star_analytic"], 4.0 / 30.0, places=6)
        self.assertIsNotNone(res["numerical_switch_f"])
        self.assertAlmostEqual(res["numerical_switch_f"], f_star, delta=0.01)
        self.assertAlmostEqual(res["bisection_switch_f"], 4.0 / 30.0, places=5)

    def test_bisection_search_convergence(self):
        """Memverifikasi pencarian bisection konvergen presisi tinggi ke f* = 4/30 = 0.133333..."""
        from decision.flood_model import find_f_star_bisection
        bisection_f, iters = find_f_star_bisection(f_min=0.0, f_max=0.5, tol=1e-6)
        self.assertAlmostEqual(bisection_f, 4.0 / 30.0, places=5)
        self.assertLessEqual(iters, 25)

    def test_extreme_cases_f_0_and_f_1(self):
        """
        Memverifikasi kasus ekstrim f = 0 dan f = 1:
        f = 0: Bebas risiko banjir -> V(Warung) = 10.0 (Pintas), V(Rumah) = -2 + 0.8*10 = 6.0
        f = 1: Pasti banjir di pintas -> V(Warung) = 6.0 (Raya), V(Rumah) = -2 + 0.8*6 = 2.8
        """
        # Kasus f = 0
        mdp_0 = create_flood_mdp(f=0.0)
        v_0, pol_0, _ = value_iteration(mdp_0)
        self.assertAlmostEqual(v_0["Warung"], 10.0, places=5)
        self.assertAlmostEqual(v_0["Rumah"], 6.0, places=5)
        self.assertEqual(pol_0["Warung"], "Pintas")

        # Kasus f = 1
        mdp_1 = create_flood_mdp(f=1.0)
        v_1, pol_1, _ = value_iteration(mdp_1)
        self.assertAlmostEqual(v_1["Warung"], 6.0, places=5)
        self.assertAlmostEqual(v_1["Rumah"], 2.8, places=5)
        self.assertEqual(pol_1["Warung"], "Raya")

    def test_warung_value_max_formula(self):
        """
        Memverifikasi rumus analitik:
          V(Warung) = max(10 - 30f, 6.0) untuk berbagai titik f in [0, 1].
        """
        test_f_points = [0.0, 0.05, 0.1, 4.0 / 30.0, 0.2, 0.35, 0.5, 0.8, 1.0]
        for f_val in test_f_points:
            mdp = create_flood_mdp(f=f_val)
            v, _, _ = value_iteration(mdp)
            expected_v = max(10.0 - 30.0 * f_val, 6.0)
            self.assertAlmostEqual(
                v["Warung"],
                expected_v,
                places=4,
                msg=f"Gagal pada f={f_val}: V(Warung)={v['Warung']}, expected={expected_v}"
            )

    def test_sensitivity_chart_generation(self):
        """Memastikan pembuatan file grafik sensitivitas PNG di temporary directory berjalan tanpa error."""
        out_chart = os.path.join(self.temp_dir.name, "sensitivity.png")
        saved = generate_sensitivity_chart(output_path=out_chart)
        self.assertTrue(os.path.exists(saved))
        self.assertGreater(os.path.getsize(saved), 1000)

    # =========================================================================
    # 7. KESALAHAN REWARD SHAPING (SLIDE 23)
    # =========================================================================
    def test_reward_shaping_loop_infinite_value_15(self):
        """Memverifikasi varian reward shaping (+3/langkah) konvergen ke V=15.0 dan loop abadi Balik-Jalan."""
        mdp_bad = create_flood_mdp(f=0.1, reward_shaping=True)
        v_bad, pol_bad, _ = value_iteration(mdp_bad, tolerance=1e-5)

        # Nilai analitik: 3 / (1 - 0.8) = 15.0
        self.assertAlmostEqual(v_bad["Rumah"], 15.0, places=4)
        self.assertAlmostEqual(v_bad["Warung"], 15.0, places=4)

        # Bandingkan Q(Warung):
        # Q(Balik) = 3 + 0.8 * 15 = 15.0
        # Q(Raya)  = 3 + 0.8 * 10 = 11.0
        # Q(Pintas) = 0.9 * 10 + 0.1 * (-20) = 7.0
        # Karena 15 > 11 > 7, agen memilih Balik
        self.assertEqual(pol_bad["Warung"], "Balik")
        self.assertEqual(pol_bad["Rumah"], "Jalan")


if __name__ == "__main__":
    unittest.main()

