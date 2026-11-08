"""
game_map.py - Modul implementasi Map Pulau (Gambar Utuh) & Sistem Walkable Mask.

Arsitektur:
  1. Runtime game HANYA membaca walkable mask (assets/maps/walkable_mask.png).
     Tidak ada logika warna di runtime dan tidak ada daftar rectangle collision tersebar.
  2. Resolusi mask 1:1 terhadap map HD (2752 x 1536).
     Piksel putih = WALKABLE (bisa dilewati), piksel hitam = BLOCKED (terhalang).
  3. Pemeriksaan Gerakan Runtime (Whitelist):
     - Hitbox kaki player berukuran kecil (PLAYER_FEET_HITBOX_W x PLAYER_FEET_HITBOX_H).
     - Gerakan HANYA diterima jika SEMUA 8 titik sampel walkable (4 sudut + 4 titik tengah sisi).
     - Sub-stepping per sumbu (X dulu, lalu Y) dengan langkah maks SUBSTEP_MAX_PIXELS (2.0 px)
       untuk mencegah tunneling tepi tipis dan memungkinkan sliding halus di sepanjang dinding.
  4. Mode Debug (F1):
     - Overlay visual mask: Hijau transparan (walkable), Merah transparan (blocked).
     - Outline hitbox kaki player dengan penanda ke-8 titik sampel.
     - Tooltip di kursor menampilkan koordinat piksel map, status walkable/blocked, dan kelas penyebab.
     - Klik kiri mencetak template override JSON ke konsol agar mudah disalin ke overrides.json.
"""

from __future__ import annotations

import json
import math
import os
from typing import List, Dict, Tuple, Optional
import pygame

import config
import mask_config as cfg


class GameMap:
    """Kelas pengelola map gambar utuh, kamera, dan Walkable Mask Collision."""

    def __init__(self,
                 image_path: Optional[str] = None,
                 mask_path: Optional[str] = None,
                 scale: int = config.MAP_SCALE):
        self.scale = max(1, int(scale))
        self.image_path = image_path or cfg.MAP_IMAGE_PATH
        self.mask_path = mask_path or cfg.WALKABLE_MASK_PATH
        self.overrides_path = cfg.OVERRIDES_PATH

        self.map_surface: pygame.Surface = None
        self.raw_surface: pygame.Surface = None

        self.width = cfg.MAP_W
        self.height = cfg.MAP_H

        # Spawn point default (Alun-Alun Meadowbrook)
        self.spawn_x = float(cfg.DEFAULT_SPAWN_X)
        self.spawn_y = float(cfg.DEFAULT_SPAWN_Y)

        # Bridge rects (untuk kompatibilitas dengan worldgen AI/grid pathfinding)
        self.bridge_rects: List[pygame.Rect] = [
            pygame.Rect(1120, 928, 192, 128),  # Central bridge
            pygame.Rect(1536, 448, 160, 96),   # North river bridge
            pygame.Rect(192, 416, 96, 352),    # NW bridge
            pygame.Rect(288, 704, 256, 96),    # West bridge
            pygame.Rect(2400, 768, 256, 96),   # East bridge
            pygame.Rect(736, 1472, 256, 64),   # South dock
        ]
        self.solid_rects: list = []
        self.dynamic_obstacles: List[pygame.Rect] = []

        # Walkable Mask Runtime
        self.walkable_mask: pygame.mask.Mask = None
        self.debug_overlay_surf: pygame.Surface = None

        # Data Overrides untuk referensi info debug
        self.overrides: Dict[str, List[Dict]] = {"force_walk": [], "force_block": []}

        # Debug Font
        self.debug_font = None
        self.debug_font_small = None

        self._load_and_build()

    # ==========================================================================
    # PEMUATAN & INISIALISASI
    # ==========================================================================
    def _load_and_build(self):
        """Memuat gambar map HD dan file walkable_mask.png."""
        # 1. Muat gambar map HD
        if os.path.exists(self.image_path):
            try:
                img = pygame.image.load(self.image_path)
                if pygame.display.get_surface() is not None:
                    self.map_surface = img.convert()
                else:
                    self.map_surface = img
                actual_w, actual_h = self.map_surface.get_size()
                self.width, self.height = actual_w, actual_h
            except Exception as e:
                print(f"[GameMap] Gagal memuat gambar map '{self.image_path}': {e}")
                self.map_surface = self._create_fallback_surface()
        else:
            print(f"[GameMap] File map '{self.image_path}' tidak ditemukan, pakai fallback")
            self.map_surface = self._create_fallback_surface()

        # 2. Muat Walkable Mask (Pure PNG: Putih = Walkable, Hitam = Blocked)
        if os.path.exists(self.mask_path):
            try:
                mask_img = pygame.image.load(self.mask_path)
                # Nilai piksel > 128 dianggap putih / walkable
                self.walkable_mask = pygame.mask.from_threshold(
                    mask_img, (255, 255, 255, 255), (127, 127, 127, 255)
                )
                print(f"[GameMap] Walkable mask berhasil dimuat dari '{self.mask_path}' "
                      f"({self.walkable_mask.count():,} piksel walkable)")
            except Exception as e:
                print(f"[GameMap] Gagal membaca walkable_mask.png: {e}, membuat mask darurat")
                self.walkable_mask = self._create_fallback_mask()
        else:
            print(f"[GameMap] File mask '{self.mask_path}' belum ada, membuat mask darurat")
            self.walkable_mask = self._create_fallback_mask()

        # 3. Muat overrides.json untuk penandaan kelas di debug HUD
        if os.path.exists(self.overrides_path):
            try:
                with open(self.overrides_path, "r", encoding="utf-8") as f:
                    self.overrides = json.load(f)
            except Exception:
                pass

        # 4. Buat surface visualisasi debug semi-transparan (Hijau = Walkable, Merah = Blocked)
        self._prepare_debug_overlay()

    def _create_fallback_surface(self) -> pygame.Surface:
        """Surface fallback hijau sederhana bila file map tidak ditemukan."""
        surf = pygame.Surface((self.width, self.height))
        surf.fill((46, 139, 87))
        pygame.draw.rect(surf, (30, 144, 255), (0, 0, self.width, self.height), 40)
        return surf

    def _create_fallback_mask(self) -> pygame.mask.Mask:
        """Mask darurat jika walkable_mask.png belum ada (area tengah walkable)."""
        m = pygame.Mask((self.width, self.height))
        margin = 64
        for y in range(margin, self.height - margin):
            for x in range(margin, self.width - margin):
                m.set_at((x, y), 1)
        return m

    def _prepare_debug_overlay(self):
        """Membuat visualisasi semi-transparan mask untuk F1."""
        if self.walkable_mask is None:
            return
        w, h = self.width, self.height
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        # Walkable: Hijau lembut (alpha=70), Blocked: Merah transparan (alpha=85)
        color_surf = self.walkable_mask.to_surface(
            setcolor=(60, 220, 100, 70),
            unsetcolor=(220, 40, 40, 85)
        )
        overlay.blit(color_surf, (0, 0))
        self.debug_overlay_surf = overlay

    # ==========================================================================
    # COLLISION SAMPLING (8 TITIK SAMPEL) & RESOLUSI GERAKAN
    # ==========================================================================
    def get_hitbox_sample_points(self, rect: pygame.Rect) -> List[Tuple[int, int]]:
        """
        Menghasilkan 8 titik sampling untuk hitbox kaki:
        4 sudut + 4 titik tengah setiap sisi.
        """
        left = int(rect.left)
        right = int(rect.right - 1)
        top = int(rect.top)
        bottom = int(rect.bottom - 1)
        mid_x = int(rect.centerx)
        mid_y = int(rect.centery)

        return [
            (left, top),        # 1. Pojok Kiri Atas
            (right, top),       # 2. Pojok Kanan Atas
            (left, bottom),     # 3. Pojok Kiri Bawah
            (right, bottom),    # 4. Pojok Kanan Bawah
            (mid_x, top),       # 5. Tengah Atas
            (mid_x, bottom),    # 6. Tengah Bawah
            (left, mid_y),      # 7. Tengah Kiri
            (right, mid_y),     # 8. Tengah Kanan
        ]

    def is_solid(self, rect: pygame.Rect) -> bool:
        """
        Cek apakah hitbox 'rect' menabrak halangan.
        Gerakan HANYA diizinkan jika SEMUA 8 titik sampel walkable di mask
        dan tidak bertabrakan dengan dynamic obstacles (footprint kincir angin, gerbang tertutup).
        Jika ada 1 saja titik sampel yang terhalang (0) atau di luar peta, kotak SOLID (True).
        """
        for obs in self.dynamic_obstacles:
            if obs.colliderect(rect):
                return True

        w, h = self.width, self.height
        mask = self.walkable_mask

        for px, py in self.get_hitbox_sample_points(rect):
            # Di luar kanvas map = BLOCKED
            if px < 0 or px >= w or py < 0 or py >= h:
                return True
            # Nilai mask 0 = BLOCKED
            if mask.get_at((px, py)) == 0:
                return True

        return False

    def is_walkable_at(self, map_x: int, map_y: int) -> bool:
        """Mengecek apakah satu titik piksel koordinat map berstatus walkable."""
        for obs in self.dynamic_obstacles:
            if obs.collidepoint(map_x, map_y):
                return False
        if 0 <= map_x < self.width and 0 <= map_y < self.height:
            return bool(self.walkable_mask.get_at((map_x, map_y)))
        return False

    def move_and_slide(self, hitbox: pygame.Rect, dx: float, dy: float) -> Tuple[float, float]:
        """
        Gerakkan hitbox secara terpisah per sumbu (X dulu, lalu Y) untuk efek sliding.
        Mencegah tunneling dengan sub-stepping (langkah maksimal SUBSTEP_MAX_PIXELS = 2.0 px).
        Mengembalikan (resolved_dx, resolved_dy).
        """
        max_step = cfg.SUBSTEP_MAX_PIXELS
        resolved_dx = 0.0
        resolved_dy = 0.0

        # ---- Gerak Sumbu X ----
        if dx != 0.0:
            total_x = abs(dx)
            steps = max(1, int(math.ceil(total_x / max_step)))
            step_dx = dx / steps

            for _ in range(steps):
                hitbox.x += int(round(step_dx))
                if self.is_solid(hitbox):
                    hitbox.x -= int(round(step_dx))
                    break
                resolved_dx += step_dx

        # ---- Gerak Sumbu Y ----
        if dy != 0.0:
            total_y = abs(dy)
            steps = max(1, int(math.ceil(total_y / max_step)))
            step_dy = dy / steps

            for _ in range(steps):
                hitbox.y += int(round(step_dy))
                if self.is_solid(hitbox):
                    hitbox.y -= int(round(step_dy))
                    break
                resolved_dy += step_dy

        return resolved_dx, resolved_dy

    def clamp_camera(self, tx: float, ty: float,
                      view_w: int = config.MAP_PIXEL_W,
                      view_h: int = config.MAP_PIXEL_H) -> Tuple[float, float]:
        """Batasi koordinat kamera agar tidak melihat ke luar batas map."""
        max_x = max(0, self.width - view_w)
        max_y = max(0, self.height - view_h)
        return max(0.0, min(float(max_x), tx)), max(0.0, min(float(max_y), ty))

    # ==========================================================================
    # RENDERING & DEBUG MODE [F1]
    # ==========================================================================
    def draw(self, surface: pygame.Surface, camera: Tuple[int, int]):
        """Gambar porsi background map yang masuk dalam viewport kamera."""
        cam_x, cam_y = camera
        view_w, view_h = surface.get_size()
        src_rect = pygame.Rect(cam_x, cam_y, view_w, view_h)

        map_rect = self.map_surface.get_rect()
        clip = src_rect.clip(map_rect)

        if clip.w > 0 and clip.h > 0:
            dest_pos = (clip.x - cam_x, clip.y - cam_y)
            surface.blit(self.map_surface, dest_pos, clip)

    def draw_debug(self, surface: pygame.Surface, camera: Tuple[int, int],
                   cursor_screen_pos: Tuple[int, int],
                   player_hitbox: Optional[pygame.Rect] = None):
        """
        Visualisasi Mode Debug F1:
          1. Overlay Walkable Mask semi-transparan (Hijau = Walkable, Merah = Blocked).
          2. Outline hitbox kaki player & penanda ke-8 titik sampelnya.
          3. Tooltip kursor dengan koordinat piksel map asli dan status walkable/blocked.
          4. Panel HUD informasi status debug.
        """
        cam_x, cam_y = camera
        view_w, view_h = surface.get_size()
        view_rect = pygame.Rect(cam_x, cam_y, view_w, view_h)

        if self.debug_font is None:
            self.debug_font = pygame.font.Font(None, 22)
            self.debug_font_small = pygame.font.Font(None, 18)

        # 1. Gambar Overlay Mask
        if self.debug_overlay_surf is not None:
            clip = view_rect.clip(self.debug_overlay_surf.get_rect())
            if clip.w > 0 and clip.h > 0:
                surface.blit(self.debug_overlay_surf, (clip.x - cam_x, clip.y - cam_y), clip)

        # 2. Gambar Player Feet Hitbox & 8 Titik Sampel
        if player_hitbox is not None:
            hb_screen = pygame.Rect(player_hitbox.x - cam_x, player_hitbox.y - cam_y,
                                    player_hitbox.w, player_hitbox.h)

            # Outline Hitbox Kuning
            hb_surf = pygame.Surface((hb_screen.w, hb_screen.h), pygame.SRCALPHA)
            hb_surf.fill((255, 230, 40, 100))
            surface.blit(hb_surf, hb_screen.topleft)
            pygame.draw.rect(surface, (255, 240, 30), hb_screen, 1)

            # Gambar ke-8 Titik Sampel
            sample_points = self.get_hitbox_sample_points(player_hitbox)
            for px, py in sample_points:
                sp_screen = (px - cam_x, py - cam_y)
                is_walk = self.is_walkable_at(px, py)
                # Hijau jika titik walkable, Merah jika titik blocked
                color = (40, 255, 80) if is_walk else (255, 40, 40)
                pygame.draw.circle(surface, (255, 255, 255), sp_screen, 3)
                pygame.draw.circle(surface, color, sp_screen, 2)

        # 3. Hitung Koordinat Kursor Map
        cx, cy = cursor_screen_pos
        map_x = cx + cam_x
        map_y = cy + cam_y
        tile_gx = int(map_x // config.TILE_SIZE)
        tile_gy = int(map_y // config.TILE_SIZE)
        walkable_here = self.is_walkable_at(map_x, map_y)

        # Cek kelas penyebab
        cause_class = self._determine_cause_class(map_x, map_y, walkable_here)

        # 4. Panel HUD Kiri Atas
        hud_w, hud_h = 360, 95
        hud_surf = pygame.Surface((hud_w, hud_h), pygame.SRCALPHA)
        hud_surf.fill((16, 22, 32, 225))
        pygame.draw.rect(hud_surf, (60, 160, 240), hud_surf.get_rect(), 1)

        status_text = "WALKABLE" if walkable_here else "BLOCKED"
        status_color = (60, 240, 110) if walkable_here else (255, 75, 75)

        t1 = self.debug_font.render("[F1] WALKABLE MASK DEBUG: AKTIF", True, (80, 230, 120))
        t2 = self.debug_font_small.render(f"Kursor Map: ({map_x}, {map_y})  |  Tile: ({tile_gx}, {tile_gy})", True, (220, 230, 245))
        t3 = self.debug_font.render(f"Status: {status_text}  [{cause_class}]", True, status_color)
        t4 = self.debug_font_small.render("Klik Kiri untuk cetak koordinat ke konsol (overrides.json)", True, (255, 220, 70))

        hud_surf.blit(t1, (10, 8))
        hud_surf.blit(t2, (10, 28))
        hud_surf.blit(t3, (10, 48))
        hud_surf.blit(t4, (10, 72))

        surface.blit(hud_surf, (14, 14))

        # 5. Tooltip di Kursor
        tip_text = f"({map_x}, {map_y}) : {status_text}"
        tip_surf = self.debug_font_small.render(tip_text, True, (255, 255, 255))
        tip_box = pygame.Surface((tip_surf.get_width() + 8, tip_surf.get_height() + 6), pygame.SRCALPHA)
        tip_box.fill((10, 14, 20, 210))
        pygame.draw.rect(tip_box, status_color, tip_box.get_rect(), 1)
        tip_box.blit(tip_surf, (4, 3))
        surface.blit(tip_box, (cx + 14, cy + 14))

    def _determine_cause_class(self, map_x: int, map_y: int, is_walkable: bool) -> str:
        """Menentukan kelas penyebab status di koordinat tertentu untuk info tooltip."""
        # Cek manual overrides
        for fw in self.overrides.get("force_walk", []):
            if fw["x"] <= map_x < fw["x"] + fw["w"] and fw["y"] <= map_y < fw["y"] + fw["h"]:
                return "override (force_walk)"
        for fb in self.overrides.get("force_block", []):
            if fb["x"] <= map_x < fb["x"] + fb["w"] and fb["y"] <= map_y < fb["y"] + fb["h"]:
                return "override (force_block)"

        # Cek batas kanvas
        if map_x < 16 or map_x >= self.width - 16 or map_y < 16 or map_y >= self.height - 16:
            return "batas peta (perimeter)"

        if is_walkable:
            return "permukaan diizinkan"
        else:
            return "air / tebing / objek"

    def handle_debug_click(self, screen_pos: Tuple[int, int], camera: Tuple[int, int]):
        """
        Dipanggil saat klik kiri di map dengan mode F1 aktif.
        Mencetak template JSON ke konsol agar pengguna mudah menyalinnya ke overrides.json.
        """
        map_x = screen_pos[0] + camera[0]
        map_y = screen_pos[1] + camera[1]
        is_walk = self.is_walkable_at(map_x, map_y)
        status_name = "WALKABLE" if is_walk else "BLOCKED"

        box_w = 16
        box_h = 16
        box_x = max(0, map_x - box_w // 2)
        box_y = max(0, map_y - box_h // 2)

        print("\n" + "=" * 65)
        print(f"[F1 DEBUG KLIK MAP] Koordinat: ({map_x}, {map_y}) -> Status: {status_name}")
        print("Template JSON untuk disalin ke assets/maps/overrides.json:")
        print(f'  {{"x": {box_x}, "y": {box_y}, "w": {box_w}, "h": {box_h}, "note": "koreksi ({map_x}, {map_y})"}}')
        print("=" * 65 + "\n")
