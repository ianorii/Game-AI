"""experiments/ablate_csp.py - Ablasi CSP antrean untuk laporan (Fase 2b/2c).

100 seed x varian x skenario x 3 target. Ukur mean/median/p90 nodes,
backtrack, dan ms + solved. Varian polos-acak memakai seed untuk value DAN
urutan variabel yang dipermutasi (baseline acak yang adil); polos-tetap =
seed None.

Jalan: `python3 experiments/ablate_csp.py [--seeds N]` (N=100 default).
"""
from __future__ import annotations

import random
import statistics as S
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.csp_solver import CSPProblem, CSPSolver, squad_problem  # noqa: E402

CFG = AmbushConfig()
Q = dict(queue_rules=True, min_active=2)

VARIANTS = [
    ("polos-tetap", dict(use_mrv=False, use_degree=False, use_lcv=False,
                          inference="none"), None, False),
    ("polos-acak", dict(use_mrv=False, use_degree=False, use_lcv=False,
                         inference="none"), "seed", True),
    ("+MRV", dict(use_mrv=True, use_degree=False, use_lcv=False,
                  inference="none"), "seed", False),
    ("+MRV/deg", dict(use_mrv=True, use_degree=True, use_lcv=False,
                       inference="none"), "seed", False),
    ("+LCV", dict(use_mrv=True, use_degree=True, use_lcv=True,
                  inference="none"), "seed", False),
    ("+FC", dict(use_mrv=True, use_degree=True, use_lcv=True,
                 inference="fc"), "seed", False),
    ("+AC-3", dict(use_mrv=True, use_degree=True, use_lcv=True,
                   inference="ac3"), "seed", False),
]


def permuted(prob: CSPProblem, seed: int) -> CSPProblem:
    """Salinan problem dengan urutan variabel diacak (adil untuk polos)."""
    order = list(prob.variables)
    random.Random(seed).shuffle(order)
    return replace(prob, variables=order)


def scenario_prob(target: float, scenario: str, seed: int) -> CSPProblem:
    """Bangun problem per skenario (HYBRID = domain singleton, tanpa mesin)."""
    wins = 9 if scenario == "wins9" else 0
    prob = squad_problem(wins, CFG.budget_q_for(target), CFG, **Q)
    if scenario == "hybrid":
        prob.domains = dict(prob.domains)
        prob.domains["ROLE_1"] = ["Warrior"]
        prob.domains["ITEM_1"] = ["Iron Sword"]
        prob.domains["ROLE_2"] = ["Mage"]
    return prob


def p90(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(0.9 * len(xs)))] if xs else 0


def run(n_seeds: int):
    seeds = list(range(n_seeds))
    for target in (0.3, 0.5, 0.8):
        for scenario in ("normal", "hybrid", "wins9"):
            print(f"--- target={target} skenario={scenario} "
                  f"budget={CFG.budget_q_for(target)}")
            print(f"{'varian':12s} {'nodes mean/med/p90':>24s} "
                  f"{'bt mean/med/p90':>21s} {'ms mean/p90':>13s} solved")
            for name, kw, seedmode, perm in VARIANTS:
                ns, bs, ms, ok = [], [], [], 0
                for s in seeds:
                    prob = scenario_prob(target, scenario, s)
                    if perm:
                        prob = permuted(prob, s)
                    seed = s if seedmode else None
                    t0 = time.perf_counter()
                    sol, st = CSPSolver(prob, seed=seed, **kw).solve()
                    ms.append((time.perf_counter() - t0) * 1000.0)
                    ns.append(st["nodes"])
                    bs.append(st["backtracks"])
                    ok += sol is not None
                print(f"{name:12s} {S.mean(ns):6.1f}/{S.median(ns):5.0f}/"
                      f"{p90(ns):4.0f} {S.mean(bs):7.1f}/{S.median(bs):5.0f}/"
                      f"{p90(bs):4.0f} {S.mean(ms):6.1f}/{p90(ms):5.0f} "
                      f"{ok}/{len(seeds)}")
            print()


if __name__ == "__main__":
    n = int(sys.argv[sys.argv.index("--seeds") + 1]) if "--seeds" in sys.argv else 100
    run(n)
