"""experiments/fit_heuristic.py - Fit bobot HeuristicEvaluator ke data sim.

Difit: affine w·[hp,atk,spec,regen,armor,chip,weaken] + bias ≈ sim margin.
Output: blok config siap tempel + metrik (korelasi, MAE). Least squares
manual (tanpa numpy) lewat eliminasi Gauss 8x8.

    python3 experiments/fit_heuristic.py --quick   # 60 squad, cepat
    python3 experiments/fit_heuristic.py           # 150 squad
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import List, Tuple

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.ambush.buff import squad_to_buff  # noqa: E402
from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.difficulty import SimulationEvaluator  # noqa: E402
from game.ambush.types import EMPTY, ITEM_TABLE, ROLE_TABLE, SquadConfig  # noqa: E402

CFG = AmbushConfig()
SEED = 20260712
FEATURES = ["hp", "atk", "spec", "regen", "armor", "chip", "weaken"]


def random_squad(rng: random.Random) -> SquadConfig:
    """Squad canonical acak (boleh Boss; wins tak relevan untuk difficulty)."""
    size = rng.randint(0, CFG.kmax)
    roles, items = [], []
    for i in range(1, CFG.kmax + 1):
        if i <= size:
            opts = [r for r in ROLE_TABLE if r != EMPTY]
            roles.append(rng.choice(opts))
            items.append(rng.choice(list(ITEM_TABLE)))
        else:
            roles.append(EMPTY)
            items.append(EMPTY)
    return SquadConfig(roles=tuple(roles), items=tuple(items))


def solve_linear(system: List[List[float]]) -> List[float]:
    """Eliminasi Gauss dengan pivot parsial (sistem n x (n+1))."""
    n = len(system)
    a = [row[:] for row in system]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(a[r][col]))
        a[col], a[piv] = a[piv], a[col]
        assert abs(a[col][col]) > 1e-12, "matriks singular"
        for r in range(col + 1, n):
            factor = a[r][col] / a[col][col]
            for c in range(col, n + 1):
                a[r][c] -= factor * a[col][c]
    out = [0.0] * n
    for i in range(n - 1, -1, -1):
        out[i] = (a[i][n] - sum(a[i][j] * out[j] for j in range(i + 1, n))) \
            / a[i][i]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--games", type=int, default=6)
    args = ap.parse_args(argv)

    n = args.n or (60 if args.quick else 150)
    rng = random.Random(SEED)
    squads = [random_squad(rng) for _ in range(n)]
    sim_cfg = replace(CFG, sim_games=args.games)
    sim = SimulationEvaluator(sim_cfg, seed=SEED)

    t0 = time.perf_counter()
    rows = []
    for i, sq in enumerate(squads):
        buff = squad_to_buff(sq, CFG)
        feats = [float(getattr(buff, f)) for f in FEATURES]
        rows.append((feats, sim.evaluate(sq)))
        if (i + 1) % 30 == 0:
            print(f"  sim {i + 1}/{n}...", flush=True)
    print(f"sim {n}x{args.games} duel: {time.perf_counter() - t0:.0f}s")

    # Normal equations (X'X)w = X'y dengan kolom bias.
    dim = len(FEATURES) + 1
    mat = [[0.0] * (dim + 1) for _ in range(dim)]
    for feats, y in rows:
        x = feats + [1.0]
        for i in range(dim):
            for j in range(dim):
                mat[i][j] += x[i] * x[j]
            mat[i][dim] += x[i] * y
    weights = solve_linear(mat)

    names = [f"w_{f}" for f in FEATURES] + ["w_bias"]
    preds = [sum(w * v for w, v in zip(weights, f + [1.0])) for f, _ in rows]
    targets = [y for _, y in rows]
    mean = sum(targets) / len(targets)
    cov = sum((p - sum(preds) / len(preds)) * (t - mean)
              for p, t in zip(preds, targets))
    var_p = sum((p - sum(preds) / len(preds)) ** 2 for p in preds)
    var_t = sum((t - mean) ** 2 for t in targets)
    corr = cov / (var_p * var_t) ** 0.5 if var_p and var_t else 0.0
    mae = sum(abs(p - t) for p, t in zip(preds, targets)) / len(targets)
    lo, hi = min(preds), max(preds)

    print(f"\nkorelasi={corr:.3f} MAE={mae:.3f} rentang_prediksi=[{lo:.3f}, "
          f"{hi:.3f}]")
    print("\n# Tempel ke AmbushConfig:")
    for name, w in zip(names, weights):
        print(f"    {name}: float = {w:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
