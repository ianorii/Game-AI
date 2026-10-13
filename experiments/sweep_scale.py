"""experiments/sweep_scale.py - Sapuan rest & skala stat (Fase 3-ulang).

Paralel (multiprocessing) karena ChainSim N=8 mahal. Hasil inkremental ke
JSON agar interupsi tak menghilangkan data. Hanya memakai kode tahap 3.

Jalan:
  python3 experiments/sweep_scale.py rest     # rest x sedang (re-run pasca-bug)
  python3 experiments/sweep_scale.py scale    # skala x 3 loadout
  python3 experiments/sweep_scale.py potion   # pembanding potion+1
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import statistics as S
import sys
from dataclasses import replace
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.ambush.chain_eval import ChainSim  # noqa: E402
from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.player_loadout import PlayerLoadout  # noqa: E402

sys.path.insert(0, str(Path(ROOT) / "experiments"))
from fit_queue import sample_queues  # noqa: E402

CFG = AmbushConfig()
OUT = "/tmp/sweep_results.json"
LOADOUTS = {
    "lemah": ("NONE", "NONE"),
    "sedang": ("Iron Sword", "Heavy Shield"),
    "kuat": ("Dragon Fang", "Heavy Shield"),
}
QUEUES = None


def _init(queues):
    global QUEUES
    QUEUES = queues


def _work(task):
    from game.ambush.types import ROLE_TABLE as _RT
    assert (_RT["Minion"].hp, _RT["Minion"].atk, _RT["Minion"].cost) == (-50, -9, 1), _RT["Minion"]
    qi, loadout_name, cfg_kw, games, seed = task
    cfg = replace(CFG, **cfg_kw)
    pl = PlayerLoadout(items=LOADOUTS[loadout_name])
    return ChainSim(cfg, pl, seed=seed, games=games).evaluate(QUEUES[qi])


def _summarize(vals):
    cov = {t: sum(1 for v in vals if abs(v - t) <= 0.15) / len(vals) * 100
           for t in (0.3, 0.5, 0.8)}
    ge08 = sum(1 for v in vals if v >= 0.8) / len(vals) * 100
    return {"min": round(min(vals), 3), "med": round(S.median(vals), 3),
            "max": round(max(vals), 3),
            "near03": round(cov[0.3], 1), "near05": round(cov[0.5], 1),
            "near08": round(cov[0.8], 1), "ge08": round(ge08, 1)}


def _save(results):
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)


def _load():
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    return {}


def run(tasks, tag):
    results = _load()
    queues = sample_queues(300, seed=31337)
    with mp.Pool(4, initializer=_init, initargs=(queues,)) as pool:
        for name, loadout, cfg_kw in tasks:
            key = f"{tag}/{name}/{loadout}"
            if key in results:
                print(f"lewati (ada): {key}", flush=True)
                continue
            jobs = [(i, loadout, cfg_kw, 8, 5) for i in range(len(queues))]
            vals = pool.map(_work, jobs, chunksize=4)
            results[key] = _summarize(vals)
            _save(results)
            r = results[key]
            print(f"{key}: min={r['min']} med={r['med']} max={r['max']} "
                  f"near={r['near03']}/{r['near05']}/{r['near08']} "
                  f"ge08={r['ge08']}", flush=True)
    return results


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "rest"
    if which == "rest":
        run([(f"rest={r}", "sedang", {"rest_heal_pct": r})
             for r in (0.0, 0.1, 0.2, 0.3)], "rest")
    elif which == "scale":
        tasks = [(f"scale={s}", lo, {"enemy_stat_scale": s})
                 for s in (1.0, 0.9, 0.8, 0.7, 0.6) for lo in LOADOUTS]
        run(tasks, "scale")
    elif which == "range":
        tasks = [(f"range/{lo}", lo, {"enemy_stat_scale": 1.0})
                 for lo in LOADOUTS]
        run(tasks, "range")
    elif which == "potion":
        run([(f"pot+{b}/{lo}", lo, {"potion_bonus_per_duel": b})
             for b in (1, 2) for lo in LOADOUTS], "potion")
