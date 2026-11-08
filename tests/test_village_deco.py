"""
tests/test_village_deco.py - Unit test untuk dekorasi desa Sunnyside (Kincir Angin & Asap Cerobong)
"""

import json
import os
import sys
import unittest
from collections import deque
import pygame

os.environ["SDL_VIDEODRIVER"] = "dummy"

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from world.village_deco import Windmill, ChimneySmoke, VillageDecorations
from world.game_map import GameMap


class TestVillageDecorations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1024, 768))

    def test_windmill_tower_hub_and_scale(self):
        """Memastikan kincir angin dimuat pada titik poros menara otentik dengan skala 2x."""
        wm = Windmill()
        self.assertEqual(wm.frame_count, 9)
        # Skala 2x: native 112x112 -> 224x224
        self.assertEqual((wm.w, wm.h), (224, 224))
        self.assertEqual(wm.hub_x, config.WINDMILL_HUB_POS[0])
        self.assertEqual(wm.hub_y, config.WINDMILL_HUB_POS[1])
        self.assertEqual(wm.sort_y, config.WINDMILL_SORT_Y)

        # Footprint berada di pondasi dasar menara (1280, 618, 96, 22)
        self.assertEqual(wm.footprint.x, 1280)
        self.assertEqual(wm.footprint.w, 96)
        self.assertEqual(wm.footprint.bottom, 640)

        # Uji kompatibilitas inisialisasi kustom
        custom_wm = Windmill(x=100, y=200, scale=1, fps=6.0)
        self.assertEqual((custom_wm.w, custom_wm.h), (112, 112))
        self.assertEqual(custom_wm.sort_y, 200.0)

    def test_windmill_tower_containment(self):
        """Poros hub kincir angin harus berada presisi di dalam bounding box menara."""
        tx, ty, tw, th = config.WINDMILL_TOWER_RECT
        hx, hy = config.WINDMILL_HUB_POS
        self.assertTrue(tx <= hx <= tx + tw, f"Hub X ({hx}) di luar menara X [{tx}, {tx+tw}]")
        self.assertTrue(ty <= hy <= ty + th, f"Hub Y ({hy}) di luar menara Y [{ty}, {ty+th}]")

    def test_windmill_animation(self):
        """Memastikan rotasi frame kincir angin berjalan dinamis dan berulang."""
        wm = Windmill(fps=8.0)
        init_frame = wm.frame_idx
        wm.update(0.5)
        self.assertNotEqual(wm.frame_idx, init_frame)
        self.assertTrue(0 <= wm.frame_idx < 9)

    def test_windmill_rendered_pixels_differ_across_frames(self):
        """Membuktikan secara fisik bahwa piksel render kincir angin benar-benar berputar antar frame."""
        wm = Windmill()
        self.assertGreaterEqual(len(wm.frames), 9)

        f0 = wm.frames[0]
        f3 = wm.frames[3]
        f6 = wm.frames[6]

        # Konversi ke bytes untuk perbandingan piksel mentah
        b0 = pygame.image.tobytes(f0, "RGBA")
        b3 = pygame.image.tobytes(f3, "RGBA")
        b6 = pygame.image.tobytes(f6, "RGBA")

        self.assertNotEqual(b0, b3, "Frame 0 dan Frame 3 memiliki piksel identik (kincir tidak berputar)!")
        self.assertNotEqual(b3, b6, "Frame 3 dan Frame 6 memiliki piksel identik (kincir tidak berputar)!")
        self.assertNotEqual(b0, b6, "Frame 0 dan Frame 6 memiliki piksel identik (kincir tidak berputar)!")

        # Hitung jumlah piksel yang berbeda (harus ribuan piksel berubah orientasi)
        diff_count_0_3 = sum(1 for i in range(0, len(b0), 4) if b0[i:i+4] != b3[i:i+4])
        diff_count_3_6 = sum(1 for i in range(0, len(b3), 4) if b3[i:i+4] != b6[i:i+4])
        diff_count_0_6 = sum(1 for i in range(0, len(b0), 4) if b0[i:i+4] != b6[i:i+4])

        self.assertGreater(diff_count_0_3, 1000, f"Perbedaan piksel Frame 0 vs 3 terlalu sedikit ({diff_count_0_3})")
        self.assertGreater(diff_count_3_6, 1000, f"Perbedaan piksel Frame 3 vs 6 terlalu sedikit ({diff_count_3_6})")
        self.assertGreater(diff_count_0_6, 1000, f"Perbedaan piksel Frame 0 vs 6 terlalu sedikit ({diff_count_0_6})")

        # Uji orientasi: Frame 0 berbentuk plus (+) dengan bilah horizontal membentang ke kiri (x=1240)
        # sedangkan Frame 3 dan 6 bilahnya berputar miring sehingga piksel di ujung horizontal berubah
        w, h = f0.get_size()
        cx, cy = w // 2, h // 2
        # Cek titik ujung horizontal kiri bilah (offset -80 px dari poros)
        pt_x = cx - 80
        pt_y = cy
        alpha_f0 = f0.get_at((pt_x, pt_y))[3]
        alpha_f3 = f3.get_at((pt_x, pt_y))[3]
        self.assertGreater(alpha_f0, 200, "Frame 0 harus memiliki bilah horizontal (plus '+') di sisi kiri")
        self.assertEqual(alpha_f3, 0, "Frame 3 bilah harus berputar miring sehingga sisi horizontal kosong")

    def test_hero_beside_tower_not_occluded_by_windmill(self):
        """Memastikan hero yang berjalan di samping menara (y >= 448) memiliki sort_y > windmill.sort_y sehingga tidak tertutup bilah."""
        wm = Windmill()
        # Posisi hero di samping kiri menara pada jalan setapak (x=1245, y=515)
        hero_px, hero_py = 1245.0, 515.0
        hero_sort_y = hero_py + config.TILE_SIZE # 547.0
        self.assertGreater(
            hero_sort_y, wm.sort_y,
            f"Hero di samping menara (sort_y={hero_sort_y}) tertutup bilah karena kincir memiliki sort_y={wm.sort_y}!"
        )

    def test_chimney_smoke_phases_and_continuous_flow(self):
        """Memastikan asap cerobong memiliki multi-instance kontinu dengan alpha lembut."""
        smoke = ChimneySmoke(948, 142, variant=1, instance_count=3, phase_offset=0.0)
        self.assertEqual(smoke.frame_count, 30)
        self.assertEqual(smoke.instance_count, 3)
        self.assertEqual(len(smoke.offsets), 3)

        # Skala 2x: native 15x37 -> 30x74
        self.assertEqual((smoke.w, smoke.h), (30, 74))

        # Cek alpha lembut (165) pada tiap frame
        for f in smoke.frames:
            # Di pygame, get_alpha mengembalikan per-surface alpha
            self.assertEqual(f.get_alpha(), 165)

    def test_chimney_anchors_house_containment(self):
        """Setiap titik CHIMNEY_ANCHORS harus berada di dalam batas atap rumah asalnya."""
        col_file = os.path.join(ROOT_DIR, "assets", "maps", "collision.json")
        with open(col_file, "r", encoding="utf-8") as f:
            colliders = json.load(f)

        houses = [c for c in colliders if c.get("type") == "house"]
        self.assertGreater(len(config.CHIMNEY_ANCHORS), 0)

        for i, (cx, cy) in enumerate(config.CHIMNEY_ANCHORS):
            matched = False
            for h in houses:
                bx = h["x"] * 2
                by = h["y"] * 2
                bw = h["w"] * 2
                bh = h["h"] * 2
                # Cek apakah anchor berada di dalam bounding box rumah (dengan toleransi kecil 12px untuk atap/cerobong)
                if bx - 12 <= cx <= bx + bw + 12 and by - 12 <= cy <= by + bh + 12:
                    matched = True
                    break
            self.assertTrue(matched, f"Anchor #{i+1} ({cx}, {cy}) tidak berada di dalam rumah mana pun!")

    def test_village_decorations_manager(self):
        """Memastikan manajer dekorasi mengelola kincir angin dan daftar cerobong lengkap."""
        deco = VillageDecorations(seed=42)
        y_drawables = deco.get_y_sort_entities()
        self.assertEqual(len(y_drawables), 1)
        self.assertIs(y_drawables[0], deco.windmill)

        col_rects = deco.get_collision_rects()
        self.assertEqual(len(col_rects), 1)
        self.assertEqual(col_rects[0], deco.windmill.footprint)

        # Tepat 7 rumah dengan cerobong nyata
        self.assertEqual(len(deco.chimneys), len(config.CHIMNEY_ANCHORS))
        self.assertEqual(len(deco.chimneys), 7)

    def test_flood_fill_reachability(self):
        """Validasi BFS Flood-fill: pemindahan kincir angin tidak merusak konektivitas ke BOSS, jembatan, dan pintu."""
        gm = GameMap()
        start_tx = int(gm.spawn_x // 32)
        start_ty = int(gm.spawn_y // 32)

        visited = set([(start_tx, start_ty)])
        queue = deque([(start_tx, start_ty)])

        while queue:
            cx, cy = queue.popleft()
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < 86 and 0 <= ny < 48:
                    if (nx, ny) not in visited and gm.is_walkable_at(nx * 32 + 16, ny * 32 + 16):
                        visited.add((nx, ny))
                        queue.append((nx, ny))

        # 1. BOSS POS harus dapat dicapai
        bx = int(config.BOSS_POS[0] // 32)
        by = int(config.BOSS_POS[1] // 32)
        boss_reachable = any((bx + dx, by + dy) in visited for dx, dy in [(0, 0), (0, 1), (0, -1), (1, 0), (-1, 0)])
        self.assertTrue(boss_reachable, "Titik BOSS tidak dapat dicapai dari spawn!")

        # 2. Jembatan Utama Desa (Central Bridge)
        central_bridge_reachable = any((x, y) in visited for x in range(35, 42) for y in range(29, 34))
        self.assertTrue(central_bridge_reachable, "Jembatan utama desa tidak dapat dicapai!")

        # 3. Jembatan Sungai Utara (North River Bridge)
        north_bridge_reachable = any((x, y) in visited for x in range(48, 54) for y in range(14, 18))
        self.assertTrue(north_bridge_reachable, "Jembatan sungai utara tidak dapat dicapai!")

        # 4. Lokasi lama kincir di (1860, 960) harus bebas / walkable setelah footprint lama dihapus
        self.assertTrue(gm.is_walkable_at(1860, 960), "Tile lokasi lama (1860, 960) masih terhalang footprint lama!")


if __name__ == "__main__":
    unittest.main()
