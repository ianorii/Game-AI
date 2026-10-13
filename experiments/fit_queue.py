"""experiments/fit_queue.py - Kalibrasi heuristik rantai (Fase 3, GERBANG).

Sampel antrean VALID dan BERAGAM (solver + acak + urutan diacak, k 2-4),
label = ChainSim N=8. Split train/test 70/30 (seed tetap), fit (random
search berseed, MSE train) -> lapor TEST: Pearson, Spearman, RMSE +
subset dekat target (sim 0.5±0.15) + noise label (seed ganda).
Bobot -> data/queue_weights.json {versi, tanggal, seed, metrik}.

Jalan: `python3 experiments/fit_queue.py [--n 150]` (~4 mnt, sekali saja).
"""
from __future__ import annotations

import datetime
import json
import math
import random
import sys
import time
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.ambush.chain_eval import (  # noqa: E402
    FALLBACK_WEIGHTS,
    ChainHeuristic,
    ChainSim,
)
from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.csp_solver import CSPSolver, squad_problem  # noqa: E402
from game.ambush.enemy_queue import (  # noqa: E402
    EnemyQueue,
    EnemySlot,
    is_queue_valid,
    queue_from_assign,
)
from game.ambush.player_loadout import PlayerLoadout  # noqa: E402
from game.ambush.types import ITEM_TABLE, ROLE_TABLE  # noqa: E402

CFG = AmbushConfig()
QFLAGS = dict(queue_rules=True, min_active=2)
PLAYER = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
FIT_SEED = 20260712
OUT = str(Path(ROOT) / "data" / "queue_weights.json")


def sample_queues(n: int, seed: int) -> list:
    """Antrean valid BERAGAM: solver 1/3, acak 1/3, acak-urut 1/3."""
    rng = random.Random(seed)
    roles = [r for r in ROLE_TABLE if r != "NONE"]
    items = list(ITEM_TABLE)
    out, seen = [], set()

    def add(q: EnemyQueue):
        if q.key() not in seen and is_queue_valid(
                q, 0, CFG.budget_q_for(0.5), CFG):
            seen.add(q.key())
            out.append(q)

    s = 0
    while len([q for q in out if q.k() >= 2]) < n // 3 and s < n * 20:
        sol, _ = CSPSolver(
            squad_problem(0, CFG.budget_q_for(0.5), CFG, **QFLAGS),
            seed=seed + s).solve()
        if sol is not None:
            add(queue_from_assign(sol, CFG))
        s += 1
    tries = 0
    while len(out) < 2 * n // 3 and tries < n * 50:
        tries += 1
        k = rng.randint(2, 4)
        slots = tuple(EnemySlot(rng.choice(roles), rng.choice(items))
                      for _ in range(k))
        add(EnemyQueue(slots=slots))
    base = [q for q in out]
    while len(out) < n and base:
        q = rng.choice(base)
        slots = list(q.slots)
        rng.shuffle(slots)
        add(EnemyQueue(slots=tuple(slots)))
        if len(out) >= n:
            break
        if len(slots) >= 2:
            i, j = rng.sample(range(len(slots)), 2)
            slots[i], slots[j] = slots[j], slots[i]
            add(EnemyQueue(slots=tuple(slots)))
    return out[:n]


def pearson(xs, ys) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    return cov / math.sqrt(vx * vy) if vx and vy else 0.0


def _rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    for pos, i in enumerate(order):
        ranks[i] = pos + 1
    return ranks


def spearman(xs, ys) -> float:
    return pearson(_rank(xs), _rank(ys))


def rmse(xs, ys) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(xs, ys)) / len(xs))


def fit(n: int):
    print(f"sampel {n} antrean (seed {FIT_SEED})...", flush=True)
    queues = sample_queues(n, FIT_SEED)
    ks = {}
    for q in queues:
        ks[q.k()] = ks.get(q.k(), 0) + 1
    print(f"  k: {ks}, unik: {len({q.key() for q in queues})}")
    from game.ambush.chain_eval import config_fingerprint
    lab_path = str(Path(ROOT) / "data" / "labels_cache.json")
    lab_key = f"{config_fingerprint(CFG)}:{FIT_SEED}:{n}:8"
    try:
        cached = json.load(open(lab_path, encoding="utf-8"))
    except (OSError, ValueError):
        cached = {}
    if lab_key in cached and len(cached[lab_key]) == len(queues):
        labels = cached[lab_key]
        print(f"  label dari cache ({lab_path})", flush=True)
    else:
        sim = ChainSim(CFG, PLAYER, seed=5, games=8)
        t0 = time.perf_counter()
        labels = [sim.evaluate(q) for q in queues]
        cached[lab_key] = labels
        json.dump(cached, open(lab_path, "w", encoding="utf-8"))
        print(f"  label sim N=8: {(time.perf_counter() - t0):.0f}s", flush=True)

    rng = random.Random(FIT_SEED)
    idx = list(range(len(queues)))
    rng.shuffle(idx)
    cut = int(0.7 * len(idx))
    train, test = idx[:cut], idx[cut:]

    def mse(weights, ids):
        # Objective FIT = standardized-MSE (= 2(1-Pearson)): distribusi label
        # miring (median 1.0) membuat MSE mentah memilih solusi konstan.
        # Pemilihan model tetap train-only; RMSE mentah dilaporkan apa adanya.
        import statistics as _S2
        ev = ChainHeuristic(CFG, PLAYER, weights)
        pred = [ev.evaluate(queues[i]) for i in ids]
        lab = [labels[i] for i in ids]
        mp, ml = sum(pred) / len(pred), sum(lab) / len(lab)
        sp = (sum((x - mp) ** 2 for x in pred) / len(pred)) ** 0.5 or 1.0
        sl = (sum((x - ml) ** 2 for x in lab) / len(lab)) ** 0.5 or 1.0
        return sum((((a - mp) / sp) - ((b - ml) / sl)) ** 2
                   for a, b in zip(pred, lab)) / len(ids)

    # Coordinate descent dari FALLBACK (ronde-3): base_dmg DIKUNCI 17.5
    # (konstanta game yang diketahui) dan koreksi linear w_k/w_heal/w_min
    # DIKUNCI 0 (ronde-2 membuktikan keduanya membajak model: atrisi
    # dikempiskan, Pearson 0.64->0.44). Hanya 9 parameter taktis difit.
    # Random search luas + TOLAK solusi degenerate (ronde-4): MSE mentah
    # pada label miring memilih prediksi ~konstan (std->0, korelasi ambruk).
    # base_dmg dikunci; w_k/w_heal/w_min dikunci 0 (terbukti membajak).
    import statistics as _S3
    best = dict(FALLBACK_WEIGHTS)
    best["base_dmg"] = 17.5
    best["w_k"] = best["w_heal"] = best["w_min"] = 0.0
    best_mse = mse(best, train)
    keys = ["v_atk", "w_atk", "w_spec", "spec_freq", "w_chip", "v0",
            "slope", "w_pot_p", "w_pot_e"]
    bounds = {"v_atk": (0.2, 3.0), "w_atk": (0.2, 3.0), "w_spec": (0.1, 2.0),
              "spec_freq": (0.05, 1.0), "w_chip": (0.2, 4.0),
              "v0": (0.0, 8.0), "slope": (0.05, 1.0),
              "w_pot_p": (0.0, 1.5), "w_pot_e": (0.0, 1.5),
              "w_def": (0.0, 0.6), "w_weaken": (0.0, 1.5)}
    keys = [k for k in keys if k in bounds]
    for _ in range(5000):
        cand = {k: (rng.uniform(*bounds[k]) if k in bounds else best[k])
                for k in best}
        ev0 = ChainHeuristic(CFG, PLAYER, cand)
        spread = _S3.pstdev([ev0.evaluate(queues[i]) for i in train])
        if spread < 0.08:
            continue  # degenerate: korelasi pasti ambruk
        m = mse(cand, train)
        if m < best_mse:
            best_mse, best = m, cand
    import statistics as _S
    std_all = _S.pstdev(labels)
    print(f"  label: min={min(labels):.3f} max={max(labels):.3f} "
          f"std={std_all:.3f}", flush=True)
    if std_all < 0.1:
        print("  BERHENTI: std label < 0.1 (tak ada yang bisa difit)",
              flush=True)
        raise SystemExit(2)
    ev = ChainHeuristic(CFG, PLAYER, best)
    pred_test = [ev.evaluate(queues[i]) for i in test]
    lab_test = [labels[i] for i in test]
    metrics = {
        "pearson_test": round(pearson(pred_test, lab_test), 4),
        "spearman_test": round(spearman(pred_test, lab_test), 4),
        "rmse_test": round(rmse(pred_test, lab_test), 4),
        "n_train": len(train), "n_test": len(test),
    }
    sat = sum(1 for x in lab_test if x >= 0.9) / len(lab_test) * 100
    print(f"  SATURASI test: {sat:.1f}% label >= 0.9", flush=True)
    metrics["saturated_pct"] = round(sat, 1)
    ns = [(p, lab) for p, lab in zip(pred_test, lab_test) if lab < 0.9]
    if len(ns) > 5:
        metrics["pearson_nonsat"] = round(pearson(*zip(*ns)), 4)
        metrics["spearman_nonsat"] = round(spearman(*zip(*ns)), 4)
        metrics["rmse_nonsat"] = round(rmse(*zip(*ns)), 4)
    else:
        metrics["pearson_nonsat"] = metrics["spearman_nonsat"] = None
        metrics["rmse_nonsat"] = None
    metrics["n_nonsat"] = len(ns)
    for tname, tval in (("03", 0.3), ("04", 0.40), ("05", 0.5),
                        ("08", 0.8)):
        near = [(p, lab) for p, lab in zip(pred_test, lab_test)
                if abs(lab - tval) <= 0.15]
        if len(near) > 5:
            metrics[f"pearson_near_{tname}"] = round(pearson(*zip(*near)), 4)
            metrics[f"spearman_near_{tname}"] = round(spearman(*zip(*near)), 4)
            metrics[f"rmse_near_{tname}"] = round(rmse(*zip(*near)), 4)
        else:
            metrics[f"pearson_near_{tname}"] = None
            metrics[f"spearman_near_{tname}"] = None
            metrics[f"rmse_near_{tname}"] = None
        metrics[f"n_near_{tname}"] = len(near)
    # Sebaran fitur latih (bukti "valid dan beragam termasuk Minion").
    from collections import Counter as _C
    rc = _C()
    nmin = 0
    for i in train:
        for s in queues[i].slots:
            rc[s.role] += 1
            nmin += s.role == "Minion"
    print(f"  fitur train: {dict(rc)} minion={nmin}", flush=True)
    # Noise label: 20 antrean × 3 seed sim.
    noise = []
    for q in queues[:20]:
        vals = [ChainSim(CFG, PLAYER, seed=sd, games=8).evaluate(q)
                for sd in (5, 6, 7)]
        noise.append(max(vals) - min(vals))
    metrics["label_noise_maxmin"] = round(sum(noise) / len(noise), 4)
    print("  TEST:", {k: v for k, v in metrics.items()})
    import sys as _sys
    cfg = AmbushConfig()
    calibrated = (metrics["pearson_test"] >= cfg.corr_pearson_min
                  and metrics["spearman_test"] >= cfg.corr_spearman_min
                  and metrics["rmse_test"] <= cfg.rmse_max)
    from game.ambush.chain_eval import config_fingerprint
    doc = {"version": 1, "date": datetime.date.today().isoformat(),
           "fit_seed": FIT_SEED, "player": list(PLAYER.items),
           "weights": best, "metrics": metrics, "calibrated": calibrated,
           "config_hash": config_fingerprint(AmbushConfig())}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    print(f"  tersimpan: {OUT}")
    return doc


if __name__ == "__main__":
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 150
    fit(n)
