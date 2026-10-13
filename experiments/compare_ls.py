"""experiments/compare_ls.py - Perbandingan algoritma LS yang bermakna (Fase 5).

Satu seed identik tidak membedakan (semua gap 0.000) -> ukur agregat:
20 seed x 3 target (0.40/0.50/0.80) x 3 loadout x seed BEST/RANDOM.
Per algoritma: mean+p90 gap akhir, mean evaluasi, mean ms, % dalam
toleransi. Kolom SA accepted_bad: bukti anil benar mencoba langkah buruk.
Setelan demo/cepat (games=2, GA 8x5, SA cap 200) HANYA di sini; default
gameplay tak berubah (dilaporkan).

Jalan: `python3 experiments/compare_ls.py` (~10 mnt).
"""
from __future__ import annotations

import statistics as S
import sys
import time
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.ambush.chain_eval import ChainLightSim  # noqa: E402
from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.csp_solver import CSPSolver, squad_problem  # noqa: E402
from game.ambush.director import AmbushDirector  # noqa: E402
from game.ambush.difficulty import difficulty_gap  # noqa: E402
from game.ambush.enemy_queue import queue_from_assign  # noqa: E402
from game.ambush.governor import DifficultyGovernor  # noqa: E402
from game.ambush.player_loadout import PlayerLoadout  # noqa: E402
from game.ambush.queue_search import (  # noqa: E402
    drain,
    genetic_q,
    hill_climb_q,
    random_restart_q,
    simulated_annealing_q,
)

CFG = AmbushConfig()
LOADOUTS = {
    "lemah": PlayerLoadout(items=("NONE", "NONE")),
    "sedang": PlayerLoadout(items=("Iron Sword", "Heavy Shield")),
    "kuat": PlayerLoadout(items=("Dragon Fang", "Heavy Shield")),
}
TARGETS = (0.40, 0.50, 0.80)


def seeds_for(base_seed: int, n: int = 3):
    """Seed CSP beragam (value-shuffle + dedup, tanpa ubah mesin)."""
    director = AmbushDirector(CFG, DifficultyGovernor(CFG),
                              base_seed=base_seed)
    return director._queue_seeds(0, CFG.budget_q_for(0.5))[:n] or []


def run_algo(algo: str, start, seeds, light, target: float):
    """Satu run + metrik (+ accepted_bad untuk SA)."""
    t0 = time.perf_counter()
    kw = dict(tracer=None)
    if algo == "hc_plain":
        res, _ = drain(hill_climb_q(start, light, target, 0,
                                    CFG.budget_q_for(target), CFG,
                                    sideways_limit=0, **kw))
    elif algo == "hc":
        res, _ = drain(hill_climb_q(start, light, target, 0,
                                    CFG.budget_q_for(target), CFG, **kw))
    elif algo == "restart":
        res, _ = drain(random_restart_q(
            lambda r: seeds[r % len(seeds)], light, target, 0,
            CFG.budget_q_for(target), CFG, **kw))
    elif algo == "sa":
        res, _ = drain(simulated_annealing_q(
            start, light, target, 0, CFG.budget_q_for(target), CFG,
            max_iters=200, seed=7, **kw))
    else:
        res, _ = drain(genetic_q(seeds, light, target, 0,
                                 CFG.budget_q_for(target), CFG, pop_size=8,
                                 generations=5, seed=7, **kw))
    ms = (time.perf_counter() - t0) * 1000.0
    bad = res.extra.get("accepted_bad", 0) if algo == "sa" else 0
    return res.best_gap, res.evals, ms, bad, res.stop


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def _one_seed(seed: int):
    """Seluruh sel satu seed (untuk paralel Pool)."""
    out = []
    for target in TARGETS:
        for loname, lo in LOADOUTS.items():
            light = ChainLightSim(CFG, lo, seed=1000 + seed, games=2)
            seeds = seeds_for(seed)
            if not seeds:
                continue
            gaps0 = [(difficulty_gap(light.evaluate(s), target), s)
                     for s in seeds]
            starts = {"BEST": min(gaps0, key=lambda t: t[0])[1],
                      "RANDOM": seeds[0]}
            for mode, start in starts.items():
                for algo in ("hc_plain", "hc", "restart", "sa", "ga"):
                    g, e, ms, bad, _stop = run_algo(
                        algo, start, seeds, light, target)
                    out.append((mode, algo, g, e, ms, bad,
                                g <= CFG.target_tol))
    return out


def main():
    import multiprocessing as mp
    print("perhatian: setelan cepat (games=2, GA 8x5, SA cap 200); "
          "default gameplay tak berubah", flush=True)
    rows = []
    with mp.Pool(4) as pool:
        for batch in pool.imap_unordered(_one_seed, range(20), chunksize=1):
            rows.extend(batch)
    for mode in ("BEST", "RANDOM"):
        print(f"=== seed {mode} ===", flush=True)
        for algo in ("hc_plain", "hc", "restart", "sa", "ga"):
            sel = [r for r in rows if r[0] == mode and r[1] == algo]
            gaps = [r[2] for r in sel]
            evals = [r[3] for r in sel]
            mss = [r[4] for r in sel]
            bads = [r[5] for r in sel]
            hits = sum(r[6] for r in sel)
            n = len(gaps)
            print(f"{algo:10s} gap {S.mean(gaps):.3f}/p90 {pct(gaps, .9):.3f} "
                  f"eval {S.mean(evals):.0f} ms {S.mean(mss):.0f} "
                  f"tol {hits / n * 100:.0f}% bad {S.mean(bads):.1f}",
                  flush=True)


if __name__ == "__main__":
    main()
