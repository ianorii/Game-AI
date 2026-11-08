"""
world_actions.py - API Aksi Dunia Tunggal untuk Planner dan Interaksi Manual

Menyediakan fungsi aksi formal dengan precondition, state changes, dan hasil
terstruktur (ActionResult) yang dapat dieksekusi secara:
  1. Headless oleh STRIPS Expedition Planner & HTN Planner
  2. Interaktif saat player menekan tombol [E] pada game loop
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
import math
import pygame

import config
from world_state import WorldState
from inventory import Inventory


@dataclass
class ActionResult:
    """Hasil eksekusi satu aksi formal di dunia game."""
    success: bool
    message: str
    duration: float = 0.0   # Estimasi durasi waktu simulasi aksi (detik)
    cost: int = 0           # Biaya koin (positif = pengeluaran, negatif = pendapatan)


def goto_location(world_state: WorldState, hero: Any, location_name: str, game_map: Any = None,
                  distance_matrix: Optional[Any] = None, from_location: Optional[str] = None) -> ActionResult:
    """Hero berpindah posisi ke lokasi tertentu di dunia dengan perhitungan waktu tempuh nyata."""
    locs = getattr(config, "LOCATIONS", {})
    if location_name not in locs:
        return ActionResult(False, f"Lokasi '{location_name}' tidak dikenal!", duration=0.0)

    prev_pos = None
    if hero is not None and hasattr(hero, "px") and hasattr(hero, "py"):
        prev_pos = (hero.px, hero.py)

    target_pos = locs[location_name]
    if hero is not None:
        if hasattr(hero, "px"):
            hero.px = float(target_pos[0])
            hero.py = float(target_pos[1])
        if hasattr(hero, "x"):
            hero.x = float(target_pos[0])
            hero.y = float(target_pos[1])
        if hasattr(hero, "gx"):
            hero.gx = int(target_pos[0] // 32)
            hero.gy = int(target_pos[1] // 32)
        if hasattr(hero, "cell"):
            hero.cell = (int(target_pos[0] // 32), int(target_pos[1] // 32))

    # Hitung durasi tempuh fisik aktual
    duration = 2.0
    if distance_matrix is not None:
        start_loc = from_location
        if not start_loc and prev_pos:
            start_loc = min(locs.keys(), key=lambda k: (locs[k][0] - prev_pos[0])**2 + (locs[k][1] - prev_pos[1])**2)
        if start_loc and start_loc != location_name:
            t, _, _ = distance_matrix.get_distance(start_loc, location_name, gate_open=world_state.gate.is_open)
            if not math.isinf(t):
                duration = t
    elif prev_pos:
        dist_px = math.hypot(target_pos[0] - prev_pos[0], target_pos[1] - prev_pos[1])
        speed_px_per_s = getattr(config, "HERO_SPEED_TPS", 4.6) * 32.0
        if speed_px_per_s > 0:
            duration = max(0.5, dist_px / speed_px_per_s)

    return ActionResult(True, f"Hero tiba di lokasi '{location_name}' {target_pos}.", duration=duration)


def plant(world_state: WorldState, crop_type: str = "radish", plot_id: Optional[int] = None) -> ActionResult:
    """Menanam benih tanaman pada petak ladang yang kosong."""
    seed_id = f"seeds_{crop_type.lower()}"
    if not world_state.inventory.has_item(seed_id, 1):
        return ActionResult(False, f"Precondition gagal: Tidak memiliki {seed_id} di tas!", duration=0.0)

    target_plot = None
    if plot_id is not None:
        if 0 <= plot_id < len(world_state.farm.plots):
            target_plot = world_state.farm.plots[plot_id]
    else:
        # Cari petak kosong pertama
        for p in world_state.farm.plots:
            if p.crop_type is None:
                target_plot = p
                break

    if target_plot is None:
        return ActionResult(False, "Tidak ada petak kosong yang dapat ditanami!", duration=0.0)

    ok, msg = target_plot.plant(crop_type, world_state.inventory)
    return ActionResult(ok, msg, duration=1.0)


def water(world_state: WorldState, plot_id: Optional[int] = None) -> ActionResult:
    """Menyiram air pada tanaman di ladang untuk mempercepat pertumbuhan."""
    target_plot = None
    if plot_id is not None:
        if 0 <= plot_id < len(world_state.farm.plots):
            target_plot = world_state.farm.plots[plot_id]
    else:
        # Cari petak berisi tanaman yang belum disiram dan belum matang
        for p in world_state.farm.plots:
            if p.crop_type is not None and not p.is_watered and not p.is_mature:
                target_plot = p
                break

    if target_plot is None:
        return ActionResult(False, "Tidak ada petak yang membutuhkan siraman air!", duration=0.0)

    ok, msg = target_plot.water()
    return ActionResult(ok, msg, duration=1.0)


def harvest(world_state: WorldState, plot_id: Optional[int] = None) -> ActionResult:
    """Memanen tanaman yang sudah mencapai tahap matang (stage 5)."""
    target_plot = None
    if plot_id is not None:
        if 0 <= plot_id < len(world_state.farm.plots):
            target_plot = world_state.farm.plots[plot_id]
    else:
        # Cari petak yang sudah matang
        for p in world_state.farm.plots:
            if p.is_mature:
                target_plot = p
                break

    if target_plot is None:
        return ActionResult(False, "Belum ada tanaman yang matang untuk dipanen!", duration=0.0)

    ok, msg = target_plot.harvest(world_state.inventory)
    return ActionResult(ok, msg, duration=1.0)


def sell(world_state: WorldState, item_id: str, count: int = 1) -> ActionResult:
    """Menjual barang dari inventori hero ke toko desa."""
    if not world_state.inventory.has_item(item_id, count):
        return ActionResult(False, f"Precondition gagal: Tidak memiliki {count}x {item_id} di tas!", duration=0.0)

    if item_id not in world_state.shop.sell_prices:
        return ActionResult(False, f"Toko tidak menerima pembelian item '{item_id}'!", duration=0.0)

    unit_price = world_state.shop.get_sell_price(item_id)
    total_gain = unit_price * count

    ok, new_coins, msg = world_state.shop.sell_item(item_id, count, world_state.coins, world_state.inventory)
    if ok:
        world_state.coins = new_coins
        return ActionResult(True, msg, duration=0.5, cost=-total_gain)
    return ActionResult(False, msg, duration=0.0)


def buy(world_state: WorldState, item_id: str, count: int = 1) -> ActionResult:
    """Membeli barang dari toko desa menggunakan koin hero."""
    if item_id not in world_state.shop.catalog:
        return ActionResult(False, f"Item '{item_id}' tidak dijual di toko desa!", duration=0.0)

    unit_price = world_state.shop.get_buy_price(item_id)
    total_cost = unit_price * count
    if world_state.coins < total_cost:
        return ActionResult(False, f"Koin tidak mencukupi! Butuh {total_cost} koin (Hero: {world_state.coins}).", duration=0.0)

    ok, new_coins, msg = world_state.shop.buy_item(item_id, count, world_state.coins, world_state.inventory)
    if ok:
        world_state.coins = new_coins
        return ActionResult(True, msg, duration=0.5, cost=total_cost)
    return ActionResult(False, msg, duration=0.0)


def collect_egg(world_state: WorldState) -> ActionResult:
    """Mengambil telur dari kandang ayam desa."""
    ok, msg = world_state.collect_egg()
    return ActionResult(ok, msg, duration=1.5)


def collect_milk(world_state: WorldState) -> ActionResult:
    """Memerah susu dari sapi di padang rumput desa."""
    ok, msg = world_state.collect_milk()
    return ActionResult(ok, msg, duration=2.0)


def fish(world_state: WorldState) -> ActionResult:
    """Memancing ikan segar di dermaga sungai desa."""
    extra = 0.0
    if world_state.cooldowns.get("fishing", 0.0) > 0:
        extra = world_state.cooldowns["fishing"]
        world_state.update(extra)
    ok, msg = world_state.fish()
    return ActionResult(ok, msg, duration=2.5 + extra)


def chop_wood(world_state: WorldState) -> ActionResult:
    """Menebang kayu dari pohon di tepi hutan desa."""
    extra = 0.0
    if world_state.cooldowns.get("tree_wood", 0.0) > 0:
        extra = world_state.cooldowns["tree_wood"]
        world_state.update(extra)
    ok, msg = world_state.chop_wood()
    return ActionResult(ok, msg, duration=2.0 + extra)


def mine_rock(world_state: WorldState) -> ActionResult:
    """Menambang batu dari singkapan batu di tebing."""
    extra = 0.0
    if world_state.cooldowns.get("rock_mining", 0.0) > 0:
        extra = world_state.cooldowns["rock_mining"]
        world_state.update(extra)
    ok, msg = world_state.mine_rock()
    return ActionResult(ok, msg, duration=2.0 + extra)


def craft_potion(world_state: WorldState) -> ActionResult:
    """Meracik Health Potion di bengkel (1 lobak + 1 botol kosong)."""
    ok, msg = world_state.craft_potion()
    return ActionResult(ok, msg, duration=1.5)


def craft_key(world_state: WorldState) -> ActionResult:
    """Menempa Kunci Gerbang di bengkel (1 kayu + 1 batu)."""
    ok, msg = world_state.craft_gate_key()
    return ActionResult(ok, msg, duration=2.0)


def open_gate(world_state: WorldState, game_map: Any = None) -> ActionResult:
    """Membuka gerbang pembatas reruntuhan menuju area Boss dengan Kunci Gerbang."""
    ok, msg = world_state.gate.unlock(world_state.inventory)
    if ok and game_map is not None:
        obs = world_state.gate.collision_rect
        if hasattr(game_map, "dynamic_obstacles") and obs in game_map.dynamic_obstacles:
            game_map.dynamic_obstacles.remove(obs)
    return ActionResult(ok, msg, duration=1.0)


def rest(world_state: WorldState, hero: Any) -> ActionResult:
    """Istirahat di ranjang rumah warga untuk memulihkan HP hero ke 100% penuh."""
    if hero is None:
        return ActionResult(False, "Hero tidak valid!", duration=0.0)
    ok, msg = world_state.rest_hero(hero)
    return ActionResult(ok, msg, duration=3.0)


def equip_loadout(world_state: WorldState, loadout_dict: Dict[str, str]) -> ActionResult:
    """Memverifikasi kepemilikan item dan memasang loadout perlengkapan tempur hero."""
    for slot, item_name in loadout_dict.items():
        if item_name and not world_state.inventory.has_item(item_name, 1):
            return ActionResult(False, f"Precondition gagal: Hero belum memiliki '{item_name}' untuk slot {slot}!", duration=0.0)

    # Catat loadout aktif ke inventory
    world_state.inventory.equipped = dict(loadout_dict)
    return ActionResult(True, f"Loadout berhasil dipasang: {loadout_dict}", duration=0.5)


def start_boss_battle(world_state: WorldState, hero: Any = None, game: Any = None,
                      rng_seed: Optional[int] = None) -> ActionResult:
    """
    Eksekusi pertarungan boss melawan Skeleton Overlord (Hero Minimax vs Boss Minimax).
    Bila Menang: world_state.boss_defeated = True, game tamat (layar kemenangan).
    Bila Kalah: hero respawn di spawn/bed dengan HP reset, potion berkurang sesuai yang terpakai,
    dan memicu REPLAN otomatis (ActionResult.success = False).
    """
    if not world_state.gate.is_open:
        return ActionResult(False, "Precondition gagal: Gerbang menuju Boss masih terkunci!", duration=0.0)

    # Bila game berjalan interaktif
    if game is not None and hasattr(game, "start_battle"):
        game.start_battle()
        return ActionResult(True, "Persiapan Boss Battle dimulai!", duration=10.0)

    # Simulasi pertarungan Minimax sungguhan (Headless / Automated Execution)
    import random
    from ai.adversarial import BattleState, apply_action, is_terminal, pure_minimax_root, hero_actions
    from battle.csp_loadout import apply_loadout

    inv_potions = world_state.inventory.get_item_count("potion_red")
    loadout = getattr(world_state.inventory, "equipped", {})
    if not loadout:
        loadout = {"WEAPON": "Pedang Biasa", "ARMOR": "Kain"}

    formatted_loadout = {
        "WEAPON": loadout.get("weapon") or loadout.get("WEAPON") or "Pedang Biasa",
        "ARMOR": loadout.get("armor") or loadout.get("ARMOR") or "Kain",
        "CHARM": loadout.get("charm") or loadout.get("CHARM") or "Kosong",
        "CONSUMABLE": loadout.get("consumable") or loadout.get("CONSUMABLE") or "Kosong"
    }

    base_st = BattleState(player_hp=getattr(hero, "hp", 100) if hero else 100,
                          boss_hp=config.BOSS_MAX_HP, potion_count=inv_potions)
    st = apply_loadout(base_st, formatted_loadout, base_potion_count=inv_potions)
    initial_potions = st.potion_count

    rng = random.Random(rng_seed) if rng_seed is not None else random.Random(42)

    while not is_terminal(st):
        if st.turn == "player":
            # Kebijakan Hero 1b (sesuai spesifikasi Bagian 1b):
            # Finisher: jika boss bisa ditumbangkan langsung, serang!
            min_hero_dmg = config.HERO_ATTACK_DMG[0] + getattr(st, "hero_attack_bonus", 0)
            if st.boss_hp <= min_hero_dmg and not st.boss_defending:
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

    potions_used = max(0, initial_potions - st.potion_count)
    if potions_used > 0:
        world_state.inventory.remove_item("potion_red", potions_used)

    if st.boss_hp <= 0:
        world_state.boss_defeated = True
        return ActionResult(True, f"Hero MENANG melawan Boss! (Sisa HP Hero: {st.player_hp}, Boss: {st.boss_hp})", duration=10.0)
    else:
        # Kalah: Respawn di spawn dengan HP reset
        if hero is not None:
            if hasattr(hero, "hp"):
                hero.hp = getattr(hero, "max_hp", 100)
            if hasattr(hero, "alive"):
                hero.alive = True
            locs = getattr(config, "LOCATIONS", {})
            if "spawn" in locs:
                if hasattr(hero, "px"):
                    hero.px, hero.py = float(locs["spawn"][0]), float(locs["spawn"][1])
        return ActionResult(False, f"Hero KALAH melawan Boss (Sisa HP Boss: {st.boss_hp})! Respawn di spawn, terpakai {potions_used} potion. Replan!", duration=10.0)
