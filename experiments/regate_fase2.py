"""experiments/regate_fase2.py - Ulang gerbang Fase 2 dengan Minion (butir 4).

a. 1000 antrean acak/target: pelanggaran per aturan + valid.
b. Enumerasi penuh + soundness lower-bound (vs varian tanpa lower-bound
   pada sampel besar + brute-force penyelesaian parsial yang diprune).
c. 20 seed x 3 target: nodes/bt/prune/ms + valid.
d. degree, contoh LCV, skenario AC-3 (satu melibatkan Minion).
e. Petunjuk ablasi (jalankan ablate_csp.py terpisah).
f. Keragaman 50/target.

Jalan: `python3 experiments/regate_fase2.py` (~5 mnt + enumerasi ~2 mnt).
"""
from __future__ import annotations

import inspect
import itertools
import random
import statistics as S
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import game.ambush.constraints as CX  # noqa: E402
from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.csp_solver import CSPSolver, squad_problem  # noqa: E402
from game.ambush.enemy_queue import (  # noqa: E402
    is_queue_valid,
    queue_from_assign,
)
from game.ambush.types import EMPTY, ITEM_TABLE, ROLE_TABLE  # noqa: E402

CFG = AmbushConfig()
Q = dict(queue_rules=True, min_active=2)


def bucket(v: str) -> str:
    if v.startswith("total power") or "melebihi budget" in v:
        return "budget"
    if "minimal" in v or "maks" in v and "aktif" in v:
        return "min-2"
    if "terakhir" in v:
        return "boss-last"
    if "butuh wins" in v:
        return "boss-gate"
    if "berturutan" in v:
        return "adjacency"
    if "dua Healer" in v:
        return "healer-max1"
    if "unik" in v or "berbeda" in v:
        return "unique"
    if "kompatibel" in v or "terisi tapi" in v:
        return "kompat"
    if "slot kosong" in v:
        return "canonical"
    return "lain"


def part_a():
    print("== (a) 1000 antrean acak ==", flush=True)
    roles = [r for r in ROLE_TABLE if r != EMPTY]
    items = list(ITEM_TABLE)
    rng = random.Random(20260712)
    for target in (0.3, 0.5, 0.8):
        budget = CFG.budget_q_for(target)
        cats, n_valid = Counter(), 0
        for _ in range(1000):
            k = rng.randint(2, 4)
            from game.ambush.enemy_queue import EnemyQueue, EnemySlot, check_queue
            act = [EnemySlot(rng.choice(roles), rng.choice(items))
                   for _ in range(k)]
            bad = check_queue(EnemyQueue(slots=tuple(act)), 0, budget, CFG)
            if not bad:
                n_valid += 1
            else:
                seen = set()
                for v in bad:
                    b = bucket(v)
                    if b not in seen:
                        cats[b] += 1
                        seen.add(b)
        print(f"t={target} b={budget} valid={n_valid}/1000 "
              + " ".join(f"{k}={v}" for k, v in cats.most_common()),
              flush=True)


def _nolb_check():
    """Varian check tanpa blok lower-bound (orakel soundness)."""
    src = inspect.getsource(CX.check)
    start = src.index("    # Lower-bound sound (Fase 2c)")
    end = src.index("    return bad")
    stripped = src[:start] + src[end:]
    ns = dict(vars(CX))
    exec(stripped, ns)
    return ns["check"]


def part_b():
    print("== (b) enumerasi + soundness lower-bound ==", flush=True)
    check_nolb = _nolb_check()
    R1 = [r for r in ROLE_TABLE if r != EMPTY or True]
    R1 = [r for r in ROLE_TABLE]  # termasuk NONE
    RR = [r for r in ROLE_TABLE if r != "Boss"]
    IT = list(ITEM_TABLE)
    for target in (0.3, 0.5, 0.8):
        budget = CFG.budget_q_for(target)
        t0, n_valid, n = time.perf_counter(), 0, 0
        for combo in itertools.product(R1, RR, RR, RR, IT, IT, IT, IT):
            n += 1
            a = {f"ROLE_{i}": combo[i - 1] for i in (1, 2, 3, 4)}
            a.update({f"ITEM_{i}": combo[4 + i - 1] for i in (1, 2, 3, 4)})
            if not CX.check(a, 0, budget, CFG, True, 2):
                n_valid += 1
        print(f"t={target} b={budget}: valid={n_valid}/{n} "
              f"({n_valid / n * 100:.2f}%) {time.perf_counter() - t0:.0f}s",
              flush=True)
    # Sampel besar: check vs tanpa-lower-bound pada 50rb assignment.
    rng = random.Random(99)
    agree = diff = skipped = 0
    for _ in range(50000):
        a = {}
        for i in (1, 2, 3, 4):
            if rng.random() < 0.9:
                a[f"ROLE_{i}"] = rng.choice(R1)
            if rng.random() < 0.9:
                a[f"ITEM_{i}"] = rng.choice(IT)
        r1 = not CX.check(a, 0, 12, CFG, True, 2)
        r2 = not check_nolb(a, 0, 12, CFG, True, 2)
        if r1 == r2:
            agree += 1
        else:
            verdict = _brute_empty(a, 12)
            if verdict is None:
                skipped += 1
            else:
                diff += 1  # new=invalid, old=valid -> klaim prune
                assert verdict, a  # terbukti tak ada penyelesaian
    print(f"50rb sampel: sama={agree} prune-terbukti={diff} "
          f"skip-terlalu-besar={skipped}", flush=True)


def _brute_empty(partial, budget) -> bool:
    """True bila TAK ADA penyelesaian (bukti prune sound)."""
    R1 = list(ROLE_TABLE)
    IT = list(ITEM_TABLE)
    un_r = [i for i in (1, 2, 3, 4) if f"ROLE_{i}" not in partial]
    un_i = [i for i in (1, 2, 3, 4) if f"ITEM_{i}" not in partial]
    if len(un_r) + len(un_i) > 6:
        return None  # terlalu besar: lewati (dilaporkan terpisah)
    for rv in itertools.product(R1, repeat=len(un_r)):
        for iv in itertools.product(IT, repeat=len(un_i)):
            a = dict(partial)
            a.update({f"ROLE_{i}": v for i, v in zip(un_r, rv)})
            a.update({f"ITEM_{i}": v for i, v in zip(un_i, iv)})
            if not CX.check(a, 0, budget, CFG, True, 2):
                return False
    return True


def part_c():
    print("== (c) 20 seed x 3 target ==", flush=True)
    for target in (0.3, 0.5, 0.8):
        ns, bs, ps, ts, ok, ks = [], [], [], [], 0, set()
        for seed in range(20):
            t0 = time.perf_counter()
            sol, st = CSPSolver(
                squad_problem(0, CFG.budget_q_for(target), CFG, **Q),
                seed=seed).solve()
            ts.append((time.perf_counter() - t0) * 1000)
            ns.append(st["nodes"])
            bs.append(st["backtracks"])
            ps.append(st["pruned"])
            q = queue_from_assign(sol, CFG)
            ks.add(q.k())
            ok += sol is not None and is_queue_valid(
                q, 0, CFG.budget_q_for(target), CFG)
        print(f"t={target}: valid={ok}/20 k={sorted(ks)} nodes={S.mean(ns):.0f} "
              f"bt={S.mean(bs):.0f} pruned={S.mean(ps):.0f} ms={S.mean(ts):.1f}",
              flush=True)


def part_d():
    print("== (d) degree/LCV/AC-3 ==", flush=True)
    from game.ambush.trace import TraceBuffer
    prob = squad_problem(0, CFG.budget_q_for(0.5), CFG, **Q)
    print("degree:", {v: len(prob.neighbors[v]) for v in prob.variables},
          flush=True)
    tr = TraceBuffer()
    CSPSolver(squad_problem(0, CFG.budget_q_for(0.5), CFG, **Q),
              tracer=tr).solve()
    first = tr.of_kind("lcv")[0]
    print(f"LCV {first['var']}:",
          [(c["val"], c["removed"]) for c in first["candidates"]], flush=True)

    def scen(name, doms, wins=0, budget=99):
        prob = squad_problem(wins, budget, CFG, **Q)
        prob.domains = dict(prob.domains)
        for k, v in doms.items():
            prob.domains[k] = v
        sol, st = CSPSolver(prob).solve()
        print(f"{name}: pruned={st['pruned']} revises={st['revises']} "
              f"sol2={sol['ROLE_2'] if sol else None}", flush=True)
    scen("adj Tank-Healer", {"ROLE_1": ["Tank"],
                             "ROLE_2": ["Healer", "Warrior"]})
    scen("minion-fang", {"ROLE_1": ["Minion", "Warrior"],
                         "ITEM_1": ["Dragon Fang"]})


def part_f():
    print("== (f) keragaman 50/target ==", flush=True)
    from collections import Counter
    for target in (0.3, 0.5, 0.8):
        r1, uniq, ks, ni, ok, minim = (Counter(), set(), [], 0, 0, 0)
        for s in range(50):
            sol, _ = CSPSolver(
                squad_problem(0, CFG.budget_q_for(target), CFG, **Q),
                seed=s, use_mrv=False, use_degree=False, use_lcv=False,
                inference="none").solve()
            q = queue_from_assign(sol, CFG)
            ok += is_queue_valid(q, 0, CFG.budget_q_for(target), CFG)
            r1[q.slots[0].role] += 1
            uniq.add(q.key())
            ks.append(q.k())
            ni += sum(1 for x in q.slots if x.item != EMPTY)
            minim += sum(1 for x in q.slots if x.role == "Minion")
        print(f"t={target}: ROLE_1=" + " ".join(f"{k}={v}" for k, v in
              r1.most_common()) + f" | unik={len(uniq)}/50 "
              f"k={S.mean(ks):.2f} item={ni / 50:.2f} minion={minim} "
              f"valid={ok}/50", flush=True)


if __name__ == "__main__":
    part_a()
    part_b()
    part_c()
    part_d()
    part_f()
