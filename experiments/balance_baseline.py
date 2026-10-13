"""experiments/balance_baseline.py - Baseline balance peran (Langkah 0).

7 peran x 6 item x 3 loadout x 3 kebijakan, seed tetap. Keluar: tabel
win-rate 1v1, panjang duel, HP hilang + noise + cek slot_to_buff.
Hanya membaca tabel tahap 3; tidak mengubah kode.

Jalan: `python3 experiments/balance_baseline.py` (~12 mnt).
"""
from __future__ import annotations

import random
import statistics as S
import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, str(Path(ROOT) / "experiments"))

from adversarial_ai import ATTACK_MAX, ATTACK_MIN, MAX_HP  # noqa: E402
from game.ambush.buff_ai import (  # noqa: E402
    BuffAwareAI,
    BuffBattleState,
    apply_chip_hook,
)
from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.enemy_queue import EnemySlot, enemy_max_hp, slot_to_buff  # noqa: E402
from game.ambush.player_loadout import PlayerLoadout, loadout_to_buff  # noqa: E402
from game.ambush.types import ITEM_TABLE, ROLE_TABLE  # noqa: E402

CFG = AmbushConfig()
ROLES = ["Warrior", "Tank", "Healer", "Archer", "Mage", "Boss", "Minion"]
ITEMS = list(ITEM_TABLE)
LOADOUTS = {
    "lemah": PlayerLoadout(items=("NONE", "NONE")),
    "sedang": PlayerLoadout(items=("Iron Sword", "Heavy Shield")),
    "kuat": PlayerLoadout(items=("Dragon Fang", "Heavy Shield")),
}
N_FAST, N_DEEP = 20, 6


def greedy(ai, state, is_npc):
    """Delegasi ke policies.greedy_action (satu sumber, anti-typo)."""
    from game.ambush.policies import greedy_action as _g
    return _g(ai, state, is_npc)


def play(role, item, pl, policy, seed, games, cfg=None,
         duels_left: int = 0, duel_last: bool = True):
    """Satu sel: (win rate player, plies, fraksi HP hilang)."""
    cfg = cfg or CFG
    from game.ambush.policies import think_policy as _tp
    eb = slot_to_buff(EnemySlot(role, item), cfg)
    pbuff = loadout_to_buff(pl, cfg)
    pmax = MAX_HP + pbuff.hp
    rng = random.Random(seed)
    wins, plies, lost = 0, [], []
    depth = 4 if policy == "depth4" else 1
    for _ in range(games):
        state = BuffBattleState(player_hp=pmax,
                                npc_hp=enemy_max_hp(eb, cfg.enemy_base_hp),
                                turn=0, buff=eb, player_buff=pbuff)
        state.npc_potions = cfg.npc_starting_potions
        ai_n = BuffAwareAI(depth=depth, buff=eb, player_buff=pbuff)
        ai_p = BuffAwareAI(depth=depth, buff=eb, player_buff=pbuff)
        n = 0
        for _ in range(80):
            if state.is_terminal():
                break
            is_npc = state.turn == 1
            if policy == "depth4":
                a = (ai_n if is_npc else ai_p).think(
                    state, run_baseline=False,
                    root_is_npc=is_npc)["best_action"]
            else:
                a = _tp(ai_n if is_npc else ai_p, state, is_npc, policy,
                        duel_last, duels_left, pmax)
            if a is None:
                break
            dmg = rng.randint(ATTACK_MIN, ATTACK_MAX) if a == "ATTACK" \
                else None
            state = state.apply_action(
                is_npc, a, **({"attack_damage": dmg} if dmg else {}))
            apply_chip_hook(state, eb)
            n += 1
        wins += state.npc_hp <= 0 < state.player_hp
        plies.append(n)
        lost.append((pmax - max(0, state.player_hp)) / pmax)
    return wins / games, sum(plies) / len(plies), sum(lost) / len(lost)


def main():
    # Pengaman kelas bug: greedy harus bisa memilih non-ATTACK (pernah
    # typo `key < key` membuatnya selalu ATTACK pertama).
    _s0 = BuffBattleState(player_hp=MAX_HP, npc_hp=110, turn=0,
                          buff=slot_to_buff(EnemySlot("Warrior", "NONE"),
                                            CFG),
                          player_buff=loadout_to_buff(
                              LOADOUTS["sedang"], CFG))
    _ai = BuffAwareAI(depth=1, buff=slot_to_buff(
        EnemySlot("Warrior", "NONE"), CFG))
    assert greedy(_ai, _s0, False) == "SPECIAL", "greedy rusak"
    print("pengaman greedy ok (pilih SPECIAL di awal)", flush=True)
    # slot_to_buff == angka battle: jumlahkan manual per kombinasi.
    for r in ROLES:
        for it in ITEMS:
            b = slot_to_buff(EnemySlot(r, it), CFG)
            rs, its = ROLE_TABLE[r], ITEM_TABLE[it]
            assert (b.hp, b.atk, b.regen, b.chip) == (
                rs.hp + its.hp, rs.atk + its.atk, rs.regen + its.regen,
                rs.chip + its.chip), (r, it)
    print("slot_to_buff konsisten (42 kombinasi)", flush=True)
    print("peran,item,loadout,policy,win,plies,hp_hilang", flush=True)
    for role in ROLES:
        for item in ITEMS:
            for loname, pl in LOADOUTS.items():
                for policy, games in (("greedy", N_FAST),
                                      ("conserve", N_FAST),
                                      ("depth4", N_DEEP)):
                    w, n, l = play(role, item, pl, policy, 5, games)
                    print(f"{role},{item},{loname},{policy},{w:.2f},"
                          f"{n:.1f},{l:.2f}", flush=True)
    # Noise: 6 sel x seed 5,6,7.
    print("--- noise (win rate, 3 seed) ---", flush=True)
    for role, item, loname, policy in (
            ("Tank", "NONE", "sedang", "greedy"),
            ("Healer", "NONE", "sedang", "greedy"),
            ("Boss", "NONE", "sedang", "depth4"),
            ("Minion", "NONE", "sedang", "greedy"),
            ("Warrior", "Iron Sword", "sedang", "greedy"),
            ("Mage", "NONE", "kuat", "depth4")):
        ws = [play(role, item, LOADOUTS[loname], policy, sd,
                   N_DEEP)[0] for sd in (5, 6, 7)]
        print(f"{role}/{item}/{loname}/{policy}: {ws} "
              f"spread={max(ws) - min(ws):.2f}", flush=True)


if __name__ == "__main__":
    main()
