"""experiments/fidelity_sample.py - Fidelitas sampel kecil (laporan, tak memblokir).

30 antrean x loadout sedang, ChainLightSim (N=4, seed 5) vs ChainSim (N=6,
seed 5): Pearson/Spearman/RMSE apa adanya + status kalibrasi bobot
(otomatis tak berlaku bila sidik stat berubah). Paket stat opsional (JSON).
Jalan: `python3 experiments/fidelity_sample.py [paket.json]` (~2 mnt).
"""
from __future__ import annotations

import json
import statistics as S
import sys
import time
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, str(Path(ROOT) / "experiments"))

from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.player_loadout import PlayerLoadout  # noqa: E402

PL = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))


def main(pkg):
    from dataclasses import replace
    from game.ambush.chain_eval import (ChainLightSim, ChainSim,
                                        config_fingerprint, resolve_weights)
    from game.ambush.types import stat_fingerprint
    if pkg:
        from game.ambush import types as T
        for name, fields in (pkg.get("roles") or {}).items():
            T.ROLE_TABLE[name] = replace(T.ROLE_TABLE[name], **fields)
        for name, fields in (pkg.get("items") or {}).items():
            T.ITEM_TABLE[name] = replace(T.ITEM_TABLE[name], **fields)
        c = pkg.get("config") or {}
        cfg = replace(AmbushConfig(),
                       rest_heal_pct=c.get("rest_heal_pct", 0.0),
                       npc_starting_potions=c.get("npc_starting_potions", 2),
                       potion_bonus_per_duel=c.get("potion_bonus_per_duel",
                                                   0))
    else:
        cfg = AmbushConfig()
    print(f"stat_fingerprint={stat_fingerprint()}", flush=True)
    print(f"config_fingerprint={config_fingerprint(cfg)}", flush=True)
    try:
        doc, cal = resolve_weights(cfg)
        print(f"bobot heuristik: calibrated={cal}", flush=True)
    except RuntimeError as e:
        print(f"bobot heuristik: TIDAK BERLAKU ({e})", flush=True)
    from fit_queue import pearson, rmse, sample_queues, spearman
    t0 = time.perf_counter()
    queues = sample_queues(30, seed=777)
    light = ChainLightSim(cfg, PL, seed=5, games=4)
    full = ChainSim(cfg, PL, seed=5, games=6)
    xs = [light.evaluate(qs) for qs in queues]
    ys = [full.evaluate(qs) for qs in queues]
    print(f"n=30: pearson={pearson(xs, ys):.3f} "
          f"spearman={spearman(xs, ys):.3f} rmse={rmse(xs, ys):.3f} "
          f"({time.perf_counter() - t0:.0f}s)", flush=True)
    print(f"ambang: pearson>=0.85 spearman>=0.80 rmse<=0.08 "
          f"(sim ringan tetap objektif; tak memblokir)", flush=True)


if __name__ == "__main__":
    pkg = None
    for a in sys.argv[1:]:
        if a.endswith(".json"):
            pkg = json.load(open(a, encoding="utf-8"))
    main(pkg)
