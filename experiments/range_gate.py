"""experiments/range_gate.py - Gerbang jangkauan Fase 3-ulang Langkah 1.

300 antrean valid BERAGAM x 3 loadout (lemah/sedang/kuat), ChainSim N=8
objektif progres. Lapor per loadout: min/median/max, histogram, % dalam
+-0.15 tiap target + otopsi duel-1 (potion habis) & duel-2 (mengapa kalah).

Jalan: `python3 experiments/range_gate.py` (~10 mnt). Syarat lolos: pada
loadout sedang, >=10% dalam +-0.15 dari TIAP target 0.3/0.5/0.8.
"""
from __future__ import annotations

import random
import statistics as S
import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.ambush.chain_eval import ChainSim  # noqa: E402
from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.enemy_queue import EnemyQueue, EnemySlot, is_queue_valid  # noqa: E402
from game.ambush.player_loadout import PlayerLoadout  # noqa: E402
from game.ambush.types import ITEM_TABLE, ROLE_TABLE  # noqa: E402

sys.path.insert(0, str(Path(ROOT) / "experiments"))
from fit_queue import sample_queues  # noqa: E402

CFG = AmbushConfig()
LOADOUTS = {
    "lemah": PlayerLoadout(items=("NONE", "NONE")),
    "sedang": PlayerLoadout(items=("Iron Sword", "Heavy Shield")),
    "kuat": PlayerLoadout(items=("Dragon Fang", "Heavy Shield")),
}


def hist(xs, bins=10):
    buckets = [0] * bins
    for x in xs:
        buckets[min(bins - 1, int(x * bins))] += 1
    return buckets


def main():
    queues = sample_queues(300, seed=31337)
    print(f"sampel: {len(queues)} antrean", flush=True)
    for name, pl in LOADOUTS.items():
        sim = ChainSim(CFG, pl, seed=5, games=8)
        vals = [sim.evaluate(q) for q in queues]
        print(f"--- loadout {name}: min={min(vals):.3f} med={S.median(vals):.3f} "
              f"max={max(vals):.3f}", flush=True)
        print(f"    histogram: {hist(vals)}", flush=True)
        for t in (0.3, 0.5, 0.8):
            pct = sum(1 for v in vals if abs(v - t) <= 0.15) / len(vals) * 100
            print(f"    dalam {t}+-0.15: {pct:.1f}%", flush=True)
    # Otopsi: 2xW, loadout sedang - potion duel-1 & duel-2.
    from game.ambush.buff_ai import BuffAwareAI, BuffBattleState, apply_chip_hook
    from game.ambush.chain_eval import carry_potions
    from game.ambush.enemy_queue import enemy_max_hp, slot_to_buff
    from game.ambush.player_loadout import loadout_to_buff
    from adversarial_ai import ATTACK_MIN, ATTACK_MAX, MAX_HP
    pl = LOADOUTS["sedang"]
    pbuff = loadout_to_buff(pl, CFG)
    rng = random.Random(5)
    pot_left, enter2, dmg_round, plies2 = [], [], [], []
    for _ in range(8):
        hp, potions = MAX_HP + pbuff.hp, 3
        for di, slot in enumerate(
                (EnemySlot("Warrior", "NONE"), EnemySlot("Warrior", "NONE"))):
            eb = slot_to_buff(slot, CFG)
            state = BuffBattleState(player_hp=hp,
                                    npc_hp=enemy_max_hp(eb, CFG.enemy_base_hp),
                                    turn=0, buff=eb, player_buff=pbuff)
            state.player_potions = potions
            ai_n = BuffAwareAI(depth=4, buff=eb, player_buff=pbuff, lookahead=3)
            ai_p = BuffAwareAI(depth=4, buff=eb, player_buff=pbuff, lookahead=3)
            hp0, n = hp, 0
            for _ in range(80):
                if state.is_terminal():
                    break
                is_npc = state.turn == 1
                a = (ai_n if is_npc else ai_p).think(
                    state, run_baseline=False, root_is_npc=is_npc)["best_action"]
                if a is None:
                    break
                dmg = rng.randint(ATTACK_MIN, ATTACK_MAX) if a == "ATTACK" else None
                state = state.apply_action(
                    is_npc, a, **({"attack_damage": dmg} if dmg else {}))
                apply_chip_hook(state, eb)
                n += 1
            if di == 0:
                pot_left.append(state.player_potions)
            else:
                enter2.append(hp0)
                if hp0 > 0:
                    dmg_round.append((hp0 - state.player_hp) / max(1, n))
                plies2.append(n)
            hp, potions = state.player_hp, carry_potions(
                state.player_potions, CFG)
    print(f"otopsi 2xW: potion sisa duel-1 = {pot_left}", flush=True)
    print(f"  HP masuk duel-2 = {[round(x) for x in enter2]}", flush=True)
    print(f"  dmg/ply duel-2 = {[round(x, 1) for x in dmg_round]} plies={plies2}",
          flush=True)


if __name__ == "__main__":
    main()
