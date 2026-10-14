"""experiments/diag_ceiling.py - OPSI PLAFON DIRECTOR (ukur saja, tak terapkan).

Baseline: director nyata @0.50/0.80/0.95 x 3 loadout x greedy+depth4,
N=8/pertemuan CRN + rentang noise (split-half seed).
Opsi A (Boss untuk target tinggi): 40 antrean Boss-terakhir paksa (k 3-4,
valid wins=9) x 3 loadout x 2 kebijakan x N=6.
Opsi B (jalur tersulit k=4): ~8 antrean terkeras rakitan dalam budget 0.95,
urutan bervariasi, Boss terakhir, x 3 loadout x 2 kebijakan x N=6.
Opsi C (cap governor): plafon terbukti per sel dari data A/B + lintasan
win-streak ber-cap sintetis + teks label jujur (tanpa main).
Aturan: antrean biasa tak boleh mustahil (cek median), tahap 1-2 untouched,
Boss-hanya-terakhir tetap.

Jalan: `python3 experiments/diag_ceiling.py` (~10 mnt, pool-4).
Keluar: data/results/diag_ceiling.csv + stdout.
"""
from __future__ import annotations

import csv
import random
import statistics as S
import sys
import time
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, str(Path(ROOT) / "experiments"))

import diag_range as D  # noqa: E402
from game.ambush.config import AmbushConfig  # noqa: E402

CFG = AmbushConfig()
LOADOUTS = D.LOADOUTS


def meeting_with_loadout(cfg, target, loname, policy, seed):
    """director_meeting D dengan loadout parameter (harness-lokal)."""
    import random as _r
    from adversarial_ai import ATTACK_MAX, ATTACK_MIN, MAX_HP
    from game.ambush.buff_ai import (BuffAwareAI, BuffBattleState,
                                     apply_chip_hook)
    from game.ambush.director import AmbushDirector
    from game.ambush.enemy_queue import enemy_max_hp
    from game.ambush.flow.queue_driver import QueueRun
    from game.ambush.governor import DifficultyGovernor
    from game.ambush.player_loadout import loadout_to_buff
    from game.ambush.policies import think_policy
    pl = LOADOUTS[loname]
    gov = DifficultyGovernor(cfg)
    gov.target = target
    director = AmbushDirector(cfg, gov, base_seed=seed)
    res = director.plan_queue(0, gov.target, pl)
    pbuff = loadout_to_buff(pl, cfg)
    cap = MAX_HP + pbuff.hp
    run = QueueRun(queue=res.queue, buffs=list(res.buffs),
                   target=res.target, pred_light=res.light,
                   pred_full=res.sim_difficulty, hp=cap, potions=3,
                   cap=cap, cfg=cfg)
    rng = _r.Random(50000 + seed)
    k = run.queue.k()
    for di, (slot, buff) in enumerate(zip(run.queue.slots, run.buffs)):
        st = BuffBattleState(
            player_hp=run.hp,
            npc_hp=enemy_max_hp(buff, cfg.enemy_base_hp),
            turn=0, buff=buff, player_buff=pbuff)
        st.player_potions = run.potions
        st.npc_potions = cfg.npc_starting_potions
        ai_n = BuffAwareAI(depth=4, buff=buff, player_buff=pbuff)
        ai_p = BuffAwareAI(depth=4 if policy == "depth4" else 1, buff=buff,
                           player_buff=pbuff)
        last = di == k - 1
        for _ in range(cfg.sim_max_plies):
            if st.is_terminal():
                break
            isnpc = st.turn == 1
            if policy == "depth4":
                a = (ai_n if isnpc else ai_p).think(
                    st, run_baseline=False,
                    root_is_npc=isnpc)["best_action"]
            else:
                a = think_policy(ai_n if isnpc else ai_p, st, isnpc, policy,
                                 last, k - 1 - di, cap)
            if a is None:
                break
            dmg = rng.randint(ATTACK_MIN, ATTACK_MAX) \
                if a == "ATTACK" else None
            kw = ({"attack_damage": dmg} if dmg is not None else {})
            st = st.apply_action(isnpc, a, **kw)
            apply_chip_hook(st, buff)
        status = run.record(max(0, st.player_hp), st.player_potions,
                            st.npc_hp <= 0)
        if status != "next":
            break
    return {"target": target, "loadout": loname, "policy": policy,
            "seed": seed, "order": run.queue.order_str(), "k": k,
            "prog": round(run.progress(), 3),
            "clear": 1 if status == "won_all" else 0}


def _tbase(task):
    target, loname, policy, seed = task
    return meeting_with_loadout(CFG, target, loname, policy, seed)


def boss_queues(n=40) -> list:
    """Antrean Boss-terakhir paksa, valid wins=9, k 3-4 (opsi A)."""
    rng = random.Random(777)
    from game.ambush.enemy_queue import (EnemyQueue, EnemySlot,
                                         is_queue_valid)
    from game.ambush.types import EMPTY, ITEM_TABLE, ROLE_TABLE
    roles = [r for r in ROLE_TABLE if r != EMPTY]
    items = list(ITEM_TABLE)
    out, seen, tries = [], set(), 0
    while len(out) < n and tries < 30000:
        tries += 1
        k = rng.randint(3, 4)
        pre = tuple(EnemySlot(rng.choice([r for r in roles if r != "Boss"]),
                              rng.choice(items)) for _ in range(k - 1))
        q = EnemyQueue(slots=pre + (EnemySlot(
            "Boss", rng.choice(items)),))
        if (q.key() not in seen
                and is_queue_valid(q, 9, CFG.budget_q_for(0.95), CFG)):
            seen.add(q.key())
            out.append(q)
    print(f"opsi A: {len(out)} antrean Boss-terakhir", flush=True)
    return out


def hardest_queues() -> list:
    """~8 antrean terkeras rakitan dalam budget 0.95 (opsi B)."""
    from game.ambush.enemy_queue import (EnemyQueue, EnemySlot,
                                         is_queue_valid)
    cands = [
        (("Archer", "Dragon Fang"), ("Tank", "Heavy Shield"),
         ("Minion", "Swift Boots"), ("Boss", "NONE")),
        (("Mage", "Swift Boots"), ("Archer", "Iron Sword"),
         ("Tank", "NONE"), ("Boss", "Healing Charm")),
        (("Tank", "Heavy Shield"), ("Mage", "Iron Sword"),
         ("Archer", "Swift Boots"), ("Boss", "Dragon Fang")),
        (("Archer", "Iron Sword"), ("Mage", "Healing Charm"),
         ("Warrior", "Dragon Fang"), ("Boss", "Swift Boots")),
        (("Mage", "Dragon Fang"), ("Tank", "Swift Boots"),
         ("Minion", "Heavy Shield"), ("Boss", "Iron Sword")),
        (("Warrior", "Swift Boots"), ("Archer", "Heavy Shield"),
         ("Mage", "NONE"), ("Boss", "NONE")),
        (("Tank", "NONE"), ("Archer", "Dragon Fang"),
         ("Mage", "Swift Boots"), ("Boss", "Heavy Shield")),
        (("Minion", "Dragon Fang"), ("Tank", "Iron Sword"),
         ("Archer", "NONE"), ("Boss", "NONE")),
    ]
    out = []
    for pairs in cands:
        q = EnemyQueue(slots=tuple(EnemySlot(r, it) for r, it in pairs))
        bad = is_queue_valid(q, 9, CFG.budget_q_for(0.95), CFG)
        cost = q.total_cost()
        print(f"opsi B {q.order_str()} cost={cost} "
              f"{'VALID' if not bad else bad}", flush=True)
        if not bad:
            out.append(q)
    return out


def _topt2(task):
    kind, qi, slots, loname, policy, seed0 = task
    prog, clear = D.play_chain(slots, LOADOUTS[loname], policy, CFG,
                               [seed0 + i for i in range(6)])
    return (kind, qi, loname, policy, round(prog, 3), round(clear, 3))


def main():
    import multiprocessing as mp
    t0 = time.perf_counter()
    outdir = Path(ROOT) / "data" / "results"
    outdir.mkdir(parents=True, exist_ok=True)

    print("== BASELINE director @0.5/0.8/0.95 x 3 loadout x 2 pol (N=8) ==",
          flush=True)
    with mp.Pool(4) as pool:
        jobs = [(t, lo, p, 8000 + i) for t in (0.50, 0.80, 0.95)
                for lo in LOADOUTS for p in ("greedy", "depth4")
                for i in range(8)]
        res = pool.map(_tbase, jobs, chunksize=2)
    with open(outdir / "diag_ceiling_base.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["target", "loadout", "policy",
                                          "seed", "order", "k", "prog",
                                          "clear"])
        w.writeheader()
        for r in res:
            w.writerow(r)
    for t in (0.50, 0.80, 0.95):
        for lo in LOADOUTS:
            for p in ("greedy", "depth4"):
                sel = [r for r in res if r["target"] == t
                       and r["loadout"] == lo and r["policy"] == p]
                a = [r["prog"] for r in sel[:4]]
                b = [r["prog"] for r in sel[4:]]
                sp = abs(S.mean(a) - S.mean(b))
                print(f"--- t={t} {lo:6s} {p:6s}: prog="
                      f"{S.mean([r['prog'] for r in sel]):.2f}(+-{sp:.2f}) "
                      f"clear={S.mean([r['clear'] for r in sel]):.2f} "
                      f"k={[r['k'] for r in sel][:4]}", flush=True)

    print("== OPSI A: 40 Boss-terakhir x 3 loadout x 2 pol (N=6) ==",
          flush=True)
    bq = boss_queues(40)
    bslots = [[(s.role, s.item) for s in q.slots] for q in bq]
    print("== OPSI B: terkeras rakitan x 3 loadout x 2 pol (N=6) ==",
          flush=True)
    hq = hardest_queues()
    hslots = [[(s.role, s.item) for s in q.slots] for q in hq]
    with mp.Pool(4) as pool:
        jobsa = [("A", qi, bslots[qi], lo, p, 3000 + qi * 6)
                 for qi in range(len(bq)) for lo in LOADOUTS
                 for p in ("greedy", "depth4")]
        resA = pool.map(_topt2, jobsa, chunksize=4)
        jobsb = [("B", qi, hslots[qi], lo, p, 4000 + qi * 6)
                 for qi in range(len(hq)) for lo in LOADOUTS
                 for p in ("greedy", "depth4")]
        resB = pool.map(_topt2, jobsb, chunksize=4)
    with open(outdir / "diag_ceiling_opts.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["kind", "qi", "order", "loadout", "policy", "prog",
                    "clear"])
        for kind, qi, lo, p, prog, clear in resA:
            w.writerow([kind, qi, bq[qi].order_str(), lo, p, prog, clear])
        for kind, qi, lo, p, prog, clear in resB:
            w.writerow([kind, qi, hq[qi].order_str(), lo, p, prog, clear])
    for kind, resx, qs in (("A", resA, bq), ("B", resB, hq)):
        for lo in LOADOUTS:
            for p in ("greedy", "depth4"):
                ps = [prog for k, _, l, q, prog, _ in resx
                      if l == lo and q == p]
                cs = [c for k, _, l, q, _, c in resx if l == lo and q == p]
                # noise: split-half seed -> di sini antar-antrean SD + catat.
                print(f"--- opsi{kind} {lo:6s} {p:6s}: prog="
                      f"{S.mean(ps):.2f}(sd={S.pstdev(ps):.2f}) clear="
                      f"{S.mean(cs):.2f} gagal<="
                      f"{sum(1 for v in ps if v <= 0.5) / len(ps) * 100:.0f}%",
                      flush=True)

    print("== OPSI C: plafon terbukti + cap governor (sintetis) ==",
          flush=True)
    from game.ambush.governor import DifficultyGovernor
    # Plafon = difficulty (1-prog) terbesar yang terbukti dibuat director
    # pada baseline; cap = target setara plafon per kebijakan (sedang).
    for p in ("greedy", "depth4"):
        sel95 = [r["prog"] for r in res if r["target"] == 0.95
                 and r["loadout"] == "sedang" and r["policy"] == p]
        ceil_diff = 1 - min(sel95)
        print(f"--- {p}: prog-min@0.95={min(sel95):.2f} "
              f"plafon-diff={ceil_diff:.2f}", flush=True)
    for cap in (0.80, 0.95):
        gov = DifficultyGovernor(CFG)
        traj = []
        for _ in range(40):
            gov.update("player", 0.3, progress=1.0, failed_at=None)
            gov.target = min(gov.target, cap)  # cap hipotetis
            traj.append(round(gov.target, 3))
        print(f"--- cap {cap}: t10={traj[9]} t40={traj[39]}", flush=True)
    print('LABEL: "target di atas plafon, antrean tersulit: {order}"',
          flush=True)
    print(f"SELESAI ({time.perf_counter() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
