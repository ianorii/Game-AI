"""
tests/test_asset_catalog.py - Unit Test untuk Modul AssetCatalog (Sunnyside World)
"""

import os
import sys
import unittest
import pygame

# Set dummy video driver for headless testing
os.environ["SDL_VIDEODRIVER"] = "dummy"

# Add project root and src to path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from asset_catalog import AssetCatalog, get_asset_catalog, make_catalog_placeholder


class TestAssetCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.catalog = get_asset_catalog()

    def setUp(self):
        self.catalog.clear_cache()

    def test_singleton_instance(self):
        """Memastikan get_asset_catalog() mengembalikan instans singleton yang konsisten."""
        cat1 = get_asset_catalog()
        cat2 = get_asset_catalog()
        self.assertIs(cat1, cat2)
        self.assertIs(cat1, self.catalog)

    def test_strip_frame_slicing_counts(self):
        """Memastikan strip _stripN.png dipotong menjadi tepat N frame horizontal."""
        # Skeleton idle -> strip6
        skel_idle = self.catalog.get_skeleton_anim("idle")
        self.assertEqual(len(skel_idle), 6)
        self.assertEqual(skel_idle[0].get_size(), (96, 64))

        # Skeleton jump -> strip10
        skel_jump = self.catalog.get_skeleton_anim("jump")
        self.assertEqual(len(skel_jump), 10)

        # Windmill -> strip9
        windmill = self.catalog.get_prop("windmill")
        self.assertEqual(len(windmill), 9)
        self.assertEqual(windmill[0].get_size(), (112, 112))

        # Chimney smoke -> strip30
        smoke = self.catalog.get_vfx("chimneysmoke_01")
        self.assertEqual(len(smoke), 30)

        # Goblin death -> strip13
        gob_death = self.catalog.get_goblin_anim("death")
        self.assertEqual(len(gob_death), 13)

    def test_integer_scaling(self):
        """Memastikan nearest-neighbor scaling menghasilkan dimensi integer yang presisi."""
        # Skala 1x vs 2x vs 3x
        orig_frames = self.catalog.get_skeleton_anim("idle", scale=1)
        scaled_frames_2x = self.catalog.get_skeleton_anim("idle", scale=2)
        scaled_frames_3x = self.catalog.get_skeleton_anim("idle", scale=3)

        w, h = orig_frames[0].get_size()
        self.assertEqual(scaled_frames_2x[0].get_size(), (w * 2, h * 2))
        self.assertEqual(scaled_frames_3x[0].get_size(), (w * 3, h * 3))

        # UI Icon scaling
        sword_1x = self.catalog.get_ui_icon("sword", scale=1)
        sword_4x = self.catalog.get_ui_icon("sword", scale=4)
        sw, sh = sword_1x.get_size()
        self.assertEqual(sword_4x.get_size(), (sw * 4, sh * 4))

    def test_caching_behavior(self):
        """Memastikan surface di-cache di memori dan tidak dibaca ulang dari disk."""
        frames_1 = self.catalog.get_skeleton_anim("idle", scale=2)
        frames_2 = self.catalog.get_skeleton_anim("idle", scale=2)

        # Harus mengembalikan list objek yang sama dari cache
        self.assertIs(frames_1, frames_2)

        # Bersihkan cache
        self.catalog.clear_cache()
        frames_3 = self.catalog.get_skeleton_anim("idle", scale=2)
        # Konten dan ukuran tetap sama setelah cache dibersihkan
        self.assertEqual(len(frames_3), len(frames_1))
        self.assertEqual(frames_3[0].get_size(), frames_1[0].get_size())

    def test_ui_icons(self):
        """Memastikan berbagai ikon antarmuka dapat dimuat dengan baik."""
        for icon_name in ["sword", "axe", "hammer", "sandtimer", "confirm", "cancel", "redbar_00", "greenbar_06"]:
            icon = self.catalog.get_ui_icon(icon_name)
            self.assertIsNotNone(icon)
            self.assertIsInstance(icon, pygame.Surface)
            self.assertGreater(icon.get_width(), 0)
            self.assertGreater(icon.get_height(), 0)

    def test_crops_growth_stages(self):
        """Memastikan 11 tanaman memiliki seluruh tahap tumbuh 0..5."""
        crops = ["beetroot", "cabbage", "carrot", "cauliflower", "kale",
                 "parsnip", "potato", "pumpkin", "radish", "sunflower", "wheat"]

        for crop in crops:
            for stage in range(6):
                surf = self.catalog.get_crop(crop, stage=stage)
                self.assertIsNotNone(surf)
                self.assertIsInstance(surf, pygame.Surface)
                self.assertGreater(surf.get_width(), 0)
                self.assertGreater(surf.get_height(), 0)

    def test_crop_items_and_soil(self):
        """Memastikan item pertanian (egg, milk, seeds, crate) dan soil dapat dimuat."""
        for item in ["egg", "milk", "fish", "seeds_generic", "wood", "rock", "crate_base"]:
            surf = self.catalog.get_crop_item(item)
            self.assertIsNotNone(surf)
            self.assertGreater(surf.get_width(), 0)

        for s_idx in [0, 1, 3, 4]:
            soil = self.catalog.get_soil(s_idx)
            self.assertIsNotNone(soil)
            self.assertGreater(soil.get_width(), 0)

    def test_human_layers_and_hairstyles(self):
        """Memastikan seluruh aksi manusia dapat memuat berbagai varian layer rambut."""
        hairstyles = ["bowlhair", "curlyhair", "longhair", "mophair", "shorthair", "spikeyhair"]
        actions = ["idle", "walk", "attack", "axe", "mining", "jump", "roll", "reeling"]

        for act in actions:
            # Base layer
            base_frames = self.catalog.get_human_layer(act, layer="base")
            self.assertTrue(len(base_frames) >= 1)

            # Hair layer
            for style in hairstyles:
                hair_frames = self.catalog.get_human_layer(act, layer=style)
                self.assertTrue(len(hair_frames) >= 1)

    def test_missing_asset_warning_and_fallback(self):
        """Memastikan aset yang hilang tidak menyebabkan crash dan mengembalikan placeholder."""
        # Non-existent single image
        missing_img = self.catalog.get_image("completely_invalid_asset_path.png", scale=2)
        self.assertIsNotNone(missing_img)
        self.assertIsInstance(missing_img, pygame.Surface)
        self.assertEqual(missing_img.get_size(), (32, 32))  # fallback default 16x16 scaled 2x

        # Non-existent strip
        missing_strip = self.catalog.get_frames("invalid_strip_strip5.png", count=5, scale=1)
        self.assertEqual(len(missing_strip), 5)
        for f in missing_strip:
            self.assertIsInstance(f, pygame.Surface)

    def test_has_asset_and_list_assets(self):
        """Memastikan pemeriksaan has_asset dan pencarian kategori list_assets akurat."""
        self.assertTrue(self.catalog.has_asset("UI/sword.png"))
        self.assertTrue(self.catalog.has_asset("sword.png"))
        self.assertTrue(self.catalog.has_asset("skeleton_idle_strip6.png"))
        self.assertFalse(self.catalog.has_asset("mythical_nonexistent_dragon.png"))

        ui_assets = self.catalog.list_assets("UI")
        self.assertGreater(len(ui_assets), 50)

        crop_assets = self.catalog.list_assets("Crops")
        self.assertGreater(len(crop_assets), 70)


if __name__ == "__main__":
    unittest.main()

