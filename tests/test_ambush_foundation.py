"""tests/test_ambush_foundation.py - Unit test fondasi Tahap 3.

Jalan tanpa dependensi baru: `python3 tests/test_ambush_foundation.py`
dari root proyek. (pytest juga bisa bila tersedia.)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.ambush.buff import squad_to_buff  # noqa: E402
from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.constraints import (  # noqa: E402
    build_domains,
    check,
    is_complete,
    is_consistent,
    neighbors_of,
    partial_cost,
    variable_names,
)
from game.ambush.difficulty import (  # noqa: E402
    HeuristicEvaluator,
    SimulationEvaluator,
    difficulty_gap,
)
from game.ambush.types import EMPTY, FANG, SquadConfig  # noqa: E402

from dataclasses import replace  # noqa: E402

CFG = replace(AmbushConfig(), mode="BUFF")  # kunci perilaku BUFF lama


def squad(roles, items):
    """Bangun SquadConfig sepanjang kmax (pendekkan penulisan test)."""
    roles = tuple(roles) + (EMPTY,) * (CFG.kmax - len(roles))
    items = tuple(items) + (EMPTY,) * (CFG.kmax - len(items))
    return SquadConfig(roles=roles, items=items)


def full_assign(roles, items):
    """Assignment lengkap untuk 2*kmax variabel X (dipad EMPTY)."""
    roles = list(roles) + [EMPTY] * (CFG.kmax - len(roles))
    items = list(items) + [EMPTY] * (CFG.kmax - len(items))
    assign = {}
    for i, r in enumerate(roles, 1):
        assign[f"ROLE_{i}"] = r
    for i, it in enumerate(items, 1):
        assign[f"ITEM_{i}"] = it
    return assign


def test_variables_domains():
    assert variable_names(CFG) == (
        [f"ROLE_{i}" for i in range(1, CFG.kmax + 1)]
        + [f"ITEM_{i}" for i in range(1, CFG.kmax + 1)]
    )
    doms = build_domains(wins=0, cfg=CFG)
    assert "Boss" in doms["ROLE_1"]           # domain slot lead memuat Boss
    assert "Boss" not in doms["ROLE_2"]       # domain tiap slot boleh berbeda
    assert "Boss" not in doms["ROLE_3"]
    assert EMPTY in doms["ITEM_1"]


def test_valid_squad_consistent():
    assign = full_assign(
        ["Warrior", "Archer", EMPTY],
        ["Iron Sword", "Swift Boots", EMPTY],
    )
    assert is_consistent(assign, wins=0, budget=CFG.budget_for(0.5), cfg=CFG)
    assert is_complete(assign, cfg=CFG)
    assert check(assign, wins=0, budget=99, cfg=CFG) == []


def test_two_healers_rejected():
    assign = full_assign(
        ["Healer", "Healer", EMPTY], [EMPTY, EMPTY, EMPTY]
    )
    assert not is_consistent(assign, wins=0, budget=99, cfg=CFG)
    assert any("Healer" in v for v in check(assign, 0, 99, CFG))


def test_forbidden_pair_rejected():
    assign = full_assign(["Healer", EMPTY, EMPTY], ["Iron Sword", EMPTY, EMPTY])
    assert not is_consistent(assign, wins=0, budget=99, cfg=CFG)


def test_boss_gated_by_wins():
    assign = full_assign(["Boss", EMPTY, EMPTY], [EMPTY, EMPTY, EMPTY])
    assert not is_consistent(assign, wins=0, budget=99, cfg=CFG)
    assert is_consistent(assign, wins=3, budget=99, cfg=CFG)


def test_budget_enforced():
    # Boss(7) + Fang(3) = 10 > budget target 0.5 (=7).
    assign = full_assign(["Boss", EMPTY, EMPTY], [FANG, EMPTY, EMPTY])
    assert partial_cost(assign) == 10
    assert not is_consistent(assign, wins=9, budget=CFG.budget_for(0.5), cfg=CFG)
    assert is_consistent(assign, wins=9, budget=10, cfg=CFG)


def test_legendary_unique():
    assign = full_assign(
        ["Warrior", "Archer", EMPTY], [FANG, FANG, EMPTY]
    )
    assert not is_consistent(assign, wins=0, budget=99, cfg=CFG)


def test_no_hole_in_middle():
    assign = full_assign(["Warrior", EMPTY, "Archer"], [EMPTY, EMPTY, EMPTY])
    assert not is_consistent(assign, wins=0, budget=99, cfg=CFG)


def test_partial_assignment_checkable():
    # Backtracking menilai partial assignment: baru 1 variabel, harus konsisten.
    assert is_consistent({"ROLE_1": "Warrior"}, wins=0, budget=9, cfg=CFG)
    assert not is_consistent({"ROLE_1": "Boss"}, wins=0, budget=99, cfg=CFG)


def test_neighbors_cover_constraints():
    nbs = neighbors_of("ROLE_1", CFG)
    assert "ROLE_2" in nbs and "ITEM_1" in nbs  # degree melihat healer + pair
    assert "ITEM_2" in neighbors_of("ITEM_1", CFG)  # legendary uniqueness


def test_buff_diminishing_returns():
    # AMANDEMEN-5: hp peran Warrior tetap 0 (Warrior 70 HP = base), jadi
    # bukti diminishing memakai atk: Warrior lead +2 penuh; slot 2 -> +1.
    one = squad_to_buff(squad(["Warrior"], [EMPTY]), CFG)
    assert one.atk == 2  # slot lead berkontribusi penuh
    # Anggota yang sama di slot 2 berkontribusi lebih kecil dari slot 1.
    late = squad_to_buff(
        SquadConfig(roles=(EMPTY, "Warrior", EMPTY),
                    items=(EMPTY, EMPTY, EMPTY)), CFG)
    assert 0 < late.atk < one.atk
    assert one.hp == 0 and late.hp == 0  # Warrior: tanpa bonus HP (base 70)


def test_heuristic_range_and_monotonic():
    ev = HeuristicEvaluator(CFG)
    weak = ev.evaluate(squad([EMPTY], [EMPTY]))
    mid = ev.evaluate(squad(["Warrior"], ["Iron Sword"]))
    strong = ev.evaluate(squad(["Boss", "Tank", "Mage"], [FANG, EMPTY, EMPTY]))
    # Skala affine hasil fit (bias ~0.47): yang dijamin = batas + monoton.
    assert 0.0 <= weak < mid < strong <= 1.0
    assert abs(difficulty_gap(0.8, 0.5) - 0.3) < 1e-9


def test_simulation_deterministic_bounded():
    ev = SimulationEvaluator(CFG, seed=7)
    s = squad(["Warrior", "Archer"], ["Iron Sword", EMPTY])
    first = ev.evaluate(s)
    second = ev.evaluate(s)  # dari cache, harus identik
    assert first == second
    assert 0.0 <= first <= 1.0


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
        except Exception as exc:  # noqa: BLE001 - test runner mandiri
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"{len(tests) - failed}/{len(tests)} lolos")
    raise SystemExit(1 if failed else 0)
