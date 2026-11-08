"""
goblin.py - Implementasi Minion Musuh Goblin Real-Time.

State Machine:
  IDLE -> CHASE -> ATTACK -> HURT -> DEAD

Pergerakan mematuhi Walkable Mask yang sama dengan Player:
  - Menggunakan game_map.move_and_slide dengan per-sumbu (X lalu Y) dan sub-stepping.
  - Tidak pernah menembus dinding, air, atau tebing.
  - Knockback patuh pada collision map.
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Tuple, Optional
import pygame

import config
import combat_config as ccfg


class Goblin:
    """Musuh Goblin dengan AI Real-Time, State Machine, dan Walkable Collision."""

    STATE_IDLE = "IDLE"
    STATE_CHASE = "CHASE"
    STATE_ATTACK = "ATTACK"
    STATE_HURT = "HURT"
    STATE_DEAD = "DEAD"

    def __init__(self, x: float, y: float, anims: Dict[str, List[pygame.Surface]], name: str = "goblin"):
        self.spawn_x = float(x)
        self.spawn_y = float(y)
        self.x = float(x)
        self.y = float(y)
        self.name = name
        self.anims = anims or {}

        # Stat Tempur
        self.max_hp = ccfg.GOB_MAX_HP
        self.hp = ccfg.GOB_MAX_HP
        self.damage = ccfg.GOB_DAMAGE
        self.alive = True

        # State Machine
        self.state = self.STATE_IDLE
        self.state_timer = 0.0
        self.anim_timer = 0.0
        self.attack_cooldown = 0.0
        self.damage_dealt = False
        self.hit_flash = 0.0

        # Gerakan & Arah
        self.direction = "left" if random.random() < 0.5 else "right"
        self.patrol_target = (self.spawn_x, self.spawn_y)
        self.patrol_wait_timer = random.uniform(1.0, 3.0)

        # Knockback
        self.knockback_vx = 0.0
        self.knockback_vy = 0.0

    @property
    def px(self) -> float:
        return self.x

    @property
    def py(self) -> float:
        return self.y

    @property
    def sort_y(self) -> float:
        """Kunci kedalaman untuk y-sorting rendering bersama player."""
        return self.y + config.TILE_SIZE

    def feet_hitbox(self) -> pygame.Rect:
        """Hitbox kaki kecil untuk pengecekan walkable mask."""
        w = ccfg.GOB_FEET_HITBOX_W
        h = ccfg.GOB_FEET_HITBOX_H
        hx = int(self.x + (config.TILE_SIZE - w) / 2)
        hy = int(self.y + config.TILE_SIZE - h - 1)
        return pygame.Rect(hx, hy, w, h)

    def body_rect(self) -> pygame.Rect:
        """Hitbox tubuh untuk pendaftaran terkena serangan senjata player."""
        return pygame.Rect(int(self.x + 6), int(self.y + 4), 20, 26)

    def reset(self):
        """Kembalikan goblin ke posisi spawn dan HP penuh (saat restart game)."""
        self.x = self.spawn_x
        self.y = self.spawn_y
        self.hp = self.max_hp
        self.alive = True
        self.state = self.STATE_IDLE
        self.state_timer = 0.0
        self.anim_timer = 0.0
        self.attack_cooldown = 0.0
        self.damage_dealt = False
        self.hit_flash = 0.0
        self.knockback_vx = 0.0
        self.knockback_vy = 0.0
        self.patrol_target = (self.spawn_x, self.spawn_y)

    def take_damage(self, amount: int, knockback_vector: Tuple[float, float]):
        """Terima damage serangan player, hit-stun, dan knockback."""
        if not self.alive or self.state == self.STATE_DEAD:
            return

        self.hp = max(0, self.hp - amount)
        self.hit_flash = ccfg.GOB_HURT_STUN_SEC

        # Terapkan arah dorongan knockback
        kx, ky = knockback_vector
        dist = math.hypot(kx, ky)
        if dist > 0.001:
            self.knockback_vx = (kx / dist) * ccfg.GOB_KNOCKBACK_SPEED
            self.knockback_vy = (ky / dist) * ccfg.GOB_KNOCKBACK_SPEED
        else:
            self.knockback_vx = ccfg.GOB_KNOCKBACK_SPEED if self.direction == "left" else -ccfg.GOB_KNOCKBACK_SPEED
            self.knockback_vy = 0.0

        if self.hp <= 0:
            self.state = self.STATE_DEAD
            self.state_timer = 0.0
            self.anim_timer = 0.0
        else:
            self.state = self.STATE_HURT
            self.state_timer = 0.0

    def update(self, dt: float, player, game_map):
        """Update perilaku AI, state machine, knockback, dan walkable collision."""
        if not self.alive:
            return

        self.state_timer += dt
        self.anim_timer += dt
        if self.hit_flash > 0:
            self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.attack_cooldown > 0:
            self.attack_cooldown = max(0.0, self.attack_cooldown - dt)

        # 1. Update Knockback (mematuhi walkable mask dengan move_and_slide)
        if abs(self.knockback_vx) > 1.0 or abs(self.knockback_vy) > 1.0:
            hb = self.feet_hitbox()
            rdx, rdy = game_map.move_and_slide(hb, self.knockback_vx * dt, self.knockback_vy * dt)
            self._sync_pos_from_hitbox(hb)

            decay = max(0.0, 1.0 - ccfg.GOB_KNOCKBACK_DECAY * dt)
            self.knockback_vx *= decay
            self.knockback_vy *= decay
        else:
            self.knockback_vx = 0.0
            self.knockback_vy = 0.0

        # Jarak ke player
        dx_to_player = player.px - self.x
        dy_to_player = player.py - self.y
        dist_to_player = math.hypot(dx_to_player, dy_to_player)

        # Zona Aman Desa: Player di dalam desa aman dari kejaran musuh
        safe_rect = getattr(config, "VILLAGE_SAFE_ZONE_RECT", None)
        player_in_safe_zone = False
        if safe_rect:
            sz = pygame.Rect(safe_rect)
            if sz.collidepoint(player.px, player.py):
                player_in_safe_zone = True

        # 2. State Machine
        if self.state == self.STATE_DEAD:
            # Putar animasi mati sampai frame terakhir lalu nonaktifkan total
            death_frames = self.anims.get("death", [])
            total_death_duration = max(0.25, len(death_frames) * ccfg.GOB_DEATH_ANIM_SPEED)
            if self.state_timer >= total_death_duration:
                self.alive = False
                return

        elif self.state == self.STATE_HURT:
            # Hit-stun singkat saat terkena serangan
            if self.state_timer >= ccfg.GOB_HURT_STUN_SEC:
                self.state = self.STATE_CHASE if dist_to_player <= ccfg.GOB_DELEASH_RADIUS else self.STATE_IDLE
                self.state_timer = 0.0

        elif self.state == self.STATE_ATTACK:
            # Berhenti dan ayunkan serangan ke arah player
            if dx_to_player != 0:
                self.direction = "right" if dx_to_player > 0 else "left"

            # Aplikasi damage pada frame windup
            if not self.damage_dealt and self.state_timer >= ccfg.GOB_ATTACK_WINDUP_SEC:
                if dist_to_player <= ccfg.GOB_ATTACK_RANGE * 1.35 and player.alive:
                    kb_dir = (player.px - self.x, player.py - self.y)
                    player.take_combat_damage(self.damage, kb_dir)
                self.damage_dealt = True

            # Durasi penuh animasi serangan goblin
            atk_frames = self.anims.get("attack", [])
            total_atk_time = len(atk_frames) * 0.08
            if self.state_timer >= total_atk_time:
                self.attack_cooldown = ccfg.GOB_ATTACK_COOLDOWN_SEC
                self.damage_dealt = False
                self.state = self.STATE_CHASE if dist_to_player <= ccfg.GOB_DELEASH_RADIUS else self.STATE_IDLE
                self.state_timer = 0.0

        elif self.state == self.STATE_CHASE:
            # Cek hysteresis pelepasan pengejaran atau player masuk zona aman desa
            if dist_to_player > ccfg.GOB_DELEASH_RADIUS or not player.alive or player_in_safe_zone:
                self.state = self.STATE_IDLE
                self.state_timer = 0.0
            elif dist_to_player <= ccfg.GOB_ATTACK_RANGE and self.attack_cooldown <= 0:
                self.state = self.STATE_ATTACK
                self.state_timer = 0.0
                self.anim_timer = 0.0
                self.damage_dealt = False
            else:
                # Bergerak lurus mengejar player menggunakan walkable mask
                if dist_to_player > 0.001:
                    vx = (dx_to_player / dist_to_player) * ccfg.GOB_CHASE_SPEED
                    vy = (dy_to_player / dist_to_player) * ccfg.GOB_CHASE_SPEED
                    self.direction = "right" if vx > 0 else "left"

                    hb = self.feet_hitbox()
                    rdx, rdy = game_map.move_and_slide(hb, vx * dt, vy * dt)
                    self._sync_pos_from_hitbox(hb)

        elif self.state == self.STATE_IDLE:
            # Cek deteksi player untuk mulai mengejar (hanya jika player di luar zona aman desa)
            if dist_to_player <= ccfg.GOB_CHASE_RADIUS and player.alive and not player_in_safe_zone:
                self.state = self.STATE_CHASE
                self.state_timer = 0.0
            else:
                # Berkeliaran pelan di dekat spawn point
                self.patrol_wait_timer -= dt
                if self.patrol_wait_timer <= 0:
                    self.patrol_wait_timer = random.uniform(2.0, 4.5)
                    offset_x = random.uniform(-40.0, 40.0)
                    offset_y = random.uniform(-40.0, 40.0)
                    candidate_target = (self.spawn_x + offset_x, self.spawn_y + offset_y)
                    # Pastikan titik target patroli walkable
                    test_hb = pygame.Rect(int(candidate_target[0]), int(candidate_target[1]),
                                          ccfg.GOB_FEET_HITBOX_W, ccfg.GOB_FEET_HITBOX_H)
                    if not game_map.is_solid(test_hb):
                        self.patrol_target = candidate_target

                # Gerak pelan menuju patrol_target jika masih ada jarak
                pdx = self.patrol_target[0] - self.x
                pdy = self.patrol_target[1] - self.y
                pdist = math.hypot(pdx, pdy)
                if pdist > 4.0:
                    vx = (pdx / pdist) * ccfg.GOB_PATROL_SPEED
                    vy = (pdy / pdist) * ccfg.GOB_PATROL_SPEED
                    self.direction = "right" if vx > 0 else "left"
                    hb = self.feet_hitbox()
                    game_map.move_and_slide(hb, vx * dt, vy * dt)
                    self._sync_pos_from_hitbox(hb)

    def _sync_pos_from_hitbox(self, hb: pygame.Rect):
        """Sinkronkan posisi x, y dari hitbox kaki."""
        w = ccfg.GOB_FEET_HITBOX_W
        h = ccfg.GOB_FEET_HITBOX_H
        self.x = hb.x - (config.TILE_SIZE - w) / 2
        self.y = hb.y - config.TILE_SIZE + h + 1

    def draw(self, surface: pygame.Surface, camera: Tuple[int, int]):
        """Render sprite goblin, animasi per-state, efek hit-flash, dan HP bar mini."""
        if not self.alive:
            return

        cam_x, cam_y = camera
        draw_x = int(self.x - cam_x)
        draw_y = int(self.y - cam_y)

        # 1. Bayangan Kaki Tanah (hanya gambar jika belum mati)
        if self.state != self.STATE_DEAD:
            shadow_w, shadow_h = 18, 6
            shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow_surf, (0, 0, 0, 85), shadow_surf.get_rect())
            surface.blit(shadow_surf, (draw_x + (config.TILE_SIZE - shadow_w) // 2,
                                       draw_y + config.TILE_SIZE - shadow_h + 1))

        # 2. Pemilihan Frame Animasi Sesuai State
        frames = self._get_current_state_frames()
        if not frames:
            return

        alpha = 255
        if self.state == self.STATE_DEAD:
            total_dur = max(0.25, len(frames) * ccfg.GOB_DEATH_ANIM_SPEED)
            if self.state_timer >= total_dur:
                self.alive = False
                return
            idx = min(int(self.state_timer / ccfg.GOB_DEATH_ANIM_SPEED), len(frames) - 1)
            # Fade out mulus menjelang akhir animasi kematian
            fade_prog = min(1.0, max(0.0, self.state_timer / total_dur))
            alpha = max(0, min(255, int(255 * (1.0 - fade_prog))))
        elif self.state == self.STATE_ATTACK:
            idx = min(int(self.state_timer / 0.08), len(frames) - 1)
        elif self.state == self.STATE_HURT:
            idx = min(int(self.state_timer / (ccfg.GOB_HURT_STUN_SEC / len(frames))), len(frames) - 1)
        else:
            speed = 0.11 if self.state == self.STATE_CHASE else 0.15
            idx = int(self.anim_timer / speed) % len(frames)

        frame = frames[idx].copy()

        # Flip horizontal jika menghadap ke kiri
        if self.direction == "left":
            frame = pygame.transform.flip(frame, True, False)

        if alpha < 255:
            frame.set_alpha(alpha)

        surface.blit(frame, (draw_x, draw_y))

        # 3. Efek Flash Putih Siluet Sprite saat Terkena Hit (tanpa kotak artefak)
        if self.hit_flash > 0:
            mask = pygame.mask.from_surface(frame)
            alpha = max(0, min(255, int(220 * (self.hit_flash / ccfg.GOB_HURT_STUN_SEC))))
            flash_surf = mask.to_surface(setcolor=(255, 255, 255, alpha), unsetcolor=(0, 0, 0, 0))
            surface.blit(flash_surf, (draw_x, draw_y))

        # 4. Bar HP Mini di Atas Kepala (Hanya tampil jika HP berkurang dan masih hidup)
        if self.hp < self.max_hp and self.state != self.STATE_DEAD and self.hp > 0:
            bar_w = 24
            bar_h = 4
            bar_x = draw_x + (config.TILE_SIZE - bar_w) // 2
            bar_y = draw_y - 6

            # Background merah tua
            pygame.draw.rect(surface, (60, 15, 15), (bar_x, bar_y, bar_w, bar_h))
            # Health hijau
            health_fill = max(0, int((self.hp / self.max_hp) * bar_w))
            if health_fill > 0:
                pygame.draw.rect(surface, (60, 220, 80), (bar_x, bar_y, health_fill, bar_h))
            # Border hitam tipis
            pygame.draw.rect(surface, (10, 10, 10), (bar_x, bar_y, bar_w, bar_h), 1)

    def _get_current_state_frames(self) -> List[pygame.Surface]:
        """Ambil list frame animasi sesuai state saat ini."""
        if self.state == self.STATE_DEAD:
            return self.anims.get("death", self.anims.get("idle", []))
        elif self.state == self.STATE_HURT:
            return self.anims.get("hurt", self.anims.get("idle", []))
        elif self.state == self.STATE_ATTACK:
            return self.anims.get("attack", self.anims.get("idle", []))
        elif self.state == self.STATE_CHASE:
            return self.anims.get("run", self.anims.get("walk", self.anims.get("idle", [])))
        else:
            return self.anims.get("idle", [])
