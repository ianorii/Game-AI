"""tests/test_ambush_prep.py - Tes fase persiapan + HUD (Tahap 3 lanjutan).

Jalan: `python3 tests/test_ambush_prep.py` (headless, tanpa pygame display).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from game.ambush.buff import squad_to_buff  # noqa: E402
from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.difficulty import HeuristicEvaluator  # noqa: E402
from game.ambush.flow.prep_state_machine import (  # noqa: E402
    check_sequence,
    is_legal,
)
from game.ambush.player_loadout import (  # noqa: E402
    PlayerLoadout,
    loadout_to_buff,
)

CFG = AmbushConfig()


def test_state_machine_order():
    good = ["EXPLORE", "PREP_PLAYER", "PREP_NPC_CSP", "PREP_NPC_LS",
            "PREP_REVIEW", "BATTLE", "EXPLORE"]
    assert check_sequence(good) == []
    assert not is_legal("EXPLORE", "BATTLE")
    assert is_legal("PREP_PLAYER", "EXPLORE")  # Esc batal
    assert is_legal("PREP_REVIEW", "PREP_NPC_CSP")  # G ulang
    assert is_legal("BATTLE", "TRANSITION")  # duel berikut antrean
    assert is_legal("TRANSITION", "BATTLE")


def test_loadout_buff_single_source():
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    buff = loadout_to_buff(pl, CFG)
    assert buff.atk == 2 and abs(buff.armor - 0.10) < 1e-9
    # Angka HUD == angka battle: HUD membaca buff yang sama.
    assert buff == loadout_to_buff(PlayerLoadout(items=pl.items), CFG)


def test_evaluator_player_aware():
    from game.ambush.types import EMPTY, SquadConfig
    ev = HeuristicEvaluator(CFG)
    squad = SquadConfig(roles=("Warrior", EMPTY, EMPTY),
                        items=("Iron Sword", EMPTY, EMPTY))
    plain = ev.evaluate(squad)
    ev.set_player(PlayerLoadout(items=("Iron Sword", "Heavy Shield")))
    armed = ev.evaluate(squad)
    # Player bersenjata menurunkan difficulty NPC yang sama.
    assert armed < plain
    assert 0.0 <= armed <= 1.0


def test_npc_buff_still_applies_with_player():
    import pygame
    pygame.init()
    from battle_system import BattleSystem
    from game.ambush.types import SquadConfig
    squad = SquadConfig(roles=("Tank", "Healer", "Warrior"),
                        items=("Heavy Shield", "Healing Charm", "Iron Sword"))
    npc_buff = squad_to_buff(squad, CFG)
    pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
    pbuff = loadout_to_buff(pl, CFG)
    battle = BattleSystem(player_hp=100, npc_buff=npc_buff, npc_squad=squad,
                          player_buff=pbuff, player_loadout=pl)
    assert battle.npc_max_hp == 70 + npc_buff.hp
    assert battle.player_max_hp == 100 + pbuff.hp
    assert type(battle.ai).__name__ == "BuffAwareAI"
    assert type(battle.hud).__name__ == "BattleConfigHUD"


if __name__ == "__main__":
    tests = sorted(
        (v for k, v in globals().items() if k.startswith("test_")),
        key=lambda fn: fn.__name__,
    )
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001 - runner mandiri
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    print(f"{len(tests) - failed}/{len(tests)} lolos")
    raise SystemExit(1 if failed else 0)
