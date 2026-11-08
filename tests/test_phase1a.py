"""
test_phase1a.py - Unit Test Komprehensif Sistem Game Minimal Fase 1A

Menguji seluruh subsistem Fase 1A:
  1. Inventori 12 slot & tumpukan item (stackable)
  2. Ekonomi toko desa (beli, jual, koin, stok)
  3. Ladang pertanian bertahap (tanam, siram 2x speed, 6 tahap tumbuh, panen)
  4. Crafting workshop (Potion & Kunci Gerbang) dan sumber daya alam
  5. Rest di rumah memulihkan HP
  6. Gerbang terkunci & pengaruh obstacle dinamis terhadap akses ke Boss
  7. Integrasi Potion & Batasan Kepemilikan (Owned Constraint) pada CSP Loadout
  8. Save/Load atomik dengan pemulihan cadangan (.bak)
"""

import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import pygame

# Inisialisasi pygame headless
os.environ["SDL_VIDEODRIVER"] = "dummy"
pygame.init()
pygame.display.set_mode((1024, 768))

import config
from inventory import Inventory, ItemStack, ITEM_DEFINITIONS
from economy import Shop
from farm import CropPlot, FarmManager
from world_state import WorldState, LockedGate
from battle.csp_loadout import LoadoutCSPSolver, check_constraints, apply_loadout
from ai.adversarial import BattleState


class TestInventorySystem(unittest.TestCase):
    """Pengujian sistem inventori 12 slot dan pengelolaan item."""

    def setUp(self):
        self.inv = Inventory(max_slots=12)

    def test_max_12_slots_capacity(self):
        self.assertEqual(self.inv.max_slots, 12)
        self.assertEqual(len(self.inv.slots), 12)
        self.assertFalse(self.inv.is_full())

        # Isi 12 slot dengan item non-stackable (senjata/kunci)
        for i in range(12):
            leftover = self.inv.add_item("key", 1)
            self.assertEqual(leftover, 0)

        self.assertTrue(self.inv.is_full())
        # Menambah item baru ke tas penuh harus gagal dan mengembalikan sisa
        leftover = self.inv.add_item("Pedang Biasa", 1)
        self.assertEqual(leftover, 1)

    def test_item_stacking_limits(self):
        # Material stackable hingga 99
        leftover = self.inv.add_item("wood", 50)
        self.assertEqual(leftover, 0)
        self.assertEqual(self.inv.get_item_count("wood"), 50)

        leftover = self.inv.add_item("wood", 60)
        self.assertEqual(leftover, 0)
        self.assertEqual(self.inv.get_item_count("wood"), 110)
        # 110 kayu harus mengisi 2 slot: 99 di slot 1 dan 11 di slot 2
        self.assertEqual(self.inv.slots[0].count, 99)
        self.assertEqual(self.inv.slots[1].count, 11)

        # Equipment max_stack = 1
        self.inv.add_item("Pedang Biasa", 1)
        self.assertEqual(self.inv.slots[2].count, 1)
        self.assertEqual(self.inv.slots[2].max_stack, 1)

    def test_remove_and_has_item(self):
        self.inv.add_item("radish", 5)
        self.assertTrue(self.inv.has_item("radish", 5))
        self.assertFalse(self.inv.has_item("radish", 6))

        ok = self.inv.remove_item("radish", 3)
        self.assertTrue(ok)
        self.assertEqual(self.inv.get_item_count("radish"), 2)

        ok = self.inv.remove_item("radish", 2)
        self.assertTrue(ok)
        self.assertEqual(self.inv.get_item_count("radish"), 0)
        self.assertFalse(self.inv.has_item("radish", 1))

    def test_serialization_to_from_dict(self):
        self.inv.add_item("potion_red", 3)
        self.inv.add_item("key", 1)
        data = self.inv.to_dict()

        new_inv = Inventory(max_slots=12)
        new_inv.from_dict(data)
        self.assertEqual(new_inv.get_item_count("potion_red"), 3)
        self.assertEqual(new_inv.get_item_count("key"), 1)


class TestEconomySystem(unittest.TestCase):
    """Pengujian toko desa dan sistem transaksi koin."""

    def setUp(self):
        self.shop = Shop()
        self.inv = Inventory(max_slots=12)

    def test_buy_item_success_and_failure(self):
        coins = 50
        # Beli benih lobak seharga 5 koin
        ok, coins, msg = self.shop.buy_item("seeds_radish", 2, coins, self.inv)
        self.assertTrue(ok)
        self.assertEqual(coins, 40)
        self.assertEqual(self.inv.get_item_count("seeds_radish"), 2)

        # Coba beli barang mahal dengan koin kurang (Besi = 45 koin, sisa 40)
        ok, coins, msg = self.shop.buy_item("Besi", 1, coins, self.inv)
        self.assertFalse(ok)
        self.assertEqual(coins, 40)
        self.assertFalse(self.inv.has_item("Besi", 1))

    def test_sell_item_success(self):
        coins = 10
        self.inv.add_item("radish", 2)  # harga jual lobak = 10 koin
        ok, coins, msg = self.shop.sell_item("radish", 2, coins, self.inv)
        self.assertTrue(ok)
        self.assertEqual(coins, 30)
        self.assertEqual(self.inv.get_item_count("radish"), 0)


class TestFarmSystem(unittest.TestCase):
    """Pengujian sistem ladang bertahap."""

    def setUp(self):
        self.farm = FarmManager()
        self.inv = Inventory(max_slots=12)

    def test_six_crop_plots_initialized(self):
        self.assertEqual(len(self.farm.plots), 6)
        coords = [(p.x, p.y) for p in self.farm.plots]
        self.assertIn((480, 384), coords)
        self.assertIn((544, 416), coords)

    def test_planting_and_growth_stages(self):
        plot = self.farm.plots[0]
        self.assertIsNone(plot.crop_type)

        # Coba tanam tanpa benih -> gagal
        ok, msg = plot.plant("radish", self.inv)
        self.assertFalse(ok)

        # Beri benih lalu tanam
        self.inv.add_item("seeds_radish", 1)
        ok, msg = plot.plant("radish", self.inv)
        self.assertTrue(ok)
        self.assertEqual(plot.crop_type, "radish")
        self.assertEqual(plot.stage, 0)
        self.assertFalse(plot.is_mature)

        # Siram air -> kecepatan tumbuh meningkat
        ok, msg = plot.water()
        self.assertTrue(ok)
        self.assertTrue(plot.is_watered)

        # Update 5 detik (karena basah, 5s * 2x = 10s -> naik ke tahap 1)
        plot.update(5.0)
        self.assertEqual(plot.stage, 1)

        # Lanjutkan update sampai tahap 5 (matang)
        for _ in range(4):
            plot.water()
            plot.update(5.0)

        self.assertEqual(plot.stage, 5)
        self.assertTrue(plot.is_mature)

        # Panen hasil
        ok, msg = plot.harvest(self.inv)
        self.assertTrue(ok)
        self.assertEqual(self.inv.get_item_count("radish"), 1)
        self.assertIsNone(plot.crop_type)


class TestWorldStateAndCrafting(unittest.TestCase):
    """Pengujian state terpusat, crafting workshop, dan sumber daya."""

    def setUp(self):
        self.ws = WorldState(starting_coins=50)

    def test_starter_items(self):
        self.assertEqual(self.ws.coins, 50)
        self.assertEqual(self.ws.inventory.get_item_count("Pedang Biasa"), 1)
        self.assertEqual(self.ws.inventory.get_item_count("Kain"), 1)
        self.assertEqual(self.ws.inventory.get_item_count("seeds_radish"), 0)
        self.assertEqual(self.ws.inventory.get_item_count("bottle_empty"), 0)

    def test_craft_health_potion(self):
        # Tambah botol kosong untuk fixture tes
        self.ws.inventory.add_item("bottle_empty", 1)

        # Tanpa lobak -> gagal
        ok, msg = self.ws.craft_potion()
        self.assertFalse(ok)

        # Panen/tambah 1 lobak
        self.ws.inventory.add_item("radish", 1)
        ok, msg = self.ws.craft_potion()
        self.assertTrue(ok)
        self.assertEqual(self.ws.inventory.get_item_count("potion_red"), 1)
        self.assertEqual(self.ws.inventory.get_item_count("radish"), 0)
        self.assertEqual(self.ws.inventory.get_item_count("bottle_empty"), 0)

    def test_craft_gate_key(self):
        self.ws.inventory.add_item("wood", 1)
        self.ws.inventory.add_item("rock", 1)
        ok, msg = self.ws.craft_gate_key()
        self.assertTrue(ok)
        self.assertEqual(self.ws.inventory.get_item_count("key"), 1)
        self.assertEqual(self.ws.inventory.get_item_count("wood"), 0)
        self.assertEqual(self.ws.inventory.get_item_count("rock"), 0)

    def test_locked_gate_interaction(self):
        gate = self.ws.gate
        self.assertFalse(gate.is_open)
        self.assertIsNotNone(gate.get_obstacle_rect())

        # Coba buka tanpa kunci -> gagal
        ok, msg = gate.unlock(self.ws.inventory)
        self.assertFalse(ok)
        self.assertFalse(gate.is_open)

        # Beri kunci lalu buka
        self.ws.inventory.add_item("key", 1)
        ok, msg = gate.unlock(self.ws.inventory)
        self.assertTrue(ok)
        self.assertTrue(gate.is_open)
        self.assertIsNone(gate.get_obstacle_rect())
        self.assertEqual(self.ws.inventory.get_item_count("key"), 0)

    def test_rest_hero(self):
        class DummyHero:
            hp = 40
            max_hp = 100

        hero = DummyHero()
        ok, msg = self.ws.rest_hero(hero)
        self.assertTrue(ok)
        self.assertEqual(hero.hp, 100)

        # Istirahat saat HP sudah penuh
        ok, msg = self.ws.rest_hero(hero)
        self.assertFalse(ok)

    def test_atomic_save_and_backup_recovery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "savegame.json")
            self.ws.coins = 125
            self.ws.inventory.add_item("potion_red", 2)
            self.ws.gate.is_open = True

            ok = self.ws.save_game(save_path)
            self.assertTrue(ok)
            self.assertTrue(os.path.isfile(save_path))

            # Simpan kedua kalinya untuk membentuk file .bak
            self.ws.coins = 150
            self.ws.save_game(save_path)
            self.assertTrue(os.path.isfile(save_path + ".bak"))

            # Buat file utama korup
            with open(save_path, "w", encoding="utf-8") as f:
                f.write("CORRUPT_JSON_DATA{{{")

            # Load game harus otomatis memulihkan dari .bak
            new_ws = WorldState()
            loaded = new_ws.load_game(save_path)
            self.assertTrue(loaded)
            self.assertEqual(new_ws.coins, 125)
            self.assertTrue(new_ws.gate.is_open)


class TestBattleAndCSPOwnedIntegration(unittest.TestCase):
    """Pengujian sinkronisasi potion battle dan constraint kepemilikan item (owned)."""

    def test_csp_owned_constraint_starter_gear(self):
        # Hero hanya punya starter gear: Pedang Biasa dan Kain
        owned = {"Pedang Biasa", "Kain"}
        solver = LoadoutCSPSolver(owned_items=owned)

        solutions, stats = solver.solve_all()
        # Harus ada tepat 1 solusi valid yang hanya memakai Pedang Biasa dan Kain
        self.assertEqual(len(solutions), 1)
        best, stats = solver.best_loadout()
        self.assertEqual(best["WEAPON"], "Pedang Biasa")
        self.assertEqual(best["ARMOR"], "Kain")
        self.assertEqual(best["CHARM"], "Kosong")
        self.assertEqual(best["CONSUMABLE"], "Kosong")

        valid, _ = check_constraints(best, constraints=solver.constraints)
        self.assertTrue(valid)

    def test_csp_unowned_item_rejected(self):
        owned = {"Pedang Biasa", "Kain"}
        solver = LoadoutCSPSolver(owned_items=owned)

        # Coba loadout yang memakai Kapak Berat (belum dibeli)
        invalid_loadout = {
            "WEAPON": "Kapak Berat",
            "ARMOR": "Kain",
            "CHARM": "Kosong",
            "CONSUMABLE": "Kosong"
        }
        valid, reason = check_constraints(invalid_loadout, constraints=solver.constraints)
        self.assertFalse(valid)
        self.assertIn("Kapak Berat", reason)

    def test_battle_potion_count_synchronization(self):
        # 1. Hero membawa 4 potion di inventori
        base_state = BattleState(player_hp=100, boss_hp=120)
        loadout = {"WEAPON": "Pedang Biasa", "ARMOR": "Kain", "CHARM": "Kosong", "CONSUMABLE": "Kosong"}

        battle_state = apply_loadout(base_state, loadout, base_potion_count=4)
        self.assertEqual(battle_state.potion_count, 4)

        # 2. Hero tidak membawa potion (0)
        empty_state = apply_loadout(base_state, loadout, base_potion_count=0)
        self.assertEqual(empty_state.potion_count, 0)


if __name__ == "__main__":
    unittest.main()
