"""
asset_catalog.py - Katalog & Registry Terpusat Aset Sunnyside World

Menyediakan antarmuka tunggal, aman, dan berkinerja tinggi untuk memuat, memotong strip,
menskalakan (integer nearest-neighbor), serta menyimpan cache seluruh aset visual Sunnyside World.

Fitur:
  1. Pemotongan Otomatis Strip (_stripN.png): Menghitung jumlah frame langsung dari nama file.
  2. Nearest-Neighbor Integer Scaling: Menjaga kejernihan pixel art tanpa blur saat diskalakan.
  3. Caching Dua Tingkat: Cache frame mentah dan cache surface berskala (mencegah re-slicing).
  4. Penanganan Fallback Aman: Menampilkan peringatan jelas di terminal dan mengembalikan surface
     placeholder berwarna bila file hilang/rusak (anti-crash).
  5. API Semantik: Akses mudah via get_ui_icon, get_crop, get_skeleton_anim, get_goblin_anim,
     get_vfx, get_prop, dan get_human_anim.
"""

import os
import re
from typing import Dict, List, Optional, Tuple, Union

import pygame
import config


def _safe_convert_alpha(surf: pygame.Surface) -> pygame.Surface:
    """Mengonversi surface ke alpha jika video mode aktif; tetap aman di mode headless/test."""
    if pygame.display.get_surface() is not None:
        try:
            return surf.convert_alpha()
        except pygame.error:
            pass
    return surf


def make_catalog_placeholder(size: Tuple[int, int] = (16, 16),
                             color: Tuple[int, int, int] = (255, 0, 255),
                             label: Optional[str] = None) -> pygame.Surface:
    """Membuat surface placeholder kotak berwarna untuk aset yang hilang."""
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf = _safe_convert_alpha(surf)
    c_fill = tuple(color[:3]) + (220,)
    surf.fill(c_fill)
    border_color = tuple(max(0, c - 70) for c in color[:3]) + (255,)
    pygame.draw.rect(surf, border_color, surf.get_rect(), 1)
    if label and size[0] >= 16 and size[1] >= 12:
        try:
            if not pygame.font.get_init():
                pygame.font.init()
            f_size = max(10, min(size[1] // 2, 14))
            font = pygame.font.Font(None, f_size)
            txt = font.render(str(label)[:4], True, (255, 255, 255))
            rect = txt.get_rect(center=(size[0] // 2, size[1] // 2))
            surf.blit(txt, rect)
        except Exception:
            pass
    return surf


class AssetCatalog:
    """Katalog terpusat untuk memuat, memotong, menskalakan, dan meng-cache aset Sunnyside."""

    _instance: Optional["AssetCatalog"] = None

    @classmethod
    def get_instance(cls) -> "AssetCatalog":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = root_dir or getattr(config, "SUNNYSIDE_DIR", os.path.join(config.ASSETS_DIR, "sunnyside_world"))
        self._cache_images: Dict[str, pygame.Surface] = {}
        self._cache_frames: Dict[Tuple[str, int], List[pygame.Surface]] = {}
        self._cache_scaled_frames: Dict[Tuple[str, int, int], List[pygame.Surface]] = {}
        self._index: Dict[str, str] = {}  # stem / logical key -> relative path
        self._build_index()

    def _build_index(self):
        """Membuat indeks pencarian cepat untuk nama file dan stem di root_dir."""
        ignored = {"Sunnyside_World_Gamemaker", "GIF", "_Source"}
        if not os.path.isdir(self.root_dir):
            return

        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            dirnames[:] = [d for d in dirnames if d not in ignored]
            rel_dir = os.path.relpath(dirpath, self.root_dir)
            parts = rel_dir.split(os.sep)
            if any(p in ignored for p in parts):
                continue

            for fname in filenames:
                if fname.endswith(".png"):
                    rel_path = os.path.join(rel_dir, fname) if rel_dir != "." else fname
                    stem = os.path.splitext(fname)[0]

                    # Indeks berbasis rel_path
                    self._index[rel_path] = rel_path
                    self._index[fname] = rel_path

                    # Indeks berbasis stem (jika belum ditempati)
                    if stem not in self._index:
                        self._index[stem] = rel_path

                    # Indeks strip tanpa suffix _stripN
                    clean_stem = re.sub(r"_strip\d+$", "", stem)
                    if clean_stem not in self._index:
                        self._index[clean_stem] = rel_path

    def clear_cache(self):
        """Membersihkan seluruh cache surface di memori."""
        self._cache_images.clear()
        self._cache_frames.clear()
        self._cache_scaled_frames.clear()

    def resolve_path(self, key_or_path: str) -> Optional[str]:
        """Mencari lokasi absolut dari key, nama file, atau path relatif."""
        # 1. Cek langsung jika path absolut
        if os.path.isabs(key_or_path) and os.path.isfile(key_or_path):
            return key_or_path

        # 2. Cek path relatif langsung terhadap root_dir
        candidate = os.path.join(self.root_dir, key_or_path)
        if os.path.isfile(candidate):
            return candidate

        # 3. Cek indeks
        rel = self._index.get(key_or_path)
        if rel:
            p = os.path.join(self.root_dir, rel)
            if os.path.isfile(p):
                return p

        # 4. Cek folder assets/generated/
        base_dir = os.path.abspath(os.path.join(self.root_dir, "..", ".."))
        gen_candidate = os.path.join(base_dir, "assets", "generated", os.path.basename(key_or_path))
        if not gen_candidate.endswith(".png") and os.path.isfile(gen_candidate + ".png"):
            return gen_candidate + ".png"
        if os.path.isfile(gen_candidate):
            return gen_candidate

        # 4. Cek fallback penamaan (case-insensitive / strip)
        key_lower = key_or_path.lower()
        for idx_k, rel_p in self._index.items():
            if idx_k.lower() == key_lower:
                p = os.path.join(self.root_dir, rel_p)
                if os.path.isfile(p):
                    return p

        return None

    def has_asset(self, key_or_path: str) -> bool:
        """Memeriksa apakah aset tersedia di katalog."""
        return self.resolve_path(key_or_path) is not None

    def parse_strip_count(self, path_or_name: str) -> int:
        """Mengekstrak jumlah frame dari pola _stripN.png."""
        base = os.path.basename(path_or_name)
        m = re.search(r"_strip(\d+)", base)
        if m:
            return max(1, int(m.group(1)))
        return 1

    # ------------------------------------------------------------------ LOAD IMAGE & FRAMES
    def get_image(self, key_or_path: str, scale: int = 1,
                  fallback_color: Tuple[int, int, int] = (255, 0, 255),
                  fallback_size: Tuple[int, int] = (16, 16)) -> pygame.Surface:
        """Memuat satu citra PNG tunggal; diskalakan jika scale > 1."""
        full_path = self.resolve_path(key_or_path)
        if not full_path:
            print(f"[PERINGATAN ASSET CATALOG] Asset tidak ditemukan: '{key_or_path}'! Menggunakan fallback placeholder.")
            return make_catalog_placeholder(size=(fallback_size[0] * scale, fallback_size[1] * scale),
                                            color=fallback_color, label="ERR")

        cache_key = f"{full_path}__scale{scale}"
        if cache_key in self._cache_images:
            return self._cache_images[cache_key]

        try:
            surf = pygame.image.load(full_path)
            surf = _safe_convert_alpha(surf)
            if scale > 1:
                w, h = surf.get_size()
                surf = pygame.transform.scale(surf, (w * scale, h * scale))
                surf = _safe_convert_alpha(surf)
            self._cache_images[cache_key] = surf
            return surf
        except Exception as e:
            print(f"[PERINGATAN ASSET CATALOG] Gagal memuat citra '{full_path}': {e}! Menggunakan placeholder.")
            placeholder = make_catalog_placeholder(size=(fallback_size[0] * scale, fallback_size[1] * scale),
                                                   color=fallback_color, label="ERR")
            self._cache_images[cache_key] = placeholder
            return placeholder

    def get_frames(self, key_or_path: str, count: Optional[int] = None,
                   scale: int = 1,
                   fallback_color: Tuple[int, int, int] = (255, 0, 255),
                   fallback_size: Tuple[int, int] = (16, 16)) -> List[pygame.Surface]:
        """
        Memotong strip citra menjadi daftar surface frame (horizontal strip).
        Jika count tidak ditentukan, diekstrak otomatis dari pola _stripN di nama file.
        """
        full_path = self.resolve_path(key_or_path)
        if not full_path:
            print(f"[PERINGATAN ASSET CATALOG] Strip tidak ditemukan: '{key_or_path}'! Menggunakan fallback placeholder.")
            cnt = count or 1
            fb = make_catalog_placeholder(size=(fallback_size[0] * scale, fallback_size[1] * scale),
                                          color=fallback_color, label="ERR")
            return [fb for _ in range(cnt)]

        detected_count = count or self.parse_strip_count(full_path)
        scaled_key = (full_path, detected_count, scale)
        if scaled_key in self._cache_scaled_frames:
            return self._cache_scaled_frames[scaled_key]

        # Cek raw frames cache
        raw_key = (full_path, detected_count)
        if raw_key not in self._cache_frames:
            try:
                sheet = pygame.image.load(full_path)
                sheet = _safe_convert_alpha(sheet)
                sw, sh = sheet.get_size()
                fw = max(1, sw // detected_count)
                raw_frames = []
                for i in range(detected_count):
                    rect = pygame.Rect(i * fw, 0, fw, sh)
                    sub = sheet.subsurface(rect).copy()
                    raw_frames.append(_safe_convert_alpha(sub))
                self._cache_frames[raw_key] = raw_frames
            except Exception as e:
                print(f"[PERINGATAN ASSET CATALOG] Gagal memotong strip '{full_path}': {e}!")
                fb = make_catalog_placeholder(size=fallback_size, color=fallback_color, label="ERR")
                self._cache_frames[raw_key] = [fb for _ in range(detected_count)]

        raw_frames = self._cache_frames[raw_key]
        if scale == 1:
            self._cache_scaled_frames[scaled_key] = raw_frames
            return raw_frames

        scaled_list = []
        for f in raw_frames:
            fw, fh = f.get_size()
            scaled_surf = pygame.transform.scale(f, (fw * scale, fh * scale))
            scaled_list.append(_safe_convert_alpha(scaled_surf))

        self._cache_scaled_frames[scaled_key] = scaled_list
        return scaled_list

    # ------------------------------------------------------------------ SPESIFIK: UI
    def get_ui_icon(self, name: str, scale: int = 1) -> pygame.Surface:
        """Mengambil ikon UI dari assets/sunnyside_world/UI/."""
        # Bersihkan format
        clean_name = name.strip()
        if not clean_name.endswith(".png"):
            clean_name = f"{clean_name}.png"
        rel_path = os.path.join("UI", clean_name)
        return self.get_image(rel_path, scale=scale, fallback_color=(180, 180, 220), fallback_size=(16, 16))

    def get_generated_icon(self, name: str, scale: int = 1) -> pygame.Surface:
        """Mengambil ikon khusus yang di-generate di assets/generated/ (coin, key, bottle, potion, gate)."""
        clean_name = name.strip()
        if not clean_name.endswith(".png"):
            clean_name = f"{clean_name}.png"
        return self.get_image(clean_name, scale=scale, fallback_color=(240, 200, 80), fallback_size=(16, 16))

    # ------------------------------------------------------------------ SPESIFIK: CROPS & SOIL
    def get_crop(self, crop_name: str, stage: int = 0, scale: int = 1) -> pygame.Surface:
        """
        Mengambil sprite tanaman pada tahap pertumbuhan tertentu (0..5).
        Contoh: get_crop("wheat", stage=3, scale=2)
        """
        stage_clamped = max(0, min(5, stage))
        fname = f"{crop_name.lower().strip()}_{stage_clamped:02d}.png"
        rel_path = os.path.join("Elements", "Crops", fname)
        return self.get_image(rel_path, scale=scale, fallback_color=(120, 200, 80), fallback_size=(16, 16))

    def get_crop_item(self, item_name: str, scale: int = 1) -> pygame.Surface:
        """Mengambil item non-tanaman dari folder Crops (egg, milk, fish, seeds_generic, wood, crate)."""
        fname = item_name.strip()
        if not fname.endswith(".png"):
            fname = f"{fname}.png"
        rel_path = os.path.join("Elements", "Crops", fname)
        return self.get_image(rel_path, scale=scale, fallback_color=(200, 160, 90), fallback_size=(16, 16))

    def get_soil(self, variant: int = 0, scale: int = 1) -> pygame.Surface:
        """Mengambil tile tanah (soil_00, soil_01, soil_03, soil_04)."""
        fname = f"soil_{variant:02d}.png"
        rel_path = os.path.join("Elements", "Crops", fname)
        return self.get_image(rel_path, scale=scale, fallback_color=(140, 90, 50), fallback_size=(16, 16))

    # ------------------------------------------------------------------ SPESIFIK: SKELETON & GOBLIN
    def get_skeleton_anim(self, action: str, scale: int = 1) -> List[pygame.Surface]:
        """
        Mengambil daftar frame animasi Skeleton Sunnyside.
        Aksi didukung: idle (strip6), attack (strip7), hurt (strip7), death (strip10), walk (strip8), jump (strip10).
        """
        act = action.lower().strip()
        skel_map = {
            "idle": "skeleton_idle_strip6.png",
            "attack": "skeleton_attack_strip7.png",
            "hurt": "skeleton_hurt_strip7.png",
            "death": "skeleton_death_strip10.png",
            "walk": "skeleton_walk_strip8.png",
            "jump": "skeleton_jump_strip10.png",
        }
        fname = skel_map.get(act, f"skeleton_{act}.png")
        rel_path = os.path.join("Characters", "Skeleton", "PNG", fname)
        return self.get_frames(rel_path, scale=scale, fallback_color=(230, 230, 230), fallback_size=(96, 64))

    def get_goblin_anim(self, action: str, scale: int = 1) -> List[pygame.Surface]:
        """
        Mengambil daftar frame animasi Goblin Sunnyside.
        Mendukung 20 aksi lengkap: attack, axe, carry, casting, caught, death, dig, doing,
        hammering, hurt, idle, jump, mining, reeling, roll, run, swimming, waiting, walk, watering.
        """
        act = action.lower().strip()
        # Cari file di Characters/Goblin/PNG/
        prefix = f"spr_{act}_strip"
        target_file = None
        for k in self._index:
            if k.startswith("Characters/Goblin/PNG/") and os.path.basename(k).startswith(prefix):
                target_file = k
                break
        if not target_file:
            target_file = os.path.join("Characters", "Goblin", "PNG", f"spr_{act}.png")

        return self.get_frames(target_file, scale=scale, fallback_color=(80, 180, 80), fallback_size=(96, 64))

    # ------------------------------------------------------------------ SPESIFIK: VFX & PROPS
    def get_vfx(self, name: str, scale: int = 1) -> List[pygame.Surface]:
        """
        Mengambil animasi VFX (fire, glint, chimney smoke).
        Contoh: get_vfx("fire_01"), get_vfx("chimneysmoke_01"), get_vfx("glint_01")
        """
        clean_name = name.lower().strip()
        vfx_map = {
            "fire_01": "Elements/VFX/Fire/spr_deco_fire_01_strip4.png",
            "fire_02": "Elements/VFX/Fire/spr_deco_fire_02_strip4.png",
            "glint_01": "Elements/VFX/Glint/spr_deco_glint_01_strip6.png",
            "glint_02": "Elements/VFX/Glint/spr_deco_glint_02_strip4.png",
            "chimneysmoke_01": "Elements/VFX/Chimney Smoke/chimneysmoke_01_strip30.png",
            "chimneysmoke_02": "Elements/VFX/Chimney Smoke/chimneysmoke_02_strip30.png",
            "chimneysmoke_03": "Elements/VFX/Chimney Smoke/chimneysmoke_03_strip30.png",
            "chimneysmoke_04": "Elements/VFX/Chimney Smoke/chimneysmoke_04_strip30.png",
            "chimneysmoke_05": "Elements/VFX/Chimney Smoke/chimneysmoke_05_strip30.png",
        }
        rel = vfx_map.get(clean_name, clean_name)
        return self.get_frames(rel, scale=scale, fallback_color=(255, 160, 40), fallback_size=(16, 16))

    def get_prop(self, name: str, scale: int = 1) -> Union[pygame.Surface, List[pygame.Surface]]:
        """
        Mengambil prop animasi atau statis dari Elements (windmill, coracle, animal).
        """
        clean_name = name.lower().strip()
        prop_map = {
            "windmill": "Elements/Other/spr_deco_windmill_strip9.png",
            "windmill_shadow": "Elements/Other/spr_deco_windmillshadow_strip9.png",
            "windmill_withshadow": "Elements/Other/spr_deco_windmill_withshadow_strip9.png",
            "coracle_land": "Elements/Other/spr_deco_coracle_land.png",
            "coracle_water": "Elements/Other/spr_deco_coracle_strip4.png",
        }
        rel = prop_map.get(clean_name, clean_name)
        if "_strip" in rel:
            return self.get_frames(rel, scale=scale, fallback_color=(160, 160, 160), fallback_size=(32, 32))
        return self.get_image(rel, scale=scale, fallback_color=(160, 160, 160), fallback_size=(32, 32))

    # ------------------------------------------------------------------ SPESIFIK: HUMAN ANIMATION LAYER
    def get_human_layer(self, action: str, layer: str = "base",
                        scale: int = 1) -> List[pygame.Surface]:
        """
        Mengambil layer animasi Human (base, spikeyhair, bowlhair, tools, dll).
        Contoh: get_human_layer("axe", "base", scale=2)
        """
        act = action.upper().strip()
        folder_act = act
        # Normalisasi nama folder
        if folder_act == "WALK":
            folder_act = "WALKING"

        # Cari file di folder tersebut
        prefix = f"{layer.lower()}_"
        rel_dir = os.path.join("Characters", "Human", folder_act)
        full_dir = os.path.join(self.root_dir, rel_dir)

        if os.path.isdir(full_dir):
            for f in sorted(os.listdir(full_dir)):
                if f.startswith(prefix) and f.endswith(".png"):
                    rel_file = os.path.join(rel_dir, f)
                    return self.get_frames(rel_file, scale=scale, fallback_color=(200, 140, 100), fallback_size=(96, 64))

        # Fallback peringatan
        print(f"[PERINGATAN ASSET CATALOG] Human layer '{layer}' untuk aksi '{action}' tidak ditemukan!")
        fb = make_catalog_placeholder((96 * scale, 64 * scale), (200, 140, 100), label=action[:3])
        return [fb]

    def list_assets(self, category: Optional[str] = None) -> List[str]:
        """Menampilkan daftar path relatif aset yang terdaftar dalam katalog."""
        if not category:
            return sorted(list(set(self._index.values())))
        cat_lower = category.lower()
        return sorted([p for p in set(self._index.values()) if cat_lower in p.lower()])


def get_asset_catalog() -> AssetCatalog:
    """Mengambil instans singleton AssetCatalog."""
    return AssetCatalog.get_instance()

