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
from ai.pathfinding import astar


class Goblin:
    """Musuh Goblin dengan AI Real-Time, State Machine, dan Walkable Collision."""

    STATE_IDLE = "IDLE"
    STATE_CHASE = "CHASE"
    STATE_ATTACK = "ATTACK"
    STATE_HURT = "HURT"
    STATE_DEAD = "DEAD"

    def __init__(self, x: float, y: float, anims: Dict[str, List[pygame.Surface]], name: str = "goblin", is_elite: bool = False):
        self.spawn_x = float(x)
        self.spawn_y = float(y)
        self.x = float(x)
        self.y = float(y)
        self.is_elite = is_elite
        self.name = f"{name}_elite" if is_elite else name
        self.anims = anims or {}

        # Stat Tempur
        self.max_hp = 5 if is_elite else ccfg.GOB_MAX_HP
        self.hp = self.max_hp
        self.damage = 6 if is_elite else ccfg.GOB_DAMAGE
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

        # Smart Pathfinding & Anti-Stuck
        self.chase_path: List[Tuple[float, float]] = []
        self.repath_timer: float = 0.0
        self.stuck_timer: float = 0.0
        self.last_x: float = float(x)
        self.last_y: float = float(y)
        self.chase_duration: float = 0.0
        self.deleash_cooldown: float = 0.0

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
        self.chase_path = []
        self.repath_timer = 0.0
        self.stuck_timer = 0.0
        self.last_x = self.spawn_x
        self.last_y = self.spawn_y
        self.chase_duration = 0.0
        self.deleash_cooldown = 0.0

    def _has_line_of_sight(self, tx: float, ty: float, game_map) -> bool:
        """Cek apakah jalur lurus dari kaki goblin ke (tx, ty) bebas rintangan (tidak menabrak air/dinding)."""
        ghb = self.feet_hitbox()
        gx, gy = ghb.centerx, ghb.centery
        dist = math.hypot(tx - gx, ty - gy)
        if dist < 16.0:
            return True

        w = ccfg.GOB_FEET_HITBOX_W
        h = ccfg.GOB_FEET_HITBOX_H
        steps = max(2, int(dist // 14))
        for i in range(1, steps + 1):
            t = i / steps
            cx = gx + (tx - gx) * t
            cy = gy + (ty - gy) * t
            sample_hb = pygame.Rect(int(cx - w / 2), int(cy - h / 2), w, h)
            if hasattr(game_map, "can_stand"):
                if not game_map.can_stand(sample_hb):
                    return False
            elif getattr(game_map, "is_solid", lambda hb: False)(sample_hb):
                return False
        return True

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
        if self.deleash_cooldown > 0:
            self.deleash_cooldown = max(0.0, self.deleash_cooldown - dt)

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

        # Jarak ke player & jarak dari sarang/spawn (leash boundary)
        dx_to_player = player.px - self.x
        dy_to_player = player.py - self.y
        dist_to_player = math.hypot(dx_to_player, dy_to_player)
        dist_from_spawn = math.hypot(self.x - self.spawn_x, self.y - self.spawn_y)

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
                max_leash = getattr(ccfg, "GOB_MAX_LEASH_DIST", 260.0)
                can_chase = (dist_to_player <= ccfg.GOB_DELEASH_RADIUS and dist_from_spawn <= max_leash)
                self.state = self.STATE_CHASE if can_chase else self.STATE_IDLE
                self.state_timer = 0.0

        elif self.state == self.STATE_ATTACK:
            # Berhenti dan ayunkan serangan ke arah player
            if dx_to_player != 0:
                self.direction = "right" if dx_to_player > 0 else "left"

            # Aplikasi damage pada frame windup
            if not self.damage_dealt and self.state_timer >= ccfg.GOB_ATTACK_WINDUP_SEC:
                if dist_to_player <= ccfg.GOB_ATTACK_RANGE * 1.35 and player.alive:
                    kb_dir = (player.px - self.x, player.py - self.y)
                    dmg = player.take_combat_damage(self.damage, kb_dir)
                    if dmg > 0 and hasattr(player, "combat_model") and player.combat_model:
                        is_high = (self.damage >= 5) or getattr(self, "is_elite", False)
                        player.combat_model.record_hit_observation(dmg, is_high, self)
                self.damage_dealt = True

            # Durasi penuh animasi serangan goblin
            atk_frames = self.anims.get("attack", [])
            total_atk_time = len(atk_frames) * 0.08
            if self.state_timer >= total_atk_time:
                self.attack_cooldown = ccfg.GOB_ATTACK_COOLDOWN_SEC
                self.damage_dealt = False
                max_leash = getattr(ccfg, "GOB_MAX_LEASH_DIST", 260.0)
                can_chase = (dist_to_player <= ccfg.GOB_DELEASH_RADIUS and dist_from_spawn <= max_leash)
                self.state = self.STATE_CHASE if can_chase else self.STATE_IDLE
                self.state_timer = 0.0

        elif self.state == self.STATE_CHASE:
            self.chase_duration += dt
            max_leash = getattr(ccfg, "GOB_MAX_LEASH_DIST", 260.0)
            max_time = getattr(ccfg, "GOB_MAX_CHASE_TIME", 6.0)
            deleash_cd = getattr(ccfg, "GOB_DELEASH_COOLDOWN_SEC", 2.0)

            # Batasan Pengejaran (Deleash / Boundary Limits):
            # 1. Player mulai menjauh melebihi batas batas deleash (ccfg.GOB_DELEASH_RADIUS)
            # 2. Goblin terpancing keluar terlalu jauh dari wilayah sarang/spawn (ccfg.GOB_MAX_LEASH_DIST)
            # 3. Durasi kejar habis saat player terus menjaga jarak (> max_time & dist > GOB_CHASE_RADIUS)
            # 4. Player mati / tidak aktif
            is_too_far_player = dist_to_player > ccfg.GOB_DELEASH_RADIUS
            is_too_far_spawn = dist_from_spawn > max_leash
            is_chase_timeout = (self.chase_duration > max_time and dist_to_player > ccfg.GOB_CHASE_RADIUS)

            if is_too_far_player or is_too_far_spawn or is_chase_timeout or not player.alive:
                self.state = self.STATE_IDLE
                self.state_timer = 0.0
                self.chase_duration = 0.0
                self.deleash_cooldown = deleash_cd
                self.chase_path.clear()
                # Langsung arahkan goblin kembali pulang ke titik spawn-nya
                self.patrol_target = (self.spawn_x, self.spawn_y)
                self.patrol_wait_timer = random.uniform(3.0, 5.0)
            elif dist_to_player <= ccfg.GOB_ATTACK_RANGE and self.attack_cooldown <= 0:
                self.state = self.STATE_ATTACK
                self.state_timer = 0.0
                self.anim_timer = 0.0
                self.damage_dealt = False
                self.chase_path.clear()
            else:
                # Koordinat kaki / anchor player
                if hasattr(player, "feet_hitbox"):
                    pf = player.feet_hitbox()
                    target_player = (float(pf.centerx), float(pf.centery))
                else:
                    target_player = (float(getattr(player, "px", self.x) + 16), float(getattr(player, "py", self.y) + 24))

                ghb = self.feet_hitbox()
                gob_center = (float(ghb.centerx), float(ghb.centery))

                # Deteksi jika goblin terhalang / tersangkut pada obstacle
                moved = math.hypot(self.x - self.last_x, self.y - self.last_y)
                self.last_x = self.x
                self.last_y = self.y
                if moved < (ccfg.GOB_CHASE_SPEED * 0.2 * dt):
                    self.stuck_timer += dt
                else:
                    self.stuck_timer = max(0.0, self.stuck_timer - dt * 2.0)

                # Cek Line of Sight (LOS) langsung ke player
                has_los = self._has_line_of_sight(target_player[0], target_player[1], game_map)
                self.repath_timer -= dt

                # Hitung path A* jika jalur langsung terhalang (air/dinding/tebing) atau goblin tersangkut
                if (not has_los or self.stuck_timer > 0.12) and (self.repath_timer <= 0 or not self.chase_path):
                    self.repath_timer = 0.35
                    start_tile = (int(gob_center[0] // config.TILE_SIZE), int(gob_center[1] // config.TILE_SIZE))
                    goal_tile = (int(target_player[0] // config.TILE_SIZE), int(target_player[1] // config.TILE_SIZE))

                    map_w_tiles = getattr(game_map, "width", 86 * config.TILE_SIZE) // config.TILE_SIZE
                    map_h_tiles = getattr(game_map, "height", 48 * config.TILE_SIZE) // config.TILE_SIZE

                    def is_blocked(cx, cy):
                        test_hb = pygame.Rect(cx * config.TILE_SIZE + 9, cy * config.TILE_SIZE + 12, 14, 8)
                        if hasattr(game_map, "can_stand"):
                            return not game_map.can_stand(test_hb)
                        return getattr(game_map, "is_solid", lambda hb: False)(test_hb)

                    res = astar(map_w_tiles, map_h_tiles, start_tile, goal_tile, is_blocked, track=False)
                    if res and res.path:
                        self.chase_path = [(cx * config.TILE_SIZE + 16, cy * config.TILE_SIZE + 20) for (cx, cy) in res.path]
                    elif res and res.best_effort and res.best_effort != start_tile:
                        self.chase_path = [(res.best_effort[0] * config.TILE_SIZE + 16, res.best_effort[1] * config.TILE_SIZE + 20)]

                # Tentukan titik target kemudi (waypoint A* vs langsung)
                if has_los and self.stuck_timer < 0.1 and len(self.chase_path) <= 1:
                    target_steer = target_player
                    self.chase_path.clear()
                elif self.chase_path:
                    wp = self.chase_path[0]
                    dist_wp = math.hypot(wp[0] - gob_center[0], wp[1] - gob_center[1])
                    if dist_wp < 12.0:
                        self.chase_path.pop(0)
                        wp = self.chase_path[0] if self.chase_path else target_player
                    target_steer = wp
                else:
                    target_steer = target_player

                # Kemudi menuju target_steer
                tdx = target_steer[0] - gob_center[0]
                tdy = target_steer[1] - gob_center[1]
                tdist = math.hypot(tdx, tdy)
                if tdist > 1.0:
                    vx = (tdx / tdist) * ccfg.GOB_CHASE_SPEED
                    vy = (tdy / tdist) * ccfg.GOB_CHASE_SPEED

                    # Anti-stuck tangential sliding nudge saat terbentur sudut rintangan
                    if self.stuck_timer > 0.15:
                        perp_vx = -vy * 0.75
                        perp_vy = vx * 0.75
                        vx += perp_vx
                        vy += perp_vy
                        spd = math.hypot(vx, vy)
                        if spd > 0.001:
                            vx = (vx / spd) * ccfg.GOB_CHASE_SPEED
                            vy = (vy / spd) * ccfg.GOB_CHASE_SPEED

                    self.direction = "right" if vx > 0 else "left"
                    rdx, rdy = game_map.move_and_slide(ghb, vx * dt, vy * dt)
                    self._sync_pos_from_hitbox(ghb)

        elif self.state == self.STATE_IDLE:
            # Cek deteksi player untuk mulai mengejar: masuk dalam range GOB_CHASE_RADIUS, tidak dalam cooldown deleash, dan masih dalam teritori spawn
            max_leash = getattr(ccfg, "GOB_MAX_LEASH_DIST", 260.0)
            if dist_to_player <= ccfg.GOB_CHASE_RADIUS and player.alive and self.deleash_cooldown <= 0 and dist_from_spawn <= max_leash:
                self.state = self.STATE_CHASE
                self.state_timer = 0.0
                self.chase_duration = 0.0
            else:
                # Berkeliaran pelan / kembali ke dekat spawn point
                self.patrol_wait_timer -= dt
                if self.patrol_wait_timer <= 0:
                    self.patrol_wait_timer = random.uniform(2.5, 5.0)
                    w = ccfg.GOB_FEET_HITBOX_W
                    h = ccfg.GOB_FEET_HITBOX_H
                    # Cari titik patroli yang walkable dan memiliki LOS dari posisi saat ini
                    for _ in range(6):
                        offset_x = random.uniform(-45.0, 45.0)
                        offset_y = random.uniform(-45.0, 45.0)
                        cand_x = self.spawn_x + offset_x
                        cand_y = self.spawn_y + offset_y
                        test_hx = int(cand_x + (config.TILE_SIZE - w) / 2)
                        test_hy = int(cand_y + config.TILE_SIZE - h - 1)
                        test_hb = pygame.Rect(test_hx, test_hy, w, h)

                        is_walkable = False
                        if hasattr(game_map, "can_stand"):
                            is_walkable = game_map.can_stand(test_hb)
                        else:
                            is_walkable = not getattr(game_map, "is_solid", lambda hb: False)(test_hb)

                        if is_walkable and self._has_line_of_sight(test_hb.centerx, test_hb.centery, game_map):
                            self.patrol_target = (cand_x, cand_y)
                            break

                # Gerak menuju patrol_target jika masih ada jarak
                pdx = self.patrol_target[0] - self.x
                pdy = self.patrol_target[1] - self.y
                pdist = math.hypot(pdx, pdy)
                if pdist > 4.0:
                    # Kecepatan kembali lebih sigap bila sedang berjalan pulang dari kejauhan pasca de-leash
                    speed = getattr(ccfg, "GOB_RETURN_SPEED", 50.0) if pdist > 35.0 else ccfg.GOB_PATROL_SPEED
                    vx = (pdx / pdist) * speed
                    vy = (pdy / pdist) * speed
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

        # 4. Indikator & Bar HP Mini di Atas Kepala
        if getattr(self, "is_elite", False) and self.state != self.STATE_DEAD and self.hp > 0:
            font_xs = pygame.font.Font(None, 13)
            star_s = font_xs.render("★ ELITE", True, (245, 158, 11))
            surface.blit(star_s, (draw_x + (config.TILE_SIZE - star_s.get_width()) // 2, draw_y - 14))

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
