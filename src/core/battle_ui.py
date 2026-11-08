"""
battle_ui.py - ANTARMUKA BATTLE MODE FULLSCREEN & ANIMASI VFX

Layout 4 Zona Fullscreen (1024x768) tanpa tumpang tindih:
  1. ARENA (atas, ~56% tinggi - 1024x430):
     - Latar arena atmosferik dungeon (dinding batu kuno, obor menyala, lantai batu)
     - Aura/cahaya mistis lembut di belakang Skeleton Boss
     - Partikel debu/abu melayang halus
     - Hero Sunnyside otentik (idle loop, attack, hurt) dengan rambut & senjata (skala 7x)
     - Boss Skeleton Sunnyside otentik (idle loop, attack, hurt, death) (skala 8x)
     - Animasi idle looping 8-10 FPS
     - Bayangan proporsional sebanding lebar kaki (60-70%)
     - Turn pill di tengah atas, judul nama Boss
  2. HP BARS:
     - Ditaruh tepat di atas kepala sprite (rata tengah, offset tetap, tidak menimpa kepala)
     - Bar Hero di (120, 185, 220, 22), Bar Boss di (680, 165, 220, 22)
     - Sub-info (Potion, Heal, Heavy cd) berada di bawah bar tanpa menyentuh sprite
     - Ikon & badge perisai saat DEFEND aktif
  3. MENU AKSI (bawah kiri - 520x316):
     - 3 tombol besar: [1] ATTACK, [2] POTION xN, [3] DEFEND dengan ikon
     - States: normal, hover, selected (emas), disabled (abu-abu, HABIS)
     - Deskripsi 2 baris kontras tinggi (min 14-16 px)
     - Hint kontrol lengkap di bawah
  4. BATTLE LOG (bawah kanan - 444x316):
     - Tampilkan 4-5 baris dengan tinggi baris seragam, terbaru di bawah
     - Badge warna semantik per jenis aksi
     - Ringkasan status ikon di header log
  5. PANEL AI THINKING (F3, default tersembunyi):
     - Sisi kanan arena (650, 14, 360, 140), tidak menimpa bar HP atau sprite
     - Menampilkan depth, nodes, pruned, waktu (ms), dan tabel kandidat aksi dengan highlight
"""

import math
import os
import random
import pygame

import config
from hero_sprite import get_hero_sprite_manager
from asset_catalog import get_asset_catalog


def get_battle_layout_rects():
    """
    Menghitung dan mengembalikan Rect setiap elemen UI Battle Mode.
    Digunakan oleh unit test untuk memverifikasi tidak ada tumpang tindih (0 overlaps).
    """
    return {
        "arena": pygame.Rect(config.BATTLE_ARENA_RECT),          # (0, 0, 1024, 430)
        "menu_panel": pygame.Rect(config.BATTLE_MENU_RECT),      # (20, 440, 520, 316)
        "log_panel": pygame.Rect(config.BATTLE_LOG_RECT),        # (560, 440, 444, 316)
        "btn_attack": pygame.Rect(config.BATTLE_BUTTON_1_RECT),  # (36, 482, 488, 48)
        "btn_potion": pygame.Rect(config.BATTLE_BUTTON_2_RECT),  # (36, 536, 488, 48)
        "btn_defend": pygame.Rect(config.BATTLE_BUTTON_3_RECT),  # (36, 590, 488, 48)
        "action_desc": pygame.Rect(config.BATTLE_DESC_RECT),     # (36, 646, 488, 54)
        "action_hint": pygame.Rect(config.BATTLE_HINT_RECT),     # (36, 708, 488, 24)
        "hero_hp": pygame.Rect(config.BATTLE_HERO_HP_RECT),      # (120, 185, 220, 22)
        "boss_hp": pygame.Rect(config.BATTLE_BOSS_HP_RECT),      # (680, 165, 220, 22)
        "turn_pill": pygame.Rect(config.BATTLE_TURN_PILL_RECT),  # (382, 14, 260, 32)
        "boss_title": pygame.Rect(config.BATTLE_BOSS_TITLE_RECT),# (382, 48, 260, 20)
        "ai_panel": pygame.Rect(config.BATTLE_AI_PANEL_RECT),    # (650, 14, 360, 140)
    }


class BattleSpriteLoader:
    """Loader aset otentik Sunnyside World dengan pemotongan presisi dan logging lengkap."""

    def __init__(self):
        self.has_asset_missing = False
        self.hero_scale = 7
        self.boss_scale = 8

        # Slicing bounding boxes di canvas asli 96x64 (center x=48, feet y=40)
        self.hero_crop_box = (20, 6, 72, 36)
        self.hero_anchor = (28, 34)  # (48 - 20, 40 - 6)

        self.boss_crop_box = (24, 8, 56, 34)
        self.boss_anchor = (24, 32)  # (48 - 24, 40 - 8)

        # Muat animasi Hero dari modul tunggal hero_sprite.py
        hero_mgr = get_hero_sprite_manager()
        self.hero_idle = hero_mgr.get_battle_frames("idle", scale=self.hero_scale, crop_box=self.hero_crop_box)
        self.hero_attack = hero_mgr.get_battle_frames("attack", scale=self.hero_scale, crop_box=self.hero_crop_box)
        self.hero_hurt = hero_mgr.get_battle_frames("hurt", scale=self.hero_scale, crop_box=self.hero_crop_box)

        # Muat animasi Boss (Skeleton Overlord)
        skel_dir = os.path.join(config.SUNNYSIDE_DIR, "Characters", "Skeleton", "PNG")
        self.boss_idle = self._load_anim(
            os.path.join(skel_dir, "skeleton_idle_strip6.png"), 6,
            self.boss_crop_box, self.boss_scale, flip_x=True
        )
        self.boss_attack = self._load_anim(
            os.path.join(skel_dir, "skeleton_attack_strip7.png"), 7,
            self.boss_crop_box, self.boss_scale, flip_x=True
        )
        self.boss_hurt = self._load_anim(
            os.path.join(skel_dir, "skeleton_hurt_strip7.png"), 7,
            self.boss_crop_box, self.boss_scale, flip_x=True
        )
        self.boss_death = self._load_anim(
            os.path.join(skel_dir, "skeleton_death_strip10.png"), 10,
            self.boss_crop_box, self.boss_scale, flip_x=True
        )

        # Slash VFX & Glint
        h_dir = os.path.join(config.SUNNYSIDE_DIR, "Characters", "Human")
        self.slash_vfx_path = os.path.join(h_dir, "ATTACK", "base_attack_strip10.png")
        glint_path = os.path.join(config.SUNNYSIDE_DIR, "Elements", "VFX", "Glint", "spr_deco_glint_01_strip6.png")
        self.glint_frames = self._load_glint_vfx(glint_path)
        spark_path = os.path.join(config.SUNNYSIDE_DIR, "Elements", "VFX", "Glint", "spr_deco_glint_02_strip4.png")
        self.spark_frames = self._load_spark_vfx(spark_path)

        # Obor / Api Dinding Arena
        fire_path = os.path.join(config.SUNNYSIDE_DIR, "Elements", "VFX", "Fire", "spr_deco_fire_01_strip4.png")
        self.torch_frames = self._load_torch_vfx(fire_path)

    def _load_anim(self, path: str, count: int, crop_box: tuple, scale: int,
                   overlays: list = None, flip_x: bool = False) -> list:
        if not os.path.exists(path):
            print(f"[PERINGATAN ASSET BATTLE] Gagal memuat file: '{path}'! Menggunakan placeholder.")
            self.has_asset_missing = True
            return [self._make_placeholder(crop_box, scale, (200, 50, 50))]

        try:
            sheet = pygame.image.load(path)
            w, h = sheet.get_size()
            fw = w // count
            overlay_surfs = []
            if overlays:
                for ov in overlays:
                    if os.path.exists(ov):
                        overlay_surfs.append(pygame.image.load(ov))
                    else:
                        print(f"[PERINGATAN ASSET BATTLE] Overlay hilang: '{ov}'")

            cx, cy, cw, ch = crop_box
            frames = []
            for i in range(count):
                frame_surf = pygame.Surface((fw, h), pygame.SRCALPHA)
                frame_surf.blit(sheet.subsurface((i * fw, 0, fw, h)), (0, 0))
                for ov_s in overlay_surfs:
                    frame_surf.blit(ov_s.subsurface((i * fw, 0, fw, h)), (0, 0))

                cropped = frame_surf.subsurface((cx, cy, cw, ch))
                scaled = pygame.transform.scale(cropped, (cw * scale, ch * scale))
                if flip_x:
                    scaled = pygame.transform.flip(scaled, True, False)
                frames.append(scaled)

            ov_info = f" (+ {len(overlay_surfs)} layer)" if overlay_surfs else ""
            if getattr(config, "VERBOSE_SPRITE_LOGS", True):
                print(f"[BATTLE SPRITE] Dimuat: {path}{ov_info} | Ukuran strip: ({w}, {h}) | {count} frame | Per frame: ({fw}, {h}) | Scale: {scale}x")
            return frames
        except Exception as e:
            print(f"[PERINGATAN ASSET BATTLE] Error memproses '{path}': {e}")
            self.has_asset_missing = True
            return [self._make_placeholder(crop_box, scale, (200, 50, 50))]

    def _load_glint_vfx(self, path: str) -> list:
        """Memuat kilatan tebasan pedang otentik dari spr_deco_glint_01_strip6."""
        if not os.path.exists(path):
            print(f"[PERINGATAN ASSET BATTLE] Glint VFX '{path}' tidak ditemukan!")
            return []
        try:
            s = pygame.image.load(path)
            w, h = s.get_size()
            count = 6
            fw = w // count
            frames = []
            for i in range(count):
                sub = s.subsurface((i * fw, 0, fw, h))
                scaled = pygame.transform.scale(sub, (fw * 7, h * 7))
                frames.append(scaled)
            if getattr(config, "VERBOSE_SPRITE_LOGS", True):
                print(f"[BATTLE SPRITE] Dimuat Glint VFX (Potion/Heal): {path} | {len(frames)} frame | Scale: 7x")
            return frames
        except Exception as e:
            print(f"[PERINGATAN ASSET BATTLE] Error memuat glint VFX '{path}': {e}")
            return []

    def _load_spark_vfx(self, path: str) -> list:
        """Memuat hit spark VFX dari spr_deco_glint_02_strip4."""
        if not os.path.exists(path):
            return []
        try:
            s = pygame.image.load(path)
            w, h = s.get_size()
            count = 4
            fw = w // count
            frames = []
            for i in range(count):
                sub = s.subsurface((i * fw, 0, fw, h))
                scaled = pygame.transform.scale(sub, (fw * 6, h * 6))
                frames.append(scaled)
            if getattr(config, "VERBOSE_SPRITE_LOGS", True):
                print(f"[BATTLE SPRITE] Dimuat Hit Spark VFX: {path} | {len(frames)} frame | Scale: 6x")
            return frames
        except Exception:
            return []

    def _load_torch_vfx(self, path: str) -> list:
        if not os.path.exists(path):
            return []
        try:
            s = pygame.image.load(path)
            w, h = s.get_size()
            count = 4
            fw = w // count
            frames = []
            for i in range(count):
                sub = s.subsurface((i * fw, 0, fw, h))
                scaled = pygame.transform.scale(sub, (fw * 4, h * 4))
                frames.append(scaled)
            if getattr(config, "VERBOSE_SPRITE_LOGS", True):
                print(f"[BATTLE SPRITE] Dimuat Torch VFX: {path} | {len(frames)} frame | Scale: 4x")
            return frames
        except Exception:
            return []

    def _make_placeholder(self, crop_box: tuple, scale: int, color: tuple) -> pygame.Surface:
        cx, cy, cw, ch = crop_box
        surf = pygame.Surface((cw * scale, ch * scale), pygame.SRCALPHA)
        surf.fill(color)
        return surf


class BattleUI:
    """Manajer Antarmuka & Animasi Turn-Based Battle Mode Fullscreen."""

    def __init__(self):
        # Font pixel terpadu (semua >= 14px)
        self.font_title = pygame.font.Font(None, 24)
        self.font_head = pygame.font.Font(None, 20)
        self.font_body = pygame.font.Font(None, 17)
        self.font_small = pygame.font.Font(None, 14)

        self._text_cache = {}

        # Loader aset battle otentik
        self.loader = BattleSpriteLoader()

        # Navigasi & Input Menu
        self.selected_action_index = 0       # 0: ATTACK, 1: POTION, 2: DEFEND
        self.hovered_action_index = -1
        self.show_ai_panel = False          # Toggle F3 (default tersembunyi)

        # State Machine Animasi & VFX
        self.anim_state = "IDLE"             # "IDLE", "HERO_LUNGE", "HERO_SLASH", "BOSS_HIT", "HERO_RETURN", etc.
        self.anim_timer = 0.0
        self.anim_data = {}
        self.hero_offset_x = 0.0
        self.boss_offset_x = 0.0
        self.hero_flash = 0.0
        self.boss_flash = 0.0
        self.slash_vfx_timer = 0.0
        self.slash_target_pos = (float(config.BATTLE_BOSS_POS[0] - 10), float(config.BATTLE_BOSS_POS[1] - 85))
        self.glint_vfx_timer = 0.0
        self.glint_vfx_pos = (0.0, 0.0)
        self.telegraph_timer = 0.0
        self.shake_intensity = 0.0
        self.hitstop_timer = 0.0

        # Partikel debu/abu atmosferik melayang di arena
        self.ambient_dust = []
        for _ in range(24):
            self.ambient_dust.append({
                "x": random.uniform(20, 1004),
                "y": random.uniform(20, 410),
                "vx": random.uniform(-12, 12),
                "vy": random.uniform(-20, -6),
                "radius": random.uniform(1.2, 2.5),
                "alpha": random.uniform(80, 180)
            })

        # Floating combat text & particles
        self.floating_texts = []
        self.particles = []

        # Surface latar arena & fullscreen yang di-precompute
        self._arena_bg = None
        self._screen_bg = None

    # ------------------------------------------------------------------ UTILITAS TEKS
    def _txt(self, msg, color=config.WHITE, font=None):
        key = (str(msg), color, id(font or self.font_body))
        surf = self._text_cache.get(key)
        if surf is None:
            surf = (font or self.font_body).render(str(msg), True, color)
            if len(self._text_cache) > 800:
                self._text_cache.clear()
            self._text_cache[key] = surf
        return surf

    def _txt_outlined(self, screen, msg, x, y, color=config.WHITE, outline_color=(10, 10, 14), font=None):
        """Render teks dengan outline gelap untuk kontras tinggi di latar mana pun."""
        f = font or self.font_body
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            s_out = self._txt(msg, outline_color, f)
            screen.blit(s_out, (x + dx, y + dy))
        s_main = self._txt(msg, color, f)
        screen.blit(s_main, (x, y))
        return s_main.get_width()

    # ------------------------------------------------------------------ ANIMASI & VFX KONTROL
    def is_animating(self) -> bool:
        """Kunci input pemain bila animasi sedang berlangsung."""
        return self.anim_state != "IDLE" or self.hitstop_timer > 0.0

    def trigger_action_animation(self, actor: str, action: str, amount: int = 0, is_blocked: bool = False):
        """Mulai rangkaian animasi untuk aksi tertentu."""
        if actor in ("hero", "player"):
            if action == "ATTACK":
                self.anim_state = "HERO_LUNGE"
                self.anim_timer = 0.14
                self.anim_data = {"dmg": amount, "blocked": is_blocked}
            elif action == "POTION":
                self.anim_state = "POTION_DRINK"
                self.anim_timer = 0.35
                self.anim_data = {"heal": amount}
                self.glint_vfx_timer = 0.35
                self.glint_vfx_pos = (float(config.BATTLE_HERO_POS[0]), float(config.BATTLE_HERO_POS[1] - 80))
                self.spawn_floating_text(f"+{amount} HP", config.BATTLE_HERO_POS[0], config.BATTLE_HERO_POS[1] - 170, config.GREEN)
                self.spawn_particles(config.BATTLE_HERO_POS[0], config.BATTLE_HERO_POS[1] - 80, (60, 240, 100), count=22)
            elif action == "DEFEND":
                self.anim_state = "DEFEND_CAST"
                self.anim_timer = 0.35
                self.anim_data = {}
                self.spawn_floating_text("DEFEND (-60%)", config.BATTLE_HERO_POS[0], config.BATTLE_HERO_POS[1] - 170, config.CYAN)
                self.spawn_particles(config.BATTLE_HERO_POS[0], config.BATTLE_HERO_POS[1] - 80, (70, 190, 255), count=20)
        else:
            if action in ("ATTACK", "HEAVY_ATTACK"):
                self.anim_state = "BOSS_TELEGRAPH"
                self.anim_timer = 0.22 if action == "ATTACK" else 0.34
                self.telegraph_timer = self.anim_timer
                self.anim_data = {"action": action, "dmg": amount, "blocked": is_blocked}
            elif action == "DEFEND":
                self.anim_state = "BOSS_DEFEND"
                self.anim_timer = 0.35
                self.anim_data = {}
                self.spawn_floating_text("DEFEND (-50%)", config.BATTLE_BOSS_POS[0], config.BATTLE_BOSS_POS[1] - 190, config.PURPLE)
                self.spawn_particles(config.BATTLE_BOSS_POS[0], config.BATTLE_BOSS_POS[1] - 90, (190, 100, 250), count=20)
            elif action == "HEAL":
                self.anim_state = "BOSS_HEAL"
                self.anim_timer = 0.35
                self.anim_data = {"heal": amount}
                self.glint_vfx_timer = 0.35
                self.glint_vfx_pos = (float(config.BATTLE_BOSS_POS[0]), float(config.BATTLE_BOSS_POS[1] - 90))
                self.spawn_floating_text(f"+{amount} HP", config.BATTLE_BOSS_POS[0], config.BATTLE_BOSS_POS[1] - 190, config.GREEN)
                self.spawn_particles(config.BATTLE_BOSS_POS[0], config.BATTLE_BOSS_POS[1] - 90, (80, 240, 120), count=22)

    def spawn_floating_text(self, text: str, x: float, y: float, color: tuple):
        self.floating_texts.append({
            "text": text,
            "x": float(x),
            "y": float(y),
            "color": color,
            "timer": 0.90,
            "duration": 0.90,
            "vy": -38.0
        })

    def spawn_particles(self, x: float, y: float, color: tuple, count: int = 14):
        for _ in range(count):
            ang = random.uniform(0, 2 * math.pi)
            spd = random.uniform(30.0, 95.0)
            self.particles.append({
                "x": float(x),
                "y": float(y),
                "vx": math.cos(ang) * spd,
                "vy": math.sin(ang) * spd,
                "color": color,
                "radius": random.uniform(2.5, 4.5),
                "timer": random.uniform(0.35, 0.60),
                "duration": 0.60
            })

    def update(self, dt: float):
        """Update timer non-blocking untuk animasi, partikel, dan getaran layar."""
        # Hitstop pause (efek benturan dramatis)
        if self.hitstop_timer > 0.0:
            self.hitstop_timer = max(0.0, self.hitstop_timer - dt)
            return

        # Decay screen shake
        if self.shake_intensity > 0.0:
            self.shake_intensity = max(0.0, self.shake_intensity - dt * 20.0)

        # Decay flashes
        if self.hero_flash > 0.0:
            self.hero_flash = max(0.0, self.hero_flash - dt)
        if self.boss_flash > 0.0:
            self.boss_flash = max(0.0, self.boss_flash - dt)
        if self.slash_vfx_timer > 0.0:
            self.slash_vfx_timer = max(0.0, self.slash_vfx_timer - dt)
        if self.glint_vfx_timer > 0.0:
            self.glint_vfx_timer = max(0.0, self.glint_vfx_timer - dt)
        if self.telegraph_timer > 0.0:
            self.telegraph_timer = max(0.0, self.telegraph_timer - dt)

        # Update Floating Texts
        for ft in self.floating_texts:
            ft["timer"] -= dt
            ft["y"] += ft["vy"] * dt
        self.floating_texts = [ft for ft in self.floating_texts if ft["timer"] > 0]

        # Update Particles
        for p in self.particles:
            p["timer"] -= dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += 35.0 * dt
        self.particles = [p for p in self.particles if p["timer"] > 0]

        # Update Ambient Dust Motes
        for d in self.ambient_dust:
            d["y"] += d["vy"] * dt
            d["x"] += d["vx"] * dt
            if d["y"] < 10:
                d["y"] = 420
                d["x"] = random.uniform(20, 1004)

        # State machine transit
        if self.anim_state != "IDLE":
            self.anim_timer -= dt
            if self.anim_timer <= 0.0:
                self._advance_anim_state()

    def _advance_anim_state(self):
        st = self.anim_state
        if st == "HERO_LUNGE":
            self.anim_state = "HERO_SLASH"
            self.anim_timer = 0.14
            self.hero_offset_x = 75.0
            self.slash_vfx_timer = 0.20
            self.slash_target_pos = (float(config.BATTLE_BOSS_POS[0] - 10), float(config.BATTLE_BOSS_POS[1] - 85))
        elif st == "HERO_SLASH":
            self.anim_state = "BOSS_HIT"
            self.anim_timer = 0.20
            self.boss_flash = 0.28
            self.shake_intensity = 8.0
            self.hitstop_timer = 0.09
            dmg = self.anim_data.get("dmg", 0)
            blocked = self.anim_data.get("blocked", False)
            color = config.CYAN if blocked else config.RED
            txt = f"-{dmg} HP" + (" (BLOK)" if blocked else "")
            self.spawn_floating_text(txt, config.BATTLE_BOSS_POS[0], config.BATTLE_BOSS_POS[1] - 190, color)
            self.spawn_particles(config.BATTLE_BOSS_POS[0], config.BATTLE_BOSS_POS[1] - 90, (255, 90, 90), count=18)
        elif st == "BOSS_HIT":
            self.anim_state = "HERO_RETURN"
            self.anim_timer = 0.15
            self.hero_offset_x = 25.0
        elif st == "HERO_RETURN":
            self.hero_offset_x = 0.0
            self.anim_state = "IDLE"
        elif st == "BOSS_TELEGRAPH":
            self.anim_state = "BOSS_LUNGE"
            self.anim_timer = 0.15
            self.boss_offset_x = -75.0
        elif st == "BOSS_LUNGE":
            self.anim_state = "BOSS_STRIKE"
            self.anim_timer = 0.14
            self.slash_vfx_timer = 0.20
            self.slash_target_pos = (float(config.BATTLE_HERO_POS[0] + 10), float(config.BATTLE_HERO_POS[1] - 65))
        elif st == "BOSS_STRIKE":
            self.anim_state = "HERO_HIT"
            is_heavy = (self.anim_data.get("action") == "HEAVY_ATTACK")
            self.anim_timer = 0.24 if is_heavy else 0.18
            self.hero_flash = 0.28
            self.shake_intensity = 12.0 if is_heavy else 7.0
            self.hitstop_timer = 0.10
            dmg = self.anim_data.get("dmg", 0)
            blocked = self.anim_data.get("blocked", False)
            color = config.CYAN if blocked else config.RED
            txt = f"-{dmg} HP" + (" (BLOK)" if blocked else "")
            self.spawn_floating_text(txt, config.BATTLE_HERO_POS[0], config.BATTLE_HERO_POS[1] - 170, color)
            self.spawn_particles(config.BATTLE_HERO_POS[0], config.BATTLE_HERO_POS[1] - 80, (255, 110, 70), count=18)
        elif st == "HERO_HIT":
            self.anim_state = "BOSS_RETURN"
            self.anim_timer = 0.15
            self.boss_offset_x = -25.0
        elif st == "BOSS_RETURN":
            self.boss_offset_x = 0.0
            self.anim_state = "IDLE"
        elif st in ("POTION_DRINK", "DEFEND_CAST", "BOSS_DEFEND", "BOSS_HEAL"):
            self.anim_state = "IDLE"

    # ------------------------------------------------------------------ RENDERING LENGKAP
    def draw(self, screen: pygame.Surface, game):
        """Gambar antarmuka Battle Mode 4 Zona Fullscreen (1024x768)."""
        battle = game.battle
        if battle is None:
            return
        state = battle["state"]

        # 0. TUTUP SELURUH LAYAR DENGAN BACKGROUND BATTLE (1024x768 OPAQUE)
        self._draw_fullscreen_backdrop(screen)

        # Hitung shake offset
        sx, sy = 0, 0
        if self.shake_intensity > 0.0:
            sx = int(random.uniform(-self.shake_intensity, self.shake_intensity))
            sy = int(random.uniform(-self.shake_intensity, self.shake_intensity))

        # 1. ZONA ARENA (ATAS ~56% TINGGI - 1024x430)
        self._draw_arena(screen, game, battle, state, sx, sy)

        # 2. HP BARS (DI ATAS KEPALA SPRITE)
        self._draw_hp_bars(screen, state)

        # 3. ZONA MENU AKSI (BAWAH KIRI)
        self._draw_action_menu(screen, state)

        # 4. ZONA BATTLE LOG (BAWAH KANAN)
        self._draw_battle_log(screen, battle, state)

        # 5. PANEL AI THINKING (F3 TOGGLE)
        if self.show_ai_panel:
            self._draw_ai_panel(screen, game)

        # Floating combat text & particles
        self._draw_effects(screen)

        # Badge "ASSET MISSING" jika ada kegagalan load
        if self.loader.has_asset_missing:
            badge = pygame.Rect(10, 10, 120, 22)
            pygame.draw.rect(screen, config.RED, badge, border_radius=4)
            screen.blit(self._txt("ASSET MISSING", config.WHITE, self.font_small), (16, 14))

    # ------------------------------------------------------------------ ZONA 0: FULLSCREEN BACKDROP
    def _draw_fullscreen_backdrop(self, screen: pygame.Surface):
        """Tutup seluruh layar 1024x768 agar peta eksplorasi tidak bocor."""
        if self._screen_bg is None:
            self._screen_bg = pygame.Surface((1024, 768), 0, 24)
            # Latar gelap batuan obsidian
            self._screen_bg.fill((14, 13, 20))
            # Tekstur framing bawah
            for y in range(430, 768, 32):
                pygame.draw.line(self._screen_bg, (20, 19, 28), (0, y), (1024, y), 1)
            for x in range(0, 1024, 32):
                pygame.draw.line(self._screen_bg, (18, 17, 26), (x, 430), (x, 768), 1)

        screen.blit(self._screen_bg, (0, 0))

    # ------------------------------------------------------------------ ZONA 1: ARENA
    def _draw_arena(self, screen: pygame.Surface, game, battle, state, sx: int, sy: int):
        arena_rect = pygame.Rect(config.BATTLE_ARENA_RECT)

        # 1. Background Arena Bertingkat (Dinding Dungeon Kuno + Lantai Paving)
        if self._arena_bg is None:
            self._arena_bg = pygame.Surface((arena_rect.w, arena_rect.h), 0, 24)
            # Gradien dinding atas (dungeon keep obsidian)
            for y in range(arena_rect.h):
                t = y / arena_rect.h
                r = int(12 + t * 16)
                g = int(10 + t * 14)
                b = int(22 + t * 20)
                pygame.draw.line(self._arena_bg, (r, g, b), (0, y), (arena_rect.w, y))

            # Pilar-pilar batu di latar belakang dinding
            for px in (120, 280, 512, 740, 900):
                pygame.draw.rect(self._arena_bg, (22, 20, 32), (px - 22, 40, 44, 250))
                pygame.draw.line(self._arena_bg, (36, 32, 50), (px - 22, 40), (px - 22, 290), 2)
                pygame.draw.line(self._arena_bg, (16, 14, 24), (px + 22, 40), (px + 22, 290), 2)
                # Lengkungan arch di atas pilar
                pygame.draw.arc(self._arena_bg, (36, 32, 50), (px - 40, 10, 80, 60), 0, math.pi, 2)

            # Lantai batu dungeon arena (dari y=290 sampai y=430)
            floor_y = 290
            pygame.draw.rect(self._arena_bg, (24, 22, 34), (0, floor_y, arena_rect.w, arena_rect.h - floor_y))
            # Garis perspektif slab paving
            for lx in range(0, arena_rect.w + 140, 80):
                pygame.draw.line(self._arena_bg, (34, 30, 46), (lx - 160, arena_rect.h), (lx, floor_y), 1)
            for ly in (305, 330, 360, 395, 428):
                pygame.draw.line(self._arena_bg, (38, 34, 52), (0, ly), (arena_rect.w, ly), 1)

            # Border pemisah bawah
            pygame.draw.line(self._arena_bg, (70, 65, 95), (0, arena_rect.h - 1), (arena_rect.w, arena_rect.h - 1), 2)

        screen.blit(self._arena_bg, (arena_rect.x, arena_rect.y))

        # 2. Obor Dinding Menyala (Animated Sunnyside Torch)
        self._draw_wall_torches(screen, game)

        # 3. Aura Mistis Lembut di Belakang Boss
        self._draw_boss_aura(screen, game)

        # 4. Partikel Debu/Abu Melayang Halus
        self._draw_ambient_dust(screen)

        # 5. Turn Indicator Pill & Judul Boss
        self._draw_turn_pill(screen, battle)
        title_rect = pygame.Rect(config.BATTLE_BOSS_TITLE_RECT)
        title_txt = f"<< {config.BOSS_NAME} >>"
        w = self.font_body.size(title_txt)[0]
        self._txt_outlined(screen, title_txt, title_rect.centerx - w // 2, title_rect.y, config.GOLD, font=self.font_body)

        # 6. Posisi & Bayangan Sprite
        hero_x = config.BATTLE_HERO_POS[0] + self.hero_offset_x + sx
        hero_y = config.BATTLE_HERO_POS[1] + sy
        boss_x = config.BATTLE_BOSS_POS[0] + self.boss_offset_x + sx
        boss_y = config.BATTLE_BOSS_POS[1] + sy

        # Bayangan proporsional sebanding lebar kaki (60-70% lebar sprite)
        # Hero lebar tubuh ~ 80px -> bayangan 64px
        shadow_hero = pygame.Surface((64, 18), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_hero, (0, 0, 0, 130), (0, 0, 64, 18))
        screen.blit(shadow_hero, (hero_x - 32, hero_y - 9))

        # Boss lebar tubuh ~ 100px -> bayangan 78px
        shadow_boss = pygame.Surface((78, 20), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_boss, (0, 0, 0, 130), (0, 0, 78, 20))
        screen.blit(shadow_boss, (boss_x - 39, boss_y - 10))

        # 7. Render Sprite Hero & Boss (Animasi Looping 8-10 FPS)
        self._draw_hero_sprite(screen, game, hero_x, hero_y)
        self._draw_boss_sprite(screen, game, boss_x, boss_y)

        # 8. Slash VFX, Glint VFX & Telegraph Flash
        if self.slash_vfx_timer > 0.0:
            is_boss_atk = (self.anim_state in ("BOSS_STRIKE", "HERO_HIT"))
            self._draw_slash_vfx(screen, self.slash_target_pos[0], self.slash_target_pos[1], is_boss=is_boss_atk)

        if self.glint_vfx_timer > 0.0:
            self._draw_glint_vfx(screen, self.glint_vfx_pos[0], self.glint_vfx_pos[1])

        if self.telegraph_timer > 0.0:
            self._draw_telegraph_vfx(screen, boss_x, boss_y - 120)

    def _draw_wall_torches(self, screen: pygame.Surface, game):
        """Render obor dinding menyala dari aset Sunnyside."""
        if not self.loader.torch_frames:
            return
        idx = int(game.time / 0.14) % len(self.loader.torch_frames)
        flame = self.loader.torch_frames[idx]

        for tx in (180, 840):
            ty = 135
            # Sconce braket logam
            pygame.draw.rect(screen, (50, 48, 60), (tx - 4, ty + 18, 8, 14), border_radius=2)
            pygame.draw.line(screen, (30, 28, 38), (tx - 6, ty + 20), (tx + 6, ty + 20), 2)

            # Cahaya hangat melingkar lembut
            glow = pygame.Surface((80, 80), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 170, 60, 35), (40, 40), 38)
            pygame.draw.circle(glow, (255, 210, 100, 55), (40, 40), 20)
            screen.blit(glow, (tx - 40, ty - 25))

            # Kobaran api obor
            screen.blit(flame, (tx - flame.get_width() // 2, ty))

    def _draw_boss_aura(self, screen: pygame.Surface, game):
        """Cahaya mistis lembut berdenyut di belakang Boss."""
        bx = config.BATTLE_BOSS_POS[0]
        by = config.BATTLE_BOSS_POS[1] - 90
        pulse = 0.5 + 0.5 * math.sin(game.time * 3.5)
        radius = int(85 + pulse * 18)
        alpha = int(45 + pulse * 25)

        aura = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(aura, (140, 40, 160, alpha), (radius, radius), radius)
        pygame.draw.circle(aura, (180, 50, 100, int(alpha * 0.7)), (radius, radius), int(radius * 0.65))
        screen.blit(aura, (bx - radius, by - radius))

    def _draw_ambient_dust(self, screen: pygame.Surface):
        """Partikel debu/abu melayang di udara arena."""
        for d in self.ambient_dust:
            dust_surf = pygame.Surface((int(d["radius"] * 2), int(d["radius"] * 2)), pygame.SRCALPHA)
            pygame.draw.circle(dust_surf, (220, 210, 240, int(d["alpha"])),
                               (int(d["radius"]), int(d["radius"])), int(d["radius"]))
            screen.blit(dust_surf, (int(d["x"]), int(d["y"])))

    def _draw_turn_pill(self, screen: pygame.Surface, battle):
        pill_rect = pygame.Rect(config.BATTLE_TURN_PILL_RECT)
        phase = battle.get("phase", "HERO")
        is_player = (phase == "HERO")

        border_col = config.YELLOW if is_player else config.RED
        bg_col = (32, 28, 18, 235) if is_player else (38, 16, 18, 235)
        label = "GILIRANMU (PILIH AKSI)" if is_player else "BOSS BERPIKIR (MINIMAX)..."

        pill_surf = pygame.Surface((pill_rect.w, pill_rect.h), pygame.SRCALPHA)
        pygame.draw.rect(pill_surf, bg_col, (0, 0, pill_rect.w, pill_rect.h), border_radius=12)
        pygame.draw.rect(pill_surf, border_col, (0, 0, pill_rect.w, pill_rect.h), 2, border_radius=12)
        screen.blit(pill_surf, pill_rect.topleft)

        w = self.font_head.size(label)[0]
        text_col = config.YELLOW if is_player else config.WHITE
        screen.blit(self._txt(label, text_col, self.font_head),
                    (pill_rect.centerx - w // 2, pill_rect.centery - 8))

    def _draw_hero_sprite(self, screen: pygame.Surface, game, x: float, y: float):
        # Pilih daftar frame animasi Hero
        if self.anim_state in ("HERO_LUNGE", "HERO_SLASH") and self.loader.hero_attack:
            frames = self.loader.hero_attack
            fps = 10.0
        elif self.anim_state == "HERO_HIT" and self.loader.hero_hurt:
            frames = self.loader.hero_hurt
            fps = 8.0
        else:
            frames = self.loader.hero_idle
            fps = 9.0  # Animasi idle 8-10 FPS

        if frames:
            idx = int(game.time * fps) % len(frames)
            spr = frames[idx]
            # Offset anchor kaki Hero: (28 * scale, 34 * scale) = (196, 238)
            ox = self.loader.hero_anchor[0] * self.loader.hero_scale
            oy = self.loader.hero_anchor[1] * self.loader.hero_scale
            pos = (int(x - ox), int(y - oy))
            screen.blit(spr, pos)

            # Hit flash effect (silhouette mask agar tidak ada kotak alpha)
            if self.hero_flash > 0.0:
                mask = pygame.mask.from_surface(spr)
                alpha = int(220 * min(1.0, self.hero_flash * 4))
                flash_surf = mask.to_surface(setcolor=(255, 255, 255, alpha), unsetcolor=(0, 0, 0, 0))
                screen.blit(flash_surf, pos)

    def _draw_boss_sprite(self, screen: pygame.Surface, game, x: float, y: float):
        # Pilih daftar frame animasi Boss
        if self.anim_state in ("BOSS_LUNGE", "BOSS_STRIKE") and self.loader.boss_attack:
            frames = self.loader.boss_attack
            fps = 10.0
        elif self.anim_state == "BOSS_HIT" and self.loader.boss_hurt:
            frames = self.loader.boss_hurt
            fps = 8.0
        else:
            frames = self.loader.boss_idle
            fps = 9.0  # Animasi idle 8-10 FPS

        if frames:
            idx = int(game.time * fps) % len(frames)
            spr = frames[idx]
            # Offset anchor kaki Boss (sudah di-flip): (32 * scale, 32 * scale) = (256, 256)
            ox = (56 - self.loader.boss_anchor[0]) * self.loader.boss_scale
            oy = self.loader.boss_anchor[1] * self.loader.boss_scale
            pos = (int(x - ox), int(y - oy))
            screen.blit(spr, pos)

            # Hit flash effect (silhouette mask agar tidak ada kotak alpha)
            if self.boss_flash > 0.0:
                mask = pygame.mask.from_surface(spr)
                alpha = int(220 * min(1.0, self.boss_flash * 4))
                flash_surf = mask.to_surface(setcolor=(255, 255, 255, alpha), unsetcolor=(0, 0, 0, 0))
                screen.blit(flash_surf, pos)

    def _draw_slash_vfx(self, screen: pygame.Surface, x: float, y: float, is_boss: bool = False):
        """Gambar tebasan dinamis melengkung (crescent arc) + hit impact spark (spr_deco_glint_02_strip4)."""
        progress = max(0.0, min(1.0, (0.20 - self.slash_vfx_timer) / 0.20))

        # 1. Busur tebasan dinamis melengkung tajam (Dynamic Crescent Slash Arc)
        arc_surf = pygame.Surface((130, 130), pygame.SRCALPHA)
        core_col = (255, 255, 255, int(240 * (1.0 - progress)))
        edge_col = (232, 184, 74, int(210 * (1.0 - progress))) if not is_boss else (235, 45, 55, int(210 * (1.0 - progress)))

        start_angle = math.pi * 0.15 if not is_boss else math.pi * 0.85
        sweep = math.pi * 0.75 * progress
        rect = pygame.Rect(12, 12, 106, 106)
        pygame.draw.arc(arc_surf, edge_col, rect, start_angle, start_angle + sweep, 6)
        pygame.draw.arc(arc_surf, core_col, pygame.Rect(16, 16, 98, 98), start_angle + 0.08, start_angle + sweep, 3)
        screen.blit(arc_surf, (int(x - 65), int(y - 65)))

        # 2. Hit impact spark frames dari Sunnyside (spr_deco_glint_02_strip4.png)
        if self.loader.spark_frames:
            spark_idx = min(len(self.loader.spark_frames) - 1, int(progress * len(self.loader.spark_frames)))
            spark_img = self.loader.spark_frames[spark_idx]
            screen.blit(spark_img, (int(x - spark_img.get_width() // 2), int(y - spark_img.get_height() // 2)))

    def _draw_glint_vfx(self, screen: pygame.Surface, x: float, y: float):
        """Gambar kilatan lembut naik (spr_deco_glint_01_strip6) khusus untuk efek pemulihan POTION dan HEAL."""
        if not self.loader.glint_frames:
            return
        progress = max(0.0, min(1.0, (0.35 - self.glint_vfx_timer) / 0.35))
        frame_idx = min(len(self.loader.glint_frames) - 1, int(progress * len(self.loader.glint_frames)))
        glint_img = self.loader.glint_frames[frame_idx]
        lift = progress * 24.0
        screen.blit(glint_img, (int(x - glint_img.get_width() // 2), int(y - lift - glint_img.get_height() // 2)))

    def _draw_telegraph_vfx(self, screen: pygame.Surface, x: float, y: float):
        """Peringatan kilau merah '!' sebelum serangan berat Boss."""
        self._txt_outlined(screen, "!", x - 8, y, config.RED, font=self.font_title)

    # ------------------------------------------------------------------ ZONA 2: HP BARS
    def _draw_hp_bars(self, screen: pygame.Surface, state):
        # 1. HERO HP BAR
        hero_rect = pygame.Rect(config.BATTLE_HERO_HP_RECT)
        self._draw_single_hp_bar(
            screen, hero_rect,
            name="HERO",
            hp=state.player_hp,
            max_hp=state.player_max_hp,
            bar_color=config.GREEN,
            is_defending=state.player_defending,
            defend_pct="60%",
            subtext=f"Potions: x{state.potion_count}"
        )

        # 2. BOSS HP BAR
        boss_rect = pygame.Rect(config.BATTLE_BOSS_HP_RECT)
        self._draw_single_hp_bar(
            screen, boss_rect,
            name="BOSS",
            hp=state.boss_hp,
            max_hp=state.boss_max_hp,
            bar_color=config.PINK,
            is_defending=state.boss_defending,
            defend_pct="50%",
            subtext=f"Heal: x{state.boss_heal_count}  |  Heavy cd: {state.boss_heavy_cd}"
        )

    def _draw_single_hp_bar(self, screen: pygame.Surface, rect: pygame.Rect,
                            name: str, hp: int, max_hp: int, bar_color: tuple,
                            is_defending: bool, defend_pct: str, subtext: str):
        # Latar & Frame Bar HP
        pygame.draw.rect(screen, (20, 20, 28), rect, border_radius=4)
        frac = max(0.0, min(1.0, hp / max(1, max_hp)))
        fill_w = int(rect.w * frac)
        if fill_w > 0:
            fill_rect = pygame.Rect(rect.x, rect.y, fill_w, rect.h)
            pygame.draw.rect(screen, bar_color, fill_rect, border_radius=4)
        pygame.draw.rect(screen, (85, 85, 105), rect, 1, border_radius=4)

        # Sprite Bar HP Otentik Sunnyside (greenbar untuk Hero, redbar untuk Boss)
        cat = get_asset_catalog()
        bar_kind = "greenbar" if "HERO" in name.upper() else "redbar"
        bar_idx = max(0, min(6, int(round(frac * 6))))
        bar_sprite = cat.get_ui_icon(f"{bar_kind}_0{bar_idx}.png", scale=2)
        screen.blit(bar_sprite, (rect.x - 34, rect.y + 4))

        # Label nama & angka HP di dalam bar
        self._txt_outlined(screen, name, rect.x + 8, rect.y + 3, config.WHITE, font=self.font_head)
        hp_str = f"{max(0, hp)}/{max_hp}"
        w_val = self.font_head.size(hp_str)[0]
        self._txt_outlined(screen, hp_str, rect.right - w_val - 8, rect.y + 3, config.WHITE, font=self.font_head)

        # Badge perisai jika DEFEND aktif (di samping bar)
        if is_defending:
            shield_badge = pygame.Rect(rect.right + 6, rect.y - 1, 88, rect.h + 2)
            pygame.draw.rect(screen, (24, 48, 80), shield_badge, border_radius=5)
            pygame.draw.rect(screen, config.CYAN, shield_badge, 1, border_radius=5)
            screen.blit(self._txt(f"SHIELD -{defend_pct}", config.CYAN, self.font_small),
                        (shield_badge.x + 6, shield_badge.y + 4))

        # Sub-info kecil (Potion, Heal, Cooldown) ditaruh DI BAWAH bar, tidak menyentuh sprite
        if subtext:
            self._txt_outlined(screen, subtext, rect.x + 4, rect.bottom + 4, config.GREY, font=self.font_small)

    # ------------------------------------------------------------------ ZONA 3: MENU AKSI
    def _draw_action_menu(self, screen: pygame.Surface, state):
        panel_rect = pygame.Rect(config.BATTLE_MENU_RECT)

        # Drop shadow panel
        shadow_rect = panel_rect.move(4, 5)
        pygame.draw.rect(screen, (8, 8, 12), shadow_rect, border_radius=8)

        # Frame latar panel aksi
        pygame.draw.rect(screen, (20, 18, 28), panel_rect, border_radius=8)
        pygame.draw.rect(screen, (65, 65, 90), panel_rect, 2, border_radius=8)

        # Header panel aksi
        screen.blit(self._txt("MENU AKSI PLAYER", config.YELLOW, self.font_title),
                    (panel_rect.x + 16, panel_rect.y + 10))

        # 3 Tombol Aksi
        weapon_name = "Pedang"
        atk_min = config.HERO_ATTACK_DMG[0]
        atk_max = config.HERO_ATTACK_DMG[1]
        if hasattr(state, "loadout") and state.loadout:
            w_item = state.loadout.get("WEAPON")
            if w_item and w_item != "Kosong":
                weapon_name = w_item
        atk_bonus = getattr(state, "hero_attack_bonus", 0)
        atk_min += atk_bonus
        atk_max += atk_bonus
        atk_avg = (atk_min + atk_max) // 2

        buttons_info = [
            (pygame.Rect(config.BATTLE_BUTTON_1_RECT), "1", "ATTACK", weapon_name, True,
             f"Serang musuh dengan {weapon_name} ({atk_min}-{atk_max} DMG, rata-rata {atk_avg})",
             "Tanpa biaya, menghasilkan damage langsung"),
            (pygame.Rect(config.BATTLE_BUTTON_2_RECT), "2", f"POTION  x{state.potion_count}", "Ramuan", state.potion_count > 0,
             f"Pulihkan +{config.HERO_POTION_HEAL} HP segera (tersisa {state.potion_count} botol)",
             "Memulihkan HP Hero, dibatasi maksimal 3 botol"),
            (pygame.Rect(config.BATTLE_BUTTON_3_RECT), "3", "DEFEND", "Perisai", True,
             f"Pasang kuda-kuda bertahan (kurangi {int(config.HERO_DEFEND_REDUCE * 100)}% damage serangan lawan)",
             "Berlaku untuk 1 giliran lawan berikutnya"),
        ]

        active_desc = ""
        active_subdesc = ""
        for i, (b_rect, key_str, label, icon_name, is_enabled, desc, subdesc) in enumerate(buttons_info):
            is_selected = (self.selected_action_index == i)
            is_hovered = (self.hovered_action_index == i)

            # Warna & State Tombol
            if not is_enabled:
                bg_col = (28, 28, 34)
                border_col = (55, 55, 65)
                text_col = (110, 110, 120)
            elif is_selected:
                bg_col = (42, 50, 72)
                border_col = config.YELLOW
                text_col = config.YELLOW
                active_desc = desc
                active_subdesc = subdesc
            elif is_hovered:
                bg_col = (34, 40, 56)
                border_col = config.CYAN
                text_col = config.WHITE
            else:
                bg_col = (26, 26, 38)
                border_col = (70, 70, 95)
                text_col = config.WHITE

            pygame.draw.rect(screen, bg_col, b_rect, border_radius=6)
            pygame.draw.rect(screen, border_col, b_rect, 2 if (is_selected or is_hovered) else 1, border_radius=6)

            # Shortcut Tag: [1], [2], [3]
            tag_box = pygame.Rect(b_rect.x + 10, b_rect.y + 9, 30, 30)
            pygame.draw.rect(screen, (16, 16, 24), tag_box, border_radius=4)
            pygame.draw.rect(screen, border_col, tag_box, 1, border_radius=4)
            tag_surf = self._txt(f"[{key_str}]", text_col, self.font_body)
            screen.blit(tag_surf, (tag_box.centerx - tag_surf.get_width() // 2, tag_box.centery - 7))

            # Icon visual
            icon_x = b_rect.x + 50
            if icon_name == "Pedang":
                pygame.draw.line(screen, text_col, (icon_x + 4, b_rect.centery + 10), (icon_x + 18, b_rect.centery - 10), 3)
                pygame.draw.line(screen, text_col, (icon_x + 6, b_rect.centery + 4), (icon_x + 12, b_rect.centery + 10), 2)
            elif icon_name == "Ramuan":
                pygame.draw.rect(screen, text_col, (icon_x + 6, b_rect.centery - 6, 12, 16), border_radius=3)
                pygame.draw.rect(screen, text_col, (icon_x + 9, b_rect.centery - 11, 6, 5))
            elif icon_name == "Perisai":
                pygame.draw.polygon(screen, text_col, [
                    (icon_x + 4, b_rect.centery - 10),
                    (icon_x + 20, b_rect.centery - 10),
                    (icon_x + 20, b_rect.centery + 2),
                    (icon_x + 12, b_rect.centery + 12),
                    (icon_x + 4, b_rect.centery + 2)
                ], 2)

            # Nama Aksi
            screen.blit(self._txt(label, text_col, self.font_head),
                        (b_rect.x + 82, b_rect.centery - 8))

            # Status Disabled / Selected
            if not is_enabled:
                screen.blit(self._txt("(HABIS)", config.RED, self.font_small),
                            (b_rect.right - 70, b_rect.centery - 7))
            elif is_selected:
                screen.blit(self._txt("< ENTER >", config.YELLOW, self.font_small),
                            (b_rect.right - 84, b_rect.centery - 7))

        # Deskripsi 2 baris kontras tinggi
        desc_rect = pygame.Rect(config.BATTLE_DESC_RECT)
        pygame.draw.rect(screen, (14, 14, 22), desc_rect, border_radius=6)
        pygame.draw.rect(screen, (50, 50, 70), desc_rect, 1, border_radius=6)
        if active_desc:
            screen.blit(self._txt(active_desc, config.CYAN, self.font_body),
                        (desc_rect.x + 10, desc_rect.y + 8))
            screen.blit(self._txt(active_subdesc, config.WHITE, self.font_small),
                        (desc_rect.x + 10, desc_rect.y + 30))

        # Hint Kontrol (min 14 px, kontras tinggi)
        hint_rect = pygame.Rect(config.BATTLE_HINT_RECT)
        hint_str = "[1/2/3] Tombol Angka  |  [<- / ->] Pilih Aksi  |  [Enter / Klik] Eksekusi"
        screen.blit(self._txt(hint_str, config.GREY, self.font_small),
                    (hint_rect.x + 6, hint_rect.y + 4))

    # ------------------------------------------------------------------ ZONA 4: BATTLE LOG
    def _draw_battle_log(self, screen: pygame.Surface, battle, state):
        panel_rect = pygame.Rect(config.BATTLE_LOG_RECT)

        # Drop shadow panel
        shadow_rect = panel_rect.move(4, 5)
        pygame.draw.rect(screen, (8, 8, 12), shadow_rect, border_radius=8)

        pygame.draw.rect(screen, (20, 18, 28), panel_rect, border_radius=8)
        pygame.draw.rect(screen, (65, 65, 90), panel_rect, 2, border_radius=8)

        # Header Log & Status Summary Icons
        screen.blit(self._txt("BATTLE LOG", config.GREEN, self.font_title),
                    (panel_rect.x + 16, panel_rect.y + 10))

        # Summary Icons status bar di header
        status_summary = f"Ronde: {state.turn_number}/{config.BATTLE_MAX_TURNS}  |  P:{state.potion_count}  CD:{state.boss_heavy_cd}  H:{state.boss_heal_count}"
        screen.blit(self._txt(status_summary, config.GOLD, self.font_small),
                    (panel_rect.right - 210, panel_rect.y + 14))

        # Tampilkan 4-5 baris terakhir dengan tinggi baris seragam (44 px)
        lines = list(battle.get("log", []))[-5:]
        y = panel_rect.y + 42

        for line in lines:
            line_box = pygame.Rect(panel_rect.x + 12, y, panel_rect.w - 24, 46)
            pygame.draw.rect(screen, (24, 22, 34), line_box, border_radius=6)
            pygame.draw.rect(screen, (45, 42, 60), line_box, 1, border_radius=6)

            # Strip warna di kiri
            if "Boss" in line or "BOSS" in line:
                indicator_col = config.RED
            elif "Hero" in line or "POTION" in line:
                indicator_col = config.YELLOW
            else:
                indicator_col = config.CYAN

            pygame.draw.rect(screen, indicator_col, (line_box.x, line_box.y, 4, line_box.h),
                             border_top_left_radius=6, border_bottom_left_radius=6)

            if len(line) > 52:
                line_display = line[:49] + "..."
            else:
                line_display = line

            text_color = config.WHITE
            if "HP" in line and ("-" in line or "Attack" in line):
                text_color = (255, 140, 140)
            elif "POTION" in line or "Pulih" in line or "HEAL" in line:
                text_color = (130, 255, 150)
            elif "DEFEND" in line or "tahan" in line or "menahan" in line:
                text_color = (130, 210, 255)

            self._txt_outlined(screen, line_display, line_box.x + 12, line_box.centery - 7, text_color, font=self.font_body)
            y += 52

    # ------------------------------------------------------------------ ZONA 5: PANEL AI THINKING (F3)
    def _draw_ai_panel(self, screen: pygame.Surface, game):
        panel_rect = pygame.Rect(config.BATTLE_AI_PANEL_RECT)

        # Latar panel AI
        panel_surf = pygame.Surface((panel_rect.w, panel_rect.h), pygame.SRCALPHA)
        panel_surf.fill((16, 18, 30, 245))
        screen.blit(panel_surf, panel_rect.topleft)
        pygame.draw.rect(screen, config.CYAN, panel_rect, 2, border_radius=8)

        screen.blit(self._txt("AI ADVERSARIAL THINKING [F3]", config.CYAN, self.font_head),
                    (panel_rect.x + 10, panel_rect.y + 6))

        ai = game.battle_ai
        st = ai.last_stats

        info_1 = f"Depth: {st.depth}  |  Nodes: {st.nodes}  |  Pruned: {st.pruned}"
        info_2 = f"Waktu: {st.elapsed_ms:.1f} ms  |  Alpha: {st.alpha}  |  Beta: {st.beta}"
        screen.blit(self._txt(info_1, config.WHITE, self.font_small), (panel_rect.x + 10, panel_rect.y + 26))
        screen.blit(self._txt(info_2, config.GREY, self.font_small), (panel_rect.x + 10, panel_rect.y + 40))

        pygame.draw.line(screen, (50, 60, 90), (panel_rect.x + 8, panel_rect.y + 56),
                         (panel_rect.right - 8, panel_rect.y + 56), 1)

        y = panel_rect.y + 62
        candidates = getattr(st, "candidates", [])
        if not candidates and ai.last_root_children:
            candidates = [{"action": it[0], "score": it[1], "chosen": (it[0] == st.best_action)}
                          for it in ai.last_root_children]

        for item in candidates[:3]:
            act = item.get("action", "-")
            score = item.get("score", 0)
            is_chosen = item.get("chosen", False)

            row_rect = pygame.Rect(panel_rect.x + 8, y - 2, panel_rect.w - 16, 20)
            if is_chosen:
                pygame.draw.rect(screen, (40, 50, 75), row_rect, border_radius=4)
                pygame.draw.rect(screen, config.GOLD, row_rect, 1, border_radius=4)
                arrow = "> "
                act_col = config.GOLD
            else:
                arrow = "  "
                act_col = config.WHITE

            screen.blit(self._txt(f"{arrow}{act}", act_col, self.font_small),
                        (panel_rect.x + 12, y))

            score_col = config.GREEN if score >= 0 else config.RED
            score_surf = self._txt(f"{score:+d}", score_col, self.font_small)
            screen.blit(score_surf, (panel_rect.right - 35 - score_surf.get_width(), y))

            y += 22

    # ------------------------------------------------------------------ FLOATING TEXT & PARTICLES
    def _draw_effects(self, screen: pygame.Surface):
        for p in self.particles:
            alpha = max(0, min(255, int(255 * (p["timer"] / p["duration"]))))
            r, g, b = p["color"][:3]
            part_surf = pygame.Surface((int(p["radius"] * 2), int(p["radius"] * 2)), pygame.SRCALPHA)
            pygame.draw.circle(part_surf, (r, g, b, alpha), (int(p["radius"]), int(p["radius"])), int(p["radius"]))
            screen.blit(part_surf, (int(p["x"] - p["radius"]), int(p["y"] - p["radius"])))

        for ft in self.floating_texts:
            self._txt_outlined(screen, ft["text"], int(ft["x"]), int(ft["y"]), ft["color"], font=self.font_head)

    # ------------------------------------------------------------------ INPUT HANDLING MENU
    def handle_mouse_motion(self, pos: tuple):
        b1 = pygame.Rect(config.BATTLE_BUTTON_1_RECT)
        b2 = pygame.Rect(config.BATTLE_BUTTON_2_RECT)
        b3 = pygame.Rect(config.BATTLE_BUTTON_3_RECT)

        if b1.collidepoint(pos):
            self.hovered_action_index = 0
        elif b2.collidepoint(pos):
            self.hovered_action_index = 1
        elif b3.collidepoint(pos):
            self.hovered_action_index = 2
        else:
            self.hovered_action_index = -1

    def handle_mouse_click(self, pos: tuple, state) -> str:
        b1 = pygame.Rect(config.BATTLE_BUTTON_1_RECT)
        b2 = pygame.Rect(config.BATTLE_BUTTON_2_RECT)
        b3 = pygame.Rect(config.BATTLE_BUTTON_3_RECT)

        if b1.collidepoint(pos):
            self.selected_action_index = 0
            return "ATTACK"
        elif b2.collidepoint(pos):
            self.selected_action_index = 1
            if state.potion_count > 0:
                return "POTION"
        elif b3.collidepoint(pos):
            self.selected_action_index = 2
            return "DEFEND"
        return None

    def navigate_menu(self, direction: int, state):
        self.selected_action_index = (self.selected_action_index + direction) % 3

    def get_selected_action(self, state) -> str:
        actions = ["ATTACK", "POTION", "DEFEND"]
        act = actions[self.selected_action_index]
        if act == "POTION" and state.potion_count <= 0:
            return None
        return act

    # ------------------------------------------------------------- GAME OVER
    def draw_game_over(self, screen: pygame.Surface, game):
        """Layar akhir permainan (kalah/menang) + opsi respawn/restart."""
        veil = pygame.Surface(config.WINDOW_SIZE, pygame.SRCALPHA)
        veil.fill((0, 0, 0, 210))
        screen.blit(veil, (0, 0))

        win = (game.game_over == "HERO")
        title = "HERO VICTORY - BOSS DIKALAHKAN!" if win else "GAME OVER - HERO TEWAS"
        color = config.GOLD if win else config.RED
        surf = self._txt(title, color, self.font_title)
        screen.blit(surf, surf.get_rect(center=(config.WINDOW_SIZE[0] // 2,
                                                config.WINDOW_SIZE[1] // 2 - 45)))
        msg = ("Hero berhasil menaklukkan Skeleton Overlord dan mengamankan Core!"
               if win else
               "Hero gugur di tangan Boss. Tekan [R] untuk respawn di alun-alun desa.")
        surf = self._txt(msg, config.WHITE, self.font_body)
        screen.blit(surf, surf.get_rect(center=(config.WINDOW_SIZE[0] // 2,
                                                config.WINDOW_SIZE[1] // 2)))
        hint = "Tekan [R] untuk respawn di desa  |  [N] level baru  |  [ESC] keluar"
        surf = self._txt(hint, config.CYAN, self.font_small)
        screen.blit(surf, surf.get_rect(center=(config.WINDOW_SIZE[0] // 2,
                                                config.WINDOW_SIZE[1] // 2 + 45)))
