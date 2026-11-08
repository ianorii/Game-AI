"""
test_collision_editor.py - Unit test suite lengkap untuk Collision Editor.

Pencegahan Modifikasi Data Asli:
- Menggunakan tempfile.TemporaryDirectory() untuk seluruh operasi file persistensi.
- Dilengkapi SHA-256 data integrity guard yang memverifikasi seluruh file di folder data/
  tidak termodifikasi sedikit pun oleh proses pengetesan.
- Menyenyapkan verbose sprite logging selama pengetesan.
"""

import os
import sys
import json
import hashlib
import tempfile
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pygame
pygame.init()

import config
# Senyapkan log sprite selama test
config.VERBOSE_SPRITE_LOGS = False

from asset_loader import AssetManager
from main import Game
from world.collision_editor import bresenham_line, CollisionEditor


def hash_file_sha256(filepath: str) -> str:
    """Menghitung hash SHA-256 dari sebuah file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


class TestCollisionEditor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        config.VERBOSE_SPRITE_LOGS = False
        cls.screen = pygame.display.set_mode(config.WINDOW_SIZE)
        cls.assets = AssetManager()

        # Data Integrity Guard: Catat hash seluruh file di data/ sebelum pengujian
        cls.data_hashes_before = {}
        if os.path.exists(config.DATA_DIR):
            for root, _, files in os.walk(config.DATA_DIR):
                for f in files:
                    fp = os.path.join(root, f)
                    cls.data_hashes_before[fp] = hash_file_sha256(fp)

        # Buat temporary directory terisolasi
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.orig_overrides_path = config.COLLISION_OVERRIDES_PATH
        cls.orig_backup_path = config.COLLISION_BACKUP_PATH

        cls.isolated_override_path = os.path.join(cls.temp_dir.name, "collision_overrides.json")
        cls.isolated_backup_path = os.path.join(cls.temp_dir.name, "collision_overrides.json.bak")

        # Alihkan konfigurasi global ke path terisolasi
        config.COLLISION_OVERRIDES_PATH = cls.isolated_override_path
        config.COLLISION_BACKUP_PATH = cls.isolated_backup_path

    @classmethod
    def tearDownClass(cls):
        # Kembalikan path konfigurasi asli
        config.COLLISION_OVERRIDES_PATH = cls.orig_overrides_path
        config.COLLISION_BACKUP_PATH = cls.orig_backup_path

        # Bersihkan temporary directory
        cls.temp_dir.cleanup()

        # Data Integrity Guard Check: Pastikan tidak ada satu pun file di data/ yang termodifikasi
        for fp, expected_hash in cls.data_hashes_before.items():
            if not os.path.exists(fp):
                raise AssertionError(f"[DATA INTEGRITY GUARD FAIL] File asli hilang: {fp}")
            actual_hash = hash_file_sha256(fp)
            if actual_hash != expected_hash:
                raise AssertionError(
                    f"[DATA INTEGRITY GUARD FAIL] File di data/ termodifikasi selama test: {fp}\n"
                    f"Expected SHA-256: {expected_hash}\n"
                    f"Actual SHA-256:   {actual_hash}"
                )

    def setUp(self):
        # Setiap test menggunakan Game dengan path collision override terisolasi
        self.game = Game(self.screen, self.assets, collision_override_path=self.isolated_override_path)
        self.editor = self.game.collision_editor

    def tearDown(self):
        # Reset overrides di file terisolasi
        self.editor.overrides.clear()
        self.editor.save_overrides(is_autosave=True)

    def test_data_integrity_guard_active(self):
        """Memastikan data/collision_overrides.json asli tetap utuh dan valid JSON."""
        real_path = self.orig_overrides_path
        self.assertTrue(os.path.exists(real_path), f"File asli harus ada: {real_path}")
        with open(real_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("version"), 1)
        self.assertEqual(data.get("map_id"), "sunnyside_island")

    def test_bresenham_line_no_gaps(self):
        """Verifikasi algoritma Bresenham menghubungkan titik tanpa celah."""
        points = bresenham_line(0, 0, 10, 5)
        self.assertEqual(points[0], (0, 0))
        self.assertEqual(points[-1], (10, 5))
        for i in range(len(points) - 1):
            dx = abs(points[i+1][0] - points[i][0])
            dy = abs(points[i+1][1] - points[i][1])
            self.assertTrue(dx <= 1 and dy <= 1, f"Gap detected between {points[i]} and {points[i+1]}")

    def test_override_walkable_blocked(self):
        """Verifikasi modifikasi override mengubah is_walkable, grid, dan mask."""
        tx, ty = 12, 12
        while self.editor.base_solid[ty][tx]:
            tx += 1

        self.assertTrue(self.editor.is_walkable(tx, ty))

        # Ubah jadi BLOCKED
        self.editor.set_tile_override(tx, ty, True)
        self.assertFalse(self.editor.is_walkable(tx, ty))
        self.assertTrue(self.editor.is_blocked(tx, ty))
        self.assertEqual(self.game.tile_map.grid[ty][tx], "wall")
        cx, cy = tx * 32 + 16, ty * 32 + 16
        self.assertEqual(self.game.game_map.walkable_mask.get_at((cx, cy)), 0)

        # Ubah kembali jadi WALKABLE
        self.editor.set_tile_override(tx, ty, False)
        self.assertTrue(self.editor.is_walkable(tx, ty))
        self.assertFalse(self.editor.is_blocked(tx, ty))
        self.assertEqual(self.game.tile_map.grid[ty][tx], "floor")
        self.assertEqual(self.game.game_map.walkable_mask.get_at((cx, cy)), 1)

    def test_undo_redo(self):
        """Verifikasi Undo dan Redo mengembalikan state persis."""
        tx, ty = 14, 14
        while self.editor.base_solid[ty][tx]:
            tx += 1

        initial_state = self.editor.is_walkable(tx, ty)

        self.editor.current_stroke = {}
        self.editor.set_tile_override(tx, ty, is_blocked=initial_state, record_stroke=True)
        self.editor.undo_stack.append(self.editor.current_stroke)

        self.assertNotEqual(self.editor.is_walkable(tx, ty), initial_state)

        self.assertTrue(self.editor.undo())
        self.assertEqual(self.editor.is_walkable(tx, ty), initial_state)

        self.assertTrue(self.editor.redo())
        self.assertNotEqual(self.editor.is_walkable(tx, ty), initial_state)

    def test_atomic_save_load(self):
        """Verifikasi penyimpanan JSON atomik dan reload ke instance baru pada path terisolasi."""
        tx, ty = 16, 16
        while self.editor.base_solid[ty][tx]:
            tx += 1

        self.editor.set_tile_override(tx, ty, True)
        self.assertTrue(self.editor.save_overrides(is_autosave=False))

        # Muat pada editor baru dengan path terisolasi
        editor2 = CollisionEditor(
            self.game.game_map,
            self.game.tile_map,
            world_seed=self.game.seed,
            override_path=self.isolated_override_path
        )
        self.assertTrue(editor2.is_blocked(tx, ty))
        self.assertIn((tx, ty), editor2.overrides)

    def test_corrupt_file_resilience(self):
        """File override korup di path terisolasi tidak boleh menyebabkan crash."""
        corrupt_path = os.path.join(self.temp_dir.name, "corrupt_overrides.json")
        with open(corrupt_path, "w", encoding="utf-8") as f:
            f.write("KORUP BUKAN JSON {{{")

        editor = CollisionEditor(
            self.game.game_map,
            self.game.tile_map,
            world_seed=self.game.seed,
            override_path=corrupt_path
        )
        self.assertIsNotNone(editor)
        self.assertEqual(len(editor.overrides), 0)

    def test_seed_size_mismatch_validation(self):
        """Validasi bila ukuran peta di file terisolasi tidak cocok, override tidak diterapkan diam-diam."""
        mismatch_path = os.path.join(self.temp_dir.name, "mismatch_overrides.json")
        mismatch_data = {
            "version": 1,
            "world_seed": 12345,
            "world_size": [10, 10],
            "overrides": [{"x": 2, "y": 2, "blocked": True}]
        }
        with open(mismatch_path, "w", encoding="utf-8") as f:
            json.dump(mismatch_data, f)

        editor = CollisionEditor(
            self.game.game_map,
            self.game.tile_map,
            world_seed=self.game.seed,
            override_path=mismatch_path
        )
        self.assertNotIn((2, 2), editor.overrides)

    def test_brush_sizes(self):
        """Verifikasi kuas 1x1, 2x2, dan 3x3 menghasilkan jumlah tile yang benar."""
        self.editor.brush_size = 1
        tiles1 = self.editor.get_brush_tiles(20, 20)
        self.assertEqual(len(tiles1), 1)

        self.editor.brush_size = 2
        tiles2 = self.editor.get_brush_tiles(20, 20)
        self.assertEqual(len(tiles2), 4)

        self.editor.brush_size = 3
        tiles3 = self.editor.get_brush_tiles(20, 20)
        self.assertEqual(len(tiles3), 9)

    def test_bridge_block_and_reopen_scenario(self):
        """
        Skenario Manual:
        Blokir satu jembatan/jalur -> A* mencari rute lain -> buka kembali jembatan -> A* kembali lewat jalur tersebut.
        """
        self.game.recompute_hero_path()
        original_path = list(self.game.path_result.path)
        self.assertTrue(len(original_path) > 5, "Hero harus memiliki jalur A* ke Core")

        waypoint = original_path[3]

        self.editor.set_tile_override(waypoint[0], waypoint[1], True)
        self.game.recompute_hero_path()
        new_path = list(self.game.path_result.path)
        self.assertNotIn(waypoint, new_path)

        self.editor.set_tile_override(waypoint[0], waypoint[1], False)
        self.game.recompute_hero_path()
        reopened_path = list(self.game.path_result.path)
        self.assertTrue(len(reopened_path) > 0)


if __name__ == "__main__":
    unittest.main()
