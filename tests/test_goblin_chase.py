"""
test_goblin_chase.py - Pengujian Unit Perilaku Pengejaran Goblin pada Range Tertentu.
"""

import unittest
import math
import os
import sys
import pygame

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
os.environ["SDL_VIDEODRIVER"] = "dummy"
pygame.init()
pygame.display.set_mode((100, 100), pygame.HIDDEN)

from entities.goblin import Goblin
import combat_config as ccfg


class DummyPlayer:
    def __init__(self, px: float, py: float):
        self.px = px
        self.py = py
        self.alive = True
        self.damage_taken = 0

    def take_combat_damage(self, amount: int, kb_dir):
        self.damage_taken += amount
        return amount


class DummyGameMap:
    def move_and_slide(self, hb, vx_dt, vy_dt):
        hb.x += int(vx_dt)
        hb.y += int(vy_dt)
        return vx_dt, vy_dt

    def is_solid(self, hb):
        return False


class TestGoblinChaseRange(unittest.TestCase):

    def setUp(self):
        self.gob = Goblin(500.0, 500.0, anims={})
        self.game_map = DummyGameMap()

    def test_01_idle_when_player_out_of_range(self):
        """Goblin tetap IDLE saat player berada di luar jarak deteksi (> GOB_CHASE_RADIUS)."""
        # Player di jarak 400 px (> 240 px)
        player = DummyPlayer(900.0, 500.0)
        self.gob.update(0.1, player, self.game_map)
        self.assertEqual(self.gob.state, Goblin.STATE_IDLE)

    def test_02_chase_when_player_in_range(self):
        """Goblin beralih ke STATE_CHASE saat player masuk ke dalam range (<= GOB_CHASE_RADIUS)."""
        # Player di jarak 180 px (< 240 px)
        player = DummyPlayer(680.0, 500.0)
        self.gob.update(0.1, player, self.game_map)
        self.assertEqual(self.gob.state, Goblin.STATE_CHASE)

    def test_03_movement_towards_player_in_chase(self):
        """Dalam STATE_CHASE, goblin bergerak mendekati koordinat player."""
        player = DummyPlayer(700.0, 500.0)  # di sebelah kanan
        initial_x = self.gob.x
        
        # Update dalam range pengejaran
        self.gob.update(0.1, player, self.game_map)
        self.assertEqual(self.gob.state, Goblin.STATE_CHASE)
        
        # Panggil update kedua agar gerak slide dieksekusi
        self.gob.update(0.2, player, self.game_map)
        self.assertGreater(self.gob.x, initial_x, "Koordinat X goblin harus bergerak ke arah player (kanan)")
        self.assertEqual(self.gob.direction, "right")

    def test_04_attack_when_in_melee_range(self):
        """Goblin beralih ke STATE_ATTACK saat jarak <= GOB_ATTACK_RANGE."""
        # Player sangat dekat, jarak 20 px (< 36 px)
        player = DummyPlayer(520.0, 500.0)
        self.gob.state = Goblin.STATE_CHASE
        self.gob.attack_cooldown = 0.0
        
        self.gob.update(0.1, player, self.game_map)
        self.assertEqual(self.gob.state, Goblin.STATE_ATTACK)

    def test_05_deleash_when_player_escapes_far(self):
        """Goblin melepaskan pengejaran dan kembali ke IDLE saat player kabur (> GOB_DELEASH_RADIUS)."""
        self.gob.state = Goblin.STATE_CHASE
        # Player kabur jauh: jarak 500 px (> GOB_DELEASH_RADIUS)
        player = DummyPlayer(1000.0, 500.0)
        
        self.gob.update(0.1, player, self.game_map)
        self.assertEqual(self.gob.state, Goblin.STATE_IDLE)

    def test_06_deleash_when_exceeding_spawn_territory(self):
        """Goblin melepaskan pengejaran jika terpancing keluar terlalu jauh dari titik spawn-nya."""
        self.gob.state = Goblin.STATE_CHASE
        # Pindahkan posisi goblin 300 px dari titik spawn (500, 500)
        self.gob.x = 800.0
        self.gob.y = 500.0
        # Player ada di dekat goblin (jarak 50 px, masih dalam DELEASH_RADIUS)
        player = DummyPlayer(850.0, 500.0)

        self.gob.update(0.1, player, self.game_map)
        self.assertEqual(self.gob.state, Goblin.STATE_IDLE, "Goblin harus kembali IDLE jika melebihi GOB_MAX_LEASH_DIST dari spawn")
        self.assertEqual(self.gob.patrol_target, (self.gob.spawn_x, self.gob.spawn_y), "Patrol target harus diarahkan pulang ke spawn")

    def test_07_deleash_cooldown_prevents_instant_reaggro(self):
        """Setelah de-leash, goblin memiliki jeda cooldown dan tidak langsung mengejar kembali seketika."""
        self.gob.state = Goblin.STATE_IDLE
        self.gob.deleash_cooldown = 2.0
        # Player berada dalam range kejar normal (150 px < GOB_CHASE_RADIUS)
        player = DummyPlayer(650.0, 500.0)

        self.gob.update(0.1, player, self.game_map)
        self.assertEqual(self.gob.state, Goblin.STATE_IDLE, "Goblin tidak boleh langsung re-aggro selama deleash_cooldown aktif")


if __name__ == "__main__":
    unittest.main()

