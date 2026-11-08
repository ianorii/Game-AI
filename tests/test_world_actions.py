"""
test_world_actions.py - Pengujian API Aksi Dunia Tunggal untuk Planner & Player

Memverifikasi:
  1. Kontrak kembalian ActionResult(success, message, duration, cost).
  2. Prekondisi dan efek perubahan state pada setiap fungsi aksi.
  3. Keterjangkauan (reachability) seluruh lokasi di LOCATIONS melalui algoritma A*.
  4. Eksekusi headless tanpa GUI/window display.
"""

import unittest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import pygame

# Set headless display driver untuk lingkungan uji tanpa layar
os.environ["SDL_VIDEODRIVER"] = "dummy"
pygame.init()

import config
from world_state import WorldState
import world_actions
from world.game_map import GameMap
from ai.pathfinding import astar


class DummyHero:
    def __init__(self, x=1440.0, y=1056.0, hp=40, max_hp=100):
        self.x = float(x)
        self.y = float(y)
        self.hp = hp
        self.max_hp = max_hp
        self.cell = (int(self.x // 32), int(self.y // 32))


class TestWorldActions(unittest.TestCase):
    """Suite pengujian unit untuk modul world_actions."""

    def setUp(self):
        self.ws = WorldState(starting_coins=100)
        self.hero = DummyHero()

    def test_action_result_structure(self):
        res = world_actions.ActionResult(True, "Aksi berhasil", duration=1.5, cost=10)
        self.assertTrue(res.success)
        self.assertEqual(res.message, "Aksi berhasil")
        self.assertEqual(res.duration, 1.5)
        self.assertEqual(res.cost, 10)

    def test_goto_location(self):
        # Lokasi valid
        res = world_actions.goto_location(self.ws, self.hero, "shop")
        self.assertTrue(res.success)
        self.assertEqual(self.hero.x, float(config.LOCATIONS["shop"][0]))
        self.assertEqual(self.hero.y, float(config.LOCATIONS["shop"][1]))

        # Lokasi tidak valid
        res_invalid = world_actions.goto_location(self.ws, self.hero, "lokasi_khayalan_xyz")
        self.assertFalse(res_invalid.success)

    def test_farming_cycle_actions(self):
        # 1. Plant tanpa benih -> Gagal
        res_plant = world_actions.plant(self.ws, "radish")
        self.assertFalse(res_plant.success)

        # Beri benih lalu tanam
        self.ws.inventory.add_item("seeds_radish", 1)
        res_plant = world_actions.plant(self.ws, "radish")
        self.assertTrue(res_plant.success)
        self.assertEqual(self.ws.inventory.get_item_count("seeds_radish"), 0)

        # 2. Water
        res_water = world_actions.water(self.ws)
        self.assertTrue(res_water.success)
        self.assertTrue(self.ws.farm.plots[0].is_watered)

        # 3. Harvest sebelum matang -> Gagal
        res_harv = world_actions.harvest(self.ws)
        self.assertFalse(res_harv.success)

        # Simulasikan pertumbuhan sampai matang (stage 5)
        self.ws.farm.plots[0].stage = 5
        res_harv = world_actions.harvest(self.ws)
        self.assertTrue(res_harv.success)
        self.assertEqual(self.ws.inventory.get_item_count("radish"), 1)
        self.assertIsNone(self.ws.farm.plots[0].crop_type)

    def test_economy_actions(self):
        # Beli benih di toko
        res_buy = world_actions.buy(self.ws, "seeds_radish", 2)
        self.assertTrue(res_buy.success)
        self.assertEqual(self.ws.inventory.get_item_count("seeds_radish"), 2)
        self.assertEqual(self.ws.coins, 100 - (res_buy.cost))

        # Jual hasil panen
        self.ws.inventory.add_item("radish", 1)
        res_sell = world_actions.sell(self.ws, "radish", 1)
        self.assertTrue(res_sell.success)
        self.assertEqual(self.ws.inventory.get_item_count("radish"), 0)
        self.assertLess(res_sell.cost, 0)  # Pendapatan koin bertanda negatif di cost

    def test_crafting_and_gate_actions(self):
        # Crafting Potion
        self.ws.inventory.add_item("radish", 1)
        self.ws.inventory.add_item("bottle_empty", 1)
        res_pot = world_actions.craft_potion(self.ws)
        self.assertTrue(res_pot.success)
        self.assertEqual(self.ws.inventory.get_item_count("potion_red"), 1)

        # Crafting Kunci
        self.ws.inventory.add_item("wood", 1)
        self.ws.inventory.add_item("rock", 1)
        res_key = world_actions.craft_key(self.ws)
        self.assertTrue(res_key.success)
        self.assertEqual(self.ws.inventory.get_item_count("key"), 1)

        # Buka gerbang dengan kunci
        res_gate = world_actions.open_gate(self.ws)
        self.assertTrue(res_gate.success)
        self.assertTrue(self.ws.gate.is_open)

    def test_rest_action(self):
        self.assertEqual(self.hero.hp, 40)
        res_rest = world_actions.rest(self.ws, self.hero)
        self.assertTrue(res_rest.success)
        self.assertEqual(self.hero.hp, 100)

    def test_equip_loadout_action(self):
        # Mencoba memasang senjata yang belum dimiliki
        res_fail = world_actions.equip_loadout(self.ws, {"WEAPON": "Kapak Berat", "ARMOR": "Kain"})
        self.assertFalse(res_fail.success)

        # Memasang loadout dengan item yang dimiliki
        res_ok = world_actions.equip_loadout(self.ws, {"WEAPON": "Pedang Biasa", "ARMOR": "Kain"})
        self.assertTrue(res_ok.success)
        self.assertEqual(self.ws.inventory.equipped["WEAPON"], "Pedang Biasa")

    def test_locations_reachability_from_spawn(self):
        """Memverifikasi seluruh lokasi di config.LOCATIONS dapat dicapai dari titik spawn melalui A*."""
        game_map = GameMap(scale=2)
        w, h = 86, 48
        spawn_px, spawn_py = config.LOCATIONS["spawn"]
        spawn_cell = (spawn_px // 32, spawn_py // 32)

        def is_blocked(cx, cy):
            px = cx * 32 + 16
            py = cy * 32 + 16
            return not game_map.is_walkable_at(px, py)

        for loc_name, (lx, ly) in config.LOCATIONS.items():
            self.assertTrue(game_map.is_walkable_at(lx, ly), f"Titik {loc_name} ({lx}, {ly}) tidak dapat dipijak (non-walkable)!")
            dest_cell = (lx // 32, ly // 32)
            res = astar(w, h, spawn_cell, dest_cell, is_blocked)
            self.assertTrue(res.found, f"Titik {loc_name} ({lx}, {ly}) tidak dapat dicapai dari spawn melalui A*!")

    def test_mission_feasibility_two_distinct_paths(self):
        """
        Memverifikasi kelayakan misi mencapai Boss dari state awal Game Baru (20 koin, tanpa bahan)
        melalui minimal DUA rencana manual berbeda secara headless:
          Jalur 1: Pertanian (tanam lobak, siram, panen, craft potion & key, jual kelebihan).
          Jalur 2: Peternakan & Memancing (kumpul telur, susu, ikan, jual ke toko, beli armor/senjata baru, craft key).
        """
        # ======================================================================
        # JALUR 1: PERTANIAN (FARMING PATH)
        # ======================================================================
        ws_a = WorldState(starting_coins=20)
        hero_a = DummyHero()
        time_a = 0.0

        # Beli benih dan botol kosong
        r = world_actions.goto_location(ws_a, hero_a, "shop"); self.assertTrue(r.success); time_a += r.duration
        r = world_actions.buy(ws_a, "seeds_radish", 2); self.assertTrue(r.success); time_a += r.duration
        r = world_actions.buy(ws_a, "bottle_empty", 1); self.assertTrue(r.success); time_a += r.duration
        self.assertEqual(ws_a.coins, 2)

        # Tanam di petak ladang
        r = world_actions.goto_location(ws_a, hero_a, "farm"); self.assertTrue(r.success); time_a += r.duration
        r = world_actions.plant(ws_a, "radish", 0); self.assertTrue(r.success); time_a += r.duration
        r = world_actions.plant(ws_a, "radish", 1); self.assertTrue(r.success); time_a += r.duration

        # Tumbuh 5 tahap
        for _ in range(5):
            world_actions.water(ws_a, 0); time_a += 0.5
            world_actions.water(ws_a, 1); time_a += 0.5
            ws_a.update(5.0); time_a += 5.0

        # Panen
        r = world_actions.harvest(ws_a, 0); self.assertTrue(r.success); time_a += r.duration
        r = world_actions.harvest(ws_a, 1); self.assertTrue(r.success); time_a += r.duration
        self.assertEqual(ws_a.inventory.get_item_count("radish"), 2)

        # Bahan kunci: tebang kayu & tambang batu
        r = world_actions.goto_location(ws_a, hero_a, "forest_wood"); self.assertTrue(r.success); time_a += r.duration
        r = world_actions.chop_wood(ws_a); self.assertTrue(r.success); time_a += r.duration
        r = world_actions.goto_location(ws_a, hero_a, "quarry_rock"); self.assertTrue(r.success); time_a += r.duration
        r = world_actions.mine_rock(ws_a); self.assertTrue(r.success); time_a += r.duration

        # Bengkel: Crafting Kunci dan Ramuan
        r = world_actions.goto_location(ws_a, hero_a, "workshop"); self.assertTrue(r.success); time_a += r.duration
        r = world_actions.craft_key(ws_a); self.assertTrue(r.success); time_a += r.duration
        r = world_actions.craft_potion(ws_a); self.assertTrue(r.success); time_a += r.duration
        self.assertEqual(ws_a.inventory.get_item_count("key"), 1)
        self.assertEqual(ws_a.inventory.get_item_count("potion_red"), 1)

        # Jual sisa 1 lobak ke toko
        r = world_actions.goto_location(ws_a, hero_a, "shop"); self.assertTrue(r.success); time_a += r.duration
        r = world_actions.sell(ws_a, "radish", 1); self.assertTrue(r.success); time_a += r.duration
        self.assertEqual(ws_a.coins, 12)

        # Pasang loadout starter + ramuan
        r = world_actions.equip_loadout(ws_a, {"WEAPON": "Pedang Biasa", "ARMOR": "Kain", "CONSUMABLE": "potion_red"})
        self.assertTrue(r.success); time_a += r.duration

        # Buka gerbang & capai Boss
        r = world_actions.goto_location(ws_a, hero_a, "gate"); self.assertTrue(r.success); time_a += r.duration
        r = world_actions.open_gate(ws_a); self.assertTrue(r.success); time_a += r.duration
        self.assertTrue(ws_a.gate.is_open)
        r = world_actions.goto_location(ws_a, hero_a, "boss"); self.assertTrue(r.success); time_a += r.duration
        self.assertGreater(time_a, 0.0)

        # ======================================================================
        # JALUR 2: PETERNAKAN & MEMANCING (HUSBANDRY & FISHING PATH)
        # ======================================================================
        ws_b = WorldState(starting_coins=20)
        hero_b = DummyHero()
        time_b = 0.0

        # Kumpulkan telur, susu, ikan
        r = world_actions.goto_location(ws_b, hero_b, "chicken_coop"); self.assertTrue(r.success); time_b += r.duration
        r = world_actions.collect_egg(ws_b); self.assertTrue(r.success); time_b += r.duration
        r = world_actions.goto_location(ws_b, hero_b, "cow_pasture"); self.assertTrue(r.success); time_b += r.duration
        r = world_actions.collect_milk(ws_b); self.assertTrue(r.success); time_b += r.duration
        r = world_actions.goto_location(ws_b, hero_b, "river_fishing"); self.assertTrue(r.success); time_b += r.duration
        r = world_actions.fish(ws_b); self.assertTrue(r.success); time_b += r.duration

        # Bahan kunci
        r = world_actions.goto_location(ws_b, hero_b, "forest_wood"); self.assertTrue(r.success); time_b += r.duration
        r = world_actions.chop_wood(ws_b); self.assertTrue(r.success); time_b += r.duration
        r = world_actions.goto_location(ws_b, hero_b, "quarry_rock"); self.assertTrue(r.success); time_b += r.duration
        r = world_actions.mine_rock(ws_b); self.assertTrue(r.success); time_b += r.duration

        # Jual hasil sumber daya ke toko (20 + 6 + 12 + 15 = 53 koin)
        r = world_actions.goto_location(ws_b, hero_b, "shop"); self.assertTrue(r.success); time_b += r.duration
        r = world_actions.sell(ws_b, "egg", 1); self.assertTrue(r.success); time_b += r.duration
        r = world_actions.sell(ws_b, "milk", 1); self.assertTrue(r.success); time_b += r.duration
        r = world_actions.sell(ws_b, "fish", 1); self.assertTrue(r.success); time_b += r.duration
        self.assertEqual(ws_b.coins, 53)

        # Beli perlengkapan tempur baru di toko (Zirah Kulit 20 koin, Belati Cepat 25 koin)
        r = world_actions.buy(ws_b, "Kulit", 1); self.assertTrue(r.success); time_b += r.duration
        r = world_actions.buy(ws_b, "Belati Cepat", 1); self.assertTrue(r.success); time_b += r.duration
        self.assertEqual(ws_b.coins, 8)

        # Bengkel: Crafting Kunci
        r = world_actions.goto_location(ws_b, hero_b, "workshop"); self.assertTrue(r.success); time_b += r.duration
        r = world_actions.craft_key(ws_b); self.assertTrue(r.success); time_b += r.duration
        self.assertEqual(ws_b.inventory.get_item_count("key"), 1)

        # Pasang loadout baru hasil perdagangan
        r = world_actions.equip_loadout(ws_b, {"WEAPON": "Belati Cepat", "ARMOR": "Kulit"})
        self.assertTrue(r.success); time_b += r.duration
        self.assertEqual(ws_b.inventory.equipped["WEAPON"], "Belati Cepat")
        self.assertEqual(ws_b.inventory.equipped["ARMOR"], "Kulit")

        # Buka gerbang & capai Boss
        r = world_actions.goto_location(ws_b, hero_b, "gate"); self.assertTrue(r.success); time_b += r.duration
        r = world_actions.open_gate(ws_b); self.assertTrue(r.success); time_b += r.duration
        self.assertTrue(ws_b.gate.is_open)
        r = world_actions.goto_location(ws_b, hero_b, "boss"); self.assertTrue(r.success); time_b += r.duration
        self.assertGreater(time_b, 0.0)


if __name__ == "__main__":
    unittest.main()

