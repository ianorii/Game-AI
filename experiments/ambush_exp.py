"""experiments/ambush_exp.py - Eksperimen Tahap 3 (reproducible, seed tetap).

CS1: backtracking polos vs +MRV vs +MRV/degree vs +LCV vs +AC-3 vs FC
     (nodes & backtrack) pada instans ketat agar heuristik terlihat.
LS1: hill climbing vs +sideways vs random restart vs SA vs GA
     (jarak ke target, evaluasi, waktu).
CAL: kapan CSP saja cukup vs local search diperlukan (seed gap vs akhir).

Cara pakai (dari root proyek):
    python3 experiments/ambush_exp.py --quick
    python3 experiments/ambush_exp.py --only CS1 --out /tmp/ambush.md
    python3 experiments/ambush_exp.py --csv-dir data
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.csp_solver import CSPSolver, squad_problem  # noqa: E402
from game.ambush.csv_export import (  # noqa: E402
    write_csp_csv,
    write_ls_csv,
    write_summary_csv,
)
from game.ambush.difficulty import HeuristicEvaluator  # noqa: E402
from game.ambush.director import AmbushDirector  # noqa: E402
from game.ambush.governor import DifficultyGovernor  # noqa: E402
from game.ambush.trace import TraceBuffer  # noqa: E402

CFG = AmbushConfig()
SEED = 20260712  # seed tetap: hasil bisa direproduksi

CSP_CONFIGS = [
    ("polos", {"use_mrv": False, "use_degree": False, "use_lcv": False,
               "inference": "none"}),
    ("+mrv", {"use_mrv": True, "use_degree": False, "use_lcv": False,
              "inference": "none"}),
    ("+mrv/deg", {"use_mrv": True, "use_degree": True, "use_lcv": False,
                  "inference": "none"}),
    ("+lcv", {"use_mrv": True, "use_degree": True, "use_lcv": True,
              "inference": "none"}),
    ("+fc", {"use_mrv": True, "use_degree": True, "use_lcv": True,
             "inference": "fc"}),
    ("+ac3", {"use_mrv": True, "use_degree": True, "use_lcv": True,
              "inference": "ac3"}),
]


def _table(headers: List[str], rows: List[list]) -> str:
    def fmt(v):
        return f"{v:.2f}" if isinstance(v, float) else str(v)
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in rows]
    return "\n".join(out)


def exp_cs1(instances, csv_dir: Optional[str]) -> str:
    """Perbandingan 6 konfigurasi CSP pada instans ketat."""
    rows = []
    for wins, target in instances:
        budget = CFG.budget_for(target)
        problem = squad_problem(wins, budget, CFG)
        for name, kw in CSP_CONFIGS:
            nodes = back = pruned = ms = 0.0
            n = 3
            for s in range(n):
                tr = TraceBuffer()
                _, stats = CSPSolver(
                    problem, seed=SEED + s, tracer=tr,
                    time_limit=CFG.csp_time_limit,
                    max_nodes=CFG.csp_max_nodes, **kw).solve()
                nodes += stats["nodes"]
                back += stats["backtracks"]
                pruned += stats["pruned"]
                ms += stats["time_ms"]
            if csv_dir and name == "+ac3" and (wins, target) == instances[0]:
                write_csp_csv(tr, f"{csv_dir}/csp_trace.csv")
            rows.append([f"w{wins}/t{target}", name, round(nodes / n, 1),
                         round(back / n, 1), round(pruned / n, 1),
                         round(ms / n, 2)])
    return _table(["instans", "konfig", "nodes", "backtrack", "pruned",
                   "ms"], rows)


def exp_ls1(instances, csv_dir: Optional[str]) -> str:
    """Perbandingan 5 konfigurasi LS (gap akhir, evaluasi, waktu)."""
    algos = [
        ("hc", "hill_climbing", {"sideways_limit": 0}),
        ("hc+side", "hill_climbing", {}),
        ("restart", "random_restart", {}),
        ("sa", "simulated_annealing", {}),
        ("ga", "genetic", {}),
    ]
    rows = []
    run_id = 0
    for wins, target in instances:
        for name, algo, extra in algos:
            tr = TraceBuffer()
            director = _run_ls_with(algo, extra, wins, target, SEED, tr)
            t0 = time.perf_counter()
            result = director.plan(wins, target)
            wall = (time.perf_counter() - t0) * 1000.0
            rows.append([f"w{wins}/t{target}", name,
                         round(result.gap, 4), result.ls_evals,
                         round(wall, 1), result.ls_stop])
            if csv_dir and (wins, target) == instances[0] and name == "sa":
                write_ls_csv(tr, f"{csv_dir}/ls_trace.csv",
                             run_id=run_id, algo=algo)
            run_id += 1
    return _table(["instans", "algo", "gap_akhir", "evaluasi", "ms",
                   "berhenti"], rows)


def _run_ls_with(algo: str, extra: dict, wins: int, target: float,
                 seed: int, tracer: TraceBuffer):
    """Jalankan director dengan override kecil khusus eksperimen.

    hc tanpa sideways = config copy dengan hc_sideways=0 (hill_climb sudah
    membaca batas itu dari config), jadi tidak ada logika duplikat.
    """
    from dataclasses import replace
    cfg = replace(CFG, hc_sideways=extra.get("sideways_limit",
                                             CFG.hc_sideways))
    return AmbushDirector(cfg, DifficultyGovernor(cfg), tracer=tracer,
                          ls_algo=algo, base_seed=seed,
                          csp_options=CSP_CONFIGS[-1][1])


def exp_cal(instances) -> str:
    """CSP saja vs +LS: kolom peningkatan gap (seed_gap -> gap akhir)."""
    rows = []
    for wins, target in instances:
        tr = TraceBuffer()
        director = AmbushDirector(
            CFG, DifficultyGovernor(CFG), tracer=tr, base_seed=SEED,
            csp_options=CSP_CONFIGS[-1][1])
        result = director.plan(wins, target)
        better = result.seed_gap - result.gap
        verdict = ("LS perlu" if better > 0.01 else "CSP cukup")
        rows.append([f"w{wins}/t{target}", round(result.seed_gap, 4),
                     round(result.gap, 4), round(better, 4), verdict])
    return (_table(["instans", "seed_gap", "gap_akhir", "peningkatan",
                    "kesimpulan"], rows)
            + "\n\nAturan baca: peningkatan > 0.01 berarti local search "
              "berkontribusi nyata; bila tidak, seed CSP sudah pas target.")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Eksperimen Tahap 3")
    ap.add_argument("--only", nargs="*", default=None,
                    help="CS1 LS1 CAL")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=None, help="file markdown output")
    ap.add_argument("--csv-dir", default=None, help="direktori CSV output")
    args = ap.parse_args(argv)

    instances = ([(0, 0.3), (0, 0.5)] if args.quick
                 else [(0, 0.2), (0, 0.3), (0, 0.5), (0, 0.7), (3, 0.8)])
    chosen = [c.upper() for c in (args.only or ["CS1", "LS1", "CAL"])]
    chunks = ["# Eksperimen Ambush Director (Tahap 3)", "",
              f"seed={SEED}, instans={instances}", ""]
    if "CS1" in chosen:
        t0 = time.perf_counter()
        chunks += ["## CS1. Backtracking vs heuristik vs inferensi", "",
                   exp_cs1(instances, args.csv_dir), ""]
        print(f"[CS1] {time.perf_counter() - t0:.1f}s")
    if "LS1" in chosen:
        t0 = time.perf_counter()
        chunks += ["## LS1. Perbandingan local search", "",
                   exp_ls1(instances, args.csv_dir), ""]
        print(f"[LS1] {time.perf_counter() - t0:.1f}s")
    if "CAL" in chosen:
        t0 = time.perf_counter()
        chunks += ["## CAL. Kapan CSP cukup vs LS diperlukan", "",
                   exp_cal(instances), ""]
        print(f"[CAL] {time.perf_counter() - t0:.1f}s")
    report = "\n".join(chunks)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(f"-> {args.out}")
    else:
        print()
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
