"""
village_deco.py - Sistem Dekorasi Desa Sunnyside (Kincir Angin & Asap Cerobong)

Mengelola elemen visual otentik desa:
1. Kincir Angin (Windmill):
   - Dipasang di puncak menara kincir angin asli Sunnyside (dekat sungai & jembatan utara)
   - Poros bilah berlabuh presisi di WINDMILL_HUB_POS (1328, 526)
   - Animasi berputar 9 frame (spr_deco_windmill_withshadow_strip9) skala 2x (densitas piksel serasi dunia)
   - Urutan gambar: Menara (latar peta) -> Bilah (depan menara dengan y-sort di dasar menara sort_y=640)
   - Collision footprint dasar di pondasi menara (1280, 618, 96, 22), bebas hambatan di area lain
2. Asap Cerobong (Chimney Smoke):
   - Titik keluar asap presisi per rumah dari config.CHIMNEY_ANCHORS (hanya rumah ber-cerobong nyata)
   - Emitter aliran kontinu multi-instance (3 kepulan bertumpuk dengan offset fase 0, 10, 20 frame)
   - Skala 2x mencocokkan dunia, ujung bawah tepat di puncak cerobong, rata tengah horizontal
   - Alpha lembut (165) untuk mengurangi kedip keras dan menyatu mulus di atas atap
   - Frustum culling dengan margin aman 60px agar asap tidak lenyap mendadak di tepi layar
"""

import math
import random
from typing import List, Tuple, Optional
import pygame

import config
from asset_catalog import get_asset_catalog


class Windmill:
    """Objek Kincir Angin dengan bilah berputar di puncak menara dan footprint pondasi."""

    def __init__(self,
                 x: Optional[int] = None,
                 y: Optional[int] = None,
                 hub_x: Optional[int] = None,
                 hub_y: Optional[int] = None,
                 sort_y: Optional[float] = None,
                 scale: int = 2,
                 fps: float = 8.0):
        # Default koordinat hub poros kincir angin
        default_hub = getattr(config, "WINDMILL_HUB_POS", (1328, 526))
        default_sort_y = getattr(config, "WINDMILL_SORT_Y", 448.0)

        # Penentuan titik poros (hub) dan y-sort
        if hub_x is not None:
            self.hub_x = float(hub_x)
        elif x is not None and (x != 1860 or y != 960):
            self.hub_x = float(x)
        else:
            self.hub_x = float(default_hub[0])

        if hub_y is not None:
            self.hub_y = float(hub_y)
        elif y is not None and (x != 1860 or y != 960):
            self.hub_y = float(y)
        else:
            self.hub_y = float(default_hub[1])

        if sort_y is not None:
            self.sort_y = float(sort_y)
        elif y is not None and (x != 1860 or y != 960):
            self.sort_y = float(y)
        else:
            self.sort_y = float(default_sort_y)

        # Kompatibilitas atribut posisi
        self.x = self.hub_x
        self.y = self.sort_y
        self.scale = scale
        self.fps = fps
        self.is_active = True      # Dapat diaktifkan/dinonaktifkan oleh NPC penggiling di HTN

        cat = get_asset_catalog()
        self.frames = cat.get_prop("windmill_withshadow", scale=self.scale)
        if not self.frames:
            self.frames = cat.get_prop("windmill", scale=self.scale)

        self.frame_count = max(1, len(self.frames))
        self.frame_idx = 0.0

        # Ukuran frame (112 * scale px, e.g. 224x224 pada skala 2x)
        self.w, self.h = self.frames[0].get_size()
        self.hub_offset_x = self.w // 2
        self.hub_offset_y = self.h // 2

        # Footprint pondasi dasar menara (hanya di bagian bawah menara tempat batu berdiri)
        # Menara HD: x in [1280, 1376], y in [448, 640]
        if self.hub_x == default_hub[0]:
            self.footprint = pygame.Rect(1280, 618, 96, 22)
        else:
            fp_w = int(48 * self.scale)
            fp_h = int(22 * self.scale)
            self.footprint = pygame.Rect(int(self.x - fp_w // 2), int(self.sort_y - fp_h), fp_w, fp_h)

    def update(self, dt: float):
        if self.is_active:
            self.frame_idx = (self.frame_idx + self.fps * dt) % self.frame_count

    def draw(self, screen: pygame.Surface, camera: Tuple[int, int], *args, **kwargs):
        cam_x, cam_y = camera
        draw_x = int(self.hub_x - self.hub_offset_x - cam_x)
        draw_y = int(self.hub_y - self.hub_offset_y - cam_y)

        # Frustum culling dengan batas aman
        viewport_w = getattr(config, "WINDOW_SIZE", (1024, 768))[0]
        viewport_h = getattr(config, "WINDOW_SIZE", (1024, 768))[1]
        if draw_x + self.w < -40 or draw_x > viewport_w + 40:
            return
        if draw_y + self.h < -40 or draw_y > viewport_h + 40:
            return

        idx = int(self.frame_idx) % self.frame_count
        frame_surf = self.frames[idx]
        screen.blit(frame_surf, (draw_x, draw_y))


class ChimneySmoke:
    """Emitter animasi asap cerobong di atap rumah dengan aliran kontinu multi-instance."""

    def __init__(self, x: int, y: int, variant: int = 1, scale: int = 2, fps: float = 10.0,
                 instance_count: int = 3, phase_offset: float = 0.0):
        self.x = float(x)
        self.y = float(y)
        self.scale = scale
        self.fps = fps
        self.variant = max(1, min(5, variant))
        self.instance_count = max(1, instance_count)

        cat = get_asset_catalog()
        key = f"chimneysmoke_{self.variant:02d}"
        raw_frames = cat.get_vfx(key, scale=self.scale)
        self.frame_count = max(1, len(raw_frames))

        # Soft alpha processing (165) untuk mengurangi kedip keras dan menyatu mulus di atap
        self.frames = []
        for rf in raw_frames:
            f = rf.copy()
            f.set_alpha(165)
            self.frames.append(f)

        self.w, self.h = self.frames[0].get_size()

        # Timer dan offset multi-instance agar aliran asap kontinu (mis. 0, 10, 20 frame)
        self.timer = float(phase_offset / self.fps) if self.fps > 0 else 0.0
        step = self.frame_count / float(self.instance_count)
        self.offsets = [i * step for i in range(self.instance_count)]

    @property
    def frame_idx(self) -> float:
        """Indeks frame instance pertama (untuk backward compatibility test)."""
        return (self.timer * self.fps) % self.frame_count

    def update(self, dt: float):
        self.timer += dt

    def draw(self, screen: pygame.Surface, camera: Tuple[int, int]):
        cam_x, cam_y = camera
        # Ujung bawah frame (draw_y + h) tepat di titik atas cerobong (self.y)
        # Rata tengah horizontal (draw_x + w/2 = self.x)
        draw_x = int(self.x - self.w // 2 - cam_x)
        draw_y = int(self.y - self.h - cam_y)

        # Frustum Culling dengan margin aman 60px agar asap tidak lenyap mendadak di tepi layar
        viewport_w = getattr(config, "WINDOW_SIZE", (1024, 768))[0]
        viewport_h = getattr(config, "WINDOW_SIZE", (1024, 768))[1]
        if draw_x + self.w < -60 or draw_x > viewport_w + 60:
            return
        if draw_y + self.h < -60 or draw_y > viewport_h + 60:
            return

        # Render instance bertumpuk dengan offset fase berbeda
        for offset in self.offsets:
            idx = int((self.timer * self.fps + offset) % self.frame_count)
            screen.blit(self.frames[idx], (draw_x, draw_y))


class VillageDecorations:
    """Manajer terpadu dekorasi visual desa (Kincir Angin & Asap Cerobong)."""

    def __init__(self, seed: int = 42):
        rng = random.Random(seed)

        # 1. Kincir Angin dipasang di puncak menara kincir angin otentik
        hub_x, hub_y = getattr(config, "WINDMILL_HUB_POS", (1328, 526))
        sort_y = getattr(config, "WINDMILL_SORT_Y", 448.0)
        scale = getattr(config, "WINDMILL_SCALE", 2)
        fps = getattr(config, "WINDMILL_FPS", 8.0)
        self.windmill = Windmill(hub_x=hub_x, hub_y=hub_y, sort_y=sort_y, scale=scale, fps=fps)

        # 2. Asap Cerobong pada rumah-rumah desa yang memiliki cerobong nyata
        # Ambil koordinat dari config.CHIMNEY_ANCHORS
        anchors = getattr(config, "CHIMNEY_ANCHORS", [
            (948, 142),
            (1742, 230),
            (1070, 614),
            (1388, 812),
            (1774, 838),
            (1900, 1036),
            (814, 1070),
        ])

        variants = [2, 3, 4, 1, 5, 2, 1]
        self.chimneys: List[ChimneySmoke] = []
        for i, (cx, cy) in enumerate(anchors):
            var = variants[i % len(variants)]
            offset = rng.uniform(0.0, 30.0)
            self.chimneys.append(ChimneySmoke(
                x=cx, y=cy, variant=var, scale=2, fps=10.0,
                instance_count=3, phase_offset=offset
            ))

    def update(self, dt: float):
        self.windmill.update(dt)
        for ch in self.chimneys:
            ch.update(dt)

    def get_y_sort_entities(self) -> list:
        """Mengembalikan objek yang ikut dalam y-sort (kincir angin di depan menara)."""
        return [self.windmill]

    def get_collision_rects(self) -> List[pygame.Rect]:
        """Mengembalikan footprint collision untuk diintegrasikan ke map collision."""
        return [self.windmill.footprint]

    def draw_overhead(self, screen: pygame.Surface, camera: Tuple[int, int]):
        """Menggambar efek visual di atas layer atap bangunan (asap cerobong)."""
        for ch in self.chimneys:
            ch.draw(screen, camera)
