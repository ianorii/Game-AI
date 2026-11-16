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


class WeatherNoticeBoardProp:
    """Papan Pengumuman Ramalan Cuaca di Alun-Alun Desa (1504, 1024)."""
    def __init__(self, x: int = 1486, y: int = 1000):
        self.x = x
        self.y = y
        self.w = 36
        self.h = 36
        self.surf = self._create_surface()
        self.footprint = pygame.Rect(x + 4, y + 24, 28, 8)

    @property
    def sort_y(self) -> float:
        return float(self.y + 28)

    def _create_surface(self) -> pygame.Surface:
        surf = pygame.Surface((36, 36), pygame.SRCALPHA)
        # Bayangan tanah
        pygame.draw.ellipse(surf, (0, 0, 0, 75), (4, 26, 28, 8))
        # Dua tiang kayu
        c_wood_dark = (68, 44, 28)
        c_wood_mid = (118, 81, 48)
        pygame.draw.rect(surf, c_wood_dark, (6, 10, 4, 20))
        pygame.draw.rect(surf, c_wood_dark, (26, 10, 4, 20))
        # Papan kayu horizontal
        pygame.draw.rect(surf, c_wood_dark, (2, 2, 32, 22), border_radius=2)
        pygame.draw.rect(surf, c_wood_mid, (4, 4, 28, 18), border_radius=1)
        # Kertas pengumuman cuaca (parchment)
        c_paper = (235, 225, 195)
        pygame.draw.rect(surf, c_paper, (6, 6, 24, 14))
        # Simbol cuaca kecil (matahari & gelombang air)
        pygame.draw.circle(surf, (220, 160, 40), (12, 13), 3)  # matahari
        pygame.draw.line(surf, (50, 120, 210), (17, 11), (26, 11), 2)  # awan/air
        pygame.draw.line(surf, (50, 120, 210), (18, 15), (25, 15), 1)
        # Paku besi di sudut
        for px, py in [(6, 6), (28, 6)]:
            pygame.draw.circle(surf, (45, 48, 55), (px, py), 1)
        return surf

    def draw(self, screen: pygame.Surface, camera: Tuple[int, int]):
        cam_x, cam_y = camera
        screen.blit(self.surf, (self.x - cam_x, self.y - cam_y))


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


class BeachProp:
    """Objek peti atau tong dekorasi di area pantai/dermaga."""
    def __init__(self, kind: str, gx: int, gy: int):
        self.kind = kind
        self.gx = gx
        self.gy = gy
        self.x = gx * 32
        self.y = gy * 32
        self.w = 32
        self.h = 32
        # Footprint solid HANYA di bagian dasar (10px paling bawah)
        self.footprint = pygame.Rect(self.x + 4, self.y + 20, 24, 10)
        self.image = self._create_surface()

    @property
    def footprint_rect(self) -> pygame.Rect:
        return self.footprint

    @property
    def sort_y(self) -> float:
        return float(self.y + 32)

    def _create_surface(self) -> pygame.Surface:
        surf = pygame.Surface((32, 32), pygame.SRCALPHA)
        # Bayangan lembut di bawah
        pygame.draw.ellipse(surf, (0, 0, 0, 70), (4, 22, 24, 10))

        if self.kind == "crate":
            # Peti kayu rapi dengan palang silang dan paku sudut
            c_dark = (68, 44, 28)
            c_mid = (118, 81, 48)
            c_light = (165, 119, 72)
            c_iron = (45, 48, 55)

            pygame.draw.rect(surf, c_dark, (4, 6, 24, 24), border_radius=2)
            pygame.draw.rect(surf, c_mid, (6, 8, 20, 20))
            # Garis papan kayu
            pygame.draw.line(surf, c_dark, (6, 17), (25, 17), 1)
            # Palang silang kayu
            pygame.draw.line(surf, c_dark, (7, 9), (24, 26), 2)
            pygame.draw.line(surf, c_light, (8, 9), (25, 26), 1)
            pygame.draw.line(surf, c_dark, (24, 9), (7, 26), 2)
            pygame.draw.line(surf, c_light, (24, 10), (8, 26), 1)
            # Bingkai & pelat sudut besi
            pygame.draw.rect(surf, c_dark, (4, 6, 24, 24), 2, border_radius=2)
            for cx, cy in [(4, 6), (24, 6), (4, 26), (24, 26)]:
                pygame.draw.rect(surf, c_iron, (cx, cy, 4, 4))
        else:
            # Tong kayu dengan sabuk besi
            c_dark = (55, 38, 25)
            c_mid = (110, 75, 45)
            c_light = (150, 105, 65)
            c_iron = (50, 52, 60)
            c_highlight = (190, 145, 95)

            # Badan tong cembung
            pygame.draw.ellipse(surf, c_dark, (5, 4, 22, 26))
            pygame.draw.ellipse(surf, c_mid, (6, 5, 20, 24))
            # Tutup atas tong
            pygame.draw.ellipse(surf, c_dark, (7, 4, 18, 8))
            pygame.draw.ellipse(surf, c_highlight, (8, 5, 16, 6))
            # Sabuk besi penahan (lingkar atas & bawah)
            pygame.draw.line(surf, c_iron, (6, 12), (25, 12), 2)
            pygame.draw.line(surf, c_iron, (6, 22), (25, 22), 2)
            # Garis kayu vertikal
            pygame.draw.line(surf, c_dark, (11, 7), (11, 26), 1)
            pygame.draw.line(surf, c_dark, (16, 7), (16, 27), 1)
            pygame.draw.line(surf, c_dark, (21, 7), (21, 26), 1)

        return surf

    def draw(self, screen: pygame.Surface, camera: Tuple[int, int], *args, **kwargs):
        cam_x, cam_y = camera
        screen.blit(self.image, (int(self.x - cam_x), int(self.y - cam_y)))


class BeachDecorations:
    """
    Manajer dekorasi area pantai/dermaga tenggara.
    Area pantai dikosongkan total dari tumpukan peti dan bangunan agar lapang dan alami.
    """
    def __init__(self, assets=None):
        self.props: List[BeachProp] = []

    def get_y_sort_entities(self) -> List[BeachProp]:
        return list(self.props)

    def get_collision_rects(self) -> List[pygame.Rect]:
        return [p.footprint for p in self.props]

    def update(self, dt: float):
        pass
