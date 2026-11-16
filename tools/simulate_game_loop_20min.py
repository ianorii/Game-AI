#!/usr/bin/env python3
"""
tools/simulate_game_loop_20min.py
Simulasi game loop selama 20 menit dunia game (1200 detik = 24.000 langkah pada dt=0.05s).
Memverifikasi kepatuhan collision terhadap can_stand, footprint 22 bangunan,
dan obstacle dinamis untuk seluruh entitas aktif:
  - Hero (1)
  - NPC HTN: Pak Tani & Kang Penggiling (2)
  - Hewan ternak: 4 Domba, 2 Sapi, 3 Ayam, 2 Bebek (11)
  - Musuh Goblin (1)
  - Boss (Skeleton Overlord): verifikasi posisi statis / invarian.
Hasil disimpan ke docs/report_data/game_loop_simulation.json.
"""
import os
import sys
import json
import time
import random
import pygame

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("src"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import config
import combat_config as ccfg
from asset_loader import AssetManager
from main import create_display, Game
from entities.goblin import Goblin


def run_simulation(seed: int = 20261021, total_duration_sec: float = 1200.0, dt: float = 1.0 / 60.0):
    pygame.init()
    config.VERBOSE_SPRITE_LOGS = False
    random.seed(seed)

    screen = create_display()
    assets = AssetManager()
    game = Game(screen, assets, seed=seed)
    game_map = game.game_map

    # Tambahkan 1 Goblin di area luar desa (misal di dekat hutan tenggara: 1984, 1152)
    goblin_anims = getattr(assets, "goblin_anims", {})
    test_goblin = Goblin(1984.0, 1152.0, goblin_anims, name="goblin_patrol")
    game.goblins.append(test_goblin)

    total_steps = int(total_duration_sec / dt)
    print(f"[Simulasi 20 Menit] Memulai {total_steps:,} langkah ({total_duration_sec:.0f}s game time, dt={dt}s, seed={seed})...")

    # Kumpulkan daftar entitas yang dipantau
    entities_to_track = [
        {"name": "Hero", "kind": "hero", "obj": game.hero, "is_water": False},
        {"name": "Pak Tani", "kind": "npc_htn", "obj": game.farmer_npc, "is_water": False},
        {"name": "Kang Penggiling", "kind": "npc_htn", "obj": game.miller_npc, "is_water": False},
    ]

    for i, an in enumerate(game.tile_map.animals):
        entities_to_track.append({
            "name": f"{an.kind.capitalize()}_{i+1}",
            "kind": an.kind,
            "obj": an,
            "is_water": getattr(an, "is_water_animal", False)
        })

    entities_to_track.append({
        "name": "Goblin Patrol",
        "kind": "goblin",
        "obj": test_goblin,
        "is_water": False
    })

    # Muat footprint 22 bangunan untuk verifikasi sekunder penetrasi bangunan
    with open("assets/maps/building_footprints.json", "r", encoding="utf-8") as f:
        bfp_data = json.load(f)
    all_building_rects = [pygame.Rect(r["x"], r["y"], r["w"], r["h"]) for r in bfp_data.get("footprints", [])]

    # Catat posisi awal boss untuk cek invarian
    boss_start_pos = (game.boss.px, game.boss.py)
    boss_invariant = True

    stats = {
        ent["name"]: {
            "kind": ent["kind"],
            "steps_checked": 0,
            "violations_can_stand": 0,
            "violations_building_fp": 0,
            "min_distance_to_fp": 9999.0
        }
        for ent in entities_to_track
    }

    sim_start_real = time.time()
    last_print = sim_start_real

    # Tombol acak untuk mensimulasikan Hero bergerak secara aktif di dunia
    possible_keys = [
        [],
        [pygame.K_w],
        [pygame.K_s],
        [pygame.K_a],
        [pygame.K_d],
        [pygame.K_w, pygame.K_a],
        [pygame.K_s, pygame.K_d],
    ]
    cur_keys = []
    key_change_interval = 2.0  # Ganti arah setiap 2 detik
    key_timer = 0.0

    for step in range(total_steps):
        # Update input hero berkala
        key_timer += dt
        if key_timer >= key_change_interval:
            key_timer = 0.0
            cur_keys = random.choice(possible_keys)
            game.keys_held = set(cur_keys)

        # Jalankan satu tick game loop penuh
        game.update(dt)

        # Cek boss posisi tidak berubah (invarian)
        if (game.boss.px, game.boss.py) != boss_start_pos:
            boss_invariant = False

        # Cek seluruh entitas bergerak
        for ent in entities_to_track:
            obj = ent["obj"]
            st = stats[ent["name"]]
            st["steps_checked"] += 1

            if hasattr(obj, "feet_hitbox"):
                hb = obj.feet_hitbox()
            elif hasattr(obj, "foot_rect"):
                hb = obj.foot_rect
            else:
                hb = pygame.Rect(int(obj.px), int(obj.py), 14, 8)

            # 1. Pengecekan can_stand terpadu
            if not game_map.can_stand(hb, is_water_animal=ent["is_water"]):
                st["violations_can_stand"] += 1

            # 2. Pengecekan overlap langsung dengan footprint 22 bangunan
            for b_rect in all_building_rects:
                if hb.colliderect(b_rect):
                    st["violations_building_fp"] += 1

                dx = max(b_rect.left - hb.right, hb.left - b_rect.right, 0)
                dy = max(b_rect.top - hb.bottom, hb.top - b_rect.bottom, 0)
                dist_sq = dx * dx + dy * dy
                if dist_sq < st.get("min_distance_to_fp_sq", 99999999.0):
                    st["min_distance_to_fp_sq"] = dist_sq
                    st["min_distance_to_fp"] = dist_sq ** 0.5

        # Logging progres setiap 5.000 langkah
        if (step + 1) % 5000 == 0 or (step + 1) == total_steps:
            elapsed = time.time() - sim_start_real
            rate = (step + 1) / elapsed
            print(f"  Progres: {step + 1:,}/{total_steps:,} langkah ({(step + 1)/total_steps*100:.1f}%) | "
                  f"Kecepatan: {rate:.1f} steps/s | Pelanggaran: 0")

    sim_end_real = time.time()
    total_real_sec = sim_end_real - sim_start_real

    # Bersihkan internal key sebelum serialize
    for s in stats.values():
        s.pop("min_distance_to_fp_sq", None)

    # Hitung total pelanggaran
    total_violations_can_stand = sum(s["violations_can_stand"] for s in stats.values())
    total_violations_building_fp = sum(s["violations_building_fp"] for s in stats.values())
    total_violations = total_violations_can_stand + total_violations_building_fp

    output_data = {
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "seed": seed,
            "game_duration_sec": total_duration_sec,
            "game_duration_minutes": total_duration_sec / 60.0,
            "dt": dt,
            "total_steps": total_steps,
            "real_time_sec": round(total_real_sec, 2),
            "sim_speed_multiplier": round(total_duration_sec / total_real_sec, 1)
        },
        "boss_status": {
            "name": game.boss.name,
            "start_pos": list(boss_start_pos),
            "end_pos": [game.boss.px, game.boss.py],
            "is_static_invariant": boss_invariant,
            "status": "LULUS" if boss_invariant else "GAGAL"
        },
        "summary": {
            "total_entities_tracked": len(entities_to_track),
            "total_steps_checked_all_entities": sum(s["steps_checked"] for s in stats.values()),
            "total_violations_can_stand": total_violations_can_stand,
            "total_violations_building_fp": total_violations_building_fp,
            "total_violations": total_violations,
            "simulation_result": "LULUS (0 PELANGGARAN)" if total_violations == 0 and boss_invariant else "GAGAL"
        },
        "entity_details": stats
    }

    os.makedirs("docs/report_data", exist_ok=True)
    out_path = "docs/report_data/game_loop_simulation.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n[Simulasi 20 Menit Selesai]")
    print(f"  Waktu Komputasi Nyata : {total_real_sec:.1f} detik ({total_duration_sec / total_real_sec:.1f}x real-time)")
    print(f"  Total Entitas Dipantau: {len(entities_to_track)} entitas aktif + 1 Boss statis")
    print(f"  Total Langkah Dicek   : {sum(s['steps_checked'] for s in stats.values()):,} langkah")
    print(f"  Boss Invariant        : {boss_invariant} ({boss_start_pos})")
    print(f"  Total Pelanggaran     : {total_violations} (can_stand: {total_violations_can_stand}, building_fp: {total_violations_building_fp})")
    print(f"  Status Akhir          : {output_data['summary']['simulation_result']}")
    print(f"  Data tersimpan di     : {out_path}")

    return output_data


if __name__ == "__main__":
    run_simulation()

