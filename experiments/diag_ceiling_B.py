"""experiments/diag_ceiling_B.py - Opsi B ULANG: terkeras VALID (budget<=16).

Harness diag_ceiling memakai is_queue_valid() (bool) sebagai daftar
pelanggaran sehingga filter terbalik dan antrean over-budget lolos.
Di sini: validasi via check_queue() (list) dengan benar + main N=6.
Jalan: `python3 experiments/diag_ceiling_B.py` (~3 mnt).
"""
from __future__ import annotations

import csv
import statistics as S
import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, str(Path(ROOT) / "experiments"))

import diag_range as D  # noqa: E402
from game.ambush.config import AmbushConfig  # noqa: E402

CFG = AmbushConfig()
BUDGET = CFG.budget_q_for(0.95)
print(f"budget t=0.95: {BUDGET}", flush=True)

CANDS = [
    (("Archer", "Iron Sword"), ("Tank", "NONE"), ("Minion", "NONE"),
     ("Boss", "NONE")),
    (("Tank", "NONE"), ("Archer", "NONE"), ("Minion", "Iron Sword"),
     ("Boss", "NONE")),
    (("Warrior", "NONE"), ("Mage", "NONE"), ("Minion", "NONE"),
     ("Boss", "NONE")),
    (("Minion", "Healing Charm"), ("Warrior", "Swift Boots"),
     ("Archer", "NONE"), ("Boss", "NONE")),
    (("Healer", "Healing Charm"), ("Archer", "Iron Sword"),
     ("Minion", "NONE"), ("Boss", "NONE")),
    (("Tank", "Heavy Shield"), ("Warrior", "NONE"), ("Minion", "NONE"),
     ("Boss", "NONE")),
    (("Archer", "Swift Boots"), ("Tank", "NONE"), ("Minion", "NONE"),
     ("Boss", "NONE")),
    (("Tank", "NONE"), ("Warrior", "NONE"), ("Minion", "Swift Boots"),
     ("Boss", "NONE")),
]


def main():
    import multiprocessing as mp
    from game.ambush.enemy_queue import (EnemyQueue, EnemySlot,
                                         check_queue)
    queues = []
    for pairs in CANDS:
        q = EnemyQueue(slots=tuple(EnemySlot(r, it) for r, it in pairs))
        bad = check_queue(q, 9, BUDGET, CFG)
        print(f"{q.order_str()} cost={q.total_cost()}/{BUDGET} "
              f"{'VALID' if not bad else bad}", flush=True)
        assert not bad, (pairs, bad)
        queues.append(q)
    slots = [[(s.role, s.item) for s in q.slots] for q in queues]
    with mp.Pool(4) as pool:
        jobs = [(qi, slots[qi], lo, p, 4000 + qi * 6)
                for qi in range(len(queues)) for lo in D.LOADOUTS
                for p in ("greedy", "depth4")]
        res = pool.map(_play, jobs, chunksize=4)
    out = Path(ROOT) / "data" / "results" / "diag_ceiling_B.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["qi", "order", "loadout", "policy", "prog", "clear"])
        for qi, lo, p, prog, clear in res:
            w.writerow([qi, queues[qi].order_str(), lo, p, prog, clear])
    for lo in D.LOADOUTS:
        for p in ("greedy", "depth4"):
            ps = [prog for _, l, q, prog, _ in res if l == lo and q == p]
            cs = [c for _, l, q, _, c in res if l == lo and q == p]
            print(f"opsiB-valid {lo:6s} {p:6s}: prog={S.mean(ps):.2f} "
                  f"clear={S.mean(cs):.2f} gagal<="
                  f"{sum(1 for v in ps if v <= 0.5) / len(ps) * 100:.0f}%",
                  flush=True)


def _play(task):
    qi, sl, loname, policy, seed0 = task
    prog, clear = D.play_chain(sl, D.LOADOUTS[loname], policy, CFG,
                               [seed0 + i for i in range(6)])
    return (qi, loname, policy, round(prog, 3), round(clear, 3))


if __name__ == "__main__":
    main()
