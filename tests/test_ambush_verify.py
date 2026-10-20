"""tests/test_ambush_verify.py - Verifikasi temuan overlay (fase C).

1. Simulasi battle squad-vs-tanpa-squad (N=100, seed tetap): cetak
   perbedaan margin + pastikan buff menaikkan difficulty.
2. deg > 0 pada select awal (graph terhubung).
3. AC-3 menghapus >= 1 value pada kasus squad yang dibuat (compat).
4. Item terisi (non-NONE) di solusi CSP instans longgar, lintas seed.
5. BuffSummary tampil + buff sampai ke battle (headless).

Jalan: `python3 tests/test_ambush_verify.py` (test 1 ~10 dtk).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from game.ambush.buff import summarize_squad  # noqa: E402
from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.constraints import check  # noqa: E402
from game.ambush.csp_solver import CSPProblem, CSPSolver, squad_problem  # noqa: E402
from game.ambush.difficulty import SimulationEvaluator  # noqa: E402
from game.ambush.overlay_ambush import AmbushDebugOverlay, build_view  # noqa: E402
from game.ambush.trace import TraceBuffer  # noqa: E402
from game.ambush.types import EMPTY, SquadConfig  # noqa: E402

CFG = AmbushConfig()
STRONG = SquadConfig(
    roles=("Tank", "Healer", "Warrior", "Mage"),
    items=("Heavy Shield", "Healing Charm", "Iron Sword", "Swift Boots"))
PLAIN = SquadConfig(
    roles=(EMPTY, EMPTY, EMPTY, EMPTY),
    items=(EMPTY, EMPTY, EMPTY, EMPTY))


def _assign_of(squad: SquadConfig):
    out = {}
    for i, (r, it) in enumerate(zip(squad.roles, squad.items), 1):
        out[f"ROLE_{i}"] = r
        out[f"ITEM_{i}"] = it
    return out


def test_sim_squad_vs_tanpa_squad():
    from dataclasses import replace
    cfg = replace(CFG, sim_games=100)
    sim = SimulationEvaluator(cfg, seed=20260712)
    plain = sim.evaluate(PLAIN)
    strong = sim.evaluate(STRONG)
    print(f"\n  tanpa squad: {plain:.3f} | dengan squad: {strong:.3f} "
          f"| selisih: {strong - plain:+.3f}")
    assert strong > plain + 0.05, (plain, strong)


def test_degree_positif_di_awal():
    tr = TraceBuffer()
    CSPSolver(squad_problem(0, CFG.budget_for(0.5), CFG),
              tracer=tr).solve()
    first = tr.of_kind("select")[0]
    assert first["reason"].startswith("mrv=")
    assert ",deg=" in first["reason"]
    assert first["domains"][first["var"]] > 0
    deg = int(first["reason"].split("deg=")[1])
    assert deg > 0, first["reason"]


def test_ac3_menghapus_pada_kasus_compat():
    # ROLE_1 sudah Healer + ITEM_1 {Sword, NONE}: Sword tak punya dukungan
    # (Healer tak kompatibel) -> AC-3 wajib memangkasnya.
    prob = squad_problem(0, 99, CFG)
    prob.domains = dict(prob.domains)
    prob.domains["ROLE_1"] = ["Healer"]
    prob.domains["ITEM_1"] = ["Iron Sword", EMPTY]
    tr = TraceBuffer()
    sol, stats = CSPSolver(prob, tracer=tr).solve()
    assert stats["pruned"] >= 1, stats
    assert sol is not None and sol["ITEM_1"] == EMPTY


def test_item_terisi_lintas_seed():
    prob = squad_problem(3, CFG.budget_for(0.85), CFG)
    for seed in range(8):
        sol, _ = CSPSolver(prob, seed=seed).solve()
        assert sol is not None, seed
        assert not check(sol, 3, CFG.budget_for(0.85), CFG), seed
        n_item = sum(1 for i in (1, 2, 3, 4)
                     if sol[f"ITEM_{i}"] != EMPTY)
        assert n_item >= 1, (seed, sol)


def test_buff_sampai_ke_battle():
    pygame.init()
    from battle_system import BattleSystem
    summary = summarize_squad(STRONG, CFG)
    assert len(summary.lines()) >= 3, summary.lines()
    battle = BattleSystem(player_hp=100, npc_buff=summary.buff,
                          npc_squad=STRONG)
    from game.ambush.enemy_queue import ENEMY_BASE_HP
    assert battle.npc_max_hp == ENEMY_BASE_HP + summary.buff.hp
    assert type(battle.ai).__name__ == "BuffAwareAI"
    assert any("Buff:" in text for text, _ in battle.log)
    stats = battle.ai.think(battle.state, run_baseline=False)
    assert stats["best_action"] in ("ATTACK", "DEFEND", "POTION", "SPECIAL")

    overlay = AmbushDebugOverlay()
    view = build_view(TraceBuffer(), {"phase": "Selesai", "status": "selesai",
                                      "ls_algo": "-", "target": 0.5,
                                      "pump": "instant", "toggles": {},
                                      "sideways_limit": 10, "ls_stop": "",
                                      "seed_gap": "", "squad": STRONG,
                                      "sim": ""})
    assert len(view["buff_lines"]) >= 3
    overlay.update(view)
    screen = pygame.display.set_mode((1280, 720))
    overlay.draw(screen, pygame.font.SysFont("consolas", 14))


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
