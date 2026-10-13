"""experiments/autoplay.py - N pertemuan headless untuk battle_result.csv.

Pemain = greedy 1-ply (cermin sim ringan) agar progres aktual bisa
dibandingkan dengan prediksi (MAE). Seed tetap -> reproducible.
Jalur angka (slot_to_buff, QueueRun.record, apply_rest) SAMA dengan game.

Jalan: `python3 experiments/autoplay.py [--n 30] [--seed 99]`
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from adversarial_ai import ATTACK_MAX, ATTACK_MIN, MAX_HP  # noqa: E402
from game.ambush.buff_ai import (  # noqa: E402
    BuffAwareAI,
    BuffBattleState,
    apply_chip_hook,
)
from game.ambush.chain_eval import apply_rest  # noqa: E402
from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.csv_export import append_battle_result  # noqa: E402
from game.ambush.director import AmbushDirector  # noqa: E402
from game.ambush.enemy_queue import enemy_max_hp, slot_to_buff  # noqa: E402
from game.ambush.flow.queue_driver import QueueRun  # noqa: E402
from game.ambush.governor import DifficultyGovernor  # noqa: E402
from game.ambush.player_loadout import PlayerLoadout, loadout_to_buff  # noqa: E402

CFG = AmbushConfig()
OUT = str(Path(ROOT) / "data" / "battle_result.csv")


def greedy(ai: BuffAwareAI, state: BuffBattleState,
           is_npc: bool) -> str | None:
    """Delegasi ke policies.greedy_action (satu sumber, anti-typo)."""
    from game.ambush.policies import greedy_action as _g
    return _g(ai, state, is_npc)


def think_policy(ai: BuffAwareAI, state: BuffBattleState,
                   is_npc: bool, conserve: bool, duel_last: bool,
                   duels_left: int = 0, max_hp: int = 100):
    """Delegasi ke policies.think_policy (hemat-baru + cadangan antrean)."""
    from game.ambush.policies import think_policy as _tp
    global _POLICY
    policy = "depth4" if _POLICY == "depth4" else (
        "conserve" if conserve else "greedy")
    # _POLICY depth4 menang atas flag conserve (jalur autoplay lama).
    if _POLICY == "depth4":
        policy = "depth4"
    return _tp(ai, state, is_npc, policy, duel_last, duels_left, max_hp)


_POLICY = "greedy"


def play_meeting(run_id: int, seed: int, loadout: PlayerLoadout,
                 policy: str = "greedy") -> dict:
    """Susun (director) + mainkan satu pertemuan; kembalikan baris."""
    global _POLICY
    _POLICY = policy
    cfg, gov = AmbushConfig(), DifficultyGovernor(AmbushConfig())
    director = AmbushDirector(cfg, gov, base_seed=seed)
    res = director.plan_queue(0, gov.target, loadout)
    pbuff = loadout_to_buff(loadout, cfg)
    cap = MAX_HP + pbuff.hp
    run = QueueRun(queue=res.queue, buffs=list(res.buffs),
                   target=res.target, pred_light=res.light,
                   pred_full=res.sim_difficulty, hp=cap, potions=3,
                   cap=cap, cfg=cfg)
    rng = random.Random(1000 + seed)
    k = run.queue.k()
    for di, (slot, buff) in enumerate(zip(run.queue.slots, run.buffs)):
        state = BuffBattleState(player_hp=run.hp,
                                npc_hp=enemy_max_hp(buff, cfg.enemy_base_hp),
                                turn=0, buff=buff, player_buff=pbuff)
        state.player_potions = run.potions
        state.npc_potions = cfg.npc_starting_potions
        depth = 4 if policy == "depth4" else 1
        ai_n = BuffAwareAI(depth=depth, buff=buff, player_buff=pbuff)
        ai_p = BuffAwareAI(depth=depth, buff=buff, player_buff=pbuff)
        last = slot == run.queue.slots[-1]
        for _ in range(cfg.sim_max_plies):
            if state.is_terminal():
                break
            is_npc = state.turn == 1
            a = think_policy(ai_n if is_npc else ai_p, state, is_npc,
                             policy == "conserve", last,
                             k - 1 - di, MAX_HP + pbuff.hp)
            if a is None:
                break
            dmg = rng.randint(ATTACK_MIN, ATTACK_MAX) if a == "ATTACK" \
                else None
            kw = {"attack_damage": dmg} if dmg is not None else {}
            state = state.apply_action(is_npc, a, **kw)
            apply_chip_hook(state, buff)
        status = run.record(max(0, state.player_hp), state.player_potions,
                            state.npc_hp <= 0)
        if status != "next":
            break
    won = status == "won_all"
    gov.update("player" if won else "npc", run.margin(),
               progress=run.progress(),
               failed_at=None if won else run.failed_at + 1)
    return run.result_row(9000 + run_id, "menang" if won else "kalah")


_LOADOUTS = {
    "lemah": ("NONE", "NONE"),
    "sedang": ("Iron Sword", "Heavy Shield"),
    "kuat": ("Dragon Fang", "Heavy Shield"),
}


def main(n: int, seed: int, policy: str = "greedy", target: float = 0.5,
         loadout_name: str = "sedang"):
    from game.ambush.governor import DifficultyGovernor
    loadout = PlayerLoadout(items=_LOADOUTS[loadout_name])
    gov = DifficultyGovernor(AmbushConfig())
    gov.target = min(max(target, gov.cfg.gov_min), gov.cfg.gov_max)
    rows = []
    for i in range(n):
        row = play_meeting(i, seed + i, loadout, policy)
        row["target"] = round(gov.target, 4)
        rows.append(row)
    for row in rows:
        append_battle_result(row, OUT)
    wins = sum(1 for r in rows if r["hasil"] == "menang")
    prog = sum(r["actual_progress"] for r in rows) / max(1, len(rows))
    print(f"{n} pertemuan: menang {wins} ({wins / max(1, n) * 100:.0f}%), "
          f"progres rata-rata {prog:.3f} -> {OUT}")
    return rows


if __name__ == "__main__":
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 30
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) \
        if "--seed" in sys.argv else 99
    policy = sys.argv[sys.argv.index("--policy") + 1] \
        if "--policy" in sys.argv else "greedy"
    main(n, seed, policy)
