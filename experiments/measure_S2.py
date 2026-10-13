"""experiments/measure_S2.py - S lanjutan: K3b rantai realistis + K5 per rest.

K3b: rantai [Minion -> X] (urutan realistis: director gemar Minion di depan),
depth-4, N=20 CRN (seed 100-119): lost duel-1, HP masuk duel-2 (fraksi cap),
lost duel-2 (bagi yang sampai), chainwin. Rest bekerja di antara duel.
K5: 150 antrean, ChainSim N=6, loadout sedang, % dalam +-0.15 tiap target.

Kombinasi: rest {0, .15, .25, .35} x npot=2 (+ rest25+n1 pembanding).
Jalan: `python3 experiments/measure_S2.py` (~4 mnt).
Keluar: data/results/langkah_S2.csv + stdout.
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
ROLES = ["Warrior", "Tank", "Healer", "Archer", "Mage", "Boss"]
PL = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
SEEDS = list(range(100, 120))
COMBOS = [(0.00, 2), (0.15, 2), (0.25, 2), (0.35, 2), (0.25, 1)]


def _chain(task):
    role, rest, npot, seeds = task
    import random
    from adversarial_ai import ATTACK_MAX, ATTACK_MIN, MAX_HP
    from game.ambush.buff_ai import (BuffAwareAI, BuffBattleState,
                                     apply_chip_hook)
    from game.ambush.chain_eval import apply_rest, carry_potions
    from game.ambush.enemy_queue import EnemySlot, enemy_max_hp, slot_to_buff
    from game.ambush.player_loadout import loadout_to_buff
    cfg = replace(CFG, rest_heal_pct=rest, npc_starting_potions=npot)
    pbuff = loadout_to_buff(PL, cfg)
    cap = MAX_HP + pbuff.hp
    d1, ent2, d2, cw = [], [], [], 0
    n2 = 0
    for sd in seeds:
        rng = random.Random(sd)
        hp, potions = cap, 3
        ok = True
        for di, rn in enumerate(("Minion", role)):
            enter = hp
            eb = slot_to_buff(EnemySlot(rn, "NONE"), cfg)
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
                ok = False
                break
            loss = (enter - max(0, state.player_hp)) / cap
            if di == 0:
                d1.append(loss)
            else:
                d2.append(loss)
                n2 += 1
            hp = apply_rest(max(0, state.player_hp), cap, rest)
            if di == 0:
                ent2.append(hp / cap)
            potions = carry_potions(state.player_potions, cfg)
        cw += ok
    return (S.mean(d1), S.mean(ent2), S.mean(d2) if d2 else 0.0,
            cw / len(seeds), n2)


def main():
    t0 = time.perf_counter()
    out = Path(ROOT) / "data" / "results" / "langkah_S2.csv"
    rows = []
    with mp.Pool(4) as pool:
        for rest, npot in COMBOS:
            print(f"== rest={rest} npot={npot} (K3b Minion->X, N=20) ==",
                  flush=True)
            jobs = [(r, rest, npot, SEEDS) for r in ROLES]
            for r, (d1, e2, d2, cw, n2) in zip(
                    ROLES, pool.map(_chain, jobs, chunksize=1)):
                ok = "OK " if 0.35 <= d2 <= 0.60 else "   "
                rows.append({"rest": rest, "npot": npot, "role": r,
                             "d1_lost": round(d1, 3),
                             "enter2": round(e2, 3),
                             "d2_lost": round(d2, 3),
                             "chainwin": round(cw, 3), "n2": n2,
                             "k5_040": "", "k5_050": "", "k5_080": ""})
                print(f"   {ok}{r:8s} d1lost={d1:.2f} enter2={e2:.2f} "
                      f"d2lost={d2:.2f}(n={n2}) chainwin={cw:.2f}",
                      flush=True)
    # K5 per rest (proses utama, sim sekali per rest).
    from fit_queue import sample_queues
    from game.ambush.chain_eval import ChainSim
    queues = sample_queues(150, seed=31337)
    for rest, npot in COMBOS:
        cfg = replace(CFG, rest_heal_pct=rest, npc_starting_potions=npot)
        sim = ChainSim(cfg, PL, seed=5, games=6)
        vals = [sim.evaluate(qs) for qs in queues]
        cov = {t: sum(1 for v in vals if abs(v - t) <= 0.15) / len(vals) * 100
               for t in (0.40, 0.50, 0.80)}
        print(f"K5 rest={rest} npot={npot}: med={S.median(vals):.3f} "
              f"near40={cov[0.40]:.0f}% near50={cov[0.50]:.0f}% "
              f"near80={cov[0.80]:.0f}%", flush=True)
        for r in rows:
            if r["rest"] == rest and r["npot"] == npot and r["role"] == "Warrior":
                r["k5_040"] = round(cov[0.40], 1)
                r["k5_050"] = round(cov[0.50], 1)
                r["k5_080"] = round(cov[0.80], 1)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"ditulis {out} ({time.perf_counter() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
