"""experiments/screens.py - Screenshot headless tiap fase (Fase 6, Bagian 3).

Render memakai fungsi gambar ASLI (bukan mock) lalu surface.save ke
docs/screens/ untuk memeriksa keterbacaan. Butuh display (dummy).

Jalan: `python3 experiments/screens.py` (GameMap lambat dimuat ~1 mnt).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1280, 720))
from game.ambush.buff import summarize_squad  # noqa: E402
from game.ambush.config import AmbushConfig  # noqa: E402
from game.ambush.director import AmbushDirector  # noqa: E402
from game.ambush.governor import DifficultyGovernor  # noqa: E402
from game.ambush.overlay_ambush import (  # noqa: E402
    AmbushDebugOverlay,
    build_view,
)
from game.ambush.player_loadout import PlayerLoadout  # noqa: E402
from game.ambush.trace import TraceBuffer  # noqa: E402
from game.ambush.ui.battle_hud import BattleConfigHUD  # noqa: E402
from game.ambush.ui.player_loadout_screen import PlayerLoadoutScreen  # noqa: E402
from game.ambush.ui.transition import draw_transition  # noqa: E402
from game.map import GameMap, Viewport  # noqa: E402

SIZE = (1280, 720)
OUT = Path(ROOT) / "docs" / "screens"
OUT.mkdir(parents=True, exist_ok=True)

screen = pygame.display.get_surface()
font = pygame.font.SysFont("consolas", 14)
cfg = AmbushConfig()
pl = PlayerLoadout(items=("Iron Sword", "Heavy Shield"))
viewport = Viewport(SIZE)


def base_scene():
    """Latar beku overworld (map asli bila tampil, else gelap)."""
    screen.fill((12, 14, 18))
    try:
        game_map = GameMap()
        game_map.draw(screen, viewport)
        return game_map
    except Exception as exc:  # headless tanpa aset: tetap jalan
        print("tanpa map:", exc)
        return None


def shot(name: str):
    pygame.display.flip()
    pygame.image.save(screen, str(OUT / name))
    print("tersimpan:", name)


def main():
    game_map = base_scene()
    # 1. PREP_PLAYER.
    PlayerLoadoutScreen(pl).draw(screen, font, 0.5)
    shot("fase-prep-player.png")

    # 2-4. Director: pompa CSP (10 event), LS (sampai ls_start + 3),
    # lalu sampai selesai (REVIEW).
    tracer = TraceBuffer()
    director = AmbushDirector(cfg, DifficultyGovernor(cfg), tracer=tracer,
                              base_seed=3)
    gen = director.run_gen_queue(0, 0.5, pl)
    Jess = []
    try:
        for _ in range(10):
            Jess.append(next(gen))
    except StopIteration:
        pass
    base_scene()
    AmbushDebugOverlay().update(build_view(tracer, {
        "phase": "CSP", "status": "berjalan", "ls_algo": "random_restart",
        "target": 0.5, "pump": "slow",
        "toggles": {"mrv": True, "deg": True, "lcv": True, "infer": "ac3"},
        "sideways_limit": 10, "ls_stop": "", "seed_gap": "", "squad": None,
        "sim": "", "player_loadout": pl}))
    from game.ambush.overlay_ambush import AmbushDebugOverlay as ADO
    ov = ADO()
    ov.update(build_view(tracer, {
        "phase": "CSP", "status": "berjalan", "ls_algo": "random_restart",
        "target": 0.5, "pump": "slow",
        "toggles": {"mrv": True, "deg": True, "lcv": True, "infer": "ac3"},
        "sideways_limit": 10, "ls_stop": "", "seed_gap": "", "squad": None,
        "sim": "", "player_loadout": pl}))
    ov.draw(screen, font)
    shot("fase-csp.png")

    # Pompa sampai LS mulai + sedikit, lalu sampai selesai.
    try:
        while True:
            e = next(gen)
            Jess.append(e)
            if e.get("phase") == "ls_start":
                break
    except StopIteration:
        pass
    base_scene()
    ov.update(build_view(tracer, {
        "phase": "Local Search", "status": "berjalan",
        "ls_algo": "random_restart", "target": 0.5, "pump": "slow",
        "toggles": {"mrv": True, "deg": True, "lcv": True, "infer": "ac3"},
        "sideways_limit": 10, "ls_stop": "", "seed_gap": "",
        "squad": None, "sim": "", "player_loadout": pl}))
    ov.draw(screen, font)
    shot("fase-ls.png")

    try:
        while True:
            next(gen)
    except StopIteration:
        pass
    result = director.last_queue_result
    base_scene()
    seeds = director.last_queue_seeds
    ov.update(build_view(tracer, {
        "phase": "Selesai", "status": "selesai", "ls_algo": "random_restart",
        "target": 0.5, "pump": "slow",
        "toggles": {"mrv": True, "deg": True, "lcv": True, "infer": "ac3"},
        "sideways_limit": 10, "ls_stop": result.ls_stop,
        "seed_gap": result.seed_gap, "squad": result.queue,
        "sim": f"{result.sim_difficulty:.3f}", "player_loadout": pl,
        "seed_queue": director.last_queue_start, "final_queue": result.queue,
        "budget": result.budget, "per_duel": result.per_duel,
        "sim_entries": result.sim_entries or [],
        "k_positions": result.queue.k(), "target_tol": cfg.target_tol,
        "honest": "", "compare": None,
        "domains0": {}, "complete_consistent": "complete + consistent OK"}))
    ov.draw(screen, font)
    shot("fase-review-f3.png")

    # 5-6. BATTLE duel 1 & 2 (HUD) + TRANSISI.
    from battle_system import BattleSystem
    from game.ambush.player_loadout import loadout_to_buff
    pbuff = loadout_to_buff(pl, cfg)
    b1 = BattleSystem(player_hp=100, npc_buff=result.buffs[0],
                      player_buff=pbuff, player_loadout=pl, target=0.5,
                      sim_rate=f"{result.sim_difficulty:.3f}",
                      player_potions=3, npc_potions=3, duel_label=f"DUEL 1 DARI {result.queue.k()}",
                      queue_view={"order": [(s.role, s.item)
                                            for s in result.queue.slots],
                                  "idx": 0, "done": [False] * result.queue.k()})
    screen.fill((8, 10, 16))
    b1.draw(screen, font)
    shot("fase-battle-duel1.png")
    b2 = BattleSystem(player_hp=62, npc_buff=result.buffs[1],
                      player_buff=pbuff, player_loadout=pl, target=0.5,
                      sim_rate=f"{result.sim_difficulty:.3f}",
                      player_potions=2, npc_potions=3, duel_label=f"DUEL 2 DARI {result.queue.k()}",
                      queue_view={"order": [(s.role, s.item)
                                            for s in result.queue.slots],
                                  "idx": 1,
                                  "done": [True] + [False] * (result.queue.k() - 1)})
    screen.fill((8, 10, 16))
    b2.draw(screen, font)
    shot("fase-battle-duel2.png")

    base_scene()
    slot = result.queue.slots[1]
    draw_transition(
        screen, font,
        duel_no=min(1, result.queue.k()), k=result.queue.k(),
        result="menang",
        prev_role=result.queue.slots[0].role,
        prev_item=result.queue.slots[0].item,
        hp_after=62, cap=100, potions=2,
        next_role=slot.role, next_item=slot.item,
        foe_hp=100,
        foe_lines=["Serangan +2", "Tahan damage 10%"],
    )
    shot("fase-transisi.png")
    print("selesai:", sorted(p.name for p in OUT.glob("fase-*.png")))


if __name__ == "__main__":
    t0 = time.perf_counter()
    main()
    print(f"total {(time.perf_counter() - t0):.0f}s")
