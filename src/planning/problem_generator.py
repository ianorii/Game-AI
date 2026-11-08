"""
problem_generator.py - Generator Problem STRIPS Dinamis dari Kondisi WorldState

Menghasilkan ProblemAST dan PlanningProblem secara otomatis dari:
  - Posisi aktual Hero di peta
  - Isi inventori dan koin Hero
  - Katalog dan harga toko aktual di config/Shop (menghasilkan relasi pay/earn dinamis)
  - Solver CSP Loadout (menentukan legalitas aksi Equip)
  - Status petak ladang (kosong, tumbuh, matang)
  - Status gerbang (terkunci / terbuka)
  - Rintangan dinamis dan collision map
"""

from typing import Tuple, Optional, Any, Dict, Set, List
import math
import os
import json

import config
from world_state import WorldState
from economy import Shop
from battle.csp_loadout import LoadoutCSPSolver
from planning.pddl_parser import DomainAST, ProblemAST, parse_domain
from planning.strips import PlanningProblem
from planning.grounding import ground_problem
from planning.distance_matrix import DistanceMatrix


def find_nearest_location(px: float, py: float, locations: Optional[Dict[str, Tuple[int, int]]] = None) -> str:
    """Menemukan nama simpul lokasi terdekat dari koordinat piksel Hero."""
    locs = locations or getattr(config, "LOCATIONS", {})
    best_loc = "spawn"
    best_dist = float("inf")
    for name, (lx, ly) in locs.items():
        d = math.hypot(px - lx, py - ly)
        if d < best_dist:
            best_dist = d
            best_loc = name
    return best_loc


def compute_dynamic_coin_limit(shop: Optional[Shop] = None, catalog_path: str = "data/catalog.json",
                               min_required_coins: int = 60) -> int:
    """
    Menghitung batas atas koin secara otomatis dari kombinasi harga senjata dan zirah tertinggi di catalog.
    Bila di catalog ada item mahal (mis. Kapak Berat 35 + Besi 45 = 80, Tongkat Api 40 + Besi 45 = 85),
    batas otomatis dihitung agar seluruh kombinasi item toko dapat direncanakan.
    """
    max_w = 0
    max_a = 0
    if os.path.exists(catalog_path):
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                cat = json.load(f)
            for w in cat.get("weapons", []):
                name = w.get("name", "")
                p = shop.catalog[name]["price"] if (shop and hasattr(shop, "catalog") and name in shop.catalog) else w.get("price", 0)
                if p and p > max_w:
                    max_w = p
            for a in cat.get("armors", []):
                name = a.get("name", "")
                p = shop.catalog[name]["price"] if (shop and hasattr(shop, "catalog") and name in shop.catalog) else a.get("price", 0)
                if p and p > max_a:
                    max_a = p
        except Exception:
            pass
    if max_w + max_a > 0:
        return max(min_required_coins, max_w + max_a)
    return min_required_coins


def generate_dynamic_coin_facts(shop: Shop, starting_coins: int, max_coins: int = 70,
                               catalog_path: str = "data/catalog.json") -> Tuple[Set[str], Set[Tuple[str, ...]]]:
    """
    Menghasilkan objek tingkat koin dan relasi pay/earn secara dinamis dari harga toko,
    dipangkas hanya ke tingkat koin yang benar-benar dapat dicapai (reachable) dari
    koin awal hero (starting_coins) dibatasi oleh batas atas kebutuhan modal (max_coins).
    """
    buy_specs = [
        ("pay_seed", shop.get_buy_price("seeds_radish")),
        ("pay_bottle", shop.get_buy_price("bottle_empty")),
        ("pay_armor_leather", shop.get_buy_price("Kulit")),
        ("pay_weapon_dagger", shop.get_buy_price("Belati Cepat")),
        ("pay_weapon_axe", shop.get_buy_price("Kapak Berat")),
        ("pay_fire_staff", shop.get_buy_price("Tongkat Api")),
        ("pay_armor_iron", shop.get_buy_price("Besi")),
        ("pay_key", shop.get_buy_price("gate_key")),
    ]

    # Dynamic item purchase specs dari data/catalog.json (hanya untuk item baru di luar kanonikal)
    canonical_items = {
        "sword_basic", "weapon_dagger", "weapon_axe", "fire_staff",
        "cloth_armor", "armor_leather", "armor_iron", "seeds_radish", "bottle_empty", "gate_key"
    }
    dynamic_item_buys = []
    if os.path.exists(catalog_path):
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                cat_d = json.load(f)
            for cat_list in (cat_d.get("weapons", []), cat_d.get("armors", [])):
                for it in cat_list:
                    it_id = it.get("id")
                    if not it_id or it_id in canonical_items:
                        continue
                    it_name = it.get("name", it_id)
                    price = shop.catalog[it_name]["price"] if (hasattr(shop, "catalog") and it_name in shop.catalog) else it.get("price", 0)
                    if price and price > 0:
                        dynamic_item_buys.append((it_id, price))
                        buy_specs.append((f"pay_item_{it_id}", price))
        except Exception:
            pass

    sell_specs = [
        ("earn_radish", shop.get_sell_price("radish")),
        ("earn_egg", shop.get_sell_price("egg")),
        ("earn_milk", shop.get_sell_price("milk")),
        ("earn_fish", shop.get_sell_price("fish")),
        ("earn_wood", shop.get_sell_price("wood")),
        ("earn_rock", shop.get_sell_price("rock")),
    ]

    valid_buys = [(rel, price) for rel, price in buy_specs if price is not None and price > 0]
    valid_sells = [(rel, rev) for rel, rev in sell_specs if rev is not None and rev > 0]

    # Hitung reachable coins melalui BFS forward reachability dari starting_coins
    reachable_coins: Set[int] = {starting_coins}
    queue = [starting_coins]
    while queue:
        curr = queue.pop(0)
        # Transisi belanja (pay)
        for _, price in valid_buys:
            nxt = curr - price
            if nxt >= 0 and nxt not in reachable_coins:
                reachable_coins.add(nxt)
                queue.append(nxt)
        # Transisi penjualan (earn)
        for _, rev in valid_sells:
            nxt = curr + rev
            if nxt <= max_coins and nxt not in reachable_coins:
                reachable_coins.add(nxt)
                queue.append(nxt)

    coin_objects: Set[str] = {f"c{c}" for c in reachable_coins}
    coin_facts: Set[Tuple[str, ...]] = set()

    # 1. Relasi Pembelian (Pay)
    for rel_name, price in valid_buys:
        for c in reachable_coins:
            if c >= price and (c - price) in reachable_coins:
                coin_facts.add((rel_name, f"c{c}", f"c{c - price}"))

    # Relasi Pembelian Tergeneralisasi buy_item (?i ?c_from ?c_to)
    for it_id, price in dynamic_item_buys:
        for c in reachable_coins:
            if c >= price and (c - price) in reachable_coins:
                coin_facts.add(("pay_item", it_id, f"c{c}", f"c{c - price}"))

    # 2. Relasi Penjualan (Earn)
    for rel_name, revenue in valid_sells:
        for c in reachable_coins:
            if (c + revenue) <= max_coins and (c + revenue) in reachable_coins:
                coin_facts.add((rel_name, f"c{c}", f"c{c + revenue}"))

    return coin_objects, coin_facts


def build_problem_from_state(world_state: WorldState, hero: Any = None, game_map: Any = None,
                             domain: Optional[DomainAST] = None,
                             goal_type: str = "boss_defeated",
                             distance_matrix: Optional[DistanceMatrix] = None,
                             max_coins: int = 70,
                             enable_pruning: bool = True) -> PlanningProblem:
    """
    Membangun PlanningProblem siap cari dari kondisi dunia nyata saat ini.
    """
    if domain is None:
        with open("data/planning/expedition.domain", "r", encoding="utf-8") as f:
            domain = parse_domain(f.read())

    if distance_matrix is None:
        distance_matrix = DistanceMatrix(game_map=game_map)

    # 1. Posisi Hero
    hero_loc = "spawn"
    if hero is not None and hasattr(hero, "px") and hasattr(hero, "py"):
        hero_loc = find_nearest_location(hero.px, hero.py, distance_matrix.locations)

    # 2. Koin Hero
    hero_coins = max(0, min(max_coins, world_state.coins))
    coin_str = f"c{hero_coins}"

    # 3. Hitung jumlah potion di inventori
    potion_count = world_state.inventory.get_item_count("potion_red")
    p_clamped = min(3, max(0, potion_count))
    count_str = f"n{p_clamped}"

    init_facts: Set[Tuple[str, ...]] = set()

    # Hero state
    init_facts.add(("at", hero_loc))
    init_facts.add(("coins", coin_str))
    init_facts.add(("has_n", "potion", count_str))

    if potion_count > 0:
        init_facts.add(("has", "potion"))

    # HP
    hero_hp = getattr(hero, "hp", 100) if hero else 100
    hero_max_hp = getattr(hero, "max_hp", 100) if hero else 100
    if hero_hp >= hero_max_hp:
        init_facts.add(("hp_full",))

    # Equipment & CSP Loadout Verification
    name_to_pddl = {
        "Pedang Biasa": "sword_basic", "Belati Cepat": "weapon_dagger", "Kapak Berat": "weapon_axe", "Tongkat Api": "fire_staff",
        "Kain": "cloth_armor", "Kulit": "armor_leather", "Besi": "armor_iron"
    }

    # 1. Valid CSP Loadouts (kombinasi sah menurut solver CSP)
    # Budget pruning: singkirkan item toko yang harganya melebihi kapasitas modal hero (max_coins)
    achievable_items = set()
    for item_name in ("Pedang Biasa", "Kain", "Kulit", "Besi", "Belati Cepat", "Kapak Berat", "Tongkat Api"):
        p = world_state.shop.get_buy_price(item_name) if hasattr(world_state, "shop") else None
        if p is None or p <= max_coins or world_state.inventory.has_item(item_name, 1):
            achievable_items.add(item_name)
    for charm_name in ("Jimat Vitalitas", "Jimat Ketahanan", "Jimat Keberuntungan"):
        achievable_items.add(charm_name)

    csp_solver_all = LoadoutCSPSolver(owned_items=achievable_items)
    all_csp_solutions, _ = csp_solver_all.solve_all()
    for sol in all_csp_solutions:
        w = sol.get("WEAPON")
        a = sol.get("ARMOR")
        if w in name_to_pddl and a in name_to_pddl:
            init_facts.add(("valid_loadout", name_to_pddl[w], name_to_pddl[a]))

    # 2. Ready Loadouts dari readiness.json
    readiness_path = os.path.join("data", "planning", "readiness.json")
    if os.path.exists(readiness_path):
        try:
            with open(readiness_path, "r", encoding="utf-8") as rf:
                rdata = json.load(rf)
            loadout_key_map = {
                "starter": ("sword_basic", "cloth_armor"),
                "leather_dagger": ("weapon_dagger", "armor_leather"),
                "iron_axe": ("weapon_axe", "armor_iron"),
                "fire_staff": ("fire_staff", "armor_leather"),
            }
            min_wr = getattr(config, "READY_MIN_WIN_RATE", 0.50) * 100.0
            for l_key, (pw, pa) in loadout_key_map.items():
                if l_key in rdata:
                    for p_cnt_str, p_info in rdata[l_key].items():
                        if p_info.get("is_ready", False) and p_info.get("hero_win_rate", 0.0) >= min_wr:
                            w_real = [k for k, v in name_to_pddl.items() if v == pw]
                            a_real = [k for k, v in name_to_pddl.items() if v == pa]
                            if (not w_real or w_real[0] in achievable_items) and (not a_real or a_real[0] in achievable_items):
                                init_facts.add(("ready_loadout", pw, pa, f"n{p_cnt_str}"))

            # Dukungan dynamic loadouts dari catalog/readiness.json untuk item baru
            for l_key, l_val in rdata.items():
                if l_key == "metadata" or l_key in loadout_key_map or not isinstance(l_val, dict):
                    continue
                pw, pa = None, None
                if "__" in l_key:
                    pw, pa = l_key.split("__", 1)
                elif "weapon" in l_val and "armor" in l_val:
                    pw, pa = l_val["weapon"], l_val["armor"]
                if pw and pa:
                    for p_cnt_str, p_info in l_val.items():
                        if isinstance(p_info, dict) and p_info.get("is_ready", False) and p_info.get("hero_win_rate", 0.0) >= min_wr:
                            init_facts.add(("ready_loadout", pw, pa, f"n{p_cnt_str}"))
                            init_facts.add(("valid_loadout", pw, pa))
        except Exception as e:
            print(f"[ProblemGenerator] Gagal membaca readiness.json: {e}")

    # 3. Status Terpasang Hero Saat Ini
    equipped_dict = getattr(world_state.inventory, "equipped", None)
    if equipped_dict:
        w_eq = equipped_dict.get("weapon") or equipped_dict.get("WEAPON")
        a_eq = equipped_dict.get("armor") or equipped_dict.get("ARMOR")
        if w_eq in name_to_pddl and a_eq in name_to_pddl:
            init_facts.add(("equipped_weapon", name_to_pddl[w_eq]))
            init_facts.add(("equipped_armor", name_to_pddl[a_eq]))
            init_facts.add(("equipped_ok",))

    # Bahan & Barang di Tas
    item_mappings = {
        "seeds_radish": "seeds_radish",
        "radish": "radish",
        "bottle_empty": "bottle_empty",
        "wood": "wood",
        "rock": "rock",
        "gate_key": "gate_key",
        "egg": "egg",
        "milk": "milk",
        "fish": "fish",
        "Pedang Biasa": "sword_basic",
        "Kain": "cloth_armor",
        "Kulit": "armor_leather",
        "Besi": "armor_iron",
        "Belati Cepat": "weapon_dagger",
        "Kapak Berat": "weapon_axe",
        "Tongkat Api": "fire_staff"
    }
    for inv_id, strip_id in item_mappings.items():
        if world_state.inventory.has_item(inv_id, 1):
            init_facts.add(("has", strip_id))

    # Gerbang
    if world_state.gate.is_open:
        init_facts.add(("gate_open",))
    else:
        init_facts.add(("gate_locked",))

    # Ladang
    plots = world_state.farm.plots if hasattr(world_state, "farm") else []
    for idx, p_name in enumerate(["plot0", "plot1"]):
        if idx < len(plots):
            plot_obj = plots[idx]
            if plot_obj.crop_type is None:
                init_facts.add(("plot_empty", p_name))
            elif plot_obj.is_mature:
                init_facts.add(("plot_mature", p_name, plot_obj.crop_type))
            else:
                init_facts.add(("plot_planted", p_name, plot_obj.crop_type))
                if plot_obj.is_watered:
                    init_facts.add(("plot_watered", p_name))
        else:
            init_facts.add(("plot_empty", p_name))

    # Hitungan diskret
    init_facts.add(("next_count", "n0", "n1"))
    init_facts.add(("next_count", "n1", "n2"))
    init_facts.add(("next_count", "n2", "n3"))

    # Dinamisasi Koin dari Harga Toko
    coin_objects, coin_trans_facts = generate_dynamic_coin_facts(world_state.shop, world_state.coins, max_coins=max_coins)
    init_facts.update(coin_trans_facts)

    # Konektivitas Lokasi Desa
    village_locs = ["spawn", "shop", "workshop", "bed", "farm", "gate",
                    "chicken_coop", "cow_pasture", "river_fishing", "forest_wood", "quarry_rock"]
    for a in village_locs:
        for b in village_locs:
            if a != b:
                dur, _, _ = distance_matrix.get_distance(a, b, gate_open=world_state.gate.is_open)
                if not math.isinf(dur):
                    init_facts.add(("connected", a, b))

    # Koneksi Gerbang ke Boss (hanya ditambahkan jika jalur nyata A* terhubung saat gerbang terbuka)
    gate_boss_dur, _, _ = distance_matrix.get_distance("gate", "boss", gate_open=True)
    if not math.isinf(gate_boss_dur):
        init_facts.add(("gate_connected", "gate", "boss"))
        init_facts.add(("gate_connected", "boss", "gate"))

    # Goal
    goal_facts: Set[Tuple[str, ...]] = set()
    if goal_type == "boss_defeated":
        goal_facts.add(("boss_defeated",))
    elif goal_type in ("has_potion", "craft_potion"):
        goal_facts.add(("has", "potion"))
    elif goal_type == "open_gate":
        goal_facts.add(("gate_open",))
    elif goal_type in ("craft_key", "has_gate_key"):
        goal_facts.add(("has", "gate_key"))
    elif goal_type in ("village_prep", "prep_village", "p6"):
        goal_facts.add(("gate_open",))
        goal_facts.add(("has_n", "potion", "n1"))
        goal_facts.add(("equipped_ok",))
    else:
        goal_facts.add((goal_type,))

    # Objek terstruktur untuk ProblemAST
    objects_dict = {
        "spawn": "location", "shop": "location", "workshop": "location", "bed": "location",
        "farm": "location", "gate": "location", "chicken_coop": "location", "cow_pasture": "location",
        "river_fishing": "location", "forest_wood": "location", "quarry_rock": "location", "boss": "location",
        "plot0": "plot", "plot1": "plot",
        "n0": "count", "n1": "count", "n2": "count", "n3": "count",
        "sword_basic": "item", "weapon_dagger": "item", "weapon_axe": "item", "fire_staff": "item",
        "cloth_armor": "item", "armor_leather": "item", "armor_iron": "item"
    }
    for f in init_facts:
        if f[0] in ("ready_loadout", "valid_loadout", "equipped_weapon", "equipped_armor", "has"):
            for arg in f[1:]:
                if arg not in objects_dict and not arg.startswith("n") and not arg.startswith("c"):
                    objects_dict[arg] = "item"
    for c_obj in coin_objects:
        objects_dict[c_obj] = "coin"

    problem_ast = ProblemAST(
        name="dynamic-world-expedition",
        domain_name=domain.name,
        objects=objects_dict,
        init_facts=init_facts,
        goal_facts=goal_facts,
        metric="minimize total-time"
    )

    grounded_prob = ground_problem(domain, problem_ast, distance_matrix=distance_matrix, enable_pruning=enable_pruning)

    # Budget & Relevance Pruning untuk ekspedisi Boss Defeated:
    # Singkirkan komoditas yang tidak relevan dengan bahan ramuan (lobak) atau kunci (kayu, batu),
    # serta senjata mahal yang didominasi oleh Belati Cepat dalam batas modal.
    if enable_pruning and goal_type == "boss_defeated":
        irrelevant_actions = {"collect_egg", "collect_milk", "sell_egg", "sell_milk", "buy_weapon_axe"}
        grounded_prob.actions = [a for a in grounded_prob.actions if a.name not in irrelevant_actions]

    return grounded_prob
