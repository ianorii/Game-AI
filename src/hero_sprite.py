"""
hero_sprite.py - Satu Sumber Terpadu Sprite Hero (Dunia & Battle Mode)

Membangun sprite Hero secara modular dari multi-layer Sunnyside World:
  1. Base   : Tubuh manusia (kulit, pakaian)
  2. Hair   : Rambut karakter (warna & gaya dari config)
  3. Tools  : Senjata / peralatan (opsional, mis. pedang saat serangan)

Fitur:
  - Urutan layer presisi: base -> hair -> tools
  - Koordinat native pixel-perfect (96x64 per frame) disatukan sebelum crop/scale
  - Satu sumber untuk Dunia (skala 2x canvas 48x48) & Battle (skala 7x arena)
  - Caching agresif: frame hanya digabung sekali di memori (menjaga 60 FPS)
  - Fallback aman: jika file hair hilang, log peringatan & tampil tanpa crash
"""

import os
import re
import pygame
import config


class HeroSpriteManager:
    """Manajer & Builder Tunggal Sprite Hero dari Sunnyside World."""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.human_dir = os.path.join(config.SUNNYSIDE_DIR, "Characters", "Human")
        self.hair_style = getattr(config, "HERO_HAIR_STYLE", "spikeyhair")
        self.hair_color = getattr(config, "HERO_HAIR_COLOR", (228, 59, 68))

        # Cache frame per animasi agar tidak digabung ulang setiap game loop
        self._cache_raw = {}
        self._cache_world = {}
        self._cache_battle = {}

        # Definisi animasi standar Sunnyside
        self.anim_defs = {
            "idle": {
                "folder": "IDLE", "base": "base_idle_strip9.png",
                "hair": "{style}_idle_strip9.png", "tools": None, "count": 9,
                "alt_folder": "WAITING", "alt_base": "base_waiting_strip9.png",
                "alt_hair": "{style}_waiting_strip9.png"
            },
            "walk": {
                "folder": "WALKING", "base": "base_walk_strip8.png",
                "hair": "{style}_walk_strip8.png", "tools": None, "count": 8,
                "alt_folder": "RUN", "alt_base": "base_run_strip8.png",
                "alt_hair": "{style}_run_strip8.png"
            },
            "run": {
                "folder": "RUN", "base": "base_run_strip8.png",
                "hair": "{style}_run_strip8.png", "tools": None, "count": 8,
                "alt_folder": "WALKING", "alt_base": "base_walk_strip8.png",
                "alt_hair": "{style}_walk_strip8.png"
            },
            "attack": {
                "folder": "ATTACK", "base": "base_attack_strip10.png",
                "hair": "{style}_attack_strip10.png", "tools": "tools_attack_strip10.png", "count": 10
            },
            "hurt": {
                "folder": "HURT", "base": "base_hurt_strip8.png",
                "hair": "{style}_hurt_strip8.png", "tools": None, "count": 8
            },
            "casting": {
                "folder": "CASTING", "base": "base_casting_strip15.png",
                "hair": "{style}_casting_strip15.png", "tools": None, "count": 15
            },
            "waiting": {
                "folder": "WAITING", "base": "base_waiting_strip9.png",
                "hair": "{style}_waiting_strip9.png", "tools": None, "count": 9
            },
            "death": {
                "folder": "DEATH", "base": "base_death_strip13.png",
                "hair": "{style}_death_strip13.png", "tools": None, "count": 13
            },
            "axe": {
                "folder": "AXE", "base": "base_axe_strip10.png",
                "hair": "{style}_axe_strip10.png", "tools": "tools_axe_strip10.png", "count": 10
            },
            "mining": {
                "folder": "MINING", "base": "base_mining_strip10.png",
                "hair": "{style}_mining_strip10.png", "tools": "tools_mining_strip10.png", "count": 10
            },
            "reeling": {
                "folder": "REELING", "base": "base_reeling_strip13.png",
                "hair": "{style}_reeling_strip13.png", "tools": "tools_reeling_strip13.png", "count": 13
            },
            "caught": {
                "folder": "CAUGHT", "base": "base_caught_strip10.png",
                "hair": "{style}_caught_strip10.png", "tools": "tools_caught_strip10.png", "count": 10
            },
            "doing": {
                "folder": "DOING", "base": "base_doing_strip8.png",
                "hair": "{style}_doing_strip8.png", "tools": "tools_doing_strip8.png", "count": 8
            },
            "watering": {
                "folder": "WATERING", "base": "base_watering_strip5.png",
                "hair": "{style}_watering_strip5.png", "tools": "tools_watering_strip5.png", "count": 5
            },
        }

    def clear_cache(self):
        """Bersihkan cache frame bila konfigurasi gaya/warna rambut diubah saat runtime."""
        self._cache_raw.clear()
        self._cache_world.clear()
        self._cache_battle.clear()

    # ------------------------------------------------------------------ TINTING RAMBUT
    def _apply_hair_tint(self, hair_surface: pygame.Surface) -> pygame.Surface:
        """
        Terapkan warna kustom pada rambut.
        Bila warna adalah merah otentik Sunnyside (228, 59, 68) atau None,
        gunakan palet asli buatan artist tanpa modifikasi.
        """
        target = self.hair_color
        if target is None or target == (228, 59, 68):
            return hair_surface

        tinted = hair_surface.copy()
        w, h = tinted.get_size()
        tr, tg, tb = target[:3]
        for x in range(w):
            for y in range(h):
                c = tinted.get_at((x, y))
                if c.a > 0:
                    lum = 0.299 * c.r + 0.587 * c.g + 0.114 * c.b
                    if lum > 45:  # Lindungi garis tepi gelap (outline)
                        factor = lum / 255.0
                        nr = min(255, int(tr * factor * 1.3))
                        ng = min(255, int(tg * factor * 1.3))
                        nb = min(255, int(tb * factor * 1.3))
                        tinted.set_at((x, y), (nr, ng, nb, c.a))
        return tinted

    # ------------------------------------------------------------------ KOMPOSISI MENTAH (NATIVE 96x64)
    def get_raw_composite(self, action: str) -> list:
        """
        Bangun frame gabungan native (96x64 per frame) dengan urutan:
        base -> hair -> tools.
        """
        cache_key = (action, self.hair_style, self.hair_color)
        if cache_key in self._cache_raw:
            return self._cache_raw[cache_key]

        adef = self.anim_defs.get(action.lower())
        if not adef:
            print(f"[PERINGATAN HERO SPRITE] Animasi '{action}' tidak dikenali!")
            return [self._make_placeholder((96, 64), (220, 80, 80))]

        # Jalur file primer
        folder = adef["folder"]
        count = adef["count"]
        base_name = adef["base"]
        hair_name = adef["hair"].format(style=self.hair_style)
        tools_name = adef.get("tools")

        base_path = os.path.join(self.human_dir, folder, base_name)
        hair_path = os.path.join(self.human_dir, folder, hair_name)
        tools_path = os.path.join(self.human_dir, folder, tools_name) if tools_name else None

        # Cek fallback jalur alternatif (mis. WAITING bila IDLE tidak ada)
        if not os.path.exists(base_path) and "alt_folder" in adef:
            folder = adef["alt_folder"]
            base_path = os.path.join(self.human_dir, folder, adef["alt_base"])
            hair_path = os.path.join(self.human_dir, folder, adef["alt_hair"].format(style=self.hair_style))

        # Muat Strip Base (Wajib)
        if not os.path.exists(base_path):
            print(f"[PERINGATAN HERO SPRITE] File base tidak ditemukan: '{base_path}'! Menggunakan placeholder.")
            return [self._make_placeholder((96, 64), (220, 80, 80))]

        try:
            base_sheet = pygame.image.load(base_path)
            w, h = base_sheet.get_size()
            fw = w // count
        except Exception as e:
            print(f"[PERINGATAN HERO SPRITE] Gagal membaca base strip '{base_path}': {e}")
            return [self._make_placeholder((96, 64), (220, 80, 80))]

        # Muat Strip Hair (Opsional dengan fallback aman)
        hair_sheet = None
        if os.path.exists(hair_path):
            try:
                raw_hair = pygame.image.load(hair_path)
                hair_sheet = self._apply_hair_tint(raw_hair)
            except Exception as e:
                print(f"[PERINGATAN HERO SPRITE] Gagal memproses hair strip '{hair_path}': {e}")
                hair_sheet = None
        else:
            print(f"[PERINGATAN HERO SPRITE] File hair tidak ditemukan: '{hair_path}'! Menampilkan hero base tanpa hair.")

        # Muat Strip Tools (Opsional, mis. senjata)
        tools_sheet = None
        if tools_path and os.path.exists(tools_path):
            try:
                tools_sheet = pygame.image.load(tools_path)
            except Exception as e:
                print(f"[PERINGATAN HERO SPRITE] Gagal memuat tools strip '{tools_path}': {e}")
                tools_sheet = None

        # Komposisi layer per frame secara sinkron
        composite_frames = []
        for i in range(count):
            frame_rect = (i * fw, 0, fw, h)
            frame_surf = pygame.Surface((fw, h), pygame.SRCALPHA)

            # 1. Base Layer
            frame_surf.blit(base_sheet.subsurface(frame_rect), (0, 0))

            # 2. Hair Layer (sinkron per frame index)
            if hair_sheet is not None:
                frame_surf.blit(hair_sheet.subsurface(frame_rect), (0, 0))

            # 3. Tools Layer (sinkron per frame index)
            if tools_sheet is not None:
                frame_surf.blit(tools_sheet.subsurface(frame_rect), (0, 0))

            if pygame.display.get_surface() is not None:
                composite_frames.append(frame_surf.convert_alpha())
            else:
                composite_frames.append(frame_surf)

        layer_info = f"base + {self.hair_style}"
        if tools_sheet is not None:
            layer_info += " + tools"
        if getattr(config, "VERBOSE_SPRITE_LOGS", True):
            print(f"[HERO SPRITE] Komposisi siap: {action.upper()} ({layer_info}) | {count} frame | Per frame: ({fw}, {h})")

        self._cache_raw[cache_key] = composite_frames
        return composite_frames

    # ------------------------------------------------------------------ FRAME DUNIA
    def get_world_frames(self, action: str, target_size=(48, 48)) -> list:
        """
        Mengembalikan daftar frame Hero untuk dunia eksplorasi.
        Untuk animasi standar (idle, walk, run), ukuran default adalah (48, 48)
        dengan anchor kaki tepat pada (24, 42).
        Untuk animasi serangan ('attack'), kanvas diperlebar menjadi (193, 96)
        dengan anchor kaki di (96, 90) agar seluruh jangkauan tebasan pedang
        dan efek slash melengkung otentik Sunnyside World terlihat utuh
        tanpa terpotong (zero-clipping), serta simetris sempurna saat di-flip horizontal.
        """
        cache_key = (action, self.hair_style, self.hair_color, target_size)
        if cache_key in self._cache_world:
            return self._cache_world[cache_key]

        raw_frames = self.get_raw_composite(action)

        if action.lower() == "attack":
            # Animasi ayunan serangan memerlukan kanvas lebar (native x: 26..90 -> skala 2x: 52..180).
            # Titik kaki native Hero (48, 39) skala 2x adalah (96, 78).
            # Kanvas (193, 96) menempatkan kaki di (96, 90) [H - 6]:
            # blit dilakukan dengan offset (0, 12).
            # Lebar 193 (ganjil) menjamin flip horizontal sempurna: 193 - 1 - 96 = 96 (tanpa pergeseran 1px).
            canvas_size = (193, 96)
            offset_x = 0
            offset_y = 12
        else:
            canvas_size = target_size
            tw, th = target_size
            offset_x = (tw // 2) - 96
            offset_y = (th - 6) - 78

        world_frames = []
        for raw_f in raw_frames:
            scaled_2x = pygame.transform.scale(raw_f, (raw_f.get_width() * 2, raw_f.get_height() * 2))
            canvas = pygame.Surface(canvas_size, pygame.SRCALPHA)
            canvas.blit(scaled_2x, (offset_x, offset_y))

            if pygame.display.get_surface() is not None:
                world_frames.append(canvas.convert_alpha())
            else:
                world_frames.append(canvas)

        self._cache_world[cache_key] = world_frames
        return world_frames

    def get_npc_world_frames(self, action: str = "idle", hair_style: str = "curly",
                             hair_color: Optional[Tuple[int, int, int]] = None,
                             target_size=(48, 48)) -> list:
        """
        Menghasilkan frame animasi warga desa (NPC) dengan gaya dan warna rambut berbeda dari Hero.
        Mendukung variasi: curlyhair, mophair, bowlhair, longhair, shorthair.
        """
        style_key = hair_style if hair_style.endswith("hair") else f"{hair_style}hair"
        cache_key = ("npc", action, style_key, hair_color, target_size)
        if cache_key in self._cache_world:
            return self._cache_world[cache_key]

        old_style = self.hair_style
        old_color = self.hair_color
        try:
            self.hair_style = style_key
            self.hair_color = hair_color or (170, 120, 65)  # Warna rambut cokelat/pirang desa
            frames = self.get_world_frames(action, target_size=target_size)
            self._cache_world[cache_key] = frames
            return frames
        finally:
            self.hair_style = old_style
            self.hair_color = old_color

    # ------------------------------------------------------------------ FRAME BATTLE (CROP & INTEGER SCALE)
    def get_battle_frames(self, action: str, scale: int = 7,
                          crop_box: tuple = (34, 18, 28, 34)) -> list:
        """
        Mengembalikan daftar frame Hero untuk Battle Mode:
        Dipangkas ke crop_box (28x34) lalu diskalakan integer nearest-neighbor
        ke ukuran arena (mis. 7x -> 196x238).
        """
        cache_key = (action, self.hair_style, self.hair_color, scale, crop_box)
        if cache_key in self._cache_battle:
            return self._cache_battle[cache_key]

        raw_frames = self.get_raw_composite(action)
        cx, cy, cw, ch = crop_box
        dest_size = (cw * scale, ch * scale)

        battle_frames = []
        for raw_f in raw_frames:
            cropped = raw_f.subsurface((cx, cy, cw, ch))
            scaled = pygame.transform.scale(cropped, dest_size)
            if pygame.display.get_surface() is not None:
                battle_frames.append(scaled.convert_alpha())
            else:
                battle_frames.append(scaled)

        self._cache_battle[cache_key] = battle_frames
        return battle_frames

    def _make_placeholder(self, size: tuple, color: tuple) -> pygame.Surface:
        surf = pygame.Surface(size, pygame.SRCALPHA)
        surf.fill(color)
        return surf


def get_hero_sprite_manager() -> HeroSpriteManager:
    """Akses fungsi singleton HeroSpriteManager."""
    return HeroSpriteManager.get_instance()

