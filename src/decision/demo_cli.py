"""
demo_cli.py - Antarmuka Baris Perintah (CLI) Demonstrasi Modul Decisions Under Uncertainty.
Materi: Slide 3 - 23.

Penggunaan:
  python3 src/decision/demo_cli.py --demo-mdp
  python3 src/decision/demo_cli.py --demo-bayes
  python3 src/decision/demo_cli.py --demo-reward-shaping
  python3 src/decision/demo_cli.py --demo-sensitivity
  python3 src/decision/demo_cli.py --all
"""

import sys
import os
import argparse

# Pastikan src ada di sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from decision.probability import expected_value, expected_utility, meu, bayes_update
from decision.mdp import value_iteration, format_flood_iteration_table
from decision.flood_model import create_flood_mdp, analyze_sensitivity_f, generate_sensitivity_chart


def run_demo_mdp():
    print("\n" + "=" * 80)
    print(" DEMO 1: VALUE ITERATION & BELLMAN EQUATION PADA MODEL BANJIR (Slide 13-21)")
    print("=" * 80)

    # 1. Kasus f = 0.1 (Hari Biasa / Risiko Rendah)
    print("\n[SKENARIO A] Kasus f = 0.1 (Hari Normal, Cuaca Mendukung)")
    mdp_01 = create_flood_mdp(f=0.1, gamma=0.8, step_reward=-2.0)
    v_01, pol_01, hist_01 = value_iteration(mdp_01)
    print(format_flood_iteration_table(hist_01))
    print(f"Hasil Akhir Konvergensi (Iterasi {hist_01[-1]['iteration']}):")
    print(f"  V(Rumah)      = {v_01['Rumah']:.2f}")
    print(f"  V(Warung)     = {v_01['Warung']:.2f} -> Aksi Terpilih: '{pol_01['Warung']}'")
    print(f"  V(Jalan Raya) = {v_01['Jalan Raya']:.2f}")
    print(f"  Kebijakan Optimal (Policy): {pol_01}")

    # 2. Kasus f = 0.25 (Risiko Tinggi / Berita Banjir)
    print("\n[SKENARIO B] Kasus f = 0.25 (Risiko Tinggi, Berita Banjir Beredar)")
    mdp_025 = create_flood_mdp(f=0.25, gamma=0.8, step_reward=-2.0)
    v_025, pol_025, hist_025 = value_iteration(mdp_025)
    print(format_flood_iteration_table(hist_025))
    print(f"Hasil Akhir Konvergensi (Iterasi {hist_025[-1]['iteration']}):")
    print(f"  V(Rumah)      = {v_025['Rumah']:.2f}")
    print(f"  V(Warung)     = {v_025['Warung']:.2f} -> Aksi Terpilih: '{pol_025['Warung']}'")
    print(f"  V(Jalan Raya) = {v_025['Jalan Raya']:.2f}")
    print(f"  Kebijakan Optimal (Policy): {pol_025}")
    print("\nKESIMPULAN:")
    print("  Pada f=0.1, agen memilih 'Pintas' (V=7.0).")
    print("  Pada f=0.25, risiko banjir naik sehingga agen beralih ke 'Raya' (V=6.0 > 2.5).")


def run_demo_bayes():
    print("\n" + "=" * 80)
    print(" DEMO 2: TEOREMA BAYES, EV, DAN MAXIMUM EXPECTED UTILITY (Slide 3-8)")
    print("=" * 80)

    prior_banjir = config.FLOOD_PRIOR_DEFAULT  # 0.1
    p_berita_banjir = config.P_NEWS_GIVEN_FLOOD  # 0.9
    p_berita_nobanjir = config.P_NEWS_GIVEN_NO_FLOOD  # 0.1

    print(f"1. Prior Probabilitas Banjir : P(Banjir) = {prior_banjir}")
    print(f"2. Likelihood Bukti Berita   : P(Berita | Banjir) = {p_berita_banjir}")
    print(f"                               P(Berita | ~Banjir) = {p_berita_nobanjir}")

    # Hitung pembaruan Bayes
    post_banjir, p_berita = bayes_update(prior_banjir, p_berita_banjir, p_berita_nobanjir)

    print("\n[HASIL PERHITUNGAN BAYES]")
    print(f"  P(E) = P(Berita) = ({p_berita_banjir} * {prior_banjir}) + ({p_berita_nobanjir} * {1.0 - prior_banjir:.1f})")
    print(f"                   = {p_berita:.4f} (Persis 0.18)")
    print(f"  Posterior P(Banjir | Berita) = ({p_berita_banjir} * {prior_banjir}) / {p_berita:.4f}")
    print(f"                               = {post_banjir:.4f} (Persis 0.5)")

    # Perubahan Keputusan MEU
    ev_pintas_normal = expected_value([(0.9, 10.0), (0.1, -20.0)])
    ev_raya_normal = 6.0
    best_normal, val_normal = meu({"Pintas": [(0.9, 10.0), (0.1, -20.0)], "Jalan Utama": [(1.0, 6.0)]})

    print("\n[KEPUTUSAN SEBELUM ADA BUKTI (HARI BIASA)]")
    print(f"  EV(Pintas)      = 0.9 * 10 + 0.1 * (-20) = {ev_pintas_normal:.1f}")
    print(f"  EV(Jalan Utama) = 1.0 * 6 = {ev_raya_normal:.1f}")
    print(f"  MEU Rekomendasi : Pilih '{best_normal}' (Nilai: {val_normal:.1f})")

    ev_pintas_berita = expected_value([(1.0 - post_banjir, 10.0), (post_banjir, -20.0)])
    best_berita, val_berita = meu({"Pintas": [(1.0 - post_banjir, 10.0), (post_banjir, -20.0)], "Jalan Utama": [(1.0, 6.0)]})

    print("\n[KEPUTUSAN SETELAH MENDENGAR BERITA BANJIR]")
    print(f"  EV(Pintas | Berita) = {1.0 - post_banjir:.1f} * 10 + {post_banjir:.1f} * (-20) = {ev_pintas_berita:.1f}")
    print(f"  EV(Jalan Utama)     = {ev_raya_normal:.1f}")
    print(f"  MEU Rekomendasi     : Berubah ke '{best_berita}' (karena {val_berita:.1f} > {ev_pintas_berita:.1f})")

    # Kasus Tambahan: Bukti "Cerah"
    p_cerah_banjir = config.P_SUNNY_GIVEN_FLOOD      # 0.1
    p_cerah_nobanjir = config.P_SUNNY_GIVEN_NO_FLOOD  # 0.9
    post_cerah, p_cerah = bayes_update(prior_banjir, p_cerah_banjir, p_cerah_nobanjir)
    print("\n[BUKTI TAMBAHAN: CUACA CERAH]")
    print(f"  P(Cerah) = {p_cerah_banjir}*0.1 + {p_cerah_nobanjir}*0.9 = {p_cerah:.4f} (0.82)")
    print(f"  P(Banjir | Cerah) = (0.1*0.1) / {p_cerah:.4f} = {post_cerah:.6f} (~0.0122)")


def run_demo_reward_shaping():
    print("\n" + "=" * 80)
    print(" DEMO 3: KESALAHAN REWARD SHAPING / OBJECTIVE MIS-SPECIFICATION (Slide 23)")
    print("=" * 80)

    print("Skenario: Setiap aksi melangkah (Jalan, Balik) diberi bonus reward +3.0.")
    mdp_bad = create_flood_mdp(f=0.1, gamma=0.8, reward_shaping=True)
    v_bad, pol_bad, hist_bad = value_iteration(mdp_bad)

    print(f"Konvergensi Value Iteration tercapai pada iterasi {hist_bad[-1]['iteration']}:")
    print(f"  V(Rumah)  = {v_bad['Rumah']:.2f}")
    print(f"  V(Warung) = {v_bad['Warung']:.2f}")
    print(f"  Kebijakan Terpilih: {pol_bad}")

    print("\nANALISIS MATEMATIS LOOP ABADI:")
    print("  Jika agen bergerak bolak-balik antara Warung dan Rumah:")
    print("    V = 3 + 0.8 * (3 + 0.8 * (3 + ...))")
    print("    V = 3 / (1 - 0.8) = 3 / 0.2 = 15.0")
    print("  Bandingkan dengan jalur normal:")
    print("    Q(Warung, Raya)   = 3 + 0.8 * 10 = 11.0")
    print("    Q(Warung, Pintas) = 0.9 * 10 + 0.1 * (-20) = 7.0")
    print("  Karena 15.0 > 11.0 > 7.0, agen lebih memilih loop bolak-balik Rumah <-> Warung selamanya!")
    print("  Inti Pelajaran: Yang diberi insentif adalah 'aktivitas bergerak' (+3), bukan hasil akhir 'sampai ke kampus'.")


def run_demo_sensitivity():
    print("\n" + "=" * 80)
    print(" DEMO 4: ANALISIS SENSITIVITAS & AMBANG BATAS f* (Ekstensi Analitik di Luar Slide)")
    print(" (Catatan: Slide 22 adalah diagram hasil akhir f = 0.25)")
    print("=" * 80)

    res = analyze_sensitivity_f(f_start=0.0, f_end=0.5, steps=101)
    f_star = res["f_star_analytic"]
    f_switch = res["numerical_switch_f"]
    step_size = res.get("step_size", 0.005)
    bisection_f = res.get("bisection_switch_f", f_star)
    bisection_iters = res.get("bisection_iterations", 0)

    print(f"Batas Analitik Teoretis : f* = 4/30 = 2/15 = {f_star:.6f} (~0.1333)")
    print(f"Sweep Grid Numerik      : Rentang [0.0, 0.5] | 101 titik (Langkah/Step: {step_size:.4f})")
    print(f"  Switch Point Grid     : f  = {f_switch:.4f}")
    print(f"Pencarian Bisection     : f* = {bisection_f:.6f} (Konvergen dalam {bisection_iters} iterasi)")
    print("\nAturan Kebijakan:")
    print(f"  - Untuk f < {f_star:.4f} : Pilih 'Pintas' (Q_Pintas = 10 - 30f > 6.0)")
    print(f"  - Untuk f > {f_star:.4f} : Pilih 'Raya'   (Q_Raya = 6.0 > Q_Pintas)")

    chart_file = generate_sensitivity_chart()
    print(f"Grafik visual kurva dan region tersimpan di: {chart_file}")


def main():
    parser = argparse.ArgumentParser(description="CLI Demonstrasi Modul Decisions Under Uncertainty (Slide 3-23)")
    parser.add_argument("--demo-mdp", action="store_true", help="Jalankan demo Value Iteration f=0.1 & f=0.25")
    parser.add_argument("--demo-bayes", action="store_true", help="Jalankan demo Teorema Bayes & MEU")
    parser.add_argument("--demo-reward-shaping", action="store_true", help="Jalankan demo kesalahan Reward Shaping")
    parser.add_argument("--demo-sensitivity", action="store_true", help="Jalankan analisis sensitivitas f & grafik")
    parser.add_argument("--all", action="store_true", help="Jalankan semua demonstrasi")

    args = parser.parse_args()

    # Default jika tanpa argumen: jalankan --all
    if not any([args.demo_mdp, args.demo_bayes, args.demo_reward_shaping, args.demo_sensitivity, args.all]):
        args.all = True

    if args.all or args.demo_bayes:
        run_demo_bayes()
    if args.all or args.demo_mdp:
        run_demo_mdp()
    if args.all or args.demo_reward_shaping:
        run_demo_reward_shaping()
    if args.all or args.demo_sensitivity:
        run_demo_sensitivity()


if __name__ == "__main__":
    main()

