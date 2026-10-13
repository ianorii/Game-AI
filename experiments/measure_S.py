"""experiments/measure_S.py - Langkah S: sustain dulu, stat musuh BELUM diubah.

Mengukur K1-K3 per peran (7, loadout sedang=item NONE musuh, 3 kebijakan)
untuk tiap kombinasi sustain:
  rest_heal_pct {0, .15, .25, .35} x npc_starting_potions {3,2,1}
  x potion_bonus {0,+1}  — satu per satu lalu kombinasi kecil.

CRN: set seed tetap {100..119} dipakai bersama di SEMUA sel (N=20 untuk
greedy/hemat/depth4; depth-4 minimal N=20 topped). Noise = rentang
antar-blok seed (100-109 vs 110-119); selisih dalam noise bukan alasan.

K1: win rate 1v1 HP penuh. K2: plies. K3: rantai 2x peran sama, depth-4,
HP hilang per duel yang dimenangkan (dengan rest di antaranya).

Jalan: `python3 experiments/measure_S.py [--quick]` (~8 mnt full / ~1 mnt quick).
Keluar: data/results/langkah_S.csv + tabel ringkas ke stdout.
"""
from __future__ import annotations

import csv
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
PL = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
SEEDS = list(range(100, 120))  # CRN: 20 seed bersama semua sel
BLK_A = SEEDS[:10]
BLK_B = SEEDS[10:]

# Tuas satu-per-satu lalu kombinasi kecil (sesuai arahan S).
COMBOS = [
    ("base", 0.00, 3, 0),
    ("npot2", 0.00, 2, 0),
    ("npot1", 0.00, 1, 0),
    ("rest15+n2", 0.15, 2, 0),
    ("rest25+n2", 0.25, 2, 0),
    ("rest35+n2", 0.35, 2, 0),
    ("bonus1+n2", 0.00, 2, 1),
    ("rest25+n1", 0.25, 1, 0),
    ("rest25+n2+b1", 0.25, 2, 1),
]


def _wmean(ws):
    return sum(ws) / len(ws)


def _cell_1v1(task):
    """Satu sel 1v1 -> (win, plies, lost, spread)."""
    role, policy, rest, npot, bonus, seeds = task
    from balance_baseline import play
    cfg = replace(CFG, rest_heal_pct=rest, npc_starting_potions=npot,
                  potion_bonus_per_duel=bonus)
    ws, ns, ls = [], [], []
    for sd in seeds:
        w, n, lost = play(role, "NONE", PL, policy, sd, 1, cfg)
        ws.append(w)
        ns.append(n)
        ls.append(lost)
    # Noise: rentang antar-blok seed.
    half = len(ws) // 2
    spread = abs(_wmean(ws[:half]) - _wmean(ws[half:])) if half else 0.0
    return (_wmean(ws), _wmean(ns), _wmean(ls), spread)


def _cell_chain(task):
    """Rantai 2x peran sama, depth-4 -> HP hilang per duel + win rantai."""
    role, rest, npot, bonus, seeds = task
    import random
    from adversarial_ai import ATTACK_MAX, ATTACK_MIN, MAX_HP
    from game.ambush.buff_ai import (BuffAwareAI, BuffBattleState,
                                     apply_chip_hook)
    from game.ambush.chain_eval import apply_rest, carry_potions
    from game.ambush.enemy_queue import EnemySlot, enemy_max_hp, slot_to_buff
    from game.ambush.player_loadout import loadout_to_buff
    cfg = replace(CFG, rest_heal_pct=rest, npc_starting_potions=npot,
                  potion_bonus_per_duel=bonus)
    pbuff = loadout_to_buff(PL, cfg)
    cap = MAX_HP + pbuff.hp
    losts, chain_wins = [], 0
    for sd in seeds:
        rng = random.Random(sd)
        hp, potions = cap, 3
        ok_all, tot_lost, n_won = True, 0.0, 0
        for di in range(2):
            enter = hp
            eb = slot_to_buff(EnemySlot(role, "NONE"), cfg)
            state = BuffBattleState(player_hp=hp,
                                    npc_hp=enemy_max_hp(eb, cfg.enemy_base_hp),
                                    turn=0, buff=eb, player_buff=pbuff)
            state.player_potions = potions
            state.npc_potions = npot
            ai_n = BuffAwareAI(depth=4, buff=eb, player_buff=pbuff,
                               lookahead=cfg.bew_rounds)
            ai_p = BuffAwareAI(depth=4, buff=eb, player_buff=pbuff,
                               lookahead=cfg.bew_rounds)
            for _ in range(cfg.sim_max_plies):
                if state.is_terminal():
                    break
                is_npc = state.turn == 1
                a = (ai_n if is_npc else ai_p).think(
                    state, run_baseline=False,
                    root_is_npc=is_npc)["best_action"]
                if a is None:
                    break
                dmg = rng.randint(ATTACK_MIN, ATTACK_MAX) \
                    if a == "ATTACK" else None
                kw = {"attack_damage": dmg} if dmg is not None else {}
                state = state.apply_action(is_npc, a, **kw)
                apply_chip_hook(state, eb)
            if state.npc_hp > 0:
                ok_all = False
                break
            tot_lost += (enter - max(0, state.player_hp)) / cap
            n_won += 1
            hp = apply_rest(max(0, state.player_hp), cap, rest)
            potions = carry_potions(state.player_potions, cfg)
            if bonus > 0:
                from adversarial_ai import POTION_LIMIT
                potions = min(POTION_LIMIT, potions + bonus)
        chain_wins += ok_all
        losts.append(tot_lost / max(1, n_won))
    half = len(losts) // 2
    spread = abs(_wmean(losts[:half]) - _wmean(losts[half:])) if half else 0.0
    return (_wmean(losts), chain_wins / len(seeds), spread)


def main(quick: bool = False):
    seeds = SEEDS if not quick else SEEDS[:6]
    t0 = time.perf_counter()
    out = Path(ROOT) / "data" / "results" / "langkah_S.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with mp.Pool(4) as pool:
        for name, rest, npot, bonus in COMBOS:
            print(f"== {name} (rest={rest} npot={npot} bonus={bonus}) ==",
                  flush=True)
            jobs = [(r, p, rest, npot, bonus, seeds)
                    for r in ROLES for p in POLICIES]
            res = pool.map(_cell_1v1, jobs, chunksize=2)
            for (r, p, _, _, _, _), (w, n, lost, sp) in zip(jobs, res):
                rows.append({"combo": name, "kind": "1v1", "role": r,
                             "policy": p, "win": round(w, 3),
                             "plies": round(n, 1),
                             "hp_lost": round(lost, 3),
                             "spread": round(sp, 3),
                             "chain_win": "", "rest": rest, "npot": npot,
                             "bonus": bonus})
                print(f"   {r:8s} {p:6s} win={w:.2f}(+-{sp:.2f}) "
                      f"plies={n:.1f} lost={lost:.2f}", flush=True)
            if not quick or True:  # K3 selalu diukur (inti S)
                cjobs = [(r, rest, npot, bonus, seeds) for r in ROLES]
                cres = pool.map(_cell_chain, cjobs, chunksize=1)
                for r, (lost, cw, sp) in zip(ROLES, cres):
                    rows.append({"combo": name, "kind": "chain2-depth4",
                                 "role": r, "policy": "depth4",
                                 "win": "", "plies": "",
                                 "hp_lost": round(lost, 3),
                                 "spread": round(sp, 3),
                                 "chain_win": round(cw, 3), "rest": rest,
                                 "npot": npot, "bonus": bonus})
                    flag = "OK " if 0.35 <= lost <= 0.60 else "   "
                    print(f"   {flag}{r:8s} chain lost/duel={lost:.2f}"
                          f"(+-{sp:.2f}) chainwin={cw:.2f}", flush=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"ditulis {out} ({time.perf_counter() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main("--quick" in sys.argv)
