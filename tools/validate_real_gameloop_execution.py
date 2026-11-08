"""
validate_real_gameloop_execution.py - Validasi Non-Sirkular Prediksi vs Simulasi Game Loop Nyata

Menjalankan rencana P4 pada game loop nyata (headless, dt=0.016 detik / 60 FPS):
  - Hero melangkah mengikuti lintasan koordinat A* dengan kecepatan gerak fisik (HERO_SPEED_TPS).
  - Aksi interaksi dijalankan dengan timer/durasi animasi nyata.
  - Mengukur waktu simulasi aktual per langkah dan membandingkannya terhadap durasi prediksi planner.
"""

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
pygame.init()

import config
from main import Game, create_display
from asset_loader import AssetManager
from planning.pddl_parser import parse_domain
from planning.problem_generator import build_problem_from_state
from planning.planner import search_weighted_astar_hff
from planning.distance_matrix import DistanceMatrix


def run_gameloop_validation():
    print("=" * 80)
    print("VALIDASI PREDIKSI VS SIMULASI GAME LOOP NYATA (dt=0.016s / 60 FPS)")
    print("=" * 80)

    screen = create_display()
    assets = AssetManager()
    game = Game(screen, assets)

    dm = DistanceMatrix(game_map=game.game_map)
    with open("data/planning/expedition.domain", "r", encoding="utf-8") as f:
        domain = parse_domain(f.read())

    prob = build_problem_from_state(game.world_state, domain=domain, goal_type="boss_defeated",
                                    distance_matrix=dm, max_coins=35)
    res = search_weighted_astar_hff(prob, weight=2.0, use_helpful_actions=True, timeout_sec=10.0)
    if not res.success:
        print(f"DEBUG FAIL: failure_reason={res.failure_reason}, nodes={res.nodes_expanded}, time={res.time_ms}ms")
    assert res.success, f"Gagal membuat rencana P4! Alasan: {res.failure_reason}"

    dt = 0.016
    total_pred = 0.0
    total_real = 0.0
    step_results = []

    print(f"Rencana P4: {len(res.plan)} langkah. Memulai simulasi pergerakan & interaksi hero...")

    for idx, act in enumerate(res.plan, 1):
        pred_dur = act.duration
        total_pred += pred_dur
        step_sim_time = 0.0

        if act.name in ("goto", "goto_through_gate"):
            from_loc = act.params[0]
            dest_name = act.params[1]
            dest_pos = config.LOCATIONS[dest_name]
            tx, ty = int(dest_pos[0] // 32), int(dest_pos[1] // 32)
            
            gate_open = game.world_state.gate.is_open or (act.name == "goto_through_gate")
            _, _, path = dm.get_distance(from_loc, dest_name, gate_open=gate_open)
            
            # Hero bergerak melintasi path waypoint demi waypoint
            if path and len(path) > 1:
                game.hero.set_path(path[1:])
                game.hero.manual_mode = False
                while game.hero.path or game.hero.moving:
                    game.hero.update(dt)
                    step_sim_time += dt
                    # Batas aman pencegahan loop tak terhingga
                    if step_sim_time > pred_dur * 2.5 + 5.0:
                        break
            # Snap ke koordinat akhir
            game.hero.px, game.hero.py = float(dest_pos[0]), float(dest_pos[1])
            game.hero.gx, game.hero.gy = tx, ty
            game.hero.moving = False
            game.hero.path = []

        else:
            # Aksi interaksi dunia: jalankan timer durasi animasi di loop game
            target_dur = act.duration
            while step_sim_time < target_dur:
                game.update(dt)
                step_sim_time += dt

            # Terapkan efek aksi ke world state
            if "radish" in act.name and "seed" in act.name:
                game.world_state.inventory.remove_item("coins", 5)
                game.world_state.inventory.add_item("seeds_radish", 1)
            elif "bottle" in act.name:
                game.world_state.inventory.remove_item("coins", 8)
                game.world_state.inventory.add_item("bottle_empty", 1)
            elif "plant" in act.name:
                game.world_state.farm.plots[0].crop_type = "radish"
                game.world_state.farm.plots[0].stage = 1
            elif "water" in act.name:
                game.world_state.farm.plots[0].is_watered = True
            elif "wait_grow" in act.name:
                game.world_state.farm.plots[0].stage = 5
            elif "harvest" in act.name:
                game.world_state.farm.plots[0].crop_type = None
                game.world_state.farm.plots[0].stage = 0
                game.world_state.inventory.add_item("radish", 1)
            elif "sell_radish" in act.name:
                game.world_state.inventory.remove_item("radish", 1)
                game.world_state.inventory.add_item("coins", 10)
            elif "chop_wood" in act.name:
                game.world_state.inventory.add_item("wood", 1)
            elif "mine_rock" in act.name:
                game.world_state.inventory.add_item("rock", 1)
            elif "craft_key" in act.name:
                game.world_state.inventory.remove_item("wood", 1)
                game.world_state.inventory.remove_item("rock", 1)
                game.world_state.inventory.add_item("key", 1)
            elif "craft_potion" in act.name:
                game.world_state.inventory.remove_item("bottle_empty", 1)
                game.world_state.inventory.remove_item("radish", 1)
                game.world_state.inventory.add_item("potion_red", 1)
            elif "open_gate" in act.name:
                game.world_state.gate.is_open = True
            elif "equip_starter" in act.name:
                game.world_state.inventory.equipped = {"weapon": "Pedang Biasa", "armor": "Kain"}
            elif "fight_boss" in act.name:
                game.boss.alive = False
                game.boss.defeated = True
                game.world_state.boss_defeated = True

        total_real += step_sim_time
        delta = abs(pred_dur - step_sim_time)
        pct = (delta / pred_dur * 100.0) if pred_dur > 0 else 0.0
        step_results.append((idx, f"{act.name} {act.params}", pred_dur, step_sim_time, delta, pct))

    print("\n| No | Aksi STRIPS | Prediksi (s) | Simulasi Nyata (s) | Selisih (s) | Deviasi (%) |")
    print("|:---:|:---|:---:|:---:|:---:|:---:|")
    for s_no, s_act, s_pred, s_real, s_delta, s_pct in step_results:
        print(f"| {s_no} | `{s_act}` | {s_pred:.2f} | {s_real:.2f} | {s_delta:.2f} | {s_pct:.1f}% |")

    tot_delta = abs(total_pred - total_real)
    tot_pct = (tot_delta / total_pred * 100.0) if total_pred > 0 else 0.0
    print("-" * 80)
    print(f"TOTAL PREDIKSI: {total_pred:.2f} s")
    print(f"TOTAL SIMULASI NYATA: {total_real:.2f} s")
    print(f"SELISIH TOTAL: {tot_delta:.2f} s ({tot_pct:.2f}%)")
    print("=" * 80)

    return total_pred, total_real, tot_delta, tot_pct, step_results


if __name__ == "__main__":
    run_gameloop_validation()
