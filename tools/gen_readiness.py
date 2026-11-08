"""
gen_readiness.py - Generator Matriks Kesiapan Boss Otomatis dari data/catalog.json

Menghitung kesiapan (win rate) seluruh kombinasi senjata x armor x jumlah potion (0..3)
menggunakan simulasi Minimax vs Kebijakan Hero dengan Amplop Monoton (Monotonic Policy Envelope).
Hasil disimpan ke data/planning/readiness.json.
"""

import os
import sys
import json
import random
from typing import Dict, Any, List

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import config
from ai.adversarial import BattleState, apply_action, is_terminal, pure_minimax_root
from battle.csp_loadout import apply_loadout


def simulate_single_match(loadout: Dict[str, str], potion_count: int, seed: int) -> bool:
    """Simulasi satu pertempuran turn-based antara Hero dan Boss Minimax."""
    base_st = BattleState(player_hp=100, boss_hp=config.BOSS_MAX_HP, potion_count=potion_count)
    st = apply_loadout(base_st, loadout, base_potion_count=potion_count)
    rng = random.Random(seed)

    while not is_terminal(st):
        if st.turn == "player":
            # Kebijakan standar Hero (identik dengan world_actions.py:start_boss_battle)
            min_hero_dmg = getattr(st, "player_attack_min", 25)
            if st.boss_hp <= min_hero_dmg:
                hero_act = "ATTACK"
            elif st.player_hp <= 40 and st.potion_count > 0:
                hero_act = "POTION"
            elif st.player_hp <= 50 and st.boss_heavy_cd == 0:
                hero_act = "DEFEND"
            else:
                hero_act = "ATTACK"
            st, _ = apply_action(st, "player", hero_act, rng=rng)
        else:
            boss_act, _, _ = pure_minimax_root(st, depth=3)
            st, _ = apply_action(st, "boss", boss_act, rng=rng)

    return st.boss_hp <= 0


def evaluate_loadout_raw(loadout: Dict[str, str], potion_count: int, sample_size: int = 200, base_seed: int = 42) -> float:
    """Evaluasi win rate hero dari sample pertempuran acak."""
    rng = random.Random(base_seed + potion_count * 1000)
    wins = 0
    for _ in range(sample_size):
        seed = rng.randint(0, 10_000_000)
        if simulate_single_match(loadout, potion_count, seed):
            wins += 1
    return round((wins / sample_size) * 100.0, 1)


def generate_readiness_matrix(catalog_path: str = "data/catalog.json",
                              output_path: str = "data/planning/readiness.json",
                              sample_size: int = 200,
                              base_seed: int = 42) -> Dict[str, Any]:
    """Menghasilkan readiness.json dari data/catalog.json dengan jaminan monoton."""
    if os.path.exists(catalog_path):
        with open(catalog_path, "r", encoding="utf-8") as f:
            cat_data = json.load(f)
    else:
        cat_data = {
            "weapons": [
                {"id": "sword_basic", "name": "Pedang Biasa"},
                {"id": "weapon_dagger", "name": "Belati Cepat"},
                {"id": "weapon_axe", "name": "Kapak Berat"},
                {"id": "fire_staff", "name": "Tongkat Api"}
            ],
            "armors": [
                {"id": "cloth_armor", "name": "Kain"},
                {"id": "armor_leather", "name": "Kulit"},
                {"id": "armor_iron", "name": "Besi"}
            ]
        }

    weapons = cat_data.get("weapons", [])
    armors = cat_data.get("armors", [])

    threshold = getattr(config, "READY_MIN_WIN_RATE", 0.50)
    min_potions = getattr(config, "READY_MIN_POTIONS", 1)

    canonical_loadouts = {
        "starter": {"weapon": "sword_basic", "armor": "cloth_armor", "weapon_name": "Pedang Biasa", "armor_name": "Kain"},
        "leather_dagger": {"weapon": "weapon_dagger", "armor": "armor_leather", "weapon_name": "Belati Cepat", "armor_name": "Kulit"},
        "iron_axe": {"weapon": "weapon_axe", "armor": "armor_iron", "weapon_name": "Kapak Berat", "armor_name": "Besi"},
        "fire_staff": {"weapon": "fire_staff", "armor": "armor_leather", "weapon_name": "Tongkat Api", "armor_name": "Kulit"},
    }

    results: Dict[str, Any] = {
        "metadata": {
            "boss_config": {
                "hp": config.BOSS_MAX_HP,
                "attack_dmg": list(config.BOSS_ATTACK_DMG),
                "attack_expected": config.BOSS_ATTACK_EXPECTED,
                "heavy_dmg": config.BOSS_HEAVY_DMG,
                "heal_amount": config.BOSS_HEAL_AMOUNT,
                "max_heals": config.BOSS_MAX_HEALS
            },
            "policy_description": (
                "Kebijakan Monoton: Evaluasi kebijakan player dengan amplop monoton W(k+1) >= W(k). "
                "Hero dengan k potion dapat memilih strategi k-1 (tidak membuang giliran minum ramuan)."
            ),
            "threshold": threshold,
            "min_potions": min_potions,
            "sample_size": sample_size,
            "seed": base_seed
        }
    }

    def process_loadout(key_name: str, w_name: str, a_name: str, extra_meta: Dict[str, Any] = None):
        results[key_name] = dict(extra_meta or {})
        prev_wr = 0.0
        for p in range(4):
            raw_wr = evaluate_loadout_raw({"WEAPON": w_name, "ARMOR": a_name}, p, sample_size=sample_size, base_seed=base_seed)
            monotone_wr = max(raw_wr, prev_wr)
            prev_wr = monotone_wr
            is_ready = (monotone_wr >= threshold * 100.0) and (p >= min_potions)
            results[key_name][str(p)] = {
                "hero_win_rate": monotone_wr,
                "boss_win_rate": round(100.0 - monotone_wr, 1),
                "hero_minimax_win_rate": monotone_wr,
                "sample_size": sample_size,
                "is_ready": is_ready
            }

    # 1. Canonical preset loadouts
    for key_name, info in canonical_loadouts.items():
        process_loadout(key_name, info["weapon_name"], info["armor_name"])

    # 2. Dynamic new items from catalog (hanya jika ada item baru di luar canonical 4)
    standard_w_ids = {"sword_basic", "weapon_dagger", "weapon_axe", "fire_staff"}
    standard_a_ids = {"cloth_armor", "armor_leather", "armor_iron"}

    for w in weapons:
        w_id = w.get("id", w.get("name"))
        w_name = w.get("name", w_id)
        is_new_w = w_id not in standard_w_ids
        for a in armors:
            a_id = a.get("id", a.get("name"))
            a_name = a.get("name", a_id)
            is_new_a = a_id not in standard_a_ids

            if is_new_w or is_new_a:
                pair_key = f"{w_id}__{a_id}"
                meta = {
                    "weapon": w_id,
                    "armor": a_id,
                    "weapon_name": w_name,
                    "armor_name": a_name
                }
                process_loadout(pair_key, w_name, a_name, extra_meta=meta)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"[gen_readiness] Berhasil menghasilkan {output_path} (threshold={threshold}, min_potions={min_potions})")
    return results


if __name__ == "__main__":
    generate_readiness_matrix()
