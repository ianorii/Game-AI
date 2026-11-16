"""
animal.py - Hewan beranimasi dinamis dengan AI berkeliaran bebas (Wandering AI).

Mendukung sapi, domba, babi, ayam, dan bebek dengan siklus animasi 4 frame,
perilaku acak (makan rumput, mematuk, berjalan santai, berbalik arah),
pengecekan rintangan/batas wilayah, bayangan tanah menapak, serta reaksi
terkejut bila didekati Hero.
"""

from __future__ import annotations

import math
import random
import pygame

import config

TILE = config.TILE_SIZE

_ANIMAL_SHADOWS = {}

def _get_animal_shadow(width, height):
    key = (width, height)
    if key not in _ANIMAL_SHADOWS:
        surf = pygame.Surface((width, height), pygame.SRCALPHA).convert_alpha()
        # Bayangan bertingkat (luar transparan, dalam pekat)
        pygame.draw.ellipse(surf, (0, 0, 0, 40), surf.get_rect())
        pygame.draw.ellipse(surf, (0, 0, 0, 85), surf.get_rect().inflate(-2, -2))
        _ANIMAL_SHADOWS[key] = surf
    return _ANIMAL_SHADOWS[key]


class Animal:
    """Hewan aktif dengan AI jelajah acak, animasi frame, dan kedalaman y-sort."""

    def __init__(self, kind: str, gx: int, gy: int, frames: list,
                 wander_radius: int = 4, assets=None):
        self.kind = kind
        self.home_x = gx
        self.home_y = gy
        self.gx = gx
        self.gy = gy
        self.px = float(gx * TILE)
        self.py = float(gy * TILE)
        self.frames = frames or []
        self.wander_radius = wander_radius
        self.assets = assets

        self.facing_left = random.choice([True, False])
        self.state = "IDLE"  # "IDLE" | "WALK" | "EAT"
        self.state_timer = random.uniform(2.0, 5.0)
        self.anim_t = random.uniform(0.0, 2.0)
        self.target = None

        # Kecepatan gerak (tile per detik)
        if kind == "chicken":
            self.speed = 1.9
        elif kind == "cow":
            self.speed = 0.85
        elif kind == "sheep":
            self.speed = 1.15
        elif kind == "pig":
            self.speed = 1.25
        elif kind == "duck":
            self.speed = 1.05
        else:
            self.speed = 1.2

        self.is_water_animal = (kind == "duck")
        self.bubble = None       # [bubble_surf, timer]
        self.startled_timer = 0.0

        # Ukuran bayangan tanah
        first_w = self.frames[0].get_width() if self.frames else TILE
        self.shadow_w = max(10, int(first_w * 0.55))
        self.shadow_h = max(5, int(self.shadow_w * 0.32))

    @property
    def cell(self):
        return (self.gx, self.gy)

    @property
    def sort_y(self):
        return self.py + TILE

    def feet_hitbox(self) -> pygame.Rect:
        """Hitbox kaki kecil di area bawah animal untuk pengecekan can_stand."""
        w = max(10, min(18, self.shadow_w))
        h = max(6, min(10, self.shadow_h + 2))
        hx = int(self.px + (TILE - w) / 2)
        hy = int(self.py + TILE - h - 1)
        return pygame.Rect(hx, hy, w, h)

    def update(self, dt: float, is_passable_fn=None, hero=None, game_map=None):
        self.anim_t += dt
        if self.startled_timer > 0:
            self.startled_timer -= dt

        # Emote bubble
        if self.bubble is not None:
            self.bubble[1] -= dt
            if self.bubble[1] <= 0:
                self.bubble = None

        # Reaksi terhadap Hero: ayam & bebek terkejut dan berlari menjauh bila Hero dekat
        if hero is not None and self.startled_timer <= 0:
            dist = math.hypot(hero.px - self.px, hero.py - self.py) / TILE
            if dist < 1.4:
                self.startled_timer = 2.5
                if self.kind in ("chicken", "duck"):
                    # Tampilkan ekspresi terkejut
                    self._show_bubble("expression_alerted")
                    # Lari menjauh dari Hero
                    dx = 1 if self.px > hero.px else -1
                    dy = 1 if self.py > hero.py else -1
                    cand = (self.gx + dx, self.gy + dy)
                    passable = (is_passable_fn is None or is_passable_fn(cand[0], cand[1], self.is_water_animal))
                    if passable and game_map is not None:
                        w = max(10, min(18, self.shadow_w))
                        h = max(6, min(10, self.shadow_h + 2))
                        cand_hb = pygame.Rect(int(cand[0] * TILE + (TILE - w) / 2), int(cand[1] * TILE + TILE - h - 1), w, h)
                        passable = game_map.can_stand(cand_hb, is_water_animal=self.is_water_animal)
                    if passable:
                        self.target = cand
                        self.state = "WALK"
                        self.facing_left = (dx < 0)
                        return

        # Mesin status
        if self.state == "WALK" and self.target is not None:
            tx = self.target[0] * TILE
            ty = self.target[1] * TILE
            dx = tx - self.px
            dy = ty - self.py
            dist = math.hypot(dx, dy)
            step = (self.speed * 1.5 if self.startled_timer > 0 else self.speed) * TILE * dt
            if dist <= step:
                if game_map is not None:
                    w = max(10, min(18, self.shadow_w))
                    h = max(6, min(10, self.shadow_h + 2))
                    cand_hb = pygame.Rect(int(tx + (TILE - w) / 2), int(ty + TILE - h - 1), w, h)
                    if game_map.can_stand(cand_hb, is_water_animal=self.is_water_animal):
                        self.px = float(tx)
                        self.py = float(ty)
                        self.gx, self.gy = self.target
                    else:
                        # Terhalang, jangan tembus ke dalam
                        self.target = None
                else:
                    self.px = float(tx)
                    self.py = float(ty)
                    self.gx, self.gy = self.target
                self.target = None
                self.state = random.choice(["IDLE", "EAT"])
                self.state_timer = random.uniform(2.0, 5.5)
            else:
                step_dx = dx / dist * step
                step_dy = dy / dist * step
                if game_map is not None:
                    hb = self.feet_hitbox()
                    rdx, rdy = game_map.move_and_slide(hb, step_dx, step_dy, is_water_animal=self.is_water_animal)
                    if rdx == 0.0 and rdy == 0.0:
                        self.target = None
                        self.state = "IDLE"
                        self.state_timer = random.uniform(1.0, 3.0)
                    else:
                        self.px += rdx
                        self.py += rdy
                        self.gx = int(round(self.px / TILE))
                        self.gy = int(round(self.py / TILE))
                else:
                    self.px += step_dx
                    self.py += step_dy
                if abs(dx) > 2:
                    self.facing_left = (dx < 0)
        else:
            self.state_timer -= dt
            if self.state_timer <= 0:
                self._pick_next_action(is_passable_fn, game_map=game_map)

    def _show_bubble(self, name: str, duration: float = 1.8):
        if self.assets is not None and hasattr(self.assets, "ui"):
            spr = self.assets.ui.get(name)
            if spr is not None:
                self.bubble = [spr, duration]

    def _pick_next_action(self, is_passable_fn, game_map=None):
        """Pilih aksi berikutnya: melangkah ke petak tetangga atau makan rumput."""
        roll = random.random()
        if roll < 0.58:
            # Cari petak langkah acak dalam radius rumah
            directions = [(0, -1), (1, 0), (0, 1), (-1, 0)]
            random.shuffle(directions)
            for dx, dy in directions:
                nx, ny = self.gx + dx, self.gy + dy
                # Batasi agar tidak menjauh dari kandang/padang asalnya
                if math.hypot(nx - self.home_x, ny - self.home_y) <= self.wander_radius:
                    if is_passable_fn is None or is_passable_fn(nx, ny, self.is_water_animal):
                        if game_map is not None:
                            w = max(10, min(18, self.shadow_w))
                            h = max(6, min(10, self.shadow_h + 2))
                            cand_hb = pygame.Rect(int(nx * TILE + (TILE - w) / 2), int(ny * TILE + TILE - h - 1), w, h)
                            if not game_map.can_stand(cand_hb, is_water_animal=self.is_water_animal):
                                continue
                        self.target = (nx, ny)
                        self.state = "WALK"
                        self.facing_left = (dx < 0)
                        return
            # Bila terkurung, tetap santai di tempat
            self.state = "IDLE"
            self.state_timer = random.uniform(2.0, 4.0)
        elif roll < 0.88:
            self.state = "EAT"
            self.state_timer = random.uniform(2.5, 5.0)
            if random.random() < 0.15:
                self._show_bubble("expression_love" if random.random() < 0.5 else "expression_chat")
        else:
            self.state = "IDLE"
            self.state_timer = random.uniform(2.0, 4.5)
            self.facing_left = not self.facing_left

    def draw(self, surface: pygame.Surface, camera=(0, 0), *args):
        if not self.frames:
            return
        ox, oy = camera
        sx = int(self.px - ox)
        sy = int(self.py - oy)

        # Culling viewport
        if sx < -48 or sx > config.MAP_PIXEL_W + 48 or sy < -48 or sy > config.MAP_PIXEL_H + 48:
            return

        # Frame animasi
        if self.state == "WALK":
            frame_idx = int(self.anim_t * 6.5) % len(self.frames)
        elif self.state == "EAT":
            frame_idx = int(self.anim_t * 2.8) % len(self.frames)
        else:
            frame_idx = int(self.anim_t * 1.4) % len(self.frames)

        frame = self.frames[frame_idx]
        if self.facing_left:
            frame = pygame.transform.flip(frame, True, False)

        fw, fh = frame.get_size()
        pos_x = sx + TILE // 2 - fw // 2
        pos_y = sy + TILE - fh

        # Bayangan tanah menapak (hanya di darat, bukan saat bebek di air dalam)
        if not (self.is_water_animal and self.kind == "duck"):
            shadow = _get_animal_shadow(self.shadow_w, self.shadow_h)
            shadow_x = sx + TILE // 2 - self.shadow_w // 2
            shadow_y = sy + TILE - self.shadow_h - 1
            surface.blit(shadow, (shadow_x, shadow_y))

        # Sprite hewan
        surface.blit(frame, (pos_x, pos_y))

        # Gelembung ekspresi (jika ada)
        if self.bubble is not None:
            bspr, _ = self.bubble
            bob = int(math.sin(self.anim_t * 5.0) * 2)
            bx = pos_x + fw // 2 - bspr.get_width() // 2
            by = pos_y - bspr.get_height() - 4 + bob
            surface.blit(bspr, (bx, by))
