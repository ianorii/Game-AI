"""game/ambush/compare_panel.py - Panel perbandingan (Fase 6).

Dihitung BERTAHAP (satu unit per frame setelah REVIEW) agar game tidak
membeku; di luar anggaran 3 detik jalur gameplay. Setelan demo-compare
kecil (terdokumentasi di tiap baris); default gameplay tak berubah.
"""
from __future__ import annotations

import time
from typing import List

from game.ambush.chain_eval import ChainLightSim
from game.ambush.csp_solver import CSPSolver, squad_problem
from game.ambush.queue_search import (
    drain,
    genetic_q,
    hill_climb_q,
    random_restart_q,
    simulated_annealing_q,
)


def build_units(ctx: dict):
    """Daftar 11 unit (nama, kind, thunk). Thunk mengembalikan (row, ms)."""
    from game.ambush.enemy_queue import EnemyQueue
    units = []
    cfg, wins = ctx["cfg"], ctx["wins"]
    budget, target = ctx["budget"], ctx["target"]
    player, seeds, start = ctx["player"], ctx["seeds"], ctx["start"]
    if not isinstance(start, EnemyQueue):
        # Mode BUFF: LS antrean tak berlaku; ablasi CSP saja + catatan.
        units.append(("LS", "ls", lambda: ({"gap": "-", "evals": "-",
                                            "ms": 0.0,
                                            "note": "mode BUFF"}, 0.0)))
    else:
        def light():
            return ChainLightSim(cfg, player, seed=777, games=2)

        def ls_row(name, fn):
            t0 = time.perf_counter()
            res, _ = drain(fn())
            ms = (time.perf_counter() - t0) * 1000.0
            return {"gap": round(res.best_gap, 4), "evals": res.evals,
                    "ms": round(ms, 1)}, ms

        units.append(("HC", "ls", lambda: ls_row(
            "HC", lambda: hill_climb_q(start, light(), target, wins, budget,
                                       cfg, max_iters=4))))
        units.append(("HC+side", "ls", lambda: ls_row(
            "HC+side", lambda: hill_climb_q(start, light(), target, wins,
                                            budget, cfg, max_iters=4,
                                            sideways_limit=4))))
        units.append(("restart", "ls", lambda: ls_row(
            "restart", lambda: random_restart_q(
                lambda r: seeds[r % len(seeds)], light(), target, wins,
                budget, cfg, n_restarts=2, max_iters=4))))
        units.append(("SA", "ls", lambda: ls_row(
            "SA", lambda: simulated_annealing_q(
                start, light(), target, wins, budget, cfg, max_iters=25,
                seed=7))))
        units.append(("GA", "ls", lambda: ls_row(
            "GA", lambda: genetic_q(seeds, light(), target, wins, budget,
                                    cfg, pop_size=8, generations=3,
                                    seed=7))))
    ablations = [
        ("polos", dict(use_mrv=False, use_degree=False, use_lcv=False,
                       inference="none")),
        ("+MRV", dict(use_mrv=True, use_degree=False, use_lcv=False,
                      inference="none")),
        ("+MRV/deg", dict(use_mrv=True, use_degree=True, use_lcv=False,
                           inference="none")),
        ("+LCV", dict(use_mrv=True, use_degree=True, use_lcv=True,
                      inference="none")),
        ("+AC-3", dict(use_mrv=True, use_degree=True, use_lcv=True,
                       inference="ac3")),
        ("+FC", dict(use_mrv=True, use_degree=True, use_lcv=True,
                     inference="fc")),
    ]

    def csp_row(name, kw):
        t0 = time.perf_counter()
        sol, st = CSPSolver(ctx["problem"](), seed=11, **kw).solve()
        ms = (time.perf_counter() - t0) * 1000.0
        return {"gap": st["nodes"], "evals": st["backtracks"],
                "ms": round(ms, 1)}, ms

    for name, kw in ablations:
        units.append((name, "csp", lambda kw=kw, name=name: csp_row(
            name, kw)))
    return units
def init_compare(state) -> dict:
    """Bangun status perbandingan dari hasil director (None bila tak bisa)."""
    d = state.get("director")
    if d is None:
        return {"done": True, "note": "tanpa director"}
    director = d["director"]
    result = getattr(director, "last_queue_result", None)
    if result is None:
        result = director.last_result
    if result is None:
        return {"done": True, "note": "tanpa hasil"}
    cfg = state["ambush_cfg"]
    seeds = list(getattr(director, "last_queue_seeds", [])
                 or getattr(director, "last_seeds", []))
    start = getattr(director, "last_queue_start", None) or (
        seeds[0] if seeds else None)
    if not seeds or start is None:
        return {"done": True, "note": "tanpa seed"}
    budget = getattr(result, "budget", cfg.budget_q_for(result.target))
    ctx = {"cfg": cfg, "wins": state.get("wins", 0), "budget": budget,
           "target": result.target, "player": state.get("player_loadout"),
           "seeds": seeds, "start": start,
           "problem": lambda: squad_problem(state.get("wins", 0), budget,
                                            cfg, **cfg.csp_flags())}
    return {"units": build_units(ctx), "idx": 0,
            "total": 10, "results": {}, "done": False, "max_ms": 0.0}


def pump_compare(state) -> dict:
    """Jalankan SATU unit; kembalikan status (untuk overlay + tes)."""
    cmp_ = state.get("compare")
    if cmp_ is None or cmp_.get("done"):
        return cmp_ or {"done": True}
    units = cmp_["units"]
    if cmp_["idx"] >= len(units):
        cmp_["done"] = True
        return cmp_
    name, _kind, thunk = units[cmp_["idx"]]
    row, ms = thunk()
    cmp_["results"][name] = row
    cmp_["idx"] += 1
    cmp_["max_ms"] = max(cmp_["max_ms"], ms)
    if cmp_["idx"] >= len(units):
        cmp_["done"] = True
    return cmp_
