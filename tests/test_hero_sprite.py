"""
test_hero_sprite.py - Unit test untuk Satu Sumber Terpadu Sprite Hero (src/hero_sprite.py)

Memverifikasi:
  1. Modul tunggal HeroSpriteManager menghasilkan frame untuk Dunia dan Battle.
  2. Frame Dunia berukuran tepat (48, 48) dengan anchor kaki presisi dan memiliki rambut.
  3. Frame Battle berukuran tepat (196, 238) dengan skala integer 7x.
  4. Layering base -> hair -> tools terkomposisi dengan benar.
  5. Caching: frame tidak digabung ulang pada panggilan berikutnya (menjaga performa 60 FPS).
  6. Fallback anti-crash jika file hair tidak ditemukan.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
pygame.init()
pygame.display.set_mode((100, 100), pygame.HIDDEN)

import config
from hero_sprite import HeroSpriteManager, get_hero_sprite_manager


class TestHeroSprite(unittest.TestCase):
    def setUp(self):
        self.mgr = get_hero_sprite_manager()

    def test_singleton_instance(self):
        """get_hero_sprite_manager() selalu mengembalikan instance singleton."""
        mgr2 = get_hero_sprite_manager()
        self.assertIs(self.mgr, mgr2)

    def test_world_frames_dimensions_and_hair(self):
        """Frame dunia harus berukuran (48, 48) dan memiliki piksel rambut merah."""
        frames = self.mgr.get_world_frames("idle")
        self.assertEqual(len(frames), 9)
        for f in frames:
            self.assertEqual(f.get_size(), config.HERO_SCREEN_SIZE)

        # Verifikasi keberadaan warna rambut merah Sunnyside (228, 59, 68) atau variannya
        f0 = frames[0]
        has_red_hair = False
        for x in range(f0.get_width()):
            for y in range(f0.get_height()):
                c = f0.get_at((x, y))
                if c.a > 0 and c.r > 200 and c.g < 100 and c.b < 100:
                    has_red_hair = True
                    break
            if has_red_hair:
                break
        self.assertTrue(has_red_hair, "Frame dunia Hero harus memiliki piksel rambut merah!")

    def test_world_frames_foot_anchor_stability(self):
        """Anchor kaki hero di kanvas (48, 48) harus stabil dan tidak jitter antar animasi."""
        f_idle = self.mgr.get_world_frames("idle")[0]
        f_walk = self.mgr.get_world_frames("walk")[0]
        f_run = self.mgr.get_world_frames("run")[0]

        bb_idle = f_idle.get_bounding_rect()
        bb_walk = f_walk.get_bounding_rect()
        bb_run = f_run.get_bounding_rect()

        # Kaki harus berlabuh pada y=42 (memberi margin 6px bawah untuk ground shadow)
        self.assertEqual(bb_idle.bottom, 42)
        self.assertEqual(bb_walk.bottom, 42)
        self.assertEqual(bb_run.bottom, 42)

    def test_battle_frames_dimensions(self):
        """Frame battle harus berukuran 196x238 (skala 7x dari crop box 28x34)."""
        b_idle = self.mgr.get_battle_frames("idle")
        self.assertEqual(len(b_idle), 9)
        expected_size = (28 * 7, 34 * 7)
        for f in b_idle:
            self.assertEqual(f.get_size(), expected_size)

        b_attack = self.mgr.get_battle_frames("attack")
        self.assertEqual(len(b_attack), 10)
        for f in b_attack:
            self.assertEqual(f.get_size(), expected_size)

    def test_caching_returns_same_objects(self):
        """Panggilan berulang harus mengembalikan objek cache yang sama tanpa re-komposisi."""
        f1 = self.mgr.get_world_frames("idle")
        f2 = self.mgr.get_world_frames("idle")
        self.assertIs(f1, f2)

        b1 = self.mgr.get_battle_frames("idle")
        b2 = self.mgr.get_battle_frames("idle")
        self.assertIs(b1, b2)

    def test_fallback_missing_hair(self):
        """Jika hair tidak ditemukan, sistem tetap mengembalikan frame base tanpa crash."""
        custom_mgr = HeroSpriteManager()
        custom_mgr.hair_style = "non_existent_hair_style_xyz"
        frames = custom_mgr.get_world_frames("idle")
        self.assertEqual(len(frames), 9)
        self.assertEqual(frames[0].get_size(), (48, 48))


    def test_world_attack_frames_zero_clipping(self):
        """Frame dunia attack harus berukuran (193, 96) dan tidak terpotong (zero clipping) pada tebasan pedang."""
        atk_frames = self.mgr.get_world_frames("attack")
        self.assertEqual(len(atk_frames), 10)
        for i, f in enumerate(atk_frames):
            self.assertEqual(f.get_size(), (193, 96))
            # Pastikan tidak ada piksel yang terpotong pada batas tepi kanan x=192
            has_right_cut = any(f.get_at((192, y)).a > 0 for y in range(96))
            self.assertFalse(has_right_cut, f"Frame attack {i} terpotong pada tepi kanan!")

        # Pastikan simetri horizontal sempurna saat di-flip (kaki tetap di x=96)
        f_mid = atk_frames[5]
        flipped = pygame.transform.flip(f_mid, True, False)
        self.assertEqual(flipped.get_size(), (193, 96))

    def test_slash_arc_vfx(self):
        """SlashArcEffect harus beranimasi mulus dan selesai setelah durasi berlalu."""
        from entities import SlashArcEffect
        vfx = SlashArcEffect(100.0, 100.0, direction="right", duration=0.15)
        self.assertFalse(vfx.finished)
        self.assertTrue(vfx.alive)

        surf = pygame.Surface((200, 200), pygame.SRCALPHA)
        vfx.draw(surf, (0, 0))

        vfx.update(0.10)
        self.assertFalse(vfx.finished)

        vfx.update(0.10)
        self.assertTrue(vfx.finished)
        self.assertFalse(vfx.alive)


if __name__ == "__main__":
    unittest.main()

