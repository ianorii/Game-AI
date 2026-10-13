"""experiments/sustain_sweep.py - Sapuan sustain Langkah S (Fase balance).

(a) npc_starting_potions {3,2,1} (+bonus+1 pembanding): K1-K3 per peran,
    medium, greedy/hemat/depth4. (b) rest {0,15,25,35}: level antrean
    (150 antrean, medium, N=4) karena rest hanya bekerja antar-duel.
Tidak mengubah default; seed tetap; paralel.
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
sys.path.insert(0, str(Path(ROOT) / "experiments"))

from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.player_loadout import PlayerLoadout  # noqa: E402

CFG = AmbushConfig()
ROLES = ["Warrior", "Tank", "Healer", "Archer", "Mage", "Boss", "Minion"]
PL = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))


def _cell(task):
    role, npot, bonus, policy, games = task
    from balance_baseline import play
    cfg = replace(CFG, npc_starting_potions=npot,
                  potion_bonus_per_duel=bonus)
    return play(role, "NONE", PL, policy, 5, games, cfg)


_QUEUES = None


def _init(qs):
    global _QUEUES
    _QUEUES = qs


def _rest(task):
    rest, qi = task
    from dataclasses import replace as _rp
    from game.ambush.chain_eval import ChainSim
    cfg = _rp(CFG, rest_heal_pct=rest)
    return ChainSim(cfg, PL, seed=5, games=4).evaluate(_QUEUES[qi])


def main():
    from fit_queue import sample_queues
    print("== (a) potion musuh/duel ==", flush=True)
    with mp.Pool(4) as pool:
        for npot, bonus in ((3, 0), (2, 0), (1, 0), (3, 1)):
            rows = {}
            jobs = [(r, npot, bonus, pol, 20 if pol != "depth4" else 8)
                    for r in ROLES for pol in ("greedy", "conserve",
                                               "depth4")]
            for (r, _n, _b, pol, _g), (w, n, l) in zip(
                    jobs, pool.map(_cell, jobs, chunksize=4)):
                rows.setdefault(r, {})[pol] = (w, n, l)
            print(f"-- npot={npot} bonus=+{bonus}", flush=True)
            for r in ROLES:
                g = rows[r]
                print(f"   {r:8s} greedy {g['greedy'][0]:.2f}/{g['greedy'][2]:.2f} "
                      f"depth4 {g['depth4'][0]:.2f}/{g['depth4'][2]:.2f}",
                      flush=True)
    print("== (b) rest antar-duel (150 antrean, N=4) ==", flush=True)
    from fit_queue import sample_queues
    queues = sample_queues(150, seed=31337)
    with mp.Pool(4, initializer=_init, initargs=(queues,)) as pool:
        for rest in (0.0, 0.15, 0.25, 0.35):
            vals = pool.map(_rest, [(rest, i) for i in range(150)],
                            chunksize=4)
            cov = {t: sum(1 for v in vals if abs(v - t) <= 0.15)
                   / len(vals) * 100 for t in (0.4, 0.5, 0.8)}
            print(f"rest={rest}: med={S.median(vals):.3f} "
                  f"near={cov[0.4]:.0f}/{cov[0.5]:.0f}/{cov[0.8]:.0f}",
                  flush=True)


if __name__ == "__main__":
    main()
