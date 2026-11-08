"""
asset_loader.py - Modul pemuat aset game (folder + slicing atlas Sunnyside)

Struktur aset (Sunnyside World Asset Pack V2.1):
    assets/
    ├── tilesets/sunnyside_world.png    # atlas utama 1280x1280 (64x64 sel)
    ├── tilesets/sunnyside_forest.png   # atlas hutan (autotile kanopi)
    ├── sprites/hero/                   # hero_idle / hero_run / hero_attack / ...
    ├── sprites/monsters/               # zombie_*, ice_zombie_*, big_demon_*
    ├── props/                          # pohon, jamur, hewan, batu, peti
    └── vfx/                            # api, kilau, ikon hati

Fitur:
  1. load_folder_sprites()   : membaca SEMUA file .png dalam folder (natural sort).
  2. load_animation_groups() : mengelompokkan PNG menjadi animasi per nama.
  3. TileSheet               : pemotong atlas dengan dukungan pitch/inset
                               (sel 20 px, konten 16 px dimulai 2 px dari tepi).
  4. FALLBACK                : file hilang -> placeholder berwarna (anti-crash).

Catatan seni:
  * Karakter Sunnyside adalah strip satu arah. Semua arah gerak memakai frame
    yang sama; arah kiri dicerminkan saat render (lihat core/entity.py).
  * Hero/monster memakai kanvas 24 px -> diskalakan 48 px di layar.
  * Boss memakai kanvas yang sama -> diskalakan 72 px agar terbaca lebih besar.
"""

import glob
import os
import re

import pygame

import config
from hero_sprite import get_hero_sprite_manager
from core.world_art import WorldArt


# ==============================================================================
# UTILITAS DASAR
# ==============================================================================
def natural_key(name):
    """Kunci pengurutan alami: 'f2' < 'f10' (bukan urutan leksikografis)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def make_placeholder(color, size=(16, 16), label=None):
    """Rect berwarna sebagai pengganti aset yang hilang (anti-crash)."""
    surf = pygame.Surface(size, pygame.SRCALPHA)
    if pygame.display.get_surface() is not None:
        surf = surf.convert_alpha()
    surf.fill(tuple(color[:3]) + (255,))
    border = tuple(max(0, c - 70) for c in color[:3])
    pygame.draw.rect(surf, border, surf.get_rect(), 1)
    if label and size[0] >= 20:
        font = pygame.font.Font(None, max(12, size[0] // 2))
        text = font.render(str(label)[:3], True, border)
        surf.blit(text, text.get_rect(center=(size[0] // 2, size[1] // 2)))
    return surf


def tint(surface, color, strength=1.0):
    """Warnai ulang surface (BLEND_MULT) - dipakai untuk jebakan api/es."""
    out = surface.copy().convert_alpha()
    fill = tuple(int(c * strength) for c in color)
    out.fill(fill + (0,), special_flags=pygame.BLEND_MULT)
    return out


def load_image(path, size=None, fallback_color=None):
    """Muat 1 file PNG; bila tidak ada -> placeholder berwarna."""
    if os.path.exists(path):
        try:
            img = pygame.image.load(path).convert_alpha()
            if size and img.get_size() != size:
                img = pygame.transform.scale(img, size)
            return img
        except pygame.error:
            pass
    return make_placeholder(fallback_color or (255, 0, 255), size or (16, 16))


# ==============================================================================
# PEMBACA FOLDER SPRITES
# ==============================================================================
def load_folder_sprites(folder, scale_size=None, fallback_color=None,
                        fallback_count=0, prefix=None):
    """
    Membaca semua file .png di dalam `folder` (relatif terhadap assets/)
    secara berurutan memakai glob + natural sort, lalu menskalakan ke
    `scale_size`. Bila folder kosong/tidak ada -> `fallback_count` placeholder.
    """
    full = folder if os.path.isabs(folder) else os.path.join(config.ASSETS_DIR, folder)
    sprites = []
    if os.path.isdir(full):
        files = sorted(glob.glob(os.path.join(full, "*.png")),
                       key=lambda p: natural_key(os.path.basename(p)))
        for f in files:
            if prefix and not os.path.basename(f).startswith(prefix):
                continue
            try:
                img = pygame.image.load(f).convert_alpha()
            except pygame.error:
                continue
            if scale_size and img.get_size() != scale_size:
                img = pygame.transform.scale(img, scale_size)
            sprites.append(img.convert_alpha())
    if sprites:
        return sprites
    size = scale_size or (config.SOURCE_TILE, config.SOURCE_TILE)
    return [make_placeholder(fallback_color or (200, 200, 200), size)
            for _ in range(max(1, fallback_count))]


def load_animation_groups(folder):
    """
    Membaca semua PNG dalam folder lalu mengelompokkannya menjadi animasi
    berdasarkan nama file tanpa suffix '_fNN'.
    Contoh: hero_run_f0.png .. f7.png -> {'hero_run': [...8 frame]}
    """
    full = folder if os.path.isabs(folder) else os.path.join(config.ASSETS_DIR, folder)
    groups = {}
    if not os.path.isdir(full):
        return groups
    files = sorted(glob.glob(os.path.join(full, "*.png")),
                   key=lambda p: natural_key(os.path.basename(p)))
    for f in files:
        stem = os.path.splitext(os.path.basename(f))[0]
        key = re.sub(r"_f\d+$", "", stem)
        try:
            img = pygame.image.load(f).convert_alpha()
        except pygame.error:
            continue
        groups.setdefault(key, []).append(img.convert_alpha())
    return groups


def load_strip_frames(path, count=None, canvas=24, target_size=None, tint=None):
    """
    Potong strip sprite karakter Sunnyside World (.png) menjadi daftar frame
    yang diratakan ke kanvas berukuran canvas, dengan scaling opsional ke target_size.
    """
    if not os.path.exists(path):
        return []
    try:
        sheet = pygame.image.load(path)
        if pygame.display.get_surface() is not None:
            sheet = sheet.convert_alpha()
    except Exception:
        return []
    w, h = sheet.get_size()
    count = count or max(1, w // 96)
    fw = w // count
    frames = [sheet.subsurface((i * fw, 0, fw, h)).copy() for i in range(count)]
    rects = [f.get_bounding_rect() for f in frames if f.get_bounding_rect().w > 0]
    if not rects:
        return frames
    x0 = min(r.x for r in rects)
    y0 = min(r.y for r in rects)
    x1 = max(r.right for r in rects)
    y1 = max(r.bottom for r in rects)
    bw, bh = max(1, x1 - x0), max(1, y1 - y0)
    canvas = max(canvas, bw, bh)
    out = []
    for f in frames:
        crop = f.subsurface((x0, y0, bw, bh)).copy()
        pad = pygame.Surface((canvas, canvas), pygame.SRCALPHA)
        pad.blit(crop, ((canvas - bw) // 2, canvas - 3 - bh))
        if tint:
            pad.fill(tuple(tint) + (0,), special_flags=pygame.BLEND_MULT)
        if target_size and (canvas, canvas) != target_size:
            pad = pygame.transform.scale(pad, target_size)
        if pygame.display.get_surface() is not None:
            out.append(pad.convert_alpha())
        else:
            out.append(pad)
    return out


def pick_group(groups, patterns, target_size, fallback_color, fallback_size=None,
               frame_count=4):
    """
    Ambil grup frame pertama yang namanya cocok dengan `patterns`.
    Cocok persis diprioritaskan (agar "zombie_anim" tidak tertukar dengan
    "ice_zombie_anim"), lalu dicocokkan sebagai substring.
    """
    for pat in patterns:
        if pat in groups and groups[pat]:
            return [pygame.transform.scale(f, target_size) for f in groups[pat]]
    for pat in patterns:
        for name in sorted(groups):
            if pat in name and groups[name]:
                return [pygame.transform.scale(f, target_size) for f in groups[name]]
    fb = fallback_size or target_size
    return [make_placeholder(fallback_color, fb) for _ in range(frame_count)]


# ==============================================================================
# PEMOTONG ATLAS (Sunnyside World)
# ==============================================================================
class TileSheet:
    """
    Pemotong atlas Sunnyside World.

    Atlas utama 1280x1280 berisi grid 64x64 sel. Setiap sel berukuran
    20x20 px (pitch), tetapi konten tile hanya 16x16 px yang dimulai 2 px
    dari tepi sel (inset). Pola ini mencegah "tile bleeding" saat scaling.

    Setiap tile diambil per grid koordinat (kolom, baris) lalu diskalakan
    dengan nearest-neighbour agar pixel-art tetap jernih.
    """

    def __init__(self, candidates, tile_w=config.SOURCE_TILE,
                 tile_h=config.SOURCE_TILE, scale=config.SCALE_FACTOR,
                 fallback_colors=None, pitch=None, inset=0):
        self.tile_w = tile_w
        self.tile_h = tile_h
        self.scale = scale
        self.out_size = (tile_w * scale, tile_h * scale)
        self.pitch = pitch or tile_w
        self.inset = inset
        self.fallback_colors = fallback_colors or {}
        self.sheet = None
        self.path = None
        self.cols = 1
        self.rows = 1

        for cand in candidates:
            p = cand if os.path.isabs(cand) else os.path.join(config.ASSETS_DIR, cand)
            if os.path.exists(p):
                self.path = p
                break
        if self.path:
            try:
                self.sheet = pygame.image.load(self.path).convert_alpha()
                self.cols = max(1, (self.sheet.get_width() - self.inset
                                    - self.tile_w) // self.pitch + 1)
                self.rows = max(1, (self.sheet.get_height() - self.inset
                                    - self.tile_h) // self.pitch + 1)
            except pygame.error:
                self.sheet = None
        self._cache = {}

    @property
    def available(self):
        return self.sheet is not None

    def get_tile(self, col, row, fallback_color=None, key=None):
        """Ambil 1 tile dari grid koordinat (kolom, baris) - sudah diskalakan."""
        cache_key = key or (col, row)
        if cache_key in self._cache:
            return self._cache[cache_key]
        rect = pygame.Rect(col * self.pitch + self.inset,
                           row * self.pitch + self.inset,
                           self.tile_w, self.tile_h)
        if self.sheet is not None and self.sheet.get_rect().contains(rect):
            tile = self.sheet.subsurface(rect).copy()      # surface sendiri
            tile = pygame.transform.scale(tile, self.out_size)
            tile = tile.convert_alpha()
        else:
            color = fallback_color or self.fallback_colors.get("floor", (90, 90, 100))
            tile = make_placeholder(color, self.out_size)
        self._cache[cache_key] = tile
        return tile

    def get_tile_by_id(self, tile_id, fallback_color=None):
        """Ambil 1 tile berdasar Tile ID (row-major, kiri-atas = 0)."""
        return self.get_tile(tile_id % self.cols, tile_id // self.cols,
                             fallback_color, key=("id", tile_id))

    def get_region(self, x, y, w, h, out_size=None):
        """Ambil region bebas (px) dari atlas, mis. untuk sprite non-grid."""
        out_size = out_size or (w * self.scale, h * self.scale)
        rect = pygame.Rect(x, y, w, h)
        if self.sheet is not None and self.sheet.get_rect().contains(rect):
            region = self.sheet.subsurface(rect).copy()
            return pygame.transform.scale(region, out_size).convert_alpha()
        return make_placeholder(self.fallback_colors.get("floor"), out_size)

    def get_animation(self, coords, fallback_color=None):
        """Daftar (kolom,baris) -> daftar frame animasi yang sudah diskalakan."""
        return [self.get_tile(c, r, fallback_color, key=("anim", c, r))
                for (c, r) in coords]


# ==============================================================================
# ASSET MANAGER - gabungan semua aset game
# ==============================================================================
class AssetManager:
    """Memuat seluruh aset game + menyiapkan fallback otomatis."""

    def __init__(self):
        s = config.SCALE_FACTOR
        big = (config.TILE_SIZE, config.TILE_SIZE)
        # Peta pulau Sunnyside World resolusi tinggi
        world_map_path = getattr(config, "MAP_IMAGE_PATH",
                                os.path.join(config.MAPS_DIR, "island_map.png"))
        if os.path.exists(world_map_path):
            try:
                self.world_map_img = pygame.image.load(world_map_path).convert()
            except Exception:
                self.world_map_img = None
        else:
            self.world_map_img = None

        # ---- Atlas Sunnyside (pitch 20, inset 2) ---------------------------
        self.tileset = TileSheet(config.TILESET_CANDIDATES,
                                 fallback_colors=config.FALLBACK_COLORS,
                                 pitch=config.TILESET_PITCH,
                                 inset=config.TILESET_INSET)
        A = config.TILE_ATLAS

        # ---------- SEMUA VARIAN PERMUKAAN ---------------------------------
        # name -> [surface 32x32, ...]
        self.tiles = {}
        for name, coords in A.items():
            fallback = config.FALLBACK_COLORS.get(name, config.FALLBACK_COLORS["floor"])
            if isinstance(coords, list):
                self.tiles[name] = [
                    self.tileset.get_tile(c, r, fallback, key=("t", name, i))
                    for i, (c, r) in enumerate(coords)
                ]
            else:
                self.tiles[name] = [self.tileset.get_tile(*coords, fallback,
                                                          key=("t", name))]

        # alias lama supaya kode lain tetap jalan
        self.tile_floor_wood = self.tiles["floor_wood"][0]
        self.tile_floor_dirt = self.tiles["floor_dirt"][0]
        self.tile_floor_stone = self.tiles["floor_stone"][0]

        # ---------- WALL / OBSTACLE LAYER -----------------------------------
        # Dinding = lempeng batu + "front face" gelap di bawah (kesan 2.5D).
        self.tile_wall_block = self.tiles["wall_block"][0]
        self.tile_wall_face = self._build_wall_face()
        self.tile_wall_block_face = self._build_wall_face_tile(self.tile_wall_block)

        # ---------- Core / spawn (digambar prosedural) ----------------------
        self.frames_core = self._build_core_frames()
        self.frames_core_basin = self._build_core_basin()

        # ---- VFX: jebakan (api) dari sunnyside_world/Elements/VFX ----------
        fire_path = os.path.join(config.SUNNYSIDE_DIR, "Elements", "VFX", "Fire", "spr_deco_fire_01_strip4.png")
        fire_raw = load_strip_frames(fire_path, count=4, target_size=big)
        if not fire_raw:
            vfx = load_animation_groups("vfx")
            fire_raw = pick_group(vfx, ["fire"], big, config.ORANGE, frame_count=4)
        self.frames_trap_fire = fire_raw
        self.frames_trap_ice = [tint(f, config.CYAN) for f in fire_raw]

        # ---- HERO (modul tunggal hero_sprite.py: base + hair + tools) -------
        char = config.HERO_SCREEN_SIZE
        hero_mgr = get_hero_sprite_manager()
        self.hero_idle = hero_mgr.get_world_frames("idle", target_size=char)
        self.hero_run = hero_mgr.get_world_frames("run", target_size=char)
        self.hero_walk = hero_mgr.get_world_frames("walk", target_size=char)
        self.hero_attack = hero_mgr.get_world_frames("attack", target_size=char)
        self.hero_cast = hero_mgr.get_world_frames("casting", target_size=char)
        self.hero_hit = hero_mgr.get_world_frames("hurt", target_size=char)

        # alias per arah (semua menunjuk frame yang sama; cermin saat render)
        self.hero_walk_up = self.hero_walk_side = self.hero_walk
        self.hero_idle_up = self.hero_idle_side = self.hero_idle

        # ---- GOBLIN & MONSTER (folder assets/sunnyside_world/Characters) ----------
        goblin_dir = os.path.join(config.SUNNYSIDE_DIR, "Characters", "Goblin", "PNG")
        skel_dir = os.path.join(config.SUNNYSIDE_DIR, "Characters", "Skeleton", "PNG")
        fb_mon = config.FALLBACK_COLORS["monster"]
        fb_ice = config.FALLBACK_COLORS["monster_ice"]
        fb_boss = config.FALLBACK_COLORS["boss"]
        boss = config.BOSS_SCREEN_SIZE

        # Animasi Lengkap Goblin (Real-Time Combat)
        self.goblin_anims = {
            "idle": load_strip_frames(os.path.join(goblin_dir, "spr_idle_strip9.png"), target_size=char),
            "walk": load_strip_frames(os.path.join(goblin_dir, "spr_walk_strip8.png"), target_size=char),
            "run": load_strip_frames(os.path.join(goblin_dir, "spr_run_strip8.png"), target_size=char),
            "attack": load_strip_frames(os.path.join(goblin_dir, "spr_attack_strip10.png"), target_size=char),
            "hurt": load_strip_frames(os.path.join(goblin_dir, "spr_hurt_strip8.png"), target_size=char),
            "death": load_strip_frames(os.path.join(goblin_dir, "spr_death_strip13.png"), target_size=char),
        }

        m_zomb_run = self.goblin_anims.get("run") or load_strip_frames(os.path.join(goblin_dir, "spr_run_strip8.png"), count=8, target_size=char)
        m_zomb_idle = self.goblin_anims.get("idle") or load_strip_frames(os.path.join(goblin_dir, "spr_idle_strip9.png"), count=9, target_size=char)
        m_ice_run = load_strip_frames(os.path.join(skel_dir, "skeleton_walk_strip8.png"), count=8, target_size=char, tint=(170, 215, 255))
        m_ice_idle = load_strip_frames(os.path.join(skel_dir, "skeleton_idle_strip6.png"), count=6, target_size=char, tint=(170, 215, 255))

        # Boss Sprite: Skeleton Overlord (Sunnyside Characters Skeleton)
        skel_idle_path = os.path.join(skel_dir, "skeleton_idle_strip6.png")
        skel_walk_path = os.path.join(skel_dir, "skeleton_walk_strip8.png")
        skel_atk_path = os.path.join(skel_dir, "skeleton_attack_strip7.png")
        skel_hurt_path = os.path.join(skel_dir, "skeleton_hurt_strip7.png")
        skel_death_path = os.path.join(skel_dir, "skeleton_death_strip10.png")

        b_idle = load_strip_frames(skel_idle_path, count=6, target_size=boss)
        b_run = load_strip_frames(skel_walk_path, count=8, target_size=boss)
        self.boss_attack = load_strip_frames(skel_atk_path, count=7, target_size=boss)
        self.boss_hurt = load_strip_frames(skel_hurt_path, count=7, target_size=boss)
        self.boss_death = load_strip_frames(skel_death_path, count=10, target_size=boss)
        self.boss_remains = self.boss_death[-1] if self.boss_death else None

        self.monster_zombie = m_zomb_run or [make_placeholder(fb_mon, char) for _ in range(4)]
        self.monster_zombie_idle = m_zomb_idle or [make_placeholder(fb_mon, char) for _ in range(4)]
        self.monster_ice = m_ice_run or [make_placeholder(fb_ice, char) for _ in range(4)]
        self.monster_ice_idle = m_ice_idle or [make_placeholder(fb_ice, char) for _ in range(4)]
        self.boss_idle = b_idle or [make_placeholder(fb_boss, boss) for _ in range(4)]
        self.boss_walk = b_run or [make_placeholder(fb_boss, boss) for _ in range(4)]

        # UI indicator untuk Boss (ikon skull / seru)
        ui_attack_path = os.path.join(config.SUNNYSIDE_DIR, "UI", "expression_attack.png")
        ui_alert_path = os.path.join(config.SUNNYSIDE_DIR, "UI", "expression_alerted.png")
        try:
            if os.path.exists(ui_attack_path):
                img = pygame.image.load(ui_attack_path)
                if pygame.display.get_surface() is not None:
                    img = img.convert_alpha()
                self.ui_boss_skull = pygame.transform.scale(img, (img.get_width() * 3, img.get_height() * 3))
            else:
                self.ui_boss_skull = None
        except Exception:
            self.ui_boss_skull = None

        try:
            if os.path.exists(ui_alert_path):
                img = pygame.image.load(ui_alert_path)
                if pygame.display.get_surface() is not None:
                    img = img.convert_alpha()
                self.ui_boss_alert = pygame.transform.scale(img, (img.get_width() * 3, img.get_height() * 3))
            else:
                self.ui_boss_alert = None
        except Exception:
            self.ui_boss_alert = None

        # ---- COMBAT VFX (Hit Sparks, Dust, UI Bars) ----------------------
        glint_path1 = os.path.join(config.SUNNYSIDE_DIR, "Elements", "VFX", "Glint", "spr_deco_glint_01_strip6.png")
        glint_path2 = os.path.join(config.SUNNYSIDE_DIR, "Elements", "VFX", "Glint", "spr_deco_glint_02_strip4.png")
        self.hit_spark_frames = []
        self.hit_spark_alt_frames = []
        if os.path.exists(glint_path1):
            try:
                g_sheet1 = pygame.image.load(glint_path1).convert_alpha()
                gw1, gh1 = g_sheet1.get_width() // 6, g_sheet1.get_height()
                for i in range(6):
                    sub1 = g_sheet1.subsurface((i * gw1, 0, gw1, gh1))
                    self.hit_spark_frames.append(pygame.transform.scale(sub1, (gw1 * 4, gh1 * 4)))
            except Exception:
                pass
        if os.path.exists(glint_path2):
            try:
                g_sheet2 = pygame.image.load(glint_path2).convert_alpha()
                gw2, gh2 = g_sheet2.get_width() // 4, g_sheet2.get_height()
                for i in range(4):
                    sub2 = g_sheet2.subsurface((i * gw2, 0, gw2, gh2))
                    self.hit_spark_alt_frames.append(pygame.transform.scale(sub2, (gw2 * 4, gh2 * 4)))
            except Exception:
                pass

        dust_dir = os.path.join(config.SUNNYSIDE_DIR, "Sunnyside_World_Gamemaker", "sprites", "dust_general_strip8")
        self.dust_frames = []
        if os.path.isdir(dust_dir):
            try:
                for df in sorted(glob.glob(os.path.join(dust_dir, "*.png")), key=lambda p: natural_key(os.path.basename(p))):
                    if os.path.isfile(df) and "layers" not in df:
                        d_img = pygame.image.load(df).convert_alpha()
                        self.dust_frames.append(pygame.transform.scale(d_img, (32, 16)))
            except Exception:
                pass

        # Health bars UI (redbar_00 .. redbar_06 dan greenbar_00 .. greenbar_06)
        self.ui_redbars = []
        self.ui_greenbars = []
        ui_dir = os.path.join(config.SUNNYSIDE_DIR, "UI")
        for i in range(7):
            rp = os.path.join(ui_dir, f"redbar_0{i}.png")
            gp = os.path.join(ui_dir, f"greenbar_0{i}.png")
            if os.path.exists(rp):
                try:
                    img = pygame.image.load(rp)
                    self.ui_redbars.append(pygame.transform.scale(img, (img.get_width() * 2, img.get_height() * 2)))
                except Exception:
                    pass
            if os.path.exists(gp):
                try:
                    img = pygame.image.load(gp)
                    self.ui_greenbars.append(pygame.transform.scale(img, (img.get_width() * 2, img.get_height() * 2)))
                except Exception:
                    pass

        # ---- PROP (folder assets/sunnyside_world/Elements) ---------------
        self.props = self._load_props()

        # ---- UI (folder assets/sunnyside_world/UI) ------------------------
        self.ui = self._load_ui()

        # ---- VFX lain (ikon HUD) ------------------------------------------
        self.icon_heart_full = self.ui.get("expression_love", make_placeholder(config.RED, (16, 16)))
        self.icon_heart_half = self.ui.get("expression_confused", make_placeholder(config.ORANGE, (16, 16)))
        self.icon_heart_empty = make_placeholder(config.DARK_GREY, (16, 16))
        self.frames_coin = [make_placeholder(config.GOLD, (16, 16)) for _ in range(4)]
        self.icon_flask_red = make_placeholder(config.RED, (16, 16))
        self.icon_flask_blue = make_placeholder(config.BLUE, (16, 16))
        self.frames_bomb = [make_placeholder(config.ORANGE, (16, 16)) for _ in range(4)]

        # ---- seni prosedural open-world (tile tanah, pohon, rumah, VFX) ----
        self.world_art = None
        self.ensure_world_art()

    def ensure_world_art(self):
        """Bangun WorldArt secara lazy (aman untuk pemanggilan berulang)."""
        if self.world_art is None:
            self.world_art = WorldArt(self)
        return self.world_art

    # -------------------------------------------------------------- builders
    def _load_props(self):
        """Muat prop dari sunnyside_world/Elements."""
        out = {}
        elems_dir = os.path.join(config.SUNNYSIDE_DIR, "Elements")
        if os.path.isdir(elems_dir):
            for root, _, files in os.walk(elems_dir):
                for f in sorted(files):
                    if f.endswith(".png") and "strip" in f:
                        name = f.split("_strip")[0].replace("spr_deco_", "").replace("spr_", "")
                        # hitung frame
                        m = re.search(r"strip(\d+)", f)
                        cnt = int(m.group(1)) if m else 4
                        full_p = os.path.join(root, f)
                        frames = load_strip_frames(full_p, count=cnt, canvas=32)
                        if frames:
                            out[name] = frames
            # Alias nama hewan agar Animal('chicken') dan sejenisnya menemukan frames
            for an_type in ["chicken", "sheep", "pig", "duck"]:
                if f"{an_type}_01" in out and an_type not in out:
                    out[an_type] = out[f"{an_type}_01"]
        return out

    def _load_ui(self):
        """Muat komponen antarmuka Sunnyside World dari sunnyside_world/UI."""
        out = {}
        for folder in [os.path.join(config.SUNNYSIDE_DIR, "UI"), os.path.join(config.ASSETS_DIR, "ui")]:
            if os.path.isdir(folder):
                for root, _, files in os.walk(folder):
                    for f in files:
                        if f.endswith(".png"):
                            stem = os.path.splitext(f)[0]
                            try:
                                out[stem] = pygame.image.load(os.path.join(root, f)).convert_alpha()
                            except pygame.error:
                                pass
        return out

    def _build_wall_face(self):
        """
        'Front face' blok dinding: pita batu gelap di bagian bawah tile
        yang menghadap lantai -> memberi kesan blok batu meninggi (2.5D).
        """
        w = config.TILE_SIZE
        h = max(6, config.TILE_SIZE // config.WALL_FACE_RATIO)
        face = pygame.Surface((w, h), pygame.SRCALPHA).convert_alpha()
        face.fill((58, 60, 74, 255))
        pygame.draw.rect(face, (122, 128, 148), (2, 0, w - 4, max(2, h // 4)))
        pygame.draw.rect(face, (86, 92, 112), (2, max(2, h // 4), w - 4, h // 2))
        pygame.draw.rect(face, (40, 42, 54), (0, 0, 2, h))
        pygame.draw.rect(face, (40, 42, 54), (w - 2, 0, 2, h))
        return face

    def _build_wall_face_tile(self, block):
        """Gabungkan lempeng batu dengan 'front face' -> tile dinding 2.5D."""
        w = config.TILE_SIZE
        fh = self.tile_wall_face.get_height()
        out = pygame.Surface((w, w), pygame.SRCALPHA).convert_alpha()
        out.blit(block, (0, 0))
        out.blit(self.tile_wall_face, (0, w - fh))
        return out

    def _build_core_frames(self):
        """Kristal Core beranimasi (digambar prosedural, tanpa aset eksternal)."""
        size = config.TILE_SIZE
        frames = []
        for i in range(4):
            surf = pygame.Surface((size, size), pygame.SRCALPHA).convert_alpha()
            lift = (0, -2, -3, -2)[i]
            cx = size // 2
            top = size // 2 + lift
            pts = [(cx, top - 11), (cx + 8, top), (cx, top + 10), (cx - 8, top)]
            pygame.draw.polygon(surf, (117, 227, 255), pts)
            pygame.draw.polygon(surf, (48, 182, 230), pts, 1)
            pygame.draw.polygon(surf, (228, 237, 249),
                                [(cx, top - 9), (cx + 3, top - 1), (cx, top + 2)])
            frames.append(surf)
        return frames

    def _build_core_basin(self):
        """Pedestal Core: cincin batu berisi rune biru."""
        size = config.TILE_SIZE
        surf = pygame.Surface((size, size), pygame.SRCALPHA).convert_alpha()
        pygame.draw.ellipse(surf, (38, 43, 68), (4, 8, size - 8, size - 14))
        pygame.draw.ellipse(surf, (82, 96, 124), (5, 9, size - 10, size - 16))
        pygame.draw.ellipse(surf, (48, 182, 230), (8, 12, size - 16, size - 22))
        return surf

    # ------------------------------------------------------------------
    @staticmethod
    def _pick_icon(groups, patterns, size, color):
        for pat in patterns:
            for name in sorted(groups):
                if pat in name and groups[name]:
                    return pygame.transform.scale(groups[name][0], size)
        return make_placeholder(color, size)

    def hero_frame_buckets(self):
        """
        Kumpulan frame Hero yang dikelompokkan per arah & status gerak.

        Dikembalikan sebagai dict:
            {"walk": {"down": [...], "up": [...], "side": [...]},
             "idle": {"down": [...], "up": [...], "side": [...]}}

        Strip Sunnyside hanya punya satu arah, jadi ketiga kunci memakai frame
        yang sama. Arah kiri dicerminkan saat render oleh core/entity.py.
        """
        return {
            "walk": {"down": self.hero_walk,
                     "up": self.hero_walk_up,
                     "side": self.hero_walk_side},
            "idle": {"down": self.hero_idle,
                     "up": self.hero_idle_up,
                     "side": self.hero_idle_side},
        }
