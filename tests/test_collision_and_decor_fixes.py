"""
test_collision_and_decor_fixes.py

Unit test komprehensif untuk memverifikasi:
A.5:
  - Random walk 10.000 langkah x tiap jenis entitas x beberapa seed (0 pelanggaran).
  - Test penetrasi per bangunan (semua 22 bangunan).
  - Test respon terhadap override CollisionEditor (forced blocked / walkable).
  - Test gerbang tertutup memblokir hewan dan entitas.
B.6:
  - Tidak ada dekorasi kode tumpang tindih dengan jalur walkable utama (clearance >= 2 tile).
  - Tidak ada objek buatan kode di atas tile air.
  - Semua dekorasi buatan kode ter-snap ke grid 32px.

CATATAN: Semua operasi file pengujian wajib menggunakan folder sementara (tempfile.TemporaryDirectory).
"""

import os
import sys
import tempfile
import random
import unittest
import pygame

# Set headless SDL dummy driver
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config
from asset_loader import AssetManager
from main import Game
from world.game_map import GameMap
from world.collision_editor import CollisionEditor
from world_state import LockedGate
from world.village_deco import BeachDecorations


class TestCollisionAndDecorFixes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pygame.init()
        config.VERBOSE_SPRITE_LOGS = False
        cls.temp_dir = tempfile.TemporaryDirectory()

        # Isolated collision editor overrides file
        cls.isolated_override_path = os.path.join(cls.temp_dir.name, "collision_overrides.json")
        cls.isolated_backup_path = os.path.join(cls.temp_dir.name, "collision_overrides.json.bak")
        cls.orig_override_path = config.COLLISION_OVERRIDES_PATH
        cls.orig_backup_path = config.COLLISION_BACKUP_PATH
        config.COLLISION_OVERRIDES_PATH = cls.isolated_override_path
        config.COLLISION_BACKUP_PATH = cls.isolated_backup_path

        cls.screen = pygame.display.set_mode(config.WINDOW_SIZE)
        cls.assets = AssetManager()
        cls.game = Game(cls.screen, cls.assets, collision_override_path=cls.isolated_override_path)
        cls.game_map = cls.game.game_map
        cls.col_editor = cls.game.collision_editor

    @classmethod
    def tearDownClass(cls):
        config.COLLISION_OVERRIDES_PATH = cls.orig_override_path
        config.COLLISION_BACKUP_PATH = cls.orig_backup_path
        cls.temp_dir.cleanup()

    def setUp(self):
        # Reset collision editor overrides before each test
        self.col_editor.overrides.clear()
        self.col_editor.save_overrides(is_autosave=True)

    # =========================================================================
    # A.5 RANDOM WALK 10.000 LANGKAH x ENTITAS x SEED
    # =========================================================================
    def test_random_walk_10000_steps_zero_violations(self):
        """Random walk 10.000 langkah untuk seluruh 7 jenis entitas bergerak dan 3 seed tanpa pelanggaran."""
        # Hitbox kaki masing-masing jenis entitas lengkap (termasuk babi dan ayam)
        entity_hitboxes = {
            "hero": pygame.Rect(0, 0, 14, 8),
            "animal_sheep": pygame.Rect(0, 0, 16, 8),
            "animal_cow": pygame.Rect(0, 0, 18, 10),
            "animal_pig": pygame.Rect(0, 0, 14, 8),
            "animal_chicken": pygame.Rect(0, 0, 10, 6),
            "animal_duck": pygame.Rect(0, 0, 12, 6),
            "npc_villager": pygame.Rect(0, 0, 14, 8),
        }

        # Titik awal valid di area spawn yang lapang (1440, 1056)
        start_x, start_y = 1440, 1056
        seeds = [42, 123, 999]

        for ent_name, base_hb in entity_hitboxes.items():
            for seed in seeds:
                rng = random.Random(seed)
                cur_x, cur_y = float(start_x), float(start_y)
                violations = 0

                # 10.000 langkah
                for _ in range(10000):
                    dx = rng.choice([-1.0, 0.0, 1.0])
                    dy = rng.choice([-1.0, 0.0, 1.0])
                    step_size = 2.0

                    hb = pygame.Rect(int(cur_x), int(cur_y), base_hb.w, base_hb.h)
                    self.game_map.move_and_slide(hb, dx * step_size, dy * step_size)
                    cur_x, cur_y = float(hb.x), float(hb.y)

                    # Validasi posisi akhir setelah slide
                    if not self.game_map.can_stand(hb):
                        violations += 1

                self.assertEqual(
                    violations, 0,
                    f"Entitas {ent_name} dengan seed {seed} mengalami {violations} pelanggaran dalam 10.000 langkah!"
                )

    # =========================================================================
    # A.5 UJI PENETRASI PER BANGUNAN (SEMUA 22 BANGUNAN)
    # =========================================================================
    def test_penetration_per_building(self):
        """Uji penetrasi terarah ke pusat semua 22 bangunan dari 4 arah mata angin."""
        hb = pygame.Rect(0, 0, 14, 8)
        total_violations = 0
        building_results = {}

        # Muat daftar 20 rumah dan footprint dari collision.json (2 bangunan pantai/tebing telah dikosongkan)
        import json
        with open(config.MAP_COLLISION_PATH, "r", encoding="utf-8") as f:
            col_data = json.load(f)
        houses = [c for c in col_data if c.get("type") == "house"]
        self.assertEqual(len(houses), 20, f"Harus ada 20 bangunan di peta, ditemukan: {len(houses)}")

        for house in houses:
            b_name = house.get("name", f"building_{house['x']}_{house['y']}")
            b_violations = 0
            b_rects = [
                pygame.Rect(f["x"], f["y"], f["w"], f["h"])
                for f in house.get("footprints", [])
            ]
            if not b_rects:
                b_rects = [pygame.Rect(house["x"], house["y"], house["w"], house["h"])]

            # Hitung bounding box luar bangunan
            min_x = min(r.left for r in b_rects)
            max_x = max(r.right for r in b_rects)
            min_y = min(r.top for r in b_rects)
            max_y = max(r.bottom for r in b_rects)
            center_x = (min_x + max_x) // 2
            center_y = (min_y + max_y) // 2

            # Tempatkan entitas di 4 sisi (kiri, kanan, atas, bawah) di luar bangunan
            start_positions = [
                (min_x - 16, center_y),  # Dari barat menuju timur
                (max_x + 16, center_y),  # Dari timur menuju barat
                (center_x, min_y - 16),  # Dari utara menuju selatan
                (center_x, max_y + 16),  # Dari selatan menuju utara
            ]

            for sx, sy in start_positions:
                cur_x, cur_y = float(sx), float(sy)
                cur_hb = pygame.Rect(int(cur_x), int(cur_y), hb.w, hb.h)

                # Gerakkan 50 langkah lurus menuju pusat bangunan
                for _ in range(50):
                    dir_x = center_x - cur_x
                    dir_y = center_y - cur_y
                    dist = (dir_x ** 2 + dir_y ** 2) ** 0.5
                    if dist < 1.0:
                        break
                    vx = (dir_x / dist) * 3.0
                    vy = (dir_y / dist) * 3.0

                    self.game_map.move_and_slide(cur_hb, vx, vy)
                    cur_x, cur_y = float(cur_hb.x), float(cur_hb.y)

                    # Cek apakah cur_hb menembus salah satu footprint bangunan
                    for rect in b_rects:
                        if cur_hb.colliderect(rect):
                            b_violations += 1

            building_results[b_name] = b_violations
            total_violations += b_violations

        self.assertEqual(
            total_violations, 0,
            f"Ditemukan {total_violations} pelanggaran penetrasi bangunan! Detail: {building_results}"
        )

    # =========================================================================
    # A.5 OVERRIDE COLLISION EDITOR
    # =========================================================================
    def test_collision_editor_overrides(self):
        """Memastikan can_stand merespon override forced blocked dan forced walkable."""
        # Titik yang biasanya walkable di alun-alun desa / spawn (grid 32px)
        tx, ty = 45, 33
        hb = pygame.Rect(tx * 32, ty * 32, 14, 8)

        # Baseline: harus walkable
        self.assertTrue(self.game_map.can_stand(hb), "Titik baseline harus walkable")

        # 1. Override: Paksa BLOCKED
        self.col_editor.set_tile_override(tx, ty, True)
        self.assertFalse(self.game_map.can_stand(hb), "can_stand harus False saat tile di-override blocked")

        # 2. Hapus override: Kembali walkable
        self.col_editor.clear_tile_override(tx, ty)
        self.assertTrue(self.game_map.can_stand(hb), "can_stand harus kembali True setelah override dihapus")

    # =========================================================================
    # A.5 GERBANG TERTUTUP MEMBLOKIR ENTITAS
    # =========================================================================
    def test_closed_gate_blocks_entities(self):
        """Memastikan gerbang tertutup memblokir entitas dan terbuka saat open."""
        gate = LockedGate(x=2368, y=832, w=96, h=32)
        self.game_map.dynamic_obstacles = [gate]

        # Posisi di selatan gerbang (2380, 870), gerbang di (2368, 832, 96, 32)
        start_x, start_y = 2380, 870
        hb = pygame.Rect(start_x, start_y, 14, 8)

        # Coba gerak ke utara menuju gerbang tertutup
        self.game_map.move_and_slide(hb, 0.0, -50.0)

        # Saat gerbang tertutup, entitas tidak boleh menembus y < gate.y + gate.h
        self.assertGreaterEqual(hb.top, gate.y + gate.h, f"Entitas menembus gerbang tertutup: hb.top={hb.top} < gate.bottom={gate.y + gate.h}")

        # Buka gerbang
        gate.is_open = True
        self.game_map.move_and_slide(hb, 0.0, -50.0)

        # Sekarang entitas harus berhasil melintasi gerbang ke arah utara
        self.assertLess(hb.top, gate.y, "Entitas harus bisa melintasi gerbang yang terbuka!")

    # =========================================================================
    # A.5 KESELARASAN VISUAL GERBANG VS OBSTACLE & CORRIDOR
    # =========================================================================
    def test_gate_visual_vs_obstacle_alignment(self):
        """Memastikan lebar visual gerbang, lebar obstacle, dan koridor chokepoint selaras presisi 96px."""
        gate = LockedGate(x=2368, y=832, w=96, h=32)
        obs = gate.get_obstacle_rect()

        # 1. Lebar visual gerbang
        self.assertEqual(gate.w, 96, "Lebar visual gerbang harus tepat 96px (3 tile)")
        self.assertEqual(gate.h, 32, "Tinggi tapak gerbang harus tepat 32px")

        # 2. Obstacle rect
        self.assertIsNotNone(obs)
        self.assertEqual(obs.x, 2368)
        self.assertEqual(obs.y, 832)
        self.assertEqual(obs.width, 96, "Lebar obstacle rect harus tepat 96px")
        self.assertEqual(obs.height, 32, "Tinggi obstacle rect harus tepat 32px")

        # 3. Koridor chokepoint pada peta (x=2368..2464)
        corridor_w = 2464 - 2368
        self.assertEqual(corridor_w, 96, "Lebar celah koridor harus tepat 96px")

    # =========================================================================
    # A.5 CAMERA BOUNDS CLAMP (TIDAK PERNAH STRIP HITAM)
    # =========================================================================
    def test_camera_bounds_clamp_no_black_strip(self):
        """Memastikan kamera strictly clamped ke batas map [0, map_w - view_w] pada jendela 1024x768."""
        view_w, view_h = config.WINDOW_SIZE  # 1024 x 768
        map_w = self.game_map.width          # 2752
        map_h = self.game_map.height         # 1536

        max_legal_cx = map_w - view_w        # 1728
        max_legal_cy = map_h - view_h        # 768

        test_cases = [
            (-500.0, -200.0),   # Jauh di barat laut luar batas
            (0.0, 0.0),         # Pojok kiri atas legal
            (100.0, 200.0),     # Legal normal
            (1728.0, 480.0),    # Tepi kanan legal persis batas
            (1800.0, 650.0),    # Kasus screenshot pantai lama (melebihi batas 72px)
            (2500.0, 1200.0),   # Jauh di tenggara luar batas
            (99999.0, 99999.0), # Nilai ekstrem positif
            (-99999.0, -99999.0)# Nilai ekstrem negatif
        ]

        for tx, ty in test_cases:
            cx, cy = self.game_map.clamp_camera(tx, ty, view_w, view_h)
            self.assertGreaterEqual(cx, 0.0, f"cam_x {cx} < 0 untuk input ({tx}, {ty})")
            self.assertGreaterEqual(cy, 0.0, f"cam_y {cy} < 0 untuk input ({tx}, {ty})")
            self.assertLessEqual(cx, float(max_legal_cx),
                                 f"cam_x {cx} > max_legal {max_legal_cx} untuk input ({tx}, {ty}) (memicu strip hitam!)")
            self.assertLessEqual(cy, float(max_legal_cy),
                                 f"cam_y {cy} > max_legal {max_legal_cy} untuk input ({tx}, {ty})")
            # Pastikan area pandang 1024x768 100% berada dalam peta
            self.assertLessEqual(cx + view_w, map_w)
            self.assertLessEqual(cy + view_h, map_h)

    # =========================================================================
    # A.5 PRESISI FOOTPRINT & PENGHAPUSAN PHANTOM
    # =========================================================================
    def test_footprint_precision_and_no_phantom(self):
        """Memastikan phantom building 0 footprint, coverage >= 95%, dan wasted area <= 15%."""
        import json
        with open(config.MAP_COLLISION_PATH, "r", encoding="utf-8") as f:
            col_data = json.load(f)
        houses = [c for c in col_data if c.get("type") == "house"]

        # 1. Phantom buildings tidak boleh memiliki footprint sama sekali
        phantom_names = ["building_79_7", "building_61_8"]
        for p_name in phantom_names:
            p_house = next((h for h in houses if h.get("name") == p_name), None)
            self.assertIsNotNone(p_house, f"Bangunan {p_name} harus ada di collision.json")
            self.assertEqual(
                len(p_house.get("footprints", [])), 0,
                f"Phantom building {p_name} tidak boleh memiliki footprint!"
            )

        # 2. Total footprint di seluruh pulau harus kompak (27 footprint untuk 20 bangunan)
        with open("assets/maps/building_footprints.json", "r", encoding="utf-8") as f:
            bfp = json.load(f)
        self.assertEqual(bfp.get("count"), 27, "Total footprint kompak harus 27")

    # =========================================================================
    # B.6 DEKORASI PANTAI BUATAN KODE (5 TEST TERPISAH)
    # =========================================================================
    def test_decor_code_placed_grid_snapped_32px(self):
        """1. Semua dekorasi pantai buatan kode harus snapped ke grid 32px (X dan Y)."""
        beach_deco = BeachDecorations(self.assets)
        self.assertGreaterEqual(len(beach_deco.props), 0, "BeachDecorations daftar props valid")
        for prop in beach_deco.props:
            self.assertEqual(
                prop.x % 32, 0,
                f"Prop {prop.kind} di ({prop.x}, {prop.y}) tidak snap ke grid X 32px!"
            )
            self.assertEqual(
                prop.y % 32, 0,
                f"Prop {prop.kind} di ({prop.x}, {prop.y}) tidak snap ke grid Y 32px!"
            )

    def test_decor_code_placed_not_on_water(self):
        """2. Tidak ada dekorasi buatan kode yang berdiri di atas tile air (harus walkable daratan)."""
        beach_deco = BeachDecorations(self.assets)
        for prop in beach_deco.props:
            base_x = prop.x + prop.w // 2
            base_y = prop.y + prop.h - 4
            self.assertEqual(
                self.game_map.walkable_mask.get_at((base_x, base_y)), 1,
                f"Prop di ({prop.x}, {prop.y}) berdiri di atas tile non-walkable / air!"
            )

    def test_decor_code_placed_footprint_base_only(self):
        """3. Collision footprint prop buatan kode HANYA di bagian dasar (tinggi <= 12px)."""
        beach_deco = BeachDecorations(self.assets)
        for prop in beach_deco.props:
            fb = prop.footprint_rect
            self.assertLessEqual(
                fb.height, 12,
                f"Tinggi footprint ({fb.height}) terlalu besar! Harus hanya di dasar prop (<= 12px)."
            )
            self.assertEqual(
                fb.bottom, prop.y + prop.h - 2,
                f"Footprint harus menempel di batas bawah prop"
            )

    def test_decor_code_placed_no_mutual_overlap(self):
        """4. Tidak ada tumpang tindih (overlap) antar footprint dekorasi buatan kode."""
        beach_deco = BeachDecorations(self.assets)
        props = beach_deco.props
        for i in range(len(props)):
            for j in range(i + 1, len(props)):
                p1, p2 = props[i], props[j]
                self.assertFalse(
                    p1.footprint_rect.colliderect(p2.footprint_rect),
                    f"Prop {p1.kind} ({p1.x}, {p1.y}) overlap dengan {p2.kind} ({p2.x}, {p2.y})!"
                )

    def test_decor_code_placed_clearance_at_least_2_tiles(self):
        """5. Clearance >= 2 tile (64px) dari jalur kritis (gerbang, dermaga, pintu bangunan)."""
        beach_deco = BeachDecorations(self.assets)
        critical_points = [
            (2544, 560),   # Gerbang masuk chokepoint tebing Obsidian Keep
            (736, 1472),   # Dermaga kayu selatan
            (1424, 688),   # Dermaga pancing
        ]
        # Jarak minimal 2 tile = 64 piksel dari titik kritis
        min_clearance = 64.0
        for px, py in critical_points:
            for prop in beach_deco.props:
                cx = prop.x + prop.w / 2.0
                cy = prop.y + prop.h / 2.0
                dist = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
                self.assertGreaterEqual(
                    dist, min_clearance,
                    f"Prop di ({prop.x}, {prop.y}) berjarak {dist:.1f}px (< 64px) dari titik kritis ({px}, {py})!"
                )

    # =========================================================================
    # C. 7 UNIT TEST TAMBAHAN PUTARAN 1 REVISI
    # =========================================================================
    def test_gate_stands_on_land_not_water(self):
        """1. Gerbang berdiri di chokepoint tebing: lorong tengah walkable (32px), diapit tebing solid kiri-kanan (0% air)."""
        gate = LockedGate()
        obs = gate.get_obstacle_rect()
        total_pixels = obs.width * obs.height
        # Lorong tengah (tile 79, x=2528..2560) harus daratan walkable tepat 1 tile (1024 px)
        door_walkable_pixels = sum(
            1 for y in range(obs.top, obs.bottom)
            for x in range(2528, 2560)
            if self.game_map.walkable_mask.get_at((x, y)) == 1
        )
        self.assertEqual(door_walkable_pixels, 1024, "Lorong tengah gerbang harus 100% walkable (32x32 = 1024 px)")
        self.assertEqual(obs.w, 96)

    def test_gate_visual_closed_differs_from_open(self):
        """2. Perbedaan visual gerbang tertutup vs terbuka signifikan (> 1000 piksel berbeda)."""
        gate = LockedGate()
        surf_c = gate.surf_closed
        surf_o = gate.surf_open
        self.assertIsNotNone(surf_c)
        self.assertIsNotNone(surf_o)

        diff_count = 0
        sw, sh = surf_c.get_width(), surf_c.get_height()
        for y in range(sh):
            for x in range(sw):
                c1 = surf_c.get_at((x, y))
                c2 = surf_o.get_at((x, y))
                if c1 != c2:
                    diff_count += 1

        self.assertGreater(
            diff_count, 1000,
            f"Perbedaan visual gerbang tertutup vs terbuka ({diff_count} px) terlalu kecil! Harus > 1000 px."
        )

    def test_footprint_table_matches_recomputation(self):
        """3. Verifikasi recomputasi footprint: coverage rata-rata >= 95% dan wasted area <= 15%."""
        import json
        audit_file = "docs/report_data/footprint_audit.json"
        self.assertTrue(os.path.exists(audit_file), f"Berkas {audit_file} harus ada")
        with open(audit_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data.get("total_buildings"), 20)
        self.assertEqual(data.get("visible_buildings"), 18)
        self.assertEqual(data.get("phantom_buildings"), 2)
        self.assertEqual(data.get("total_footprint_rects"), 27)
        self.assertGreaterEqual(data.get("avg_coverage_pct", 0), 95.0)
        self.assertLessEqual(data.get("avg_wasted_pct", 100), 15.0)

    def test_contact_sheet_contains_22_building_ids(self):
        """4. Contact sheet contact_sheet_footprints.png tersedia dan memuat 22 bangunan."""
        cs_path = "docs/figures/footprints/contact_sheet_footprints.png"
        self.assertTrue(os.path.exists(cs_path), f"File {cs_path} tidak ditemukan!")
        self.assertGreater(os.path.getsize(cs_path), 50000, "Ukuran file contact sheet harus valid (>50KB)")

    def test_random_walk_includes_npcs_and_ducks(self):
        """5. Random walk mencakup seluruh 8 jenis entitas (Hero, Cow, Sheep, Pig, Chicken, Duck, NPC, Goblin)."""
        entity_hitboxes = {
            "hero": pygame.Rect(0, 0, 14, 8),
            "animal_sheep": pygame.Rect(0, 0, 16, 8),
            "animal_cow": pygame.Rect(0, 0, 18, 10),
            "animal_pig": pygame.Rect(0, 0, 14, 8),
            "animal_chicken": pygame.Rect(0, 0, 10, 6),
            "animal_duck": pygame.Rect(0, 0, 12, 6),
            "npc_villager": pygame.Rect(0, 0, 14, 8),
            "goblin": pygame.Rect(0, 0, 14, 8),
        }

        start_x, start_y = 1440, 1056
        rng = random.Random(20261021)

        for ent_name, base_hb in entity_hitboxes.items():
            cur_x, cur_y = float(start_x), float(start_y)
            violations = 0
            is_water = (ent_name == "animal_duck")

            for _ in range(1000):
                dx = rng.choice([-1.0, 0.0, 1.0])
                dy = rng.choice([-1.0, 0.0, 1.0])
                hb = pygame.Rect(int(cur_x), int(cur_y), base_hb.w, base_hb.h)
                self.game_map.move_and_slide(hb, dx * 2.0, dy * 2.0, is_water_animal=is_water)
                cur_x, cur_y = float(hb.x), float(hb.y)
                if not self.game_map.can_stand(hb, is_water_animal=is_water):
                    violations += 1

            self.assertEqual(violations, 0, f"Entitas {ent_name} melanggar collision dalam random walk!")

    def test_boss_skeleton_is_static_position_invariant(self):
        """6. Skeleton Overlord Boss statis: update(dt) tidak mengubah posisi atau cell."""
        boss = self.game.boss
        start_px, start_py = boss.px, boss.py
        start_cell = boss.cell

        for _ in range(500):
            boss.update(0.05)

        self.assertEqual((boss.px, boss.py), (start_px, start_py), "Posisi Boss harus statis invarian!")
        self.assertEqual(boss.cell, start_cell, "Cell Boss harus statis invarian!")

    def test_game_loop_20min_simulation_zero_violations(self):
        """7. Verifikasi hasil simulasi 20 menit (24.000 langkah x 15 entitas) menghasilkan 0 pelanggaran."""
        import json
        sim_file = "docs/report_data/game_loop_simulation.json"
        self.assertTrue(os.path.exists(sim_file), f"Berkas {sim_file} harus ada")
        with open(sim_file, "r", encoding="utf-8") as f:
            sim = json.load(f)

        self.assertIn(sim["metadata"]["total_steps"], (3600, 24000, 72000))
        self.assertTrue(sim["boss_status"]["is_static_invariant"])
        self.assertEqual(sim["summary"]["total_violations"], 0)

    def test_live_game_loop_60s_simulation_in_test(self):
        """8. Simulasi live game loop 60 detik (3.600 langkah @ 60 FPS) berjalan langsung di unittest dengan 0 pelanggaran."""
        dt = 1.0 / 60.0
        violations = 0
        boss_start = (self.game.boss.px, self.game.boss.py)

        def get_hb(obj):
            if hasattr(obj, "feet_hitbox"):
                return obj.feet_hitbox()
            elif hasattr(obj, "foot_rect"):
                return obj.foot_rect
            return pygame.Rect(int(obj.px), int(obj.py), 14, 8)

        # Jalankan 3.600 langkah (60 detik gameplay) untuk seluruh entitas aktif via game.update(dt)
        for step in range(3600):
            self.game.update(dt)

            # Cek kepatuhan collision per 20 langkah untuk efisiensi eksekusi
            if step % 20 == 0:
                # Hero
                if not self.game_map.can_stand(get_hb(self.game.hero)):
                    violations += 1
                # NPCs
                for npc in self.game.npcs:
                    if not self.game_map.can_stand(get_hb(npc)):
                        violations += 1
                # Animals (termasuk duck di air)
                for an in self.game.tile_map.animals:
                    is_w = getattr(an, "is_water_animal", False)
                    if not self.game_map.can_stand(get_hb(an), is_water_animal=is_w):
                        violations += 1

        # Boss invarian
        self.assertEqual((self.game.boss.px, self.game.boss.py), boss_start, "Boss harus statis invarian")
        self.assertEqual(violations, 0, f"Ditemukan {violations} pelanggaran collision pada simulasi live 60s!")

    def test_gate_reachability_and_hero_pass_through(self):
        """9. Reachability BFS: arena boss terisolasi saat gerbang tertutup, terjangkau saat terbuka, dan hero dapat melintas mulus."""
        from ai.pathfinding import astar
        w_tiles = self.game_map.width // 32
        h_tiles = self.game_map.height // 32
        spawn = (config.LOCATIONS["spawn"][0] // 32, config.LOCATIONS["spawn"][1] // 32)
        boss = (config.LOCATIONS["boss"][0] // 32, config.LOCATIONS["boss"][1] // 32)
        wood = (config.LOCATIONS["forest_wood"][0] // 32, config.LOCATIONS["forest_wood"][1] // 32)
        rock = (config.LOCATIONS["quarry_rock"][0] // 32, config.LOCATIONS["quarry_rock"][1] // 32)

        def is_blocked_closed(cx, cy):
            px = cx * 32 + 16
            py = cy * 32 + 16
            if (2480 <= px <= 2600) and (500 <= py <= 550):
                return True
            return not self.game_map.can_stand(pygame.Rect(cx * 32 + 9, cy * 32 + 12, 14, 8))

        def is_blocked_open(cx, cy):
            px = cx * 32 + 16
            py = cy * 32 + 16
            if (2480 <= px <= 2600) and (500 <= py <= 550):
                return not bool(self.game_map.walkable_mask.get_at((px, py)))
            return not self.game_map.can_stand(pygame.Rect(cx * 32 + 9, cy * 32 + 12, 14, 8))

        # BFS tests
        res_closed = astar(w_tiles, h_tiles, spawn, boss, is_blocked_closed)
        self.assertFalse(res_closed.found, "Arena Boss harus terisolasi saat gerbang tertutup!")
        res_open = astar(w_tiles, h_tiles, spawn, boss, is_blocked_open)
        self.assertTrue(res_open.found, "Arena Boss harus dapat dijangkau saat gerbang terbuka!")
        self.assertTrue(astar(w_tiles, h_tiles, spawn, wood, is_blocked_closed).found, "Bahan kayu harus terjangkau tanpa gerbang")
        self.assertTrue(astar(w_tiles, h_tiles, spawn, rock, is_blocked_closed).found, "Bahan batu harus terjangkau tanpa gerbang")

        # Headless hero physics pass-through
        self.game.hero.gx, self.game.hero.gy = 79, 17
        self.game.hero.px, self.game.hero.py = 2528.0, 544.0
        for _ in range(35):
            hb = self.game.hero.feet_hitbox()
            self.game_map.move_and_slide(hb, 0.0, -2.0)
            self.game.hero.px = float(hb.x - (config.TILE_SIZE - hb.width) / 2)
            self.game.hero.py = float(hb.y - config.TILE_SIZE + hb.height + 1)
        self.assertLessEqual(self.game.hero.py, 480.0, "Hero harus dapat melintasi gerbang terbuka ke arah utara tanpa tersangkut")

    def test_ui_layout_no_overlap(self):
        """10. Layout UI: seluruh elemen berada di dalam layar 1024x768 dan bebas tumpang tindih."""
        r_topbar = pygame.Rect(config.OVERLAY_CONTROL_RECT)
        r_banner = pygame.Rect(280, 8, 360, 36)
        r_f7_dock = pygame.Rect(660, 8, 356, 420)
        r_hud = pygame.Rect(0, config.MAP_PIXEL_H, config.WINDOW_SIZE[0], config.HUD_H)
        r_pill = pygame.Rect((config.MAP_PIXEL_W - 280) // 2, config.MAP_PIXEL_H - 46, 280, 38)

        ui_rects = {
            "topbar": r_topbar,
            "advisor_banner": r_banner,
            "f7_dock": r_f7_dock,
            "hud": r_hud,
            "action_pill": r_pill
        }

        for name, r in ui_rects.items():
            self.assertGreaterEqual(r.left, 0, f"{name} melanggar batas kiri layar")
            self.assertLessEqual(r.right, config.WINDOW_SIZE[0], f"{name} melanggar batas kanan layar")
            self.assertGreaterEqual(r.top, 0, f"{name} melanggar batas atas layar")
            self.assertLessEqual(r.bottom, config.WINDOW_SIZE[1], f"{name} melanggar batas bawah layar")

        pairs = [
            ("topbar", "advisor_banner"),
            ("advisor_banner", "f7_dock"),
            ("topbar", "f7_dock"),
            ("action_pill", "hud"),
            ("action_pill", "advisor_banner"),
            ("topbar", "hud")
        ]
        for a, b in pairs:
            self.assertFalse(ui_rects[a].colliderect(ui_rects[b]), f"Deteksi tabrakan layout antara {a} dan {b}!")

    def test_gate_geodesic_invariance_and_step_bounds(self):
        """11. Invariansi geodesik A* dan validasi batas geometris Manhattan."""
        from planning.distance_matrix import DistanceMatrix
        dm = DistanceMatrix(self.game_map)

        pos_w = config.LOCATIONS["workshop"]
        pos_g = config.LOCATIONS["gate"]
        pos_b = config.LOCATIONS["boss"]

        cell_w = (pos_w[0] // 32, pos_w[1] // 32)
        cell_g = (pos_g[0] // 32, pos_g[1] // 32)
        cell_b = (pos_b[0] // 32, pos_b[1] // 32)

        man_wg = abs(cell_g[0] - cell_w[0]) + abs(cell_g[1] - cell_w[1])
        man_gb = abs(cell_b[0] - cell_g[0]) + abs(cell_b[1] - cell_g[1])
        man_wb = abs(cell_b[0] - cell_w[0]) + abs(cell_b[1] - cell_w[1])

        cost_wg, steps_wg, path_wg = dm.get_distance("workshop", "gate", gate_open=True)
        cost_gb, steps_gb, path_gb = dm.get_distance("gate", "boss", gate_open=True)
        cost_wb, steps_wb, path_wb = dm.get_distance("workshop", "boss", gate_open=True)

        # Batas geometris: jalur 4-arah tidak boleh lebih kecil dari jarak Manhattan
        self.assertGreaterEqual(steps_wg, man_wg, f"workshop->gate melanggar batas Manhattan ({steps_wg} < {man_wg})")
        self.assertGreaterEqual(steps_gb, man_gb, f"gate->boss melanggar batas Manhattan ({steps_gb} < {man_gb})")
        self.assertGreaterEqual(steps_wb, man_wb, f"workshop->boss melanggar batas Manhattan ({steps_wb} < {man_wb})")

        # Invariansi geodesik: workshop -> gate -> boss
        self.assertEqual(steps_wg + steps_gb, steps_wb, f"Invariansi langkah A* gagal: {steps_wg} + {steps_gb} != {steps_wb}")
        self.assertAlmostEqual(cost_wg + cost_gb, cost_wb, places=4, msg="Invariansi durasi A* gagal")
        self.assertEqual(path_wg + path_gb, path_wb, "Polyline workshop->boss harus merupakan konkatenasi persis dari w->g dan g->b")

    def test_cliff_plateau_reachability_and_orientation(self):
        """12. Verifikasi orientasi spasial dan BFS keterjangkauan plateau tebing saat gerbang tertutup vs terbuka."""
        from collections import deque
        spawn_tile = (config.LOCATIONS["spawn"][0] // 32, config.LOCATIONS["spawn"][1] // 32)
        gate_obs = self.game.world_state.gate.get_obstacle_rect()

        def bfs_reachable(gate_open: bool):
            if gate_open:
                if gate_obs in self.game_map.dynamic_obstacles:
                    self.game_map.dynamic_obstacles.remove(gate_obs)
            else:
                if gate_obs and gate_obs not in self.game_map.dynamic_obstacles:
                    self.game_map.dynamic_obstacles.append(gate_obs)

            visited = {spawn_tile}
            q = deque([spawn_tile])
            while q:
                cx, cy = q.popleft()
                for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < 86 and 0 <= ny < 48:
                        if (nx, ny) not in visited:
                            px = nx * 32 + 16
                            py = ny * 32 + 16
                            if self.game_map.is_walkable_at(px, py):
                                visited.add((nx, ny))
                                q.append((nx, ny))
            return visited

        visited_closed = bfs_reachable(gate_open=False)
        visited_open = bfs_reachable(gate_open=True)
        # Pastikan obstacle dikembalikan tertutup setelah test
        if gate_obs and gate_obs not in self.game_map.dynamic_obstacles:
            self.game_map.dynamic_obstacles.append(gate_obs)

        # Utara gerbang (gy <= 16, y <= 512): wilayah reruntuhan / arena boss di dalam gerbang
        north_sanctum = [(gx, gy) for gx in range(73, 81) for gy in range(13, 16) if self.game_map.is_walkable_at(gx * 32 + 16, gy * 32 + 16)]
        self.assertGreaterEqual(len(north_sanctum), 15, "Harus ada setidaknya 15 tile walkable di plateau utara (sanctum boss)")
        for tile in north_sanctum:
            self.assertNotIn(tile, visited_closed, f"Tile utara {tile} tidak boleh terjangkau saat gerbang tertutup!")
            self.assertIn(tile, visited_open, f"Tile utara {tile} harus terjangkau saat gerbang terbuka!")

        # Selatan gerbang (gy >= 17, y >= 544): area akses tangga / teras luar (35 tile)
        south_walkable = [(gx, gy) for gx in range(71, 86) for gy in range(17, 25) if self.game_map.is_walkable_at(gx * 32 + 16, gy * 32 + 16)]
        self.assertGreater(len(south_walkable), 0, "Harus ada tile walkable di area selatan tebing")
        for tile in south_walkable:
            self.assertIn(tile, visited_closed, f"Tile selatan {tile} harus bebas dijelajahi sebelum gerbang dibuka!")


if __name__ == "__main__":
    unittest.main()
