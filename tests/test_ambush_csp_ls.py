"""tests/test_ambush_csp_ls.py - Unit test CSP + Local Search Tahap 3.

Jalan tanpa dependensi baru: `python3 tests/test_ambush_csp_ls.py`.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.constraints import check  # noqa: E402
from game.ambush.csp_solver import CSPProblem, CSPSolver, squad_problem  # noqa: E402
from game.ambush.difficulty import HeuristicEvaluator  # noqa: E402
from game.ambush.local_search import (  # noqa: E402
    decode,
    encode,
    genetic,
    hill_climb,
    neighbours,
    project_to_feasible,
    simulated_annealing,
)
from game.ambush.trace import TraceBuffer  # noqa: E402
from game.ambush.types import EMPTY, SquadConfig  # noqa: E402

from dataclasses import replace  # noqa: E402

CFG = replace(AmbushConfig(), mode="BUFF")  # kunci perilaku BUFF lama
WINS, BUDGET, TARGET = 0, CFG.budget_for(0.5), 0.5
EV = HeuristicEvaluator(CFG)


def xyz_problem() -> CSPProblem:
    """X < Y < Z klasik, D = {1,2,3} (solusi unik 1,2,3)."""
    variables = ["X", "Y", "Z"]
    less = lambda a, b: a < b
    return CSPProblem(
        variables=variables,
        domains={v: [1, 2, 3] for v in variables},
        neighbors={"X": ["Y", "Z"], "Y": ["X", "Z"], "Z": ["X", "Y"]},
        pair_ok=lambda xi, vi, xj, vj: (
            less(vi, vj) if (xi, xj) in
            (("X", "Y"), ("Y", "Z"), ("X", "Z")) else less(vj, vi)
        ),
        partial_ok=lambda a: True,
    )


def map_problem() -> CSPProblem:
    """Pewarnaan segitiga (3 node saling bertetangga, 3 warna)."""
    variables = ["A", "B", "C"]
    return CSPProblem(
        variables=variables,
        domains={v: ["R", "G", "B"] for v in variables},
        neighbors={v: [u for u in variables if u != v] for v in variables},
        pair_ok=lambda xi, vi, xj, vj: vi != vj,
        partial_ok=lambda a: True,
    )


def squad_assign(squad: SquadConfig):
    out = {}
    for i, (r, it) in enumerate(zip(squad.roles, squad.items), 1):
        out[f"ROLE_{i}"] = r
        out[f"ITEM_{i}"] = it
    return out


def assert_squad_valid(squad: SquadConfig) -> None:
    assert len(squad.roles) == CFG.kmax and len(squad.items) == CFG.kmax
    assert not check(squad_assign(squad), WINS, BUDGET, CFG)


def test_revise_xyz():
    sol, stats = CSPSolver(xyz_problem()).solve()
    assert sol == {"X": 1, "Y": 2, "Z": 3}, sol
    assert stats["stop"] == "solved"
    assert stats["nodes"] > 0


def test_backtracking_map_coloring():
    sol, stats = CSPSolver(map_problem(), inference="none",
                           use_mrv=False, use_lcv=False).solve()
    assert sol is not None and len(sol) == 3
    assert len(set(sol.values())) == 3  # segitiga butuh 3 warna beda
    assert stats["stop"] == "solved"


def test_ac3_prunes_and_detects_unsat():
    # AC-3 memangkas X<Y<Z sebelum/saat search (revises menembak).
    _, stats = CSPSolver(xyz_problem()).solve()
    assert stats["revises"] > 0 and stats["pruned"] > 0
    # Segitiga 2 warna: arc-consistent tapi tak ada solusi -> unsatisfiable.
    tri2 = CSPProblem(
        variables=["A", "B", "C"],
        domains={v: ["R", "G"] for v in ["A", "B", "C"]},
        neighbors={"A": ["B", "C"], "B": ["A", "C"], "C": ["A", "B"]},
        pair_ok=lambda xi, vi, xj, vj: vi != vj,
        partial_ok=lambda a: True,
    )
    sol, stats = CSPSolver(tri2).solve()
    assert sol is None and stats["stop"] == "unsatisfiable"


def test_solver_toggle_matrix():
    """Semua kombinasi heuristik harus menghasilkan solusi valid squad."""
    problem = squad_problem(WINS, BUDGET, CFG)
    combos = [
        {"use_mrv": False, "use_degree": False, "use_lcv": False,
         "inference": "none"},
        {"use_mrv": True, "use_degree": False, "use_lcv": False,
         "inference": "none"},
        {"use_mrv": True, "use_degree": True, "use_lcv": False,
         "inference": "none"},
        {"use_mrv": True, "use_degree": True, "use_lcv": True,
         "inference": "none"},
        {"use_mrv": True, "use_degree": True, "use_lcv": True,
         "inference": "fc"},
        {"use_mrv": True, "use_degree": True, "use_lcv": True,
         "inference": "ac3"},
    ]
    for kw in combos:
        tracer = TraceBuffer()
        sol, stats = CSPSolver(problem, tracer=tracer, **kw).solve()
        assert sol is not None, kw
        assert len(sol) == 2 * CFG.kmax, kw  # complete
        assert not check(sol, WINS, BUDGET, CFG), kw  # consistent
        assert stats["nodes"] >= 1


def test_seed_changes_tiebreak_deterministically():
    problem = squad_problem(WINS, BUDGET, CFG)
    a, _ = CSPSolver(problem, seed=1).solve()
    b, _ = CSPSolver(problem, seed=1).solve()
    c, _ = CSPSolver(problem, seed=2).solve()
    assert a == b  # seed sama -> solusi sama (reproducible)
    assert a is not None and c is not None


def test_neighbours_all_consistent():
    start = SquadConfig(roles=("Warrior", "Archer", EMPTY, EMPTY),
                        items=("Iron Sword", EMPTY, EMPTY, EMPTY))
    nbs, rejected = neighbours(start, WINS, BUDGET, CFG)
    assert len(nbs) > 0
    for nb in nbs:
        assert not check(squad_assign(nb), WINS, BUDGET, CFG), nb
    assert rejected >= 0
    # Spot-check: ganti role slot 1 Warrior->Archer mempertahankan Sword
    # (Archer kompatibel dengan Iron Sword di matriks ITEM_ALLOWED).
    assert any(nb.roles[0] == "Archer" and nb.items[0] == "Iron Sword"
               for nb in nbs)


def test_hill_climb_never_worsens():
    start = SquadConfig(roles=("Warrior", EMPTY, EMPTY, EMPTY),
                        items=(EMPTY, EMPTY, EMPTY, EMPTY))
    start_gap = abs(EV.evaluate(start) - TARGET)
    res = hill_climb(start, EV, TARGET, WINS, BUDGET, CFG)
    assert_squad_valid(res.best)
    assert res.best_gap <= start_gap + 1e-9
    assert res.stop in ("target", "local_maximum", "plateau",
                       "iter_limit", "time_limit", "no_valid_neighbour")
    assert len(res.history) >= 1


def test_simulated_annealing_returns_valid():
    start = SquadConfig(roles=("Warrior", EMPTY, EMPTY, EMPTY),
                        items=(EMPTY, EMPTY, EMPTY, EMPTY))
    res = simulated_annealing(start, EV, TARGET, WINS, BUDGET, CFG,
                              max_iters=60, seed=3)
    assert_squad_valid(res.best)
    assert 0.0 <= res.best_diff <= 1.0
    assert res.stop in ("target", "cooled", "iter_limit", "time_limit",
                       "no_valid_neighbour")


def test_genetic_penalty_and_repair():
    seeds = [SquadConfig(roles=("Warrior", EMPTY, EMPTY, EMPTY),
                         items=(EMPTY, EMPTY, EMPTY, EMPTY))]
    kw = dict(evaluator=EV, target=TARGET, wins=WINS, budget=BUDGET,
              cfg=CFG, pop_size=8, generations=5, seed=11)
    penal = genetic(seeds, repair=False, **kw)
    assert isinstance(penal.best, SquadConfig)
    fixed = genetic(seeds, repair=True, **kw)
    assert_squad_valid(fixed.best)  # repair menjamin feasible
    assert fixed.extra["feasible_found"] is True


def test_encode_decode_roundtrip_and_crossover_length():
    squad = SquadConfig(roles=("Mage", "Tank", EMPTY, EMPTY),
                        items=("Healing Charm", EMPTY, EMPTY, EMPTY))
    assert decode(encode(squad, CFG), CFG) == squad
    # Proyeksi contoh infeasible (2 Healer + Fang ganda) jadi feasible.
    bad = SquadConfig(roles=("Healer", "Healer", EMPTY, EMPTY),
                      items=("Dragon Fang", "Dragon Fang", EMPTY, EMPTY))
    assert check(squad_assign(bad), WINS, 99, CFG)
    assert not check(squad_assign(
        project_to_feasible(bad, WINS, 99, CFG)), WINS, 99, CFG)


if __name__ == "__main__":
    tests = sorted(
        (v for k, v in globals().items() if k.startswith("test_")),
        key=lambda fn: fn.__name__,
    )
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001 - runner mandiri
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"{len(tests) - failed}/{len(tests)} lolos")
    raise SystemExit(1 if failed else 0)
