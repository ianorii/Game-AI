"""experiments/minion_gate.py - Gerbang jangkauan kandidat Minion (Fase 3-ulang).

Tiap kandidat dipatch ke ROLE_TABLE dalam-proses (sementara), lalu 300
antrean x loadout sedang N=8 paralel. Finalis diukur 3 loadout.
Lapor p5/p50/p95 + near-target + ge08.

Jalan: `python3 experiments/minion_gate.py` (~20 mnt) atau
`python3 experiments/minion_gate.py --only M1` (~6 mnt).
"""
from __future__ import annotations

import multiprocessing as mp
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
from game.ambush.types import MINION, ROLE_TABLE, RoleSpec  # noqa: E402

sys.path.insert(0, str(Path(ROOT) / "experiments"))
from fit_queue import sample_queues  # noqa: E402

CFG = AmbushConfig()
CANDIDATES = {
    # Delta dari stat dasar duel (damage 15-20 rata2 17.5).
    # M1: pembanding (stat dasar). M2: HP -30 (ATK -7).
    # M3: HP -50 (ATK -9; roll min 15-9=6>0, tetap berbahaya).
    # Catatan: CANDIDATES ini disapu lewat override ROLE_TABLE["Minion"]
    # RELATIF terhadap ENEMY_BASE_HP yang berlaku (kini 70).
    "M1": RoleSpec(MINION, hp=0, atk=0, cost=1),
    "M2": RoleSpec(MINION, hp=-30, atk=-7, cost=1),
    "M3": RoleSpec(MINION, hp=-50, atk=-9, cost=1),
}
LOADOUTS = {
    "lemah": ("NONE", "NONE"),
    "sedang": ("Iron Sword", "Heavy Shield"),
    "kuat": ("Dragon Fang", "Heavy Shield"),
}
QUEUES = None


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def _init(queues):
    global QUEUES
    QUEUES = queues


def _work(task):
    qi, loadout_name, spec = task
    ROLE_TABLE[MINION] = spec
    cfg = CFG
    pl = PlayerLoadout(items=LOADOUTS[loadout_name])
    return ChainSim(cfg, pl, seed=5, games=8).evaluate(QUEUES[qi])


def measure(spec, loadouts, queues):
    with mp.Pool(4, initializer=_init, initargs=(queues,)) as pool:
        out = {}
        for lo in loadouts:
            jobs = [(i, lo, spec) for i in range(len(queues))]
            vals = pool.map(_work, jobs, chunksize=4)
            cov = {t: sum(1 for v in vals if abs(v - t) <= 0.15)
                   / len(vals) * 100 for t in (0.3, 0.5, 0.8)}
            out[lo] = {
                "p5": round(pct(vals, 0.05), 3),
                "p50": round(S.median(vals), 3),
                "p95": round(pct(vals, 0.95), 3),
                "near03": round(cov[0.3], 1), "near05": round(cov[0.5], 1),
                "near08": round(cov[0.8], 1),
                "ge08": round(sum(1 for v in vals if v >= 0.8)
                              / len(vals) * 100, 1),
            }
            r = out[lo]
            print(f"{lo}: p5={r['p5']} p50={r['p50']} p95={r['p95']} "
                  f"near={r['near03']}/{r['near05']}/{r['near08']} "
                  f"ge08={r['ge08']}", flush=True)
        return out


if __name__ == "__main__":
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    full = "--full" in sys.argv
    queues = sample_queues(300, seed=31337)
    names = [only] if only else list(CANDIDATES)
    for name in names:
        los = list(LOADOUTS) if full else ["sedang"]
        print(f"=== kandidat {name} ({'/'.join(los)}) ===", flush=True)
        measure(CANDIDATES[name], los, queues)
