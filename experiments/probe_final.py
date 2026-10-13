"""experiments/probe_final.py - Probe pelengkap laporan FINAL (kode terkunci).

(a) K5-030: 150 antrean, ChainSim N=6, sedang: % dalam +-0.15 dari 0.30 +
    desil distribusi (apakah 0.30 terjangkau? gov_min/target_cycle TAK diubah).
(b) Lintasan adaptif: 20 pertemuan berantai (governor dipakai ulang),
    greedy + depth4, sedang: target/hasil/progres per pertemuan.
Jalan: `python3 experiments/probe_final.py` (~3 mnt).
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

from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.player_loadout import PlayerLoadout  # noqa: E402

CFG = AmbushConfig()
PL = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))


def part_a():
    from fit_queue import sample_queues
    from game.ambush.chain_eval import ChainSim
    queues = sample_queues(150, seed=31337)
    sim = ChainSim(CFG, PL, seed=5, games=6)
    vals = sorted(sim.evaluate(qs) for qs in queues)
    for t in (0.30, 0.40, 0.50, 0.80):
        pct = sum(1 for v in vals if abs(v - t) <= 0.15) / len(vals) * 100
        print(f"dalam {t}+-0.15: {pct:.1f}%", flush=True)
    qs = [0, 10, 25, 50, 75, 90, 100]
    print("persentil:",
          {f"p{q}": round(vals[min(149, int(q / 100 * 150))], 3) for q in qs},
          flush=True)


def part_b():
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "autoplay_pb", str(Path(ROOT) / "experiments" / "autoplay.py"))
    ap = _ilu.module_from_spec(_spec)
    sys.modules["autoplay_pb"] = ap
    _spec.loader.exec_module(ap)
    from game.ambush.director import AmbushDirector
    from game.ambush.flow.queue_driver import QueueRun
    from game.ambush.governor import DifficultyGovernor
    from game.ambush.player_loadout import loadout_to_buff
    from game.ambush.buff_ai import (BuffAwareAI, BuffBattleState,
                                     apply_chip_hook)
    from game.ambush.chain_eval import carry_potions
    from game.ambush.enemy_queue import enemy_max_hp, slot_to_buff
    from adversarial_ai import ATTACK_MAX, ATTACK_MIN, MAX_HP
    for policy in ("greedy", "depth4"):
        ap._POLICY = policy
        gov = DifficultyGovernor(CFG)
        traj = []
        for m in range(20):
            director = AmbushDirector(CFG, gov, base_seed=3100 + m)
            res = director.plan_queue(0, gov.target, PL)
            pbuff = loadout_to_buff(PL, CFG)
            cap = MAX_HP + pbuff.hp
            run = QueueRun(queue=res.queue, buffs=list(res.buffs),
                           target=res.target, pred_light=res.light,
                           pred_full=res.sim_difficulty, hp=cap, potions=3,
                           cap=cap, cfg=CFG)
            rng = random.Random(6100 + m)
            k = run.queue.k()
            status = "failed"
            for di, (slot, buff) in enumerate(
                    zip(run.queue.slots, run.buffs)):
                st = BuffBattleState(player_hp=run.hp,
                                     npc_hp=enemy_max_hp(
                                         buff, CFG.enemy_base_hp), turn=0,
                                     buff=buff, player_buff=pbuff)
                st.player_potions = run.potions
                st.npc_potions = CFG.npc_starting_potions
                depth = 4 if policy == "depth4" else 1
                ai_n = BuffAwareAI(depth=depth, buff=buff, player_buff=pbuff)
                ai_p = BuffAwareAI(depth=depth, buff=buff, player_buff=pbuff)
                last = di == k - 1
                for _ in range(CFG.sim_max_plies):
                    if st.is_terminal():
                        break
                    is_npc = st.turn == 1
                    a = ap.think_policy(ai_n if is_npc else ai_p, st, is_npc,
                                        False, last, k - 1 - di, cap)
                    if a is None:
                        break
                    dmg = rng.randint(ATTACK_MIN, ATTACK_MAX) \
                        if a == "ATTACK" else None
                    kw = ({"attack_damage": dmg} if dmg is not None else {})
                    st = st.apply_action(is_npc, a, **kw)
                    apply_chip_hook(st, buff)
                status = run.record(max(0, st.player_hp), st.player_potions,
                                    st.npc_hp <= 0)
                if status != "next":
                    break
            won = status == "won_all"
            gov.update("player" if won else "npc", run.margin(),
                       progress=run.progress(),
                       failed_at=None if won else run.failed_at + 1)
            traj.append((round(gov.target, 3), won, round(run.progress(), 2)))
        print(f"lintasan {policy}: " +
              " ".join(f"t{t}{'W' if w else 'L'}{p}" for t, w, p in traj),
              flush=True)


if __name__ == "__main__":
    print("== (a) K5 + 0.30 ==", flush=True)
    part_a()
    print("== (b) lintasan adaptif ==", flush=True)
    part_b()
