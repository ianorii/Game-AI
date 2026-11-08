"""
entity.py - Base class Entity + Hero / Monster / Boss / Trap

Semua karakter memakai WALK CYCLE: frame animasi berganti saat bergerak
dan kembali ke frame idle saat berhenti. Pergerakan berbasis grid
(satu tile demi satu tile) dengan interpolasi pixel yang halus.
Sprite diskalakan dari 16x16 -> 32x32 (SCALE_FACTOR) lewat asset_loader;
bila file PNG tidak ada, dipakai placeholder berwarna otomatis.

PREFERRED: PERTINYAAN 3 - PLAYER CONTROLLER
  Mode MANUAL   : hero digerakkan langsung oleh keyboard (WASD / panah).
                  Satu tekan tombol = satu langkah ke sel tetangga.
                  Tabrakan dicek lewat `blocked_fn` sehingga hero tidak
                  pernah menembus dinding.
  Mode AUTO     : hero mengikuti jalur A* (Pathfinding) + rencana STRIPS.
  `manual_mode` pada entity menentukan sumber gerakan; `control_dir`
  menyimpan arah terakhir yang ditahan pemain.
"""

import math

import pygame

import config

TILE = config.TILE_SIZE
FRAME_DURATION = 0.11   # detik per frame walk cycle

DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

#: cache bayangan tanah (dibuat sekali, dipakai semua entity)
_SHADOW_CACHE = {}


def _ground_shadow():
    """Bayangan oval lembut di bawah kaki karakter."""
    key = (TILE, TILE)
    if key not in _SHADOW_CACHE:
        w = int(TILE * 0.62)
        h = max(4, int(TILE * 0.26))
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        if pygame.display.get_surface() is not None:
            surf = surf.convert_alpha()
        pygame.draw.ellipse(surf, (0, 0, 0, 95), surf.get_rect())
        _SHADOW_CACHE[key] = surf
    return _SHADOW_CACHE[key]


# ==============================================================================
# BASE CLASS
# ==============================================================================
class Entity:
    """Karakter grid: posisi tile + posisi pixel, path, animasi langkah kaki."""

    def __init__(self, gx, gy, walk_frames, idle_frames=None, speed_tps=4.0):
        self.gx, self.gy = gx, gy
        self.px = gx * TILE
        self.py = gy * TILE
        self.walk_frames = walk_frames or []
        self.idle_frames = idle_frames or self.walk_frames[:1]
        self.speed_tps = speed_tps
        self.speed_mult = 1.0            # < 1 = terkena efek lambat (es)
        self.slow_timer = 0.0
        self.path = []                   # list[(x,y)] tujuan berurutan
        self.moving = False
        self.target = None
        self.direction = "down"
        self.anim_t = 0.0
        self.hit_flash = 0.0
        self.alive = True
        # ---- player controller -------------------------------------------
        self.manual_mode = False         # True = digerakkan keyboard manual
        self.control_dir = None          # (dx, dy) arah terakhir ditekan
        self.blocked_fn = None           # callable(x, y) -> bool (tabrakan)
        self.frames_dir = None            # {"walk": {...}, "idle": {...}}

    # ------------------------------------------------------------- kontrol
    def set_path(self, tiles):
        self.path = list(tiles or [])

    def stop(self):
        self.path = []
        self.moving = False
        self.target = None

    def set_blocked(self, fn):
        """Pasang fungsi tabrakan: fn(x, y) -> True bila sel terhalang."""
        self.blocked_fn = fn

    def set_control_dir(self, direction):
        """
        Arah yang sedang ditahan pemain (None = tidak ada tombol ditekan).
        Arah disimpan agar sprite menghadap ke arah tersebut.
        """
        if direction is None:
            self.control_dir = None
            return
        self.control_dir = DIRS.get(direction, direction)
        self.direction = direction

    def is_blocked(self, x, y):
        if self.blocked_fn is None:
            return False
        try:
            return bool(self.blocked_fn(x, y))
        except Exception:
            return False

    def _try_manual_step(self):
        """Coba melangkah satu sel ke arah yang ditekan (bila tidak terhalang)."""
        if not self.control_dir:
            return False
        dx, dy = self.control_dir
        nx, ny = self.gx + dx, self.gy + dy
        if self.is_blocked(nx, ny):
            return False
        self.target = (nx, ny)
        self.moving = True
        return True

    @property
    def speed_px(self):
        return self.speed_tps * self.speed_mult * TILE

    def apply_slow(self, mult, duration):
        self.speed_mult = mult
        self.slow_timer = duration

    # -------------------------------------------------------------- update
    def update(self, dt):
        """Update gerakan & animasi. Mengembalikan event (mis. 'arrived')."""
        event = None
        if self.slow_timer > 0:
            self.slow_timer -= dt
            if self.slow_timer <= 0:
                self.speed_mult = 1.0
        if self.hit_flash > 0:
            self.hit_flash = max(0.0, self.hit_flash - dt)

        if self.moving and self.target is not None:
            tx, ty = self.target[0] * TILE, self.target[1] * TILE
            dx, dy = tx - self.px, ty - self.py
            dist = math.hypot(dx, dy)
            step = self.speed_px * dt
            if dist <= step:
                self.px, self.py = float(tx), float(ty)
                self.gx, self.gy = self.target
                self.moving = False
                self.target = None
                event = "arrived"
            else:
                self.px += dx / dist * step
                self.py += dy / dist * step
        elif self.manual_mode:
            # mode manual: hero melangkah mengikuti tombol yang ditekan
            self._try_manual_step()
        elif self.path:
            nxt = self.path.pop(0)
            if nxt == (self.gx, self.gy):
                pass
            else:
                ddx, ddy = nxt[0] - self.gx, nxt[1] - self.gy
                if abs(ddx) > abs(ddy):
                    self.direction = "right" if ddx > 0 else "left"
                else:
                    self.direction = "down" if ddy > 0 else "up"
                self.target = nxt
                self.moving = True

        self.anim_t += dt
        return event

    # --------------------------------------------------------------- render
    def _direction_frames(self, moving):
        """Pilih daftar frame sesuai arah gerak (down / up / side)."""
        if not self.frames_dir:
            return self.walk_frames if (moving and len(self.walk_frames) > 1) \
                else (self.idle_frames or self.walk_frames)
        bucket = self.frames_dir.get("walk" if moving else "idle", {})
        if self.direction == "up":
            return bucket.get("up") or bucket.get("down") or []
        if self.direction in ("left", "right"):
            return bucket.get("side") or bucket.get("down") or []
        return bucket.get("down") or []

    def _current_frame(self):
        frames = self._direction_frames(self.moving)
        if not frames:
            return None
        idx = int(self.anim_t / FRAME_DURATION) % len(frames)
        frame = frames[idx]
        if self.direction == "left":
            frame = pygame.transform.flip(frame, True, False)
        return frame

    def draw(self, surface, camera=(0, 0)):
        frame = self._current_frame()
        if frame is None:
            return
        ox, oy = camera
        px, py = self.px - ox, self.py - oy
        # bayangan tanah
        shadow = _ground_shadow()
        surface.blit(shadow, (px + TILE / 2 - shadow.get_width() / 2,
                              py + TILE - shadow.get_height() - 2))
        rect = frame.get_rect(midbottom=(px + TILE // 2,
                                         py + TILE - 4))
        surface.blit(frame, rect)
        if self.hit_flash > 0:
            flash = pygame.Surface(frame.get_size(), pygame.SRCALPHA)
            flash.fill((255, 255, 255, int(150 * min(1.0, self.hit_flash * 3))))
            surface.blit(flash, rect)

    @property
    def cell(self):
        return (self.gx, self.gy)

    def tile_rect(self):
        return pygame.Rect(self.px, self.py, TILE, TILE)


# ==============================================================================
# HERO (dikendalikan manual WASD / panah, atau auto-pilot A*)
# ==============================================================================
class Hero(Entity):
    def __init__(self, gx, gy, assets, speed_tps=config.HERO_SPEED_TPS):
        super().__init__(gx, gy, assets.hero_walk, assets.hero_idle, speed_tps)
        # set animasi per arah: depan (down), belakang (up), samping (side)
        self.frames_dir = assets.hero_frame_buckets()

        import combat_config as ccfg
        self.ccfg = ccfg

        self.hp = ccfg.PLAYER_MAX_HP
        self.max_hp = ccfg.PLAYER_MAX_HP
        self.mana = config.HERO_MAX_MANA
        self.buff_turns = 0
        self.invuln = 0.0
        self.crossed_trap = False
        self.trap_step_count = 0

        # Sistem Serangan Real-Time
        self.attack_frames = assets.hero_attack if hasattr(assets, "hero_attack") else []
        self.is_attacking = False
        self.attack_timer = 0.0
        self.attack_cooldown = 0.0
        self.attack_hit_enemies = set()

        # Knockback Player
        self.knockback_vx = 0.0
        self.knockback_vy = 0.0

        # Animasi Aksi Dunia (Axe, Mining, Reeling, Caught, Doing, Watering)
        self.action_anim: Optional[str] = None
        self.action_anim_timer: float = 0.0
        self.action_anim_duration: float = 0.0

    def play_action_animation(self, anim_name: str, duration: float = 1.0):
        """Memainkan animasi aksi tertentu (mis. axe, mining, reeling, doing, watering)."""
        self.action_anim = anim_name.lower()
        self.action_anim_timer = 0.0
        self.action_anim_duration = duration

    def can_attack(self) -> bool:
        """Cek apakah player bisa memulai serangan baru (tidak sedang serang, cooldown habis, dan tidak sedang animasi aksi dunia)."""
        return self.alive and not self.is_attacking and self.attack_cooldown <= 0.0 and self.action_anim is None

    def start_attack(self, target_pos: Optional[Tuple[float, float]] = None):
        """Mulai animasi ayunan senjata serangan player, opsional auto-aim ke arah target."""
        if not self.can_attack():
            return
        if target_pos is not None:
            tx, ty = target_pos
            dx = tx - (self.px + config.TILE_SIZE / 2)
            dy = ty - (self.py + config.TILE_SIZE / 2)
            if abs(dx) > abs(dy):
                self.direction = "right" if dx > 0 else "left"
            else:
                self.direction = "down" if dy > 0 else "up"
        self.is_attacking = True
        self.attack_timer = 0.0
        self.attack_hit_enemies.clear()

    def is_attack_active(self) -> bool:
        """Cek apakah jendela frame ayunan aktif (damage window)."""
        if not self.is_attacking or not self.alive:
            return False
        total_dur = self.ccfg.PLAYER_ATTACK_DURATION_SEC
        if total_dur <= 0:
            return False
        prog = self.attack_timer / total_dur
        return self.ccfg.PLAYER_ATTACK_ACTIVE_START <= prog <= self.ccfg.PLAYER_ATTACK_ACTIVE_END

    def get_attack_hitbox(self) -> Optional[pygame.Rect]:
        """
        Hitbox serangan aktif hanya pada frame tertentu (mis. frame ayunan tengah),
        bukan sepanjang animasi. Mengembalikan Rect hitbox atau None jika sedang pasif.
        """
        if not self.is_attack_active():
            return None

        w = self.ccfg.PLAYER_ATTACK_HITBOX_W
        h = self.ccfg.PLAYER_ATTACK_HITBOX_H

        if self.direction == "right":
            return pygame.Rect(int(self.px + 20), int(self.py + 4), w, h)
        elif self.direction == "left":
            return pygame.Rect(int(self.px - w + 12), int(self.py + 4), w, h)
        elif self.direction == "up":
            return pygame.Rect(int(self.px + 2), int(self.py - h + 10), w, h)
        else:  # down
            return pygame.Rect(int(self.px + 2), int(self.py + 22), w, h)

    def take_combat_damage(self, amount: int, knockback_vector: Tuple[float, float] = (0, 0)) -> int:
        """Menerima damage serangan real-time, memberi i-frame dan knockback."""
        if self.invuln > 0 or not self.alive:
            return 0
        self.hp = max(0, self.hp - amount)
        self.invuln = self.ccfg.PLAYER_INVULN_SEC
        self.hit_flash = self.ccfg.PLAYER_HIT_FLASH_SEC

        # Dorongan knockback
        kx, ky = knockback_vector
        dist = math.hypot(kx, ky)
        if dist > 0.001:
            self.knockback_vx = (kx / dist) * self.ccfg.PLAYER_KNOCKBACK_FORCE
            self.knockback_vy = (ky / dist) * self.ccfg.PLAYER_KNOCKBACK_FORCE

        if self.hp <= 0:
            self.alive = False
            self.is_attacking = False
        return amount

    def take_damage(self, amount):
        """Kompatibilitas legacy damage."""
        return self.take_combat_damage(amount)

    def update(self, dt):
        if self.invuln > 0:
            self.invuln = max(0.0, self.invuln - dt)
        if self.attack_cooldown > 0:
            self.attack_cooldown = max(0.0, self.attack_cooldown - dt)

        # Update durasi serangan
        if self.is_attacking:
            self.attack_timer += dt
            if self.attack_timer >= self.ccfg.PLAYER_ATTACK_DURATION_SEC:
                self.is_attacking = False
                self.attack_cooldown = self.ccfg.PLAYER_ATTACK_COOLDOWN_SEC

        # Update durasi animasi aksi dunia
        if self.action_anim:
            self.action_anim_timer += dt
            if self.action_anim_timer >= self.action_anim_duration:
                self.action_anim = None

        if self.buff_turns > 0 and self.hp > 0:
            pass
        return super().update(dt)

    def feet_hitbox(self) -> pygame.Rect:
        """Hitbox kecil di area kaki player (8 titik sampel) di koordinat map."""
        try:
            import mask_config
            w = mask_config.PLAYER_FEET_HITBOX_W
            h = mask_config.PLAYER_FEET_HITBOX_H
        except Exception:
            w, h = 14, 8
        hx = int(self.px + (config.TILE_SIZE - w) / 2)
        hy = int(self.py + config.TILE_SIZE - h - 1)
        return pygame.Rect(hx, hy, w, h)

    def move_with_map(self, game_map, dx: float, dy: float):
        """
        Gerakkan player menggunakan collision mask open-world.
        Pengecekan collision dilakukan per sumbu (X lalu Y) dengan sub-stepping 8 titik sampel.
        """
        dt = 1.0 / 60.0  # estimasi dt untuk knockback jika dipanggil per frame

        # Terapkan knockback jika ada
        if abs(self.knockback_vx) > 1.0 or abs(self.knockback_vy) > 1.0:
            hb = self.feet_hitbox()
            game_map.move_and_slide(hb, self.knockback_vx * dt, self.knockback_vy * dt)
            self.px = hb.x - (config.TILE_SIZE - self.ccfg.PLAYER_FEET_HITBOX_W) / 2
            self.py = hb.y - config.TILE_SIZE + self.ccfg.PLAYER_FEET_HITBOX_H + 1
            self.knockback_vx *= 0.8
            self.knockback_vy *= 0.8

        if dx == 0 and dy == 0:
            self.moving = False
            return

        self.moving = True
        # Jangan ubah arah hadap saat sedang ayun serangan
        if not self.is_attacking:
            if abs(dx) > abs(dy):
                self.direction = "right" if dx > 0 else "left"
            else:
                self.direction = "down" if dy > 0 else "up"

        # Kurangi kecepatan jika sedang mengayunkan senjata
        speed_mult = self.ccfg.PLAYER_ATTACK_SPEED_MULT if self.is_attacking else 1.0
        final_dx = dx * speed_mult
        final_dy = dy * speed_mult

        hb = self.feet_hitbox()
        resolved_dx, resolved_dy = game_map.move_and_slide(hb, final_dx, final_dy)
        self.px += resolved_dx
        self.py += resolved_dy

        self.gx = int(self.px // config.TILE_SIZE)
        self.gy = int(self.py // config.TILE_SIZE)

    def draw(self, surface, camera=(0, 0)):
        # Efek berkedip saat kebal (i-frame)
        if self.invuln > 0 and int(self.invuln * 20) % 2 == 0:
            return

        ox, oy = camera
        px, py = self.px - ox, self.py - oy

        # Bayangan kaki
        shadow = _ground_shadow()
        surface.blit(shadow, (px + TILE / 2 - shadow.get_width() / 2,
                              py + TILE - shadow.get_height() - 2))

        # Pilih frame: Animasi aksi, animasi serang, atau idle/walk biasa
        if self.action_anim:
            try:
                from hero_sprite import get_hero_sprite_manager
                mgr = get_hero_sprite_manager()
                frames = mgr.get_world_frames(self.action_anim)
                if frames:
                    prog = min(1.0, max(0.0, self.action_anim_timer / max(0.001, self.action_anim_duration)))
                    idx = min(int(prog * len(frames)), len(frames) - 1)
                    frame = frames[idx]
                    if self.direction == "left":
                        frame = pygame.transform.flip(frame, True, False)
                    rect = frame.get_rect(midbottom=(px + TILE // 2, py + TILE - 4))
                    surface.blit(frame, rect)
                    return
            except Exception:
                pass

        if self.is_attacking and self.attack_frames:
            total_dur = self.ccfg.PLAYER_ATTACK_DURATION_SEC
            prog = min(1.0, max(0.0, self.attack_timer / total_dur))
            idx = min(int(prog * len(self.attack_frames)), len(self.attack_frames) - 1)
            frame = self.attack_frames[idx]
            if self.direction == "left":
                frame = pygame.transform.flip(frame, True, False)
            rect = frame.get_rect(midbottom=(px + TILE // 2, py + TILE - 4))
            surface.blit(frame, rect)
            if self.hit_flash > 0:
                flash = pygame.Surface(frame.get_size(), pygame.SRCALPHA)
                flash.fill((255, 255, 255, int(150 * min(1.0, self.hit_flash * 3))))
                surface.blit(flash, rect)
        else:
            # Render standard walk/idle
            super().draw(surface, camera)

        if self.manual_mode and not self.is_attacking:
            tipx = px + TILE // 2
            tipy = py - 2
            pygame.draw.polygon(surface, config.CYAN,
                                [(tipx, tipy - 7), (tipx - 5, tipy), (tipx + 5, tipy)])

    @property
    def sort_y(self) -> float:
        """Kunci kedalaman untuk y-sorting rendering bersama entitas lain."""
        return self.py + config.TILE_SIZE


# ==============================================================================
# MONSTER (patroli Dijkstra / kejar hero)
# ==============================================================================
class Monster(Entity):
    def __init__(self, gx, gy, walk_frames, kind="zombie",
                 element=None, speed_tps=config.MONSTER_SPEED_TPS):
        super().__init__(gx, gy, walk_frames, speed_tps=speed_tps)
        self.kind = kind
        self.element = element            # None | "ice"
        self.patrol_points = []
        self.patrol_index = 0
        self.state = "PATROL"             # PATROL | ALERT | CHASE | ATTACK
        self.chase_radius = config.MONSTER_CHASE_RADIUS
        self.damage = config.MONSTER_DAMAGE
        self.attack_cd = 0.0
        self.repath_cd = 0.0
        self.alert_timer = 0.0            # jeda waspada sebelum mengejar
        self.windup_timer = 0.0           # ancang-ancang sebelum menyerang
        self.placed = False               # True bila dipasang pemain (CSP)

    def update(self, dt):
        if self.attack_cd > 0:
            self.attack_cd -= dt
        return super().update(dt)

    def next_patrol_point(self):
        if not self.patrol_points:
            return self.gx, self.gy
        self.patrol_index = (self.patrol_index + 1) % len(self.patrol_points)
        return self.patrol_points[self.patrol_index]


class Boss(Entity):
    """Boss penjaga Obsidian Keep / Dungeon - statis, didekati player."""

    def __init__(self, x=None, y=None, assets=None, speed_tps=config.BOSS_SPEED_TPS):
        if x is None or y is None:
            x, y = config.BOSS_POS
        # Jika koordinat kecil (< 200), anggap tile koordinat (kompatibilitas level/core lama)
        if x < 200 and y < 200:
            px, py = float(x * config.TILE_SIZE), float(y * config.TILE_SIZE)
            gx, gy = int(x), int(y)
        else:
            px, py = float(x), float(y)
            gx, gy = int(px // config.TILE_SIZE), int(py // config.TILE_SIZE)

        idle_frames = getattr(assets, "boss_idle", None)
        walk_frames = getattr(assets, "boss_walk", None)
        super().__init__(gx, gy, walk_frames, idle_frames, speed_tps)
        self.px = px
        self.py = py
        self.spawn_x = px
        self.spawn_y = py
        self.assets = assets
        self.name = config.BOSS_NAME
        self.hp = config.BOSS_MAX_HP
        self.max_hp = config.BOSS_MAX_HP
        self.alive = True
        self.defeated = False
        self.direction = "left"

    @property
    def cell(self):
        return (int(self.px // config.TILE_SIZE), int(self.py // config.TILE_SIZE))

    @property
    def sort_y(self) -> float:
        """Kunci kedalaman untuk y-sorting rendering bersama entitas lain."""
        return self.py + config.TILE_SIZE

    def reset(self):
        """Reset boss ke kondisi awal."""
        self.px = self.spawn_x
        self.py = self.spawn_y
        self.hp = self.max_hp
        self.alive = True
        self.defeated = False
        self.hit_flash = 0.0

    def take_damage(self, amount):
        self.hp = max(0, self.hp - amount)
        self.hit_flash = 0.4
        return amount

    def update(self, dt):
        """Boss statis: tidak bergerak atau mengejar, hanya update timer animasi."""
        self.anim_t += dt
        if self.hit_flash > 0:
            self.hit_flash = max(0.0, self.hit_flash - dt)

    def draw(self, surface, camera=(0, 0)):
        ox, oy = camera
        draw_x = int(self.px - ox)
        draw_y = int(self.py - oy)

        # Jika sudah dikalahkan, tampilkan kerangka di tanah
        if self.defeated or not self.alive:
            remains = getattr(self.assets, "boss_remains", None)
            if remains:
                shadow = _ground_shadow()
                surface.blit(shadow, (draw_x + config.TILE_SIZE // 2 - shadow.get_width() // 2,
                                      draw_y + config.TILE_SIZE - shadow.get_height()))
                rect = remains.get_rect(midbottom=(draw_x + config.TILE_SIZE // 2, draw_y + config.TILE_SIZE + 4))
                surface.blit(remains, rect)
            return

        # 1. Bayangan oval di bawah boss (anchor bottom-center)
        shadow_w = 44
        shadow_h = 16
        shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 110), shadow_surf.get_rect())
        surface.blit(shadow_surf, (draw_x + (config.TILE_SIZE - shadow_w) // 2,
                                   draw_y + config.TILE_SIZE - shadow_h // 2 - 2))

        # 2. Efek Aura Napas / Magic Ring berdenyut halus (napas/aura ringan)
        pulse = 0.5 + 0.5 * math.sin(self.anim_t * 3.0)
        aura_w = int(48 + 12 * pulse)
        aura_h = int(18 + 6 * pulse)
        aura_surf = pygame.Surface((aura_w, aura_h), pygame.SRCALPHA)
        aura_alpha = int(60 + 40 * pulse)
        pygame.draw.ellipse(aura_surf, (150, 40, 70, aura_alpha), aura_surf.get_rect(), 2)
        pygame.draw.ellipse(aura_surf, (200, 50, 90, aura_alpha // 2), aura_surf.get_rect())
        surface.blit(aura_surf, (draw_x + (config.TILE_SIZE - aura_w) // 2,
                                 draw_y + config.TILE_SIZE - aura_h // 2 - 2))

        # 3. Sprite Frame Idle dengan anchor bottom-center
        frames = self.idle_frames
        if frames:
            idx = int(self.anim_t / 0.14) % len(frames)
            frame = frames[idx].copy()
            if self.direction == "left":
                frame = pygame.transform.flip(frame, True, False)
            rect = frame.get_rect(midbottom=(draw_x + config.TILE_SIZE // 2, draw_y + config.TILE_SIZE))
            surface.blit(frame, rect)

            # Hit flash putih
            if self.hit_flash > 0:
                mask = pygame.mask.from_surface(frame)
                alpha = max(0, min(255, int(220 * (self.hit_flash / 0.4))))
                flash_surf = mask.to_surface(setcolor=(255, 255, 255, alpha), unsetcolor=(0, 0, 0, 0))
                surface.blit(flash_surf, rect)

            # 4. Indikator di atas boss (ikon tengkorak/tanda seru)
            icon = getattr(self.assets, "ui_boss_skull", None) or getattr(self.assets, "ui_boss_alert", None)
            bob = int(3 * math.sin(self.anim_t * 4.0))
            top_y = rect.top - 18 + bob
            if icon:
                icon_rect = icon.get_rect(center=(draw_x + config.TILE_SIZE // 2, top_y))
                surface.blit(icon, icon_rect)
                top_y = icon_rect.top - 4

            # 5. Label Nama Boss di atas boss
            font = pygame.font.Font(None, 16)
            name_surf = font.render(self.name, True, (255, 215, 110))
            bw, bh = name_surf.get_width() + 10, name_surf.get_height() + 4
            bx = draw_x + config.TILE_SIZE // 2 - bw // 2
            by = top_y - bh
            bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
            bg.fill((15, 10, 20, 210))
            surface.blit(bg, (bx, by))
            pygame.draw.rect(surface, (180, 50, 70), (bx, by, bw, bh), 1)
            surface.blit(name_surf, (bx + 5, by + 2))


# ==============================================================================
# TRAP (dipasang pemain, tervalidasi CSP)
# ==============================================================================
class Trap:
    """Jebakan; aktif kembali setelah TRAP_REARM_TIME detik."""

    def __init__(self, gx, gy, kind, frames):
        self.gx, self.gy = gx, gy
        self.kind = kind                  # "fire_trap" | "ice_trap"
        self.frames = frames
        self.active = True
        self.arm_timer = 0.0
        self.anim_t = 0.0
        self.trigger_flash = 0.0

    @property
    def cell(self):
        return (self.gx, self.gy)

    def trigger(self):
        if not self.active:
            return None
        self.active = False
        self.arm_timer = config.TRAP_REARM_TIME
        self.trigger_flash = 0.5
        return self.kind

    def update(self, dt):
        self.anim_t += dt
        if not self.active:
            self.arm_timer -= dt
            if self.arm_timer <= 0:
                self.active = True
        if self.trigger_flash > 0:
            self.trigger_flash = max(0.0, self.trigger_flash - dt)

    def draw(self, surface, camera=(0, 0)):
        frame = self.frames[int(self.anim_t / 0.14) % len(self.frames)]
        ox, oy = camera
        px, py = self.gx * TILE - ox, self.gy * TILE - oy
        surface.blit(frame, (px, py))
        if not self.active:
            dim = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 130))
            surface.blit(dim, (px, py))
        if self.trigger_flash > 0:
            flash = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            color = config.ORANGE if self.kind == "fire_trap" else config.CYAN
            flash.fill(tuple(color) + (int(160 * self.trigger_flash * 2),))
            surface.blit(flash, (px, py))
