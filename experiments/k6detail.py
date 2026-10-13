"""experiments/k6detail.py - Breakdown K6 penuh per peran x item (depth-4 N=20).

Memakai paket JSON (seperti measure_R). Keluar: stdout tabel + CSV.
Jalan: `python3 experiments/k6detail.py <paket.json> <tag>` (~3 mnt).
"""
from __future__ import annotations

import csv
import json
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
ITEMS = ["NONE", "Iron Sword", "Heavy Shield", "Swift Boots",
         "Healing Charm", "Dragon Fang"]
PL = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
SEEDS = list(range(100, 120))


def _init(pkg_json):
    from game.ambush import types as T
    pkg = json.loads(pkg_json)
    for name, fields in (pkg.get("roles") or {}).items():
        T.ROLE_TABLE[name] = replace(T.ROLE_TABLE[name], **fields)
    for name, fields in (pkg.get("items") or {}).items():
        T.ITEM_TABLE[name] = replace(T.ITEM_TABLE[name], **fields)
    global _CFG
    c = pkg.get("config") or {}
    _CFG = replace(CFG, rest_heal_pct=c.get("rest_heal_pct", 0.0),
                   npc_starting_potions=c.get("npc_starting_potions", 2),
                   potion_bonus_per_duel=c.get("potion_bonus_per_duel", 0))


def _cell(task):
    role, item, seeds = task
    from balance_baseline import play
    ws = [play(role, item, PL, "depth4", sd, 1, _CFG)[0] for sd in seeds]
    h = len(ws) // 2
    return S.mean(ws), abs(S.mean(ws[:h]) - S.mean(ws[h:]))


def main(pkg_path, tag):
    pkg = json.load(open(pkg_path, encoding="utf-8"))
    with mp.Pool(4, initializer=_init, initargs=(json.dumps(pkg),)) as pool:
        jobs = [(r, it, SEEDS) for r in ROLES for it in ITEMS]
        res = pool.map(_cell, jobs, chunksize=2)
    table = {}
    for (r, it, _), (w, sp) in zip(jobs, res):
        table.setdefault(r, {})[it] = (w, sp)
    rows = []
    for r in ROLES:
        base = table[r]["NONE"][0]
        line = f"{r:8s} base={base:.2f} "
        for it in ITEMS:
            if it == "NONE":
                continue
            w, sp = table[r][it]
            d = w - base
            flag = "!" if abs(d) > 0.50 else " "
            line += f"{flag}{it.split()[-1][:5]}:{w:.2f}({d:+.2f}) "
            rows.append({"tag": tag, "role": r, "item": it,
                         "win": round(w, 3), "delta": round(d, 3),
                         "spread": round(sp, 3)})
        print(line, flush=True)
    out = Path(ROOT) / "data" / "results" / f"k6detail_{tag}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"ditulis {out}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
