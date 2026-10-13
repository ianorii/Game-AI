"""experiments/fidelity.py - Fidelitas sim ringan vs sim penuh (Fase 4.1).

300 antrean x 3 loadout, seed tetap. Light = greedy 1-ply (N=8),
full = AI depth produksi (N=8). Metrik di TEST (split untuk pemetaan):
Pearson/Spearman/RMSE (mentah + peta monoton linear), pairwise accuracy,
top-1/top-3 agreement, bias per peran, saturasi, waktu.
Hasil MELAPORKAN (ambang 0.85/0.80 tetap tertulis + selisihnya), status
"calibrated: partial". TIDAK memblokir Fase 4.

Jalan: `python3 experiments/fidelity.py` (~12 mnt).
"""
from __future__ import annotations

import datetime
import itertools
import json
import math
import random
import statistics as S
import sys
import time
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.ambush.chain_eval import (  # noqa: E402
    ChainLightSim,
    ChainSim,
    config_fingerprint,
)
from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.player_loadout import PlayerLoadout  # noqa: E402

sys.path.insert(0, str(Path(ROOT) / "experiments"))
from fit_queue import pearson, rmse, sample_queues, spearman  # noqa: E402

CFG = AmbushConfig()
SEED = 20260712
OUT = str(Path(ROOT) / "data" / "fidelity.json")
LOADOUTS = {
    "lemah": PlayerLoadout(items=("NONE", "NONE")),
    "sedang": PlayerLoadout(items=("Iron Sword", "Heavy Shield")),
    "kuat": PlayerLoadout(items=("Dragon Fang", "Heavy Shield")),
}


def pairwise_accuracy(xs, ys) -> float:
    """Fraksi pasangan yang urutannya disepakati (tie diabaikan)."""
    agree = total = 0
    for i, j in itertools.combinations(range(len(xs)), 2):
        dx, dy = xs[i] - xs[j], ys[i] - ys[j]
        if abs(dx) < 1e-9 or abs(dy) < 1e-9:
            continue
        total += 1
        agree += (dx < 0) == (dy < 0)
    return agree / total if total else 1.0


def topk_agreement(xs, ys, k: int):
    """Kecocokan argmin (k=1) / overlap (k=3) atas peringkat."""
    rx = sorted(range(len(xs)), key=lambda i: xs[i])[:k]
    ry = sorted(range(len(ys)), key=lambda i: ys[i])[:k]
    if k == 1:
        return float(rx[0] == ry[0])
    return len(set(rx) & set(ry)) / k


def main():
    queues = sample_queues(300, seed=SEED)
    t0 = time.perf_counter()
    light_all = {}
    for name, pl in LOADOUTS.items():
        ev = ChainLightSim(CFG, pl, seed=5, games=8)
        light_all[name] = [ev.evaluate(q) for q in queues]
    t_light = time.perf_counter() - t0
    t0 = time.perf_counter()
    full_all = {}
    for name, pl in LOADOUTS.items():
        ev = ChainSim(CFG, pl, seed=5, games=8)
        full_all[name] = [ev.evaluate(q) for q in queues]
    t_full = time.perf_counter() - t0
    print(f"waktu: ringan {t_light:.0f}s penuh {t_full:.0f}s", flush=True)

    report = {"date": datetime.date.today().isoformat(), "seed": SEED,
              "n": len(queues), "thresholds": {"pearson": 0.85,
                                              "spearman": 0.80},
              "config_hash": config_fingerprint(CFG), "by_loadout": {}}
    for name in LOADOUTS:
        xs, ys = light_all[name], full_all[name]
        rng = random.Random(SEED)
        idx = list(range(len(queues)))
        rng.shuffle(idx)
        tr, te = idx[:210], idx[210:]
        xtr = [xs[i] for i in tr]
        ytr = [ys[i] for i in tr]
        # Peta monoton linear (a.x+b) difit di train.
        mx, my = sum(xtr) / len(xtr), sum(ytr) / len(ytr)
        vx = sum((x - mx) ** 2 for x in xtr) or 1.0
        a = sum((x - mx) * (y - my) for x, y in zip(xtr, ytr)) / vx
        a = max(0.0, a)  # monoton tak-turun
        b = my - a * mx
        xte = [xs[i] for i in te]
        yte = [ys[i] for i in te]
        mapped = [min(1.0, max(0.0, a * x + b)) for x in xte]
        sat = sum(1 for y in yte if y >= 0.9) / len(yte) * 100
        nonsat = [(m, y) for m, y in zip(mapped, yte) if y < 0.9]
        m = {"pearson": round(pearson(xte, yte), 4),
             "spearman": round(spearman(xte, yte), 4),
             "rmse": round(rmse(xte, yte), 4),
             "pearson_mapped": round(pearson(mapped, yte), 4),
             "rmse_mapped": round(rmse(mapped, yte), 4),
             "pairwise": round(pairwise_accuracy(xte, yte), 4),
             "top1": topk_agreement(xte, yte, 1),
             "top3": round(topk_agreement(xte, yte, 3), 4),
             "saturated_pct": round(sat, 1),
             "nonsat_pearson": round(pearson(*zip(*nonsat)), 4)
             if len(nonsat) > 5 else None,
             "map": {"a": round(a, 4), "b": round(b, 4)},
             "n_test": len(te)}
        # Bias per peran (selisih peta-sim rata-rata).
        roles = {}
        for p, y, i in zip(mapped, yte, te):
            for s in queues[i].slots:
                roles.setdefault(s.role, []).append(p - y)
        m["bias_per_role"] = {k: round(sum(v) / len(v), 3) for k, v in
                              sorted(roles.items())}
        report["by_loadout"][name] = m
        print(f"{name}: pearson={m['pearson']} spearman={m['spearman']} "
              f"rmse={m['rmse']} pair={m['pairwise']} top1={m['top1']} "
              f"top3={m['top3']} sat={m['saturated_pct']}% "
              f"bias={m['bias_per_role']}", flush=True)
    report["status"] = "calibrated: partial"
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print(f"tersimpan: {OUT}", flush=True)


if __name__ == "__main__":
    main()
