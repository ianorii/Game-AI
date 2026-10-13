"""experiments/measure_R.py - Langkah R: stat peran setengah-langkah (maks 3 putaran).

Mengukur K1/K2 (1v1), K6 (delta item depth-4 N=20), K5 (jangkauan 150 antrean),
K4-autoplay (3 kebijakan x 3 target x 3 loadout), solvabilitas CSP 20x3 +
keragaman, untuk SATU paket stat + config sustain.

Paket diberikan sebagai JSON: {"roles": {nama: {field: val}}, "items": {...},
"config": {"rest_heal_pct":.., "npc_starting_potions":.., "potion_bonus_per_duel":..}}.
Tanpa argumen = baseline kode saat ini (P0).

Whitelist: hanya stat peran/item, cost (bila tak sebanding; tak bersamaan
dengan stat peran sama), regen/chip cap, npc_starting_potions, rest_heal_pct,
player potion bonus. DILARANG: stat dasar player, kode tahap 2, target_cycle,
gov_min, budget tanpa persetujuan.

Jalan: `python3 experiments/measure_R.py [paket.json] [--quick] [--tag P0]`
Keluar: data/results/langkah_R_<tag>.csv + ringkasan stdout.
"""
from __future__ import annotations

import csv
import json
import multiprocessing as mp
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
ROLES = ["Warrior", "Tank", "Healer", "Archer", "Mage", "Boss", "Minion"]
POLICIES = ("greedy", "hemat", "depth4")
LOADOUTS = {
    "lemah": PlayerLoadout(items=("NONE", "NONE")),
    "sedang": PlayerLoadout(items=("Iron Sword", "Heavy Shield")),
    "kuat": PlayerLoadout(items=("Dragon Fang", "Heavy Shield")),
}
ITEMS = ["NONE", "Iron Sword", "Heavy Shield", "Swift Boots",
         "Healing Charm", "Dragon Fang"]
SEEDS20 = list(range(100, 120))
_PKG = None
_CFG = CFG


def apply_package(pkg: dict | None):
    """Terapkan override stat peran/item ke tabel modul (per worker)."""
    global _CFG
    if not pkg:
        _CFG = CFG
        return
    from game.ambush import types as T
    for name, fields in (pkg.get("roles") or {}).items():
        T.ROLE_TABLE[name] = replace(T.ROLE_TABLE[name], **fields)
    for name, fields in (pkg.get("items") or {}).items():
        T.ITEM_TABLE[name] = replace(T.ITEM_TABLE[name], **fields)
    c = pkg.get("config") or {}
    _CFG = replace(CFG,
                   rest_heal_pct=c.get("rest_heal_pct", CFG.rest_heal_pct),
                   npc_starting_potions=c.get("npc_starting_potions",
                                              CFG.npc_starting_potions),
                   potion_bonus_per_duel=c.get("potion_bonus_per_duel",
                                               CFG.potion_bonus_per_duel))


def _init(pkg_json):
    apply_package(json.loads(pkg_json) if pkg_json else None)


def _k1(task):
    role, policy, seeds = task
    from balance_baseline import play
    ws, ns, ls = [], [], []
    for sd in seeds:
        w, n, lost = play(role, "NONE", LOADOUTS["sedang"], policy, sd, 1,
                           _CFG)
        ws.append(w)
        ns.append(n)
        ls.append(lost)
    h = len(ws) // 2
    sp = abs(S.mean(ws[:h]) - S.mean(ws[h:])) if h else 0.0
    return (S.mean(ws), S.mean(ns), S.mean(ls), sp)


def _k6(task):
    role, item, seeds = task
    from balance_baseline import play
    ws = [play(role, item, LOADOUTS["sedang"], "depth4", sd, 1, _CFG)[0]
          for sd in seeds]
    return S.mean(ws)


def _range(task):
    qi, seeds_games = task
    return None  # diisi di main (butuh queues bersama)


def main(tag: str, pkg, quick: bool = False):
    seeds = SEEDS20 if not quick else SEEDS20[:6]
    t0 = time.perf_counter()
    pkg_json = json.dumps(pkg) if pkg else ""
    out = Path(ROOT) / "data" / "results" / f"langkah_R_{tag}.csv"
    rows: list = []
    with mp.Pool(4, initializer=_init, initargs=(pkg_json,)) as pool:
        print(f"== [{tag}] K1/K2 1v1 (N={len(seeds)}) ==", flush=True)
        jobs = [(r, p, seeds) for r in ROLES for p in POLICIES]
        for (r, p, _), (w, n, lost, sp) in zip(
                jobs, pool.map(_k1, jobs, chunksize=2)):
            rows.append({"tag": tag, "kind": "K1", "role": r, "policy": p,
                         "item": "NONE", "win": round(w, 3),
                         "plies": round(n, 1), "hp_lost": round(lost, 3),
                         "spread": round(sp, 3), "extra": ""})
            print(f"   {r:8s} {p:6s} win={w:.2f}(+-{sp:.2f}) plies={n:.1f} "
                  f"lost={lost:.2f}", flush=True)
        print(f"== [{tag}] K6 delta item depth-4 (N={len(seeds)}) ==",
              flush=True)
        jobs = [(r, it, seeds) for r in ROLES for it in ITEMS]
        res = pool.map(_k6, jobs, chunksize=2)
        base = {}
        for (r, it, _), w in zip(jobs, res):
            base.setdefault(r, {})[it] = w
        for r in ROLES:
            worst = max(abs(base[r][it] - base[r]["NONE"]) for it in ITEMS
                        if it != "NONE")
            fang = base[r]["Dragon Fang"] - base[r]["NONE"]
            flag = "OK " if worst <= 0.50 else "LEBIH"
            rows.append({"tag": tag, "kind": "K6", "role": r, "policy":
                         "depth4", "item": "worst-delta",
                         "win": round(worst, 3), "plies": "",
                         "hp_lost": "", "spread": "",
                         "extra": f"fang={fang:+.2f}"})
            print(f"   {flag} {r:8s} worst-delta={worst:.2f} fang={fang:+.2f} "
                  f"base={base[r]['NONE']:.2f}", flush=True)
    # K5 + K4 + CSP di proses utama (butuh director/sim, tetap CRN).
    apply_package(pkg)
    cfg = _CFG
    print(f"== [{tag}] K5 jangkauan (150 antrean, sedang) ==", flush=True)
    from fit_queue import sample_queues
    from game.ambush.chain_eval import ChainSim
    queues = sample_queues(150, seed=31337)
    sim = ChainSim(cfg, LOADOUTS["sedang"], seed=5, games=6)
    vals = [sim.evaluate(qs) for qs in queues]
    for tgt in (0.40, 0.50, 0.80):
        pct = sum(1 for v in vals if abs(v - tgt) <= 0.15) / len(vals) * 100
        rows.append({"tag": tag, "kind": "K5", "role": "sedang",
                     "policy": f"t={tgt}", "item": "", "win": round(pct, 1),
                     "plies": "", "hp_lost": "",
                     "spread": "", "extra": f"med={S.median(vals):.3f}"})
        print(f"   target {tgt}: dalam+-0.15 = {pct:.1f}% "
              f"(med={S.median(vals):.3f})", flush=True)
    print(f"== [{tag}] K4 autoplay 3x3x3 (n=8/sel) ==", flush=True)
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "autoplay_R", str(Path(ROOT) / "experiments" / "autoplay.py"))
    ap = _ilu.module_from_spec(_spec)
    sys.modules["autoplay_R"] = ap
    _spec.loader.exec_module(ap)
    import random as _r
    from game.ambush.director import AmbushDirector
    from game.ambush.flow.queue_driver import QueueRun
    from game.ambush.governor import DifficultyGovernor
    from game.ambush.player_loadout import loadout_to_buff
    from game.ambush.buff_ai import (BuffAwareAI, BuffBattleState,
                                     apply_chip_hook)
    from game.ambush.enemy_queue import enemy_max_hp, slot_to_buff
    from adversarial_ai import ATTACK_MAX, ATTACK_MIN, MAX_HP
    for loname, pl in LOADOUTS.items():
        for tgt in (0.40, 0.50, 0.80):
            for policy in ("greedy", "hemat", "depth4"):
                wins, progs, entries = 0, [], {i: [] for i in range(4)}
                nn = 8 if not quick else 3
                for i in range(nn):
                    ap._POLICY = policy
                    gov = DifficultyGovernor(cfg)
                    gov.target = tgt
                    director = AmbushDirector(cfg, gov, base_seed=7000 + i)
                    res = director.plan_queue(0, gov.target, pl)
                    pbuff = loadout_to_buff(pl, cfg)
                    cap = MAX_HP + pbuff.hp
                    run = QueueRun(queue=res.queue, buffs=list(res.buffs),
                                   target=res.target, pred_light=res.light,
                                   pred_full=res.sim_difficulty, hp=cap,
                                   potions=3, cap=cap, cfg=cfg)
                    rng = _r.Random(9000 + i)
                    k = run.queue.k()
                    status = "failed"
                    for di, (slot, buff) in enumerate(
                            zip(run.queue.slots, run.buffs)):
                        entries[di].append(run.hp / cap)
                        st = BuffBattleState(
                            player_hp=run.hp,
                            npc_hp=enemy_max_hp(buff, cfg.enemy_base_hp),
                            turn=0, buff=buff, player_buff=pbuff)
                        st.player_potions = run.potions
                        st.npc_potions = cfg.npc_starting_potions
                        depth = 4 if policy == "depth4" else 1
                        ai_n = BuffAwareAI(depth=depth, buff=buff,
                                           player_buff=pbuff)
                        ai_p = BuffAwareAI(depth=depth, buff=buff,
                                           player_buff=pbuff)
                        last = di == k - 1
                        for _ in range(cfg.sim_max_plies):
                            if st.is_terminal():
                                break
                            is_npc = st.turn == 1
                            a = ap.think_policy(
                                ai_n if is_npc else ai_p, st, is_npc,
                                policy == "conserve", last, k - 1 - di,
                                cap)
                            if a is None:
                                break
                            dmg = rng.randint(ATTACK_MIN, ATTACK_MAX) \
                                if a == "ATTACK" else None
                            kw = ({"attack_damage": dmg}
                                  if dmg is not None else {})
                            st = st.apply_action(is_npc, a, **kw)
                            apply_chip_hook(st, buff)
                        status = run.record(max(0, st.player_hp),
                                            st.player_potions,
                                            st.npc_hp <= 0)
                        if status != "next":
                            break
                    wins += status == "won_all"
                    progs.append(run.progress())
                hp_in = ";".join(
                    f"d{i}={S.mean(v):.2f}" if v else f"d{i}=-"
                    for i, v in entries.items())
                rows.append({"tag": tag, "kind": "K4", "role": loname,
                             "policy": f"{policy}/t={tgt}", "item": "",
                             "win": round(wins / nn, 3),
                             "plies": round(S.mean(progs), 3),
                             "hp_lost": "", "spread": "", "extra": hp_in})
                print(f"   {loname:6s} {policy:6s} t={tgt}: clear="
                      f"{wins / nn:.2f} prog={S.mean(progs):.2f} [{hp_in}]",
                      flush=True)
    print(f"== [{tag}] CSP 20x3 + keragaman ==", flush=True)
    from collections import Counter
    from game.ambush.csp_solver import CSPSolver, squad_problem
    from game.ambush.enemy_queue import (is_queue_valid, queue_from_assign)
    for tgt in (0.40, 0.50, 0.80):
        ok, r1, uniq, minim = 0, Counter(), set(), 0
        for seed in range(20):
            prob = squad_problem(
                0, cfg.budget_q_for(tgt), cfg, **cfg.csp_flags())
            sol, _ = CSPSolver(prob, seed=seed).solve()
            assert sol is not None, (tgt, seed)
            q = queue_from_assign(sol, cfg)
            ok += is_queue_valid(q, 0, cfg.budget_q_for(tgt), cfg)
            r1[q.slots[0].role] += 1
            uniq.add(q.key())
            minim += sum(1 for x in q.slots if x.role == "Minion")
        top = r1.most_common(1)[0]
        rows.append({"tag": tag, "kind": "CSP", "role": f"t={tgt}",
                     "policy": "", "item": "", "win": f"{ok}/20",
                     "plies": f"unik={len(uniq)}", "hp_lost": "",
                     "spread": "",
                     "extra": f"ROLE_1max={top[0]}={top[1]} minion={minim}"})
        print(f"   t={tgt}: valid={ok}/20 unik={len(uniq)}/20 "
              f"ROLE_1max={top[0]}={top[1]} minion={minim}", flush=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"ditulis {out} ({time.perf_counter() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    tag = "P0"
    pkg = None
    for a in args:
        if a.endswith(".json"):
            pkg = json.load(open(a, encoding="utf-8"))
        else:
            tag = a
    main(tag, pkg, "--quick" in sys.argv)
