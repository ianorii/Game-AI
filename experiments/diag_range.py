"""experiments/diag_range.py - DIAGNOSIS rentang kesulitan (TANPA ubah kode/default).

1. 300 antrean valid beragam (solver/random/Boss-eligible, k 2-4) x 3 loadout
   x 3 kebijakan, main MANUAL (NPC depth-4 = game nyata), N=2 CRN: sebaran
   progres (p5/p50/p95, histogram), clear penuh, % dalam +-0.15 target
   0.30/0.40/0.50/0.80, % progres <= 0.5.
2. Director nyata (CSP+LS+rerank) 30 pertemuan x target {0.80, 0.95} x 3
   kebijakan: progres aktual vs target, clear, contoh antrean tersulit.
3. Governor: lintasan target sintetis 40 pertemuan (menang-terus /
   kalah-terus / campuran) + rujukan empiris.
4. Ablasi sustain (rest 0 / refill mati / npot 2) pada target 0.50:
   clear + progres (director autoplay, n=12).
5. Tabel kriteria: clear @0.50 vs 25-40% (d4) / >=10% (greedy).
OPSI (ukur saja): 4 tuas tunggal (rest.15 / refill+1 parsial / npot 2 /
   Boss+setengah-langkah) -> dampak rentang (sedang, greedy+d4) + rasa main
   (1v1: win/plies/lost per peran).

Jalan: `python3 experiments/diag_range.py` (~20 mnt, pool-4).
Keluar: data/results/diag_{range,hardest,ablation,options}.csv + stdout.
"""
from __future__ import annotations

import csv
import random
import statistics as S
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, str(Path(ROOT) / "experiments"))

from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.player_loadout import PlayerLoadout  # noqa: E402

CFG = AmbushConfig()
LOADOUTS = {
    "lemah": PlayerLoadout(items=("NONE", "NONE")),
    "sedang": PlayerLoadout(items=("Iron Sword", "Heavy Shield")),
    "kuat": PlayerLoadout(items=("Dragon Fang", "Heavy Shield")),
}
POLICIES = ("greedy", "hemat", "depth4")
ROLES7 = ["Warrior", "Tank", "Healer", "Archer", "Mage", "Boss", "Minion"]


def sample_300() -> list:
    """100 solver-w0 + 100 acak-w0 + 100 acak-w9 (Boss boleh, terakhir)."""
    import random as _r
    from game.ambush.csp_solver import CSPSolver, squad_problem
    from game.ambush.enemy_queue import (EnemyQueue, EnemySlot,
                                         is_queue_valid, queue_from_assign)
    from game.ambush.types import ITEM_TABLE, ROLE_TABLE, EMPTY
    rng = _r.Random(31337)
    roles = [r for r in ROLE_TABLE if r != EMPTY]
    items = list(ITEM_TABLE)
    out, seen = [], set()

    def add(q):
        if q.key() not in seen:
            seen.add(q.key())
            out.append(q)

    def shuffled(q, wins, budget):
        slots = list(q.slots)
        for _ in range(8):
            pre = [s for s in slots if s.role != "Boss"]
            rng.shuffle(pre)
            fixed = pre + [s for s in slots if s.role == "Boss"]
            cand = EnemyQueue(slots=tuple(fixed))
            if is_queue_valid(cand, wins, budget, CFG):
                return cand
        return q if is_queue_valid(q, wins, budget, CFG) else None

    s = 0
    while len(out) < 100 and s < 4000:
        prob = squad_problem(0, CFG.budget_q_for(0.5), CFG,
                             **CFG.csp_flags())
        sol, _ = CSPSolver(prob, seed=1000 + s).solve()
        s += 1
        if sol is not None:
            cand = shuffled(queue_from_assign(sol, CFG), 0,
                            CFG.budget_q_for(0.5))
            if cand is not None:
                add(cand)
    tries = 0
    while len(out) < 200 and tries < 20000:
        tries += 1
        k = rng.randint(2, 4)
        q = EnemyQueue(slots=tuple(
            EnemySlot(rng.choice(roles), rng.choice(items))
            for _ in range(k)))
        if is_queue_valid(q, 0, CFG.budget_q_for(0.5), CFG):
            add(q)
    tries = 0
    while len(out) < 250 and tries < 40000:
        tries += 1
        k = rng.randint(2, 4)
        q = EnemyQueue(slots=tuple(
            EnemySlot(rng.choice(roles), rng.choice(items))
            for _ in range(k)))
        if is_queue_valid(q, 9, CFG.budget_q_for(0.5), CFG):
            cand = shuffled(q, 9, CFG.budget_q_for(0.5))
            if cand is not None:
                add(cand)
    # Boss paksa-terakhir (aturan Boss memang di ujung): prefix acak + Boss.
    tries = 0
    while len(out) < 300 and tries < 20000:
        tries += 1
        k = rng.randint(2, 4)
        pre = tuple(EnemySlot(rng.choice([r for r in roles if r != "Boss"]),
                              rng.choice(items)) for _ in range(k - 1))
        q = EnemyQueue(slots=pre + (EnemySlot(
            "Boss", rng.choice(list(ITEM_TABLE))),))
        if is_queue_valid(q, 9, CFG.budget_q_for(0.5), CFG):
            add(q)
    print(f"sampel: {len(out)} antrean "
          f"(boss={sum(1 for q in out if 'Boss' in q.roles)}, "
          f"minion={sum(1 for q in out if 'Minion' in q.roles)})",
          flush=True)
    return out


def play_chain(slots, loadout, policy, cfg, seeds):
    """Main manual satu antrean (NPC depth-4 = game nyata). -> (prog, clear)."""
    import random as _r
    from adversarial_ai import ATTACK_MAX, ATTACK_MIN, MAX_HP
    from game.ambush.buff_ai import (BuffAwareAI, BuffBattleState,
                                     apply_chip_hook)
    from game.ambush.chain_eval import apply_rest, carry_potions
    from game.ambush.enemy_queue import (EnemySlot, enemy_max_hp,
                                         slot_to_buff)
    from game.ambush.player_loadout import loadout_to_buff
    from game.ambush.policies import think_policy
    pbuff = loadout_to_buff(loadout, cfg)
    cap = MAX_HP + pbuff.hp
    progs, clears = [], 0
    for sd in seeds:
        rng = _r.Random(sd)
        hp, potions = cap, 3
        won, k = 0, len(slots)
        for di, (role, item) in enumerate(slots):
            eb = slot_to_buff(EnemySlot(role, item), cfg)
            st = BuffBattleState(
                player_hp=hp,
                npc_hp=enemy_max_hp(eb, cfg.enemy_base_hp),
                turn=0, buff=eb, player_buff=pbuff)
            st.player_potions = potions
            st.npc_potions = cfg.npc_starting_potions
            ai_n = BuffAwareAI(depth=4, buff=eb, player_buff=pbuff)
            ai_p = BuffAwareAI(depth=4 if policy == "depth4" else 1,
                               buff=eb, player_buff=pbuff)
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
                    a = think_policy(ai_n if isnpc else ai_p, st, isnpc,
                                     policy, last, k - 1 - di, cap)
                if a is None:
                    break
                dmg = rng.randint(ATTACK_MIN, ATTACK_MAX) \
                    if a == "ATTACK" else None
                kw = ({"attack_damage": dmg} if dmg is not None else {})
                st = st.apply_action(isnpc, a, **kw)
                apply_chip_hook(st, eb)
            if st.npc_hp > 0:
                break
            won += 1
            hp = apply_rest(max(0, st.player_hp), cap, cfg.rest_heal_pct)
            potions = carry_potions(st.player_potions, cfg)
            if cfg.potion_bonus_per_duel > 0:
                from adversarial_ai import POTION_LIMIT
                potions = min(POTION_LIMIT,
                              potions + cfg.potion_bonus_per_duel)
        progs.append(won / k)
        clears += won == k
    return S.mean(progs), clears / len(seeds)


def _t1(task):
    qi, slots, loname, policy, seed0 = task
    prog, clear = play_chain(slots, LOADOUTS[loname], policy, CFG,
                             [seed0 + 0, seed0 + 1])
    return (qi, loname, policy, round(prog, 3), round(clear, 3))


def director_meeting(task):
    """Satu pertemuan Director nyata (wins=0, target tetap). + detail duel."""
    target, policy, seed = task
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
    cfg = CFG
    pl = LOADOUTS["sedang"]
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
    duels = []
    for di, (slot, buff) in enumerate(zip(run.queue.slots, run.buffs)):
        enter = run.hp
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
        cleared = st.npc_hp <= 0
        duels.append((slot.role, slot.item, enter, max(0, st.player_hp),
                      st.player_potions, cleared))
        status = run.record(max(0, st.player_hp), st.player_potions, cleared)
        if status != "next":
            break
    return {"target": target, "policy": policy, "seed": seed,
            "order": run.queue.order_str(), "k": k,
            "prog": round(run.progress(), 3),
            "clear": 1 if status == "won_all" else 0,
            "pred_light": round(res.light, 3),
            "pred_full": (round(res.sim_difficulty, 3)
                          if res.sim_difficulty is not None else ""),
            "duels": duels}


def _t4(task):
    variant, policy, seed = task
    if variant == "base":
        cfg = CFG
    elif variant == "rest0":
        cfg = replace(CFG, rest_heal_pct=0.0)
    elif variant == "norefill":
        cfg = replace(CFG, refill_potions_each_duel=False)
    elif variant == "npot2":
        cfg = replace(CFG, npc_starting_potions=2)
    else:
        raise ValueError(variant)
    row = _meeting_with_cfg(cfg, 0.50, policy, seed)
    row["variant"] = variant
    return row


def _meeting_with_cfg(cfg, target, policy, seed):
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
    pl = LOADOUTS["sedang"]
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
    return {"target": target, "policy": policy, "seed": seed,
            "order": run.queue.order_str(), "k": k,
            "prog": round(run.progress(), 3),
            "clear": 1 if status == "won_all" else 0}


def _topt(task):
    lever, qi, slots, policy, seed0 = task
    from game.ambush.types import ROLE_TABLE, RoleSpec
    from dataclasses import replace as _rp
    import game.ambush.types as _T
    # Terapkan tuas TANPA menyentuh kode: salin tabel + config per worker-call.
    if lever == "base":
        cfg, over = CFG, {}
    elif lever == "rest15":
        cfg, over = _rp(CFG, rest_heal_pct=0.15), {}
    elif lever == "refill1":
        cfg, over = CFG, {}
    elif lever == "npot2":
        cfg, over = _rp(CFG, npc_starting_potions=2), {}
    elif lever == "bossup":
        cfg, over = CFG, {"Boss": dict(hp=9, spec=5)}
    else:
        raise ValueError(lever)
    saved = {}
    for name, fields in over.items():
        saved[name] = _T.ROLE_TABLE[name]
        _T.ROLE_TABLE[name] = replace(saved[name], **fields)
    try:
        if lever == "refill1":
            # Parsial +1: logika lokal harness (kode game TAK diubah).
            prog, clear = _play_refill1(slots, policy, cfg, [seed0, seed0+1])
        else:
            prog, clear = play_chain(slots, LOADOUTS["sedang"], policy, cfg,
                                     [seed0, seed0 + 1])
    finally:
        for name, spec in saved.items():
            _T.ROLE_TABLE[name] = spec
    return (lever, qi, policy, round(prog, 3), round(clear, 3))


def _play_refill1(slots, policy, cfg, seeds):
    """Varian harness-lokal: tiap ganti lawan +1 potion (cap 3)."""
    import random as _r
    from adversarial_ai import (ATTACK_MAX, ATTACK_MIN, MAX_HP, POTION_LIMIT)
    from game.ambush.buff_ai import (BuffAwareAI, BuffBattleState,
                                     apply_chip_hook)
    from game.ambush.chain_eval import apply_rest
    from game.ambush.enemy_queue import (EnemySlot, enemy_max_hp,
                                         slot_to_buff)
    from game.ambush.player_loadout import loadout_to_buff
    from game.ambush.policies import think_policy
    pbuff = loadout_to_buff(LOADOUTS["sedang"], cfg)
    cap = MAX_HP + pbuff.hp
    progs, clears = [], 0
    for sd in seeds:
        rng = _r.Random(sd)
        hp, potions = cap, 3
        won, k = 0, len(slots)
        for di, (role, item) in enumerate(slots):
            eb = slot_to_buff(EnemySlot(role, item), cfg)
            st = BuffBattleState(
                player_hp=hp,
                npc_hp=enemy_max_hp(eb, cfg.enemy_base_hp),
                turn=0, buff=eb, player_buff=pbuff)
            st.player_potions = potions
            st.npc_potions = cfg.npc_starting_potions
            ai_n = BuffAwareAI(depth=4, buff=eb, player_buff=pbuff)
            ai_p = BuffAwareAI(depth=4 if policy == "depth4" else 1,
                               buff=eb, player_buff=pbuff)
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
                    a = think_policy(ai_n if isnpc else ai_p, st, isnpc,
                                     policy, last, k - 1 - di, cap)
                if a is None:
                    break
                dmg = rng.randint(ATTACK_MIN, ATTACK_MAX) \
                    if a == "ATTACK" else None
                kw = ({"attack_damage": dmg} if dmg is not None else {})
                st = st.apply_action(isnpc, a, **kw)
                apply_chip_hook(st, eb)
            if st.npc_hp > 0:
                break
            won += 1
            hp = apply_rest(max(0, st.player_hp), cap, cfg.rest_heal_pct)
            potions = min(POTION_LIMIT, st.player_potions + 1)
        progs.append(won / k)
        clears += won == k
    return S.mean(progs), clears / len(seeds)


def _feel(task):
    role, lever = task
    import game.ambush.types as _T
    from dataclasses import replace as _rp
    cfg = CFG
    if lever == "rest15":
        cfg = _rp(CFG, rest_heal_pct=0.15)
    elif lever == "npot2":
        cfg = _rp(CFG, npc_starting_potions=2)
    saved = {}
    if lever == "bossup" and role == "Boss":
        saved["Boss"] = _T.ROLE_TABLE["Boss"]
        _T.ROLE_TABLE["Boss"] = replace(saved["Boss"], hp=9, spec=5)
    try:
        import sys as _s
        _s.path.insert(0, str(Path(ROOT) / "experiments"))
        from balance_baseline import play
        w, n, lost = [], [], []
        for sd in range(100, 108):
            wi, ni, li = play(role, "NONE", LOADOUTS["sedang"], "depth4",
                              sd, 1, cfg)
            w.append(wi)
            n.append(ni)
            lost.append(li)
    finally:
        for name, spec in saved.items():
            _T.ROLE_TABLE[name] = spec
    return (role, lever, round(S.mean(w), 2), round(S.mean(n), 1),
            round(S.mean(lost), 2))


def hist(xs, bins=10):
    out = [0] * bins
    for x in xs:
        out[min(bins - 1, int(x * bins))] += 1
    return out


def main():
    import multiprocessing as mp
    t0 = time.perf_counter()
    queues = sample_300()
    slots = [[(s.role, s.item) for s in q.slots] for q in queues]
    outdir = Path(ROOT) / "data" / "results"
    outdir.mkdir(parents=True, exist_ok=True)

    print("== 1. rentang 300 antrean x 3 loadout x 3 kebijakan (N=2) ==",
          flush=True)
    with mp.Pool(4) as pool:
        jobs = [(qi, slots[qi], lo, p, 2000 + qi * 2)
                for qi in range(len(queues)) for lo in LOADOUTS
                for p in POLICIES]
        res = pool.map(_t1, jobs, chunksize=8)
    with open(outdir / "diag_range.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["qi", "order", "k", "loadout", "policy", "prog",
                    "clear"])
        for qi, lo, p, prog, clear in res:
            w.writerow([qi, queues[qi].order_str(), queues[qi].k(), lo, p,
                        prog, clear])
    for lo in LOADOUTS:
        for p in POLICIES:
            ps = [prog for _, l, q, prog, _ in res if l == lo and q == p]
            cs = [c for _, l, q, _, c in res if l == lo and q == p]
            ps_sorted = sorted(ps)
            n = len(ps_sorted)
            q = lambda f: ps_sorted[min(n - 1, int(f * n))]
            print(f"--- {lo:6s} {p:6s}: n={n} "
                  f"p5={q(0.05):.2f} p50={q(0.50):.2f} p95={q(0.95):.2f} "
                  f"clear={S.mean(cs):.2f}", flush=True)
            print(f"    hist(progres): {hist(ps)}", flush=True)
            for t in (0.30, 0.40, 0.50, 0.80):
                # progres player = 1 - difficulty; target t_artinya progres~t.
                pct = sum(1 for v in ps if abs(v - t) <= 0.15) / n * 100
                print(f"    dalam progres {t}+-0.15: {pct:.1f}%", flush=True)
            low = sum(1 for v in ps if v <= 0.5) / n * 100
            print(f"    progres<=0.5 (gagal): {low:.1f}%", flush=True)

    print("== 2. director nyata 30 pertemuan x {0.80,0.95} x 3 kebijakan ==",
          flush=True)
    with mp.Pool(4) as pool:
        jobs2 = [(t, p, 7000 + i) for t in (0.80, 0.95) for p in POLICIES
                 for i in range(30)]
        res2 = pool.map(director_meeting, jobs2, chunksize=4)
    with open(outdir / "diag_hardest.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["target", "policy", "seed",
                                          "order", "k", "prog", "clear",
                                          "pred_light", "pred_full"])
        w.writeheader()
        for r in res2:
            d = dict(r)
            d.pop("duels")
            w.writerow(d)
    for t in (0.80, 0.95):
        for p in POLICIES:
            sel = [r for r in res2 if r["target"] == t and r["policy"] == p]
            mp_ = S.mean([r["prog"] for r in sel])
            mc = S.mean([r["clear"] for r in sel])
            print(f"--- target {t} {p:6s}: prog={mp_:.2f} (target {t}) "
                  f"clear={mc:.2f}", flush=True)
    hard = min([r for r in res2 if r["policy"] == "depth4"],
               key=lambda r: (r["prog"], -r["target"]))
    print(f"TERSULIT (depth4): target={hard['target']} "
          f"{hard['order']} k={hard['k']} prog={hard['prog']} "
          f"clear={hard['clear']} pred_light={hard['pred_light']} "
          f"pred_full={hard['pred_full']}", flush=True)
    for role, item, enter,left, pot, ok in hard["duels"]:
        print(f"    {role}+{item}: masuk={enter} sisa={left} "
              f"pot={pot} {'MENANG' if ok else 'GUGUR'}", flush=True)

    print("== 3. governor sintetis 40 pertemuan ==", flush=True)
    from game.ambush.governor import DifficultyGovernor
    for name, feed in (
            ("menang-terus", ["player"] * 40),
            ("kalah-terus", ["npc"] * 40),
            ("campuran-WL", (["player", "npc"] * 20)),
            ("campuran-WWL", (["player", "player", "npc"] * 14)[:40])):
        gov = DifficultyGovernor(CFG)
        traj = []
        for i, side in enumerate(feed):
            gov.update(side, 0.3, progress=1.0 if side == "player" else 0.0,
                       failed_at=None if side == "player" else 1)
            traj.append(round(gov.target, 3))
        print(f"--- {name}: awal={traj[0]} t10={traj[9]} t20={traj[19]} "
              f"t40={traj[39]} max={max(traj):.3f}", flush=True)

    print("== 4. ablasi sustain @0.50 (director, n=12) ==", flush=True)
    with mp.Pool(4) as pool:
        jobs4 = [(v, p, 9000 + i)
                 for v in ("base", "rest0", "norefill", "npot2")
                 for p in POLICIES for i in range(12)]
        res4 = pool.map(_t4, jobs4, chunksize=4)
    with open(outdir / "diag_ablation.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["variant", "policy", "seed",
                                          "order", "k", "prog", "clear"])
        w.writeheader()
        for r in res4:
            w.writerow({k: r[k] for k in
                        ("variant", "policy", "seed", "order", "k", "prog",
                         "clear")})
    for v in ("base", "rest0", "norefill", "npot2"):
        for p in POLICIES:
            sel = [r for r in res4 if r["variant"] == v and r["policy"] == p]
            print(f"--- {v:8s} {p:6s}: clear="
                  f"{S.mean([r['clear'] for r in sel]):.2f} prog="
                  f"{S.mean([r['prog'] for r in sel]):.2f}", flush=True)

    print("== 5. kriteria @0.50 (dari ablasi base) ==", flush=True)
    for p, lo, hi in (("depth4", 0.25, 0.40), ("greedy", 0.10, 1.01)):
        sel = [r for r in res4 if r["variant"] == "base"
               and r["policy"] == p]
        c = S.mean([r["clear"] for r in sel])
        ok = "LOLOS" if lo <= c <= hi else "GAGAL"
        print(f"--- {p}: clear={c:.2f} vs [{lo},{hi if hi < 1 else '-'}] "
              f"{ok}", flush=True)

    print("== OPSI: 4 tuas tunggal (sedang, greedy+d4, N=2, 300 antrean) ==",
          flush=True)
    with mp.Pool(4) as pool:
        jobso = [(lv, qi, slots[qi], p, 2000 + qi * 2)
                 for lv in ("base", "rest15", "refill1", "npot2", "bossup")
                 for qi in range(len(queues)) for p in ("greedy", "depth4")]
        reso = pool.map(_topt, jobso, chunksize=8)
        feels = pool.map(_feel, [(r, lv) for r in ROLES7
                                 for lv in ("base", "rest15", "refill1",
                                            "npot2", "bossup")],
                         chunksize=4)
    with open(outdir / "diag_options.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["lever", "qi", "policy", "prog", "clear"])
        for lv, qi, p, prog, clear in reso:
            w.writerow([lv, qi, p, prog, clear])
    for lv in ("base", "rest15", "refill1", "npot2", "bossup"):
        for p in ("greedy", "depth4"):
            ps = [prog for l, _, q, prog, _ in reso if l == lv and q == p]
            cs = [c for l, _, q, _, c in reso if l == lv and q == p]
            low = sum(1 for v in ps if v <= 0.5) / len(ps) * 100
            print(f"--- {lv:8s} {p:6s}: med={S.median(ps):.2f} "
                  f"clear={S.mean(cs):.2f} gagal<={low:.0f}%", flush=True)
    print("-- rasa main 1v1 depth4 (win/plies/lost):", flush=True)
    for r in ROLES7:
        line = f"  {r:8s} " + " ".join(
            f"{lv}={w}/{n}/{l}" for rr, lv, w, n, l in feels if rr == r)
        print(line, flush=True)
    print(f"SELESAI ({time.perf_counter() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
